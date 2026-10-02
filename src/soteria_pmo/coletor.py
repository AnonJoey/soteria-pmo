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
    # O Teams e o Outlook novos moram em `*.cloud.microsoft`. Medido em
    # 02/10/2026: as visitas de 10 a 30/09 ao Teams e ao Outlook vinham todas
    # deste dominio, e nenhuma casava com a lista, entao o coletor nunca as viu.
    "teams.cloud.microsoft", "outlook.cloud.microsoft", "portal.azure.com",
)

# Tipo de transicao RELOAD do Chrome, nos 8 bits de baixo de `visits.transition`.
# E o tipo que a restauracao de abas grava: em 22/09/2026 as 10:16 o navegador
# reabriu Azure, Outlook, Teams e ClickUp no mesmo segundo, todas com 8, e isso
# entrava como janela de trabalho. Abrir o navegador nao prova trabalho, e uma
# recarga manual sozinha tambem nao.
TRANSICAO_RELOAD = 8

# A restauracao nao para no RELOAD: as abas reabertas disparam sozinhas logins
# e redirecionamentos, que chegam como LINK. Em 22/09/2026 o login automatico
# do Azure, um segundo depois da rajada, manteve viva uma janela das 10:16 as
# 10:31 mesmo com o RELOAD filtrado. Por isso a unidade e a rajada: 3 ou mais
# RELOADs com no maximo RAJADA_VAO entre eles, e tudo que o navegador carregar
# ate RAJADA_CAUDA depois da ultima aba sai junto. Uma recarga isolada nao e
# rajada e nao derruba o que vem depois.
RAJADA_MINIMO = 3
RAJADA_VAO = 5          # segundos
RAJADA_CAUDA = 30       # segundos


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
        marcas: list[tuple[datetime, str, bool]] = []
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
                    marcas.append((quando, onde, _digitado(registro)))
        except OSError as e:
            logger.warning("nao foi possivel ler %s: %s", arquivo.name, e)
            continue
        if not marcas:
            continue
        quandos = [m for m, _, _ in marcas]
        if max(quandos) < ini_dt or min(quandos) > fim_dt:
            continue
        sufixo = f": {titulo[:60]}" if titulo else ""
        acompanhados, sozinhos = _separar_atencao(sorted(marcas))
        for grupo, tipo in ((acompanhados, "sessao_ia"), (sozinhos, "sessao_ia_autonoma")):
            pontos = [Ponto(m, f"sessao {arquivo.stem[:8]} em {lugar}{sufixo}")
                      for m, lugar, _ in grupo if ini_dt <= m <= fim_dt]
            evidencias.extend(_agrupar(pontos, tipo))
    return evidencias


#: Quanto tempo depois de uma mensagem digitada a atividade do agente ainda
#: conta como acompanhada. Medido em 02/10/2026 sobre os turnos de 10 a 30/09
#: (do pedido ao ultimo registro do agente antes do pedido seguinte): de dia,
#: mediana 6 min, 75% ate 23 min; acima de 45 min sobram 20 de 117, quase todos
#: jobs longos de verdade (339, 485, 1260 min). Entre 20 e 45 min ficam 12
#: turnos que sao conversa com espera, e com 20 eles viravam autonomos.
ATENCAO = timedelta(minutes=45)


