"""Item 3: the audit of what was logged.

Runs daily, for the dev who logs and for Abner who follows the day to day, and
is read again by Andre at closing. The cadence moved on 04/09: it was monthly,
at closing, and Andre said that is too late to be worth anything. A discrepancy
found while the invoice is being cut cannot be fixed by the dev any more, so it
gets billed as it stands. Found the next morning, it is a two minute correction
and the month closes almost clean.

It answers two questions. Does each logged entry have something behind it, and
is there work with evidence that nobody logged? It is the mirror of the hours
engine: that one proposes from evidence, this one starts from what is already in
ClickUp and looks for the evidence back.

Since 04/09 it also checks the entries against each other, which is where the
first two cases Andre opened on screen actually lived: three hours that swallow
another task whole, and forty minutes sitting inside another block. No amount of
comparing an entry against the day's machine trail finds either one.

The output is built for auditing by exception. Nobody reads a month line by
line, so entries that corroborate cleanly are counted and not listed, and
everything that needs a human eye is listed with the raw evidence next to it. An
audit that prints everything gets skimmed, and skimming an audit is the same as
not running it.

What this deliberately does not do is call anything fraud, or even wrong. An
entry with no evidence behind it is reported as "no evidence found", because
this module cannot see planning, phone calls, or a whiteboard, and those are
exactly where the missing 60% of the pilot's hours turned out to live. The
overlap checks are arithmetic on clock times, not a reading of intent, and the
report says so.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .periodo import Intervalo, de_ms, fundir, horas as somar_horas

logger = logging.getLogger("pmo.auditor")

# How far a logged duration may differ from the evidence before it is worth a
# human look. Evidence windows are approximate by nature, so a tight threshold
# would flag every entry and a loose one would flag none.
TOLERANCIA = 0.25

VEREDITOS = ("corroborada", "divergente", "sem lastro", "fora do formato")

# Eight hours of one day on a single task is what made Andre stop and look, in
# the cases he walked through on 04/09. It is his example, not a measurement, so
# it lives in one place and moving it is one edit.
CONCENTRACAO_H = 8.0

# Same origin: "ajustes no agente, 35 horas", read out as a task too generic for
# its size. Totalled per task across the audited window.
TAREFA_GRANDE_H = 35.0

# How far a misdated entry may sit from the orphan day that would explain it.
# One day each way covers the case he described, logging on the wrong date, and
# stops short of pairing entries a week apart that have nothing to do with each
# other.
DIAS_DE_DATA_TROCADA = 1

TIPOS_DE_CONFLITO = ("duplicidade", "contencao", "sobreposicao")

# Manual entries often share one instant because ClickUp stamps the start when
# the person clicks, not when the work happened. Three or more entries on the
# same instant is a day with no usable clock, not three double posts, and the
# pairwise check there turns one ordinary day into dozens of accusations: with
# twenty stacked entries it produced a hundred and ninety pairs. Days like that
# are reported once, as a day the clock check could not run.
LIMITE_DE_EMPILHAMENTO = 3


@dataclass
class Achado:
    """One logged entry and what the evidence says about it."""

    entry_id: str
    dia: date
    task_id: str
    descricao: str
    horas_lancadas: float
    horas_evidencia: float
    faturavel: bool
    veredito: str
    evidencias: list[str] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)

    @property
    def precisa_de_olho(self) -> bool:
        # An entry in a clock conflict corroborates against the day's evidence
        # like any other, so the verdict alone would hide it.
        return self.veredito != "corroborada" or bool(self.observacoes)

    @property
    def diferenca(self) -> float:
        return round(self.horas_lancadas - self.horas_evidencia, 2)


@dataclass
class Orfa:
    """Evidence of work with no entry against it.

    The half of the audit that recovers money instead of questioning it: an
    afternoon that happened, was witnessed, and was never billed.
    """

    dia: date
    horas: float
    fontes: tuple[str, ...]
    amostra: str


@dataclass
class Conflito:
    """Two entries whose clock times cannot both be billed as they stand.

    Found by comparing entries against each other instead of against the
    evidence. `horas` is the disputed stretch, the overlap itself, not the sum
    of the two entries.
    """

    tipo: str
    dia: date
    entradas: tuple[str, str]
    horas: float
    descricoes: tuple[str, str]

    @property
    def frase(self) -> str:
        return {
            "duplicidade": "mesma hora de inicio e mesma duracao: um lancamento em dobro",
            "contencao": "uma entrada inteira dentro da outra",
            "sobreposicao": "as duas ocupam o mesmo trecho do dia",
        }.get(self.tipo, self.tipo)


@dataclass
class Concentracao:
    """One task holding an unusual share of a day, or of the whole window."""

    escopo: str
    task_id: str
    horas: float
    descricao: str
    dia: date | None = None


@dataclass
class Auditoria:
    """A closing period, audited."""

    inicio: date
    fim: date
    achados: list[Achado] = field(default_factory=list)
    orfas: list[Orfa] = field(default_factory=list)
    conflitos: list[Conflito] = field(default_factory=list)
    concentracoes: list[Concentracao] = field(default_factory=list)
    sem_relogio: list[date] = field(default_factory=list)

    @property
    def total_lancado(self) -> float:
        return round(sum(a.horas_lancadas for a in self.achados), 2)

    @property
    def total_faturavel(self) -> float:
        return round(sum(a.horas_lancadas for a in self.achados if a.faturavel), 2)

    @property
    def corroboradas(self) -> list[Achado]:
        return [a for a in self.achados if a.veredito == "corroborada"]

    @property
    def excecoes(self) -> list[Achado]:
        return [a for a in self.achados if a.precisa_de_olho]

    @property
    def horas_orfas(self) -> float:
        return round(sum(o.horas for o in self.orfas), 2)

    @property
    def horas_em_conflito(self) -> float:
        """Disputed hours, counted once even when a stretch is claimed twice."""
        return round(sum(c.horas for c in self.conflitos), 2)

    @property
    def taxa_de_corroboracao(self) -> float:
        return len(self.corroboradas) / len(self.achados) if self.achados else 0.0


def _formato_ok(descricao: str) -> bool:
    d = (descricao or "").strip()
    return bool(d) and d.endswith(")")


def _intervalo(ent: dict) -> Intervalo | None:
    """The entry as a window on the clock, which is how ClickUp stores it."""
    comeco = de_ms(ent.get("start"))
    if comeco is None:
        return None
    return Intervalo(comeco, comeco + timedelta(milliseconds=max(int(ent.get("duration") or 0), 0)))


def _texto(descricao: str) -> str:
    return " ".join((descricao or "").lower().split())


def _id(ent: dict) -> str:
    return str(ent.get("id") or "?")


def dias_sem_relogio(entradas: list[dict]) -> list[date]:
    """Days whose entries share one start instant, so the clock says nothing."""
    por_dia: dict[date, dict] = defaultdict(lambda: defaultdict(int))
    for ent in entradas:
        iv = _intervalo(ent)
        if iv is None or iv.horas <= 0:
            continue
        por_dia[iv.inicio.date()][iv.inicio] += 1
    return sorted(d for d, inicios in por_dia.items()
                  if max(inicios.values()) >= LIMITE_DE_EMPILHAMENTO)


def conflitos(entradas: list[dict], ignorar: set[date] | None = None) -> list[Conflito]:
    """Entries checked against each other, which this audit never did before.

    Three shapes, all arithmetic on start and duration:

    - **duplicidade**: same start, same duration. The same block posted twice.
    - **contencao**: one window entirely inside another. Andre's forty minutes
      sitting inside another block, billed on both.
    - **sobreposicao**: partial overlap. His three hours that swallow the tail
      of another task.

    The pair is reported, never a culprit: which of the two is wrong is a
    question for the person who logged them.
    """
    ignorar = ignorar if ignorar is not None else set(dias_sem_relogio(entradas))
    por_dia: dict[date, list] = defaultdict(list)
    for ent in entradas:
        iv = _intervalo(ent)
        if iv is None or iv.horas <= 0 or iv.inicio.date() in ignorar:
            continue
        por_dia[iv.inicio.date()].append((ent, iv))

    achados: list[Conflito] = []
    for d, itens in sorted(por_dia.items()):
        itens.sort(key=lambda par: par[1].inicio)
        for i, (a, ia) in enumerate(itens):
            for b, ib in itens[i + 1:]:
                if not ia.sobrepoe(ib):
                    continue
                if ia.inicio == ib.inicio and ia.duracao_ms == ib.duracao_ms:
                    tipo = "duplicidade"
                elif ia.inicio <= ib.inicio and ib.fim <= ia.fim:
                    tipo = "contencao"
                elif ib.inicio <= ia.inicio and ia.fim <= ib.fim:
                    tipo = "contencao"
                else:
                    tipo = "sobreposicao"
                disputado = (min(ia.fim, ib.fim) - max(ia.inicio, ib.inicio)).total_seconds() / 3600
                achados.append(Conflito(
                    tipo=tipo, dia=d, entradas=(_id(a), _id(b)),
                    horas=round(max(disputado, 0.0), 2),
                    descricoes=(a.get("description") or "", b.get("description") or ""),
                ))
    return achados


def concentracoes(entradas: list[dict]) -> list[Concentracao]:
    """Where one task holds an unusual share of a day, or of the window.

    Both thresholds come from the cases Andre read out on 04/09 and neither is
    a measurement, so both are named constants. The finding is a size, not a
    verdict: a genuine eight hour day on one task is a normal thing that this
    report simply says out loud.
    """
    por_dia: dict[tuple[date, str], float] = defaultdict(float)
    por_tarefa: dict[str, float] = defaultdict(float)
    descricao: dict[str, str] = {}

    for ent in entradas:
        iv = _intervalo(ent)
        if iv is None or iv.horas <= 0:
            continue
        task = str((ent.get("task") or {}).get("id") or "?")
        por_dia[(iv.inicio.date(), task)] += iv.horas
        por_tarefa[task] += iv.horas
        descricao.setdefault(task, ent.get("description") or "")

    achados = [
        Concentracao(escopo="dia", dia=d, task_id=task, horas=round(h, 2),
                     descricao=descricao.get(task, ""))
        for (d, task), h in sorted(por_dia.items()) if h >= CONCENTRACAO_H
    ]
    achados += [
        Concentracao(escopo="periodo", dia=None, task_id=task, horas=round(h, 2),
                     descricao=descricao.get(task, ""))
        for task, h in sorted(por_tarefa.items()) if h >= TAREFA_GRANDE_H
    ]
    return achados


def _marcar_data_trocada(aud: "Auditoria", tolerancia: float) -> None:
    """Pair an entry with no trail against an orphan day next door.

    Andre's reading of one of his own cases: the work happened, it was logged,
    and the date was wrong. The two halves are already in the audit and were
    never put side by side. This only ever adds a note, because the same shape
    is also produced by two unrelated days, and calling it an error would be a
    guess wearing a verdict's clothes.
    """
    por_dia = {o.dia: o for o in aud.orfas}
    for a in aud.achados:
        if a.veredito != "sem lastro":
            continue
        vizinhos = [a.dia + timedelta(days=d)
                    for delta in range(1, DIAS_DE_DATA_TROCADA + 1)
                    for d in (-delta, delta)]
        for vizinho in vizinhos:
            o = por_dia.get(vizinho)
            if o is None:
                continue
            if abs(o.horas - a.horas_lancadas) <= max(tolerancia * a.horas_lancadas, 0.5):
                a.observacoes.append(
                    f"possivel data trocada: ha {o.horas:.1f}h de evidencia sem "
                    f"lancamento em {vizinho:%d/%m}, que e o tamanho desta entrada")
                break


def auditar(entradas: list[dict], evidencias: list, inicio: date, fim: date,
            tolerancia: float = TOLERANCIA) -> Auditoria:
    """Match logged entries against evidence, both directions."""
    por_dia: dict[date, list] = defaultdict(list)
    for e in evidencias:
        por_dia[e.inicio.date()].append(e)

    aud = Auditoria(inicio=inicio, fim=fim)
    dias_com_lancamento: set[date] = set()

    for ent in entradas:
        comeco = de_ms(ent.get("start"))
        if comeco is None:
            continue
        dia = comeco.date()
        dias_com_lancamento.add(dia)
        lancadas = round(int(ent.get("duration") or 0) / 3_600_000, 2)
        do_dia = por_dia.get(dia, [])
        evid_horas = round(somar_horas([e.intervalo for e in do_dia]), 2)
        descricao = ent.get("description") or ""

        observacoes: list[str] = []
        if not _formato_ok(descricao):
            # An entry without the house format vanishes from the billable
            # hours report, which is how the pilot's first days went missing.
            observacoes.append("fora do formato da casa: some do relatorio de horas")

        if not do_dia:
            veredito = "sem lastro"
            observacoes.append(
                "nenhuma evidencia de maquina neste dia. Nao quer dizer que nao houve "
                "trabalho: planejamento, ligacao e conversa nao deixam rastro, e foi "
                "ali que estavam 60% das horas do piloto")
        elif abs(lancadas - evid_horas) > max(tolerancia * max(lancadas, evid_horas), 0.5):
            veredito = "divergente"
        elif observacoes:
            veredito = "fora do formato"
        else:
            veredito = "corroborada"

        aud.achados.append(Achado(
            entry_id=str(ent.get("id") or "?"),
            dia=dia,
            task_id=str((ent.get("task") or {}).get("id") or "?"),
            descricao=descricao,
            horas_lancadas=lancadas,
            horas_evidencia=evid_horas,
            faturavel=bool(ent.get("billable")),
            veredito=veredito,
            evidencias=[e.descricao for e in do_dia[:5]],
            observacoes=observacoes,
        ))

    # The other direction: days that were witnessed and never logged.
    for dia, do_dia in sorted(por_dia.items()):
        if dia in dias_com_lancamento or not (inicio <= dia <= fim):
            continue
        h = round(somar_horas([e.intervalo for e in do_dia]), 2)
        if h <= 0:
            continue
        aud.orfas.append(Orfa(
            dia=dia, horas=h,
            fontes=tuple(sorted({e.tipo for e in do_dia})),
            amostra=do_dia[0].descricao,
        ))

    # Entries against each other, and against their own size. Both are pure
    # arithmetic on what ClickUp already returned, so they run with or without
    # any evidence at all: the daily audit is useful on a machine that has no
    # collector configured.
    aud.sem_relogio = dias_sem_relogio(entradas)
    aud.conflitos = conflitos(entradas, ignorar=set(aud.sem_relogio))
    aud.concentracoes = concentracoes(entradas)
    _marcar_conflitos(aud)
    _marcar_data_trocada(aud, tolerancia)
    return aud


def _marcar_conflitos(aud: "Auditoria") -> None:
    """Put the conflict on the entries themselves, so the listing shows it.

    Without this an entry whose hours corroborate perfectly stays counted as
    corroborated and never appears in the exceptions, which is exactly where a
    double booked block would hide.
    """
    por_id: dict[str, list[Achado]] = defaultdict(list)
    for a in aud.achados:
        por_id[a.entry_id].append(a)
    for c in aud.conflitos:
        for i, entry_id in enumerate(c.entradas):
            outro = c.entradas[1 - i]
            for a in por_id.get(entry_id, ()):
                a.observacoes.append(
                    f"{c.tipo} com a entrada {outro}: {c.frase}, {c.horas:.2f}h em disputa")


def relatorio(aud: Auditoria) -> str:
    """Render the audit for a human reading by exception."""
    linhas = [
        f"# Auditoria de apontamentos: {aud.inicio:%d/%m} a {aud.fim:%d/%m}",
        "",
        f"Lancado no periodo: {aud.total_lancado:.1f}h "
        f"({aud.total_faturavel:.1f}h faturaveis) em {len(aud.achados)} entradas",
        f"Corroboradas pela evidencia: {len(aud.corroboradas)} de {len(aud.achados)} "
        f"({aud.taxa_de_corroboracao:.0%})",
        f"Precisam de olho: {len(aud.excecoes)}",
    ]
    if aud.orfas:
        linhas.append(f"Trabalho com evidencia e sem lancamento: "
                      f"{aud.horas_orfas:.1f}h em {len(aud.orfas)} dias")
    if aud.conflitos:
        linhas.append(f"Entradas que disputam o mesmo horario: {len(aud.conflitos)} "
                      f"({aud.horas_em_conflito:.1f}h em disputa)")
    linhas.append("")

    if aud.excecoes:
        linhas.append("## Excecoes, com a evidencia ao lado")
        for a in sorted(aud.excecoes, key=lambda x: (x.veredito, x.dia)):
            linhas.append(
                f"\n### {a.dia:%d/%m} [{a.veredito}] {a.horas_lancadas:.1f}h "
                f"{'faturavel' if a.faturavel else 'nao faturavel'}")
            linhas.append(f"  lancado: {a.descricao or '(sem descricao)'}")
            if a.horas_evidencia:
                linhas.append(f"  evidencia: {a.horas_evidencia:.1f}h "
                              f"(diferenca de {a.diferenca:+.1f}h)")
            for ev in a.evidencias:
                linhas.append(f"    > {ev[:120]}")
            for o in a.observacoes:
                linhas.append(f"  nota: {o}")
        linhas.append("")

    if aud.orfas:
        linhas.append("## Dias com evidencia e sem lancamento")
        for o in aud.orfas:
            linhas.append(f"- {o.dia:%d/%m}: {o.horas:.1f}h "
                          f"({', '.join(o.fontes)})\n    > {o.amostra[:120]}")
        linhas.append("")

    if aud.sem_relogio:
        dias = ", ".join(f"{d:%d/%m}" for d in aud.sem_relogio)
        linhas.append(f"Dias em que a checagem de horario nao rodou, porque os "
                      f"lancamentos partem todos do mesmo instante: {dias}")
        linhas.append("")

    if aud.conflitos:
        linhas.append("## Horarios que se cruzam")
        for c in sorted(aud.conflitos, key=lambda x: (x.dia, x.tipo)):
            linhas.append(f"\n### {c.dia:%d/%m} [{c.tipo}] {c.horas:.2f}h em disputa")
            linhas.append(f"  {c.frase}")
            linhas.append(f"  {c.entradas[0]}: {c.descricoes[0] or '(sem descricao)'}")
            linhas.append(f"  {c.entradas[1]}: {c.descricoes[1] or '(sem descricao)'}")
        linhas.append("")

    if aud.concentracoes:
        linhas.append("## Concentracao de horas")
        for c in aud.concentracoes:
            onde = f"em {c.dia:%d/%m}" if c.dia else "no periodo"
            linhas.append(f"- {c.horas:.1f}h numa tarefa so {onde}: "
                          f"{c.descricao or '(sem descricao)'}")
        linhas.append("")

    linhas.append(
        "Nenhum veredito aqui acusa erro. 'Sem lastro' quer dizer que esta auditoria "
        "nao viu evidencia de maquina, e ela nao ve planejamento, ligacao nem conversa. "
        "Horario cruzado e concentracao sao aritmetica de relogio, nao leitura de "
        "intencao: qual das duas entradas esta errada e pergunta para quem lancou. "
        "As entradas corroboradas nao sao listadas de proposito: auditoria que imprime "
        "tudo e lida por cima, e ler por cima e o mesmo que nao auditar.")
    return "\n".join(linhas)
