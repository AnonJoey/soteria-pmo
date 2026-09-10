"""Machine evidence: what this computer can testify to about a working day.

Feeds `horas.py` and `auditor.py`, which until now received evidence by
injection and had nothing real to receive.

The honest problem this module has to solve, and the place it can go wrong:
**most sources are points in time, not windows.** A commit happened at 14:32.
A page was visited at 09:15. Neither says how long the work took, and inventing
a duration for them is exactly how an apuracao stops being measurement and
starts being fiction. Two rules follow from that:

  * Points are clustered into windows only when they are close enough together
    to be one stretch of work, and the cluster's span is the evidence, never a
    fixed duration per event. One lone commit yields a window of `MINIMO_ISOLADO`
    and is flagged, rather than being inflated into an afternoon.
  * A source that carries a real window (an AI session's first and last
    timestamp, a meeting's recorded length) is used as-is and outranks any
    cluster, because it was observed rather than derived.

Everything here is read-only. Chrome's history is copied before being opened,
because the live file is locked while the browser runs.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from .horas import Evidencia
from .periodo import BRT, janela

logger = logging.getLogger("pmo.coletor")

# Two events further apart than this are two stretches of work, not one.
# Twenty minutes: long enough to survive reading a page or writing a test
# between commits, short enough that lunch splits the morning from the
# afternoon instead of swallowing it.
INTERVALO_DE_CLUSTER = timedelta(minutes=20)

# What a single isolated event is worth. Deliberately small: one commit at
# 14:32 with nothing around it proves a moment, not an afternoon, and the gap
# protocol in horas.py is what recovers the rest by asking.
MINIMO_ISOLADO = timedelta(minutes=15)

# Chrome stores time as microseconds since 1601-01-01.
EPOCA_WEBKIT = 11_644_473_600

# Domains that mean work on this machine. Everything else is dropped rather
# than guessed at: browser evidence is the weakest source in horas.PESO_FONTE
# precisely because an open page is not work, and mixing personal browsing in
# would make it weaker still.
DOMINIOS_DE_TRABALHO = (
    "clickup.com", "teams.microsoft.com", "sharepoint.com", "office.com",
    "office365.com", "microsoftonline.com", "onedrive.live.com", "live.com",
    "github.com", "gitlab.com", "claude.ai", "anthropic.com",
    "stackoverflow.com", "docs.python.org", "developer.clickup.com",
)


# Marks on evidence that almost certainly is not client work. This machine
# mixes both: the vault holds notes on Conan Exiles and on ClickUp, and the
# browser history holds Discord and SharePoint. Billing the first kind is the
# same class of error as the 16 wrongly billed hours, so it is separated here
# rather than left for someone to notice in a report.
MARCAS_PESSOAIS = (
    "steam", "conan", "palworld", "minecraft", "discord", "protonvpn",
    "cachyos", "nvidia", "kde", "plasma", "wayland", "proton", "lutris",
    "youtube", "netflix", "spotify", "reddit", "twitch", "jogo", "game",
)


def _encurtar(caminho: str | None) -> str:
    """`/home/alguem/Projects/x` como `~/Projects/x`, para caber na descricao.

    A descricao e o que `parece_pessoal` le e o que uma pessoa confere no
    relatorio, entao o caminho precisa ser reconhecivel e curto. Nao existe
    para ser bonito: caminho absoluto de home vaza o nome de usuario para
    dentro de uma nota que pode ir para o vault ou para um card.
    """
    if not caminho:
        return ""
    texto = str(caminho)
    casa = str(Path.home())
    return f"~{texto[len(casa):]}" if texto.startswith(casa) else texto


def parece_pessoal(texto: str, marcas: tuple[str, ...] = ()) -> bool:
    """Whether this evidence looks like personal work rather than client work.

    A heuristic and named as one. It errs toward flagging: a false flag costs a
    question, and a miss costs a wrongly billed hour.

    `marcas` vem do config (`evidencia.pessoais`) e existe porque a lista fixa
    aqui so alcanca o que era previsivel escrever: jogo, streaming, distro. O
    que passou por ela em agosto de 2026 foi um projeto pessoal de nome proprio,
    `palweave`, indistinguivel de nome de cliente para quem le a palavra. Quem
    sabe quais sao os proprios projetos pessoais e o dono da maquina, entao ele
    diz, em vez de o pacote adivinhar ou carregar nome de ninguem.
    """
    t = texto.lower()
    return any(m in t for m in MARCAS_PESSOAIS) or any(
        m.strip().lower() in t for m in marcas if m.strip())


@dataclass(frozen=True)
class Ponto:
    """One instant something was witnessed, before any window is inferred."""

    quando: datetime
    descricao: str
    tarefa_sugerida: str = ""


def _agrupar(pontos: list[Ponto], tipo: str,
             intervalo: timedelta = INTERVALO_DE_CLUSTER,
             minimo: timedelta = MINIMO_ISOLADO) -> list[Evidencia]:
    """Turn instants into windows, saying which windows were inferred.

    A cluster's window is the span between its first and last point, which is
    measured. The `minimo` floor applies only to a cluster that spans less than
    it, and the description says so, so a reader can tell a measured hour from
    a floor applied to a single commit.
    """
    if not pontos:
        return []
    ordenados = sorted(pontos, key=lambda p: p.quando)
    grupos: list[list[Ponto]] = [[ordenados[0]]]
    for p in ordenados[1:]:
        if p.quando - grupos[-1][-1].quando <= intervalo:
            grupos[-1].append(p)
        else:
            grupos.append([p])

    evidencias = []
    for g in grupos:
        inicio, fim = g[0].quando, g[-1].quando
        vao = fim - inicio
        if vao < minimo:
            fim = inicio + minimo
            inferida = True
            sufixo = f" [{len(g)} evento(s) em menos de {minimo.seconds // 60}min, " \
                     f"janela minima aplicada]"
        else:
            inferida = False
            sufixo = f" [{len(g)} eventos, janela medida]"
        amostra = "; ".join(p.descricao for p in g[:3])
        evidencias.append(Evidencia(
            tipo=tipo, inicio=inicio, fim=fim,
            descricao=amostra + sufixo, inferida=inferida,
            tarefa_sugerida=next((p.tarefa_sugerida for p in g if p.tarefa_sugerida), ""),
        ))
    return evidencias


# ── git ──────────────────────────────────────────────────────────────────────


def commits(repos: list[str | Path], inicio: date, fim: date,
            autor: str = "") -> list[Evidencia]:
    """Commits by `autor` in each repo, clustered into working stretches.

    Author filtering matters on a shared repo and is harmless on a personal
    one. An empty `autor` takes every commit, which is right for a repo only
    one person writes to.
    """
    pontos: list[Ponto] = []
    for raiz in repos:
        raiz = Path(raiz).expanduser()
        if not (raiz / ".git").exists():
            logger.warning("nao e um repositorio git: %s", raiz)
            continue
        # The hour is not optional. Git's approximate date parser reads a bare
        # YYYY-MM-DD as that day *at the current wall-clock time*, so at 16:11
        # a --since of today silently drops every commit made before 16:11
        # today. Measured: --since=2026-09-02 returned 0 commits and
        # --since=2026-09-02T00:00:00 returned 18, on the same repo, one second
        # apart. Nothing errors; the day just comes back empty.
        cmd = ["git", "-C", str(raiz), "log",
               f"--since={inicio.isoformat()}T00:00:00",
               f"--until={fim.isoformat()}T23:59:59",
               "--date=iso-strict", "--pretty=%aI%x09%s"]
        if autor:
            cmd.insert(4, f"--author={autor}")
        try:
            saida = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=60, check=True).stdout
        except Exception as e:
            logger.warning("git log falhou em %s: %s", raiz, e)
            continue
        for linha in saida.splitlines():
            quando, _, assunto = linha.partition("\t")
            try:
                dt = datetime.fromisoformat(quando).astimezone(BRT)
            except ValueError:
                continue
            pontos.append(Ponto(dt, f"{raiz.name}: {assunto[:90]}"))
    return _agrupar(pontos, "commit")


# ── sessoes de IA ────────────────────────────────────────────────────────────


def sessoes_ia(raiz: str | Path, inicio: date, fim: date) -> list[Evidencia]:
    """Claude Code sessions, clustered by the gaps inside them.

    The first version of this took each session's earliest and latest stamp and
    called it a measured window. It is not. A session left open from 13:28 one
    day to 11:24 the next produced a 22 hour window with a night's sleep inside
    it, and thirteen sessions summed to 74 hours in a single week. The session's
    span is measured; the *work* inside it is not the same thing.

    So every message timestamp is a point and the same clustering applies. A
    session with a long pause becomes two windows, which is what happened.

    O QUE a sessao estava fazendo vem do `cwd` de cada mensagem, e nao do nome
    da pasta. Medido nesta maquina em 10/09/2026: as 60 sessoes estao todas sob
    duas pastas, `-home-joey` e outra, porque a pasta e o diretorio de onde o
    Claude Code foi aberto, quase sempre a home. O `cwd` das mensagens dentro
    delas aponta para 20 lugares diferentes, entre eles 1035 mensagens em
    `~/Projects/palweave` e 144 em `~/fototriagem`, que sao pessoais. Enquanto a
    descricao dizia so "sessao a1b2c3d4 em -home-joey", `parece_pessoal` nao
    tinha o que ler e 10,53h de trabalho pessoal entraram como evidencia de
    cliente no lancamento de agosto.
    """
    raiz = Path(raiz).expanduser()
    if not raiz.exists():
        logger.warning("raiz de sessoes nao existe: %s", raiz)
        return []

    ini_dt = datetime.combine(inicio, datetime.min.time(), tzinfo=BRT)
    fim_dt = datetime.combine(fim, datetime.max.time(), tzinfo=BRT)
    evidencias = []

    for arquivo in raiz.rglob("*.jsonl"):
        marcas: list[tuple[datetime, str]] = []
        titulo = ""
        onde = arquivo.parent.name
        try:
            with arquivo.open(encoding="utf-8") as fh:
                for linha in fh:
                    try:
                        registro = json.loads(linha)
                        t = registro.get("timestamp")
                    except (json.JSONDecodeError, AttributeError):
                        continue
                    # O titulo pode vir em qualquer ponto do arquivo e vale para
                    # a sessao inteira, entao e lido mesmo em linha sem carimbo.
                    titulo = titulo or str(registro.get("aiTitle") or "")
                    # Uma linha sem `cwd` herda a anterior: o diretorio da
                    # sessao so muda quando alguem o muda, e zerar aqui trocaria
                    # um caminho conhecido por um desconhecido.
                    onde = _encurtar(registro.get("cwd")) or onde
                    if not t:
                        continue
                    try:
                        quando = datetime.fromisoformat(
                            t.replace("Z", "+00:00")).astimezone(BRT)
                    except ValueError:
                        continue
                    marcas.append((quando, onde))
        except OSError as e:
            logger.warning("nao foi possivel ler %s: %s", arquivo.name, e)
            continue
        if not marcas:
            continue
        quandos = [m for m, _ in marcas]
        if max(quandos) < ini_dt or min(quandos) > fim_dt:
            continue
        sufixo = f": {titulo[:60]}" if titulo else ""
        pontos = [Ponto(m, f"sessao {arquivo.stem[:8]} em {lugar}{sufixo}")
                  for m, lugar in marcas if ini_dt <= m <= fim_dt]
        evidencias.extend(_agrupar(pontos, "sessao_ia"))
    return evidencias


# ── vault ────────────────────────────────────────────────────────────────────


def notas_vault(vault: str | Path, inicio: date, fim: date,
                pastas: tuple[str, ...] = ()) -> list[Evidencia]:
    """Notes written or touched in the window, by file modification time.

    mtime is when the work landed, not how long it took, so these are points
    and get clustered. Transcript backups are skipped: a transcript is a record
    of a session that `sessoes_ia` already measured, and counting both would
    bill the same stretch twice.
    """
    vault = Path(vault).expanduser()
    if not vault.exists():
        logger.warning("vault nao existe: %s", vault)
        return []
    ini_dt = datetime.combine(inicio, datetime.min.time(), tzinfo=BRT)
    fim_dt = datetime.combine(fim, datetime.max.time(), tzinfo=BRT)

    raizes = [vault / p for p in pastas] if pastas else [vault]
    pontos = []
    for raiz in raizes:
        if not raiz.exists():
            continue
        for nota in raiz.rglob("*.md"):
            if "transcript" in nota.name.lower() or "_processed" in str(nota):
                continue
            try:
                quando = datetime.fromtimestamp(nota.stat().st_mtime, BRT)
            except OSError:
                continue
            if ini_dt <= quando <= fim_dt:
                pontos.append(Ponto(quando, f"nota: {nota.stem[:70]}"))
    return _agrupar(pontos, "nota_vault")


def reunioes(vault: str | Path, inicio: date, fim: date,
             pasta: str = "Sessions") -> list[Evidencia]:
    """Meetings, from the transcripts saved in the vault.

    Three things this has to get right, all of them learned by running it.

    **Not every transcript is a meeting.** The folder holds 102 files matching
    "transcri" and only 33 are standups: the rest are Claude Code session
    backups, which `sessoes_ia` already counts. Counting them here too would
    bill the same stretch twice, so they are excluded by name and by shape.

    **Only the standup has a known hour.** 14:00 is a fact about the standup,
    not about every meeting: applying it to all of them put an alignment
    meeting and the daily on top of each other at the same minute.

    **A meeting whose hour is unrecorded still happened.** Its duration is
    measured and belongs in the total, so it is placed after the standup, in
    order, without overlapping, and the description says the placement is a
    convention while the duration is not.
    """
    from .daily import DURACAO_MAXIMA, HORA_DA_DAILY, e_daily, horario_no_texto, ler_transcricao

    pasta_dir = Path(vault).expanduser() / pasta
    if not pasta_dir.exists():
        return []

    por_dia: dict[date, list] = {}
    for arquivo in sorted(pasta_dir.glob("*.md")):
        # Claude Code backups are named transcript-<hash>: excluded by name
        # before parsing, so a pasted meeting inside one cannot slip through.
        if arquivo.stem.split("-")[-2:-1] == ["transcript"] or "transcript-" in arquivo.stem:
            continue
        t = ler_transcricao(arquivo)
        if t is None or not (inicio <= t.dia <= fim):
            continue
        por_dia.setdefault(t.dia, []).append(t)

    evidencias = []
    for dia, do_dia in sorted(por_dia.items()):
        # The standup first, at its known hour; everything else after it.
        do_dia.sort(key=lambda t: (not e_daily(t), t.titulo))
        proximo_livre = None
        for t in do_dia:
            faixa = horario_no_texto(t)
            if faixa is not None:
                comeco = datetime.combine(dia, faixa, tzinfo=BRT)
                origem = "horario lido da nota"
            elif e_daily(t):
                comeco = datetime.combine(dia, datetime.min.time(), tzinfo=BRT).replace(
                    hour=HORA_DA_DAILY)
                origem = "inicio 14:00 pela regra do time"
            else:
                comeco = proximo_livre or datetime.combine(
                    dia, datetime.min.time(), tzinfo=BRT).replace(hour=HORA_DA_DAILY) \
                    + DURACAO_MAXIMA
                origem = "horario nao registrado, posicao por convencao"
            fim_reuniao = comeco + t.duracao
            proximo_livre = max(proximo_livre or fim_reuniao, fim_reuniao)

            marca = " [PASSOU DE 1H, conferir]" if e_daily(t) and t.passou_da_hora else ""
            evidencias.append(Evidencia(
                tipo="reuniao", inicio=comeco, fim=fim_reuniao,
                descricao=f"{t.titulo} ({len(t.falas)} falas, "
                          f"{int(t.duracao.total_seconds() // 60)}min){marca} "
                          f"[duracao medida, {origem}]",
            ))
    return evidencias


# ── navegador ────────────────────────────────────────────────────────────────


def navegador(historico: str | Path, inicio: date, fim: date,
              dominios: tuple[str, ...] = DOMINIOS_DE_TRABALHO) -> list[Evidencia]:
    """Work-domain page visits from Chrome's history.

    The file is copied before opening: Chrome holds a lock on the live one, and
    reading it in place either fails or, worse, reads a partial write.

    The weakest source by design. An open page proves a page was open, and the
    weight in `horas.PESO_FONTE` says so.
    """
    origem = Path(historico).expanduser()
    if not origem.exists():
        logger.warning("historico do navegador nao existe: %s", origem)
        return []

    ini_ms, fim_ms = janela(inicio, fim)
    ini_wk = int((ini_ms / 1000 + EPOCA_WEBKIT) * 1_000_000)
    fim_wk = int((fim_ms / 1000 + EPOCA_WEBKIT) * 1_000_000)

    pontos = []
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "History"
        try:
            shutil.copy2(origem, copia)
            con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
            linhas = con.execute(
                "SELECT v.visit_time, u.url, u.title FROM visits v "
                "JOIN urls u ON u.id = v.url "
                "WHERE v.visit_time BETWEEN ? AND ? ORDER BY v.visit_time",
                (ini_wk, fim_wk)).fetchall()
            con.close()
        except Exception as e:
            logger.warning("nao foi possivel ler o historico: %s", e)
            return []

    for quando_wk, url, titulo in linhas:
        host = (urlparse(url).hostname or "").lower()
        if not any(host == d or host.endswith("." + d) for d in dominios):
            continue
        dt = datetime.fromtimestamp(quando_wk / 1_000_000 - EPOCA_WEBKIT, BRT)
        pontos.append(Ponto(dt, f"{host}: {(titulo or url)[:70]}"))
    return _agrupar(pontos, "navegador")


# ── tudo junto ───────────────────────────────────────────────────────────────


@dataclass
class Fontes:
    """Where to look. Absent paths are skipped with a warning, never invented."""

    repos: tuple[str, ...] = ()
    autor_git: str = ""
    sessoes_ia: str = ""
    vault: str = ""
    historico_navegador: str = ""
    #: Pedacos de caminho ou de nome que marcam trabalho pessoal nesta maquina,
    #: alem das palavras que `MARCAS_PESSOAIS` ja cobre. Vem do config.
    pessoais: tuple[str, ...] = ()


def separar_pessoal(evidencias: list[Evidencia],
                    marcas: tuple[str, ...] = ()) -> tuple[list[Evidencia], list[Evidencia]]:
    """Split evidence into likely client work and likely personal work."""
    cliente, pessoal = [], []
    for e in evidencias:
        (pessoal if parece_pessoal(e.descricao, marcas) else cliente).append(e)
    return cliente, pessoal


def coletar(fontes: Fontes, inicio: date, fim: date) -> tuple[list[Evidencia], list[str]]:
    """Every source, in one pass. Returns the evidence and what failed.

    Failures are returned rather than logged away, for the same reason
    `bolsao.vigiar` returns them: a source that could not be read and a source
    with nothing to say produce identical silence, and only one of them is fine.
    """
    evidencias: list[Evidencia] = []
    falhas: list[str] = []

    def tenta(nome: str, fn):
        try:
            achado = fn()
            evidencias.extend(achado)
            logger.info("%s: %d janelas", nome, len(achado))
        except Exception as e:
            logger.warning("fonte %s falhou: %s", nome, e)
            falhas.append(f"{nome}: {type(e).__name__}: {e}")

    if fontes.repos:
        tenta("commits", lambda: commits(list(fontes.repos), inicio, fim, fontes.autor_git))
    if fontes.sessoes_ia:
        tenta("sessoes_ia", lambda: sessoes_ia(fontes.sessoes_ia, inicio, fim))
    if fontes.vault:
        tenta("notas_vault", lambda: notas_vault(fontes.vault, inicio, fim))
        tenta("reunioes", lambda: reunioes(fontes.vault, inicio, fim))
    if fontes.historico_navegador:
        tenta("navegador", lambda: navegador(fontes.historico_navegador, inicio, fim))

    evidencias.sort(key=lambda e: e.inicio)
    return evidencias, falhas


def resumo(evidencias: list[Evidencia], falhas: list[str],
           pessoais: tuple[str, ...] = ()) -> str:
    """What was collected, by source, so a person can sanity check it."""
    from collections import Counter
    if not evidencias and not falhas:
        return "Nenhuma evidencia coletada e nenhuma falha: as fontes nao foram configuradas."
    linhas = ["Coleta de evidencia", ""]
    for tipo, n in sorted(Counter(e.tipo for e in evidencias).items()):
        horas = sum((e.fim - e.inicio).total_seconds() for e in evidencias
                    if e.tipo == tipo) / 3600
        linhas.append(f"  {tipo:12} {n:4} janelas  {horas:7.1f}h brutas")
    if falhas:
        linhas.append("")
        linhas.append("  Fontes que nao puderam ser lidas:")
        linhas.extend(f"    {f}" for f in falhas)
    _, pessoal = separar_pessoal(evidencias, pessoais)
    if pessoal:
        h = sum((e.fim - e.inicio).total_seconds() for e in pessoal) / 3600
        linhas.append("")
        linhas.append(f"  Marcadas como provavelmente pessoais e separadas: "
                      f"{len(pessoal)} janelas, {h:.1f}h brutas.")
        linhas.append("  Heuristica por palavra: confira se alguma delas era "
                      "trabalho de cliente.")
    linhas.append("")
    linhas.append("  Horas brutas somam janelas sobrepostas mais de uma vez. "
                  "A apuracao funde a sobreposicao antes de propor.")
    return "\n".join(linhas)