def _digitado(registro: dict) -> bool:
    """Se o registro e uma mensagem que a pessoa escreveu.

    O Claude Code grava como `user` tambem a volta de cada ferramenta e os
    avisos do proprio harness. So conta o texto que alguem digitou.
    """
    if registro.get("type") != "user" or registro.get("isMeta"):
        return False
    # Registros que o proprio Claude Code injeta como `user`: o resumo de uma
    # compactacao de contexto e o disparo de uma tarefa agendada. Medido na
    # noite de 26 para 27/09: o resumo das 04:24 chegava sem `isMeta` e abria
    # atencao no meio de um job autonomo.
    if registro.get("isCompactSummary") or registro.get("scheduledTaskId"):
        return False
    origem = registro.get("origin")
    if isinstance(origem, dict) and origem.get("kind") not in (None, "human"):
        return False
    conteudo = (registro.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        return bool(conteudo.strip()) and not conteudo.lstrip().startswith("<")
    if isinstance(conteudo, list):
        textos = [c.get("text", "") for c in conteudo
                  if isinstance(c, dict) and c.get("type") == "text"]
        return any(t.strip() and not t.lstrip().startswith("<") for t in textos)
    return False


def _separar_atencao(marcas: list[tuple[datetime, str, bool]]):
    """Divide os carimbos de uma sessao entre acompanhados e autonomos.

    Medido em setembro de 2026: as noites de 24 para 25 e de 25 para 26/09
    entraram como janelas de 9,5h e 9,9h de sessao de IA, com a mesma forca de
    trabalho acompanhado, e eram o agente rodando sozinho depois de um pedido.
    Uma mensagem digitada abre `ATENCAO` de atividade acompanhada; o que o
    agente faz depois disso, sem nova mensagem, e dele.
    """
    acompanhados, sozinhos = [], []
    ultima_digitada: datetime | None = None
    for quando, lugar, digitada in marcas:
        if digitada:
            ultima_digitada = quando
        if ultima_digitada is not None and quando - ultima_digitada <= ATENCAO:
            acompanhados.append((quando, lugar, digitada))
        else:
            sozinhos.append((quando, lugar, digitada))
    return acompanhados, sozinhos


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


def reunioes(pasta: str | Path, inicio: date, fim: date) -> list[Evidencia]:
    """Meetings, from the transcripts in the dailies folder.

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

    pasta_dir = Path(pasta).expanduser()
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
                "SELECT v.visit_time, u.url, u.title, v.transition & 255 FROM visits v "
                "JOIN urls u ON u.id = v.url "
                "WHERE v.visit_time BETWEEN ? AND ? ORDER BY v.visit_time",
                (ini_wk, fim_wk)).fetchall()
            con.close()
        except Exception as e:
            logger.warning("nao foi possivel ler o historico: %s", e)
            return []

    restauracoes = _rajadas_de_restauracao(
        [q for q, _, _, t in linhas if t == TRANSICAO_RELOAD])
    for quando_wk, url, titulo, transicao in linhas:
        if transicao == TRANSICAO_RELOAD:
            continue
        if any(a <= quando_wk <= b for a, b in restauracoes):
            continue
        host = (urlparse(url).hostname or "").lower()
        if not any(host == d or host.endswith("." + d) for d in dominios):
            continue
        dt = datetime.fromtimestamp(quando_wk / 1_000_000 - EPOCA_WEBKIT, BRT)
        pontos.append(Ponto(dt, f"{host}: {(titulo or url)[:70]}"))
    return _agrupar(pontos, "navegador")


def _rajadas_de_restauracao(reloads_wk: list[int]) -> list[tuple[int, int]]:
    """Intervalos (em tempo WebKit) em que o navegador estava se restaurando."""
    vao, cauda = RAJADA_VAO * 1_000_000, RAJADA_CAUDA * 1_000_000
    grupos: list[list[int]] = []
    for q in sorted(reloads_wk):
        if grupos and q - grupos[-1][-1] <= vao:
            grupos[-1].append(q)
        else:
            grupos.append([q])
    return [(g[0], g[-1] + cauda) for g in grupos if len(g) >= RAJADA_MINIMO]


# ── antigravity ──────────────────────────────────────────────────────────────


def antigravity(historico: str | Path, inicio: date, fim: date) -> list[Evidencia]:
    """Pedidos digitados no Antigravity CLI, agrupados como sessao acompanhada.

    O history.jsonl guarda so o que a pessoa escreveu (`display`, `timestamp`
    em ms, `workspace`), nao o que o agente fez. Medido em 02/10/2026: em 28/09
    os pedidos das 08:13 as 08:50 sao a conexao com o Chrome que virou o commit
    6e103b2 as 09:37, e nenhuma outra fonte desta maquina via aquela manha.
    """
    arquivo = Path(historico).expanduser()
    if not arquivo.exists():
        logger.warning("historico do antigravity nao existe: %s", arquivo)
        return []
    ini_dt = datetime.combine(inicio, datetime.min.time(), tzinfo=BRT)
    fim_dt = datetime.combine(fim, datetime.max.time(), tzinfo=BRT)
    pontos = []
    for linha in arquivo.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            r = json.loads(linha)
            quando = datetime.fromtimestamp(int(r["timestamp"]) / 1000, BRT)
        except (ValueError, KeyError, TypeError):
            continue
        if not ini_dt <= quando <= fim_dt:
            continue
        texto = str(r.get("display") or "")[:70].replace("\n", " ")
        onde = _encurtar(r.get("workspace")) or ""
        pontos.append(Ponto(quando, f"antigravity em {onde}: {texto}"))
    return _agrupar(pontos, "sessao_ia")


# ── agenda ───────────────────────────────────────────────────────────────────

#: Evento que atravessa a meia-noite e passa disto e bloco, nao compromisso.
#: Uma recepcao das 19:00 em Sao Francisco termina 01:30 em Brasilia e fica.
BLOCO_DE_DIAS = timedelta(hours=12)


def agenda(origem: str, inicio: date, fim: date) -> list[Evidencia]:
    """Eventos de agenda, lidos como DADO e nunca por import.

    `origem` e um arquivo JSON ou um comando que imprime esse JSON, com `{de}`
    e `{ate}` trocados pelas datas. O formato e uma lista de objetos com
    `titulo`, `inicio`, `fim` (ISO 8601) e, opcionais, `dia_inteiro` e
    `status`. E o que o modulo `agenda` imprime com `--json`, mas qualquer
    produtor serve: este pacote nao sabe quem gerou o arquivo.

    Evento nao prova que algo aconteceu. A "Reuniao com o Max" de 23/09/2026
    estava na agenda e nao aconteceu. Por isso o tipo e `agenda`, e o motor de
    horas nao o usa como janela medida: evento sem outra evidencia vira
    pergunta, e evento que coincide com evidencia so da nome a proposta.
    """
    texto = ""
    caminho = Path(origem).expanduser()
    if caminho.exists():
        texto = caminho.read_text(encoding="utf-8")
    else:
        cmd = origem.format(de=inicio.isoformat(), ate=fim.isoformat())
        saida = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=120, check=True)
        texto = saida.stdout
    evidencias = []
    for e in json.loads(texto or "[]"):
        if e.get("dia_inteiro") or str(e.get("status", "")).upper() == "CANCELLED":
            continue
        try:
            ini = datetime.fromisoformat(e["inicio"]).astimezone(BRT)
            fim_ev = datetime.fromisoformat(e["fim"]).astimezone(BRT)
        except (KeyError, ValueError):
            continue
        if fim_ev <= ini or not inicio <= ini.date() <= fim:
            continue
        # Bloco de varios dias nao e compromisso: e o "Dreamforce 2026", de
        # 11/09 14:00 a 20/09 15:30, que chega sem `dia_inteiro` e somava 217h.
        if fim_ev.date() > ini.date() and fim_ev - ini > BLOCO_DE_DIAS:
            continue
        evidencias.append(Evidencia(tipo="agenda", inicio=ini, fim=fim_ev,
                                    descricao=f"agenda: {e.get('titulo', '')}",
                                    inferida=True))
    return evidencias


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
    #: Pasta das transcricoes de daily e de reuniao.
    dailies: str = ""
    #: history.jsonl do Antigravity CLI.
    antigravity: str = ""
    #: Arquivo JSON de eventos, ou comando que imprime esse JSON.
    agenda: str = ""


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
    if fontes.dailies:
        tenta("reunioes", lambda: reunioes(fontes.dailies, inicio, fim))
    if fontes.historico_navegador:
        tenta("navegador", lambda: navegador(fontes.historico_navegador, inicio, fim))
    if fontes.antigravity:
        tenta("antigravity", lambda: antigravity(fontes.antigravity, inicio, fim))
    if fontes.agenda:
        tenta("agenda", lambda: agenda(fontes.agenda, inicio, fim))

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
