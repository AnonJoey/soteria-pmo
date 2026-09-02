"""Item 3: the audit of what was logged.

Runs monthly at closing and answers one question for Andre: does each logged
entry have something behind it, and is there work with evidence that nobody
logged? It is the mirror of the hours engine. That one proposes from evidence;
this one starts from what is already in ClickUp and looks for the evidence back.

The output is built for auditing by exception. Andre does not have time to read
a month line by line, so entries that corroborate cleanly are counted and not
listed, and everything that needs a human eye is listed with the raw evidence
next to it. An audit that prints everything gets skimmed, and skimming an audit
is the same as not running it.

What this deliberately does not do is call anything fraud, or even wrong. An
entry with no evidence behind it is reported as "no evidence found", because
this module cannot see planning, phone calls, or a whiteboard, and those are
exactly where the missing 60% of the pilot's hours turned out to live.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .periodo import Intervalo, de_ms, fundir, horas as somar_horas

logger = logging.getLogger("pmo.auditor")

# How far a logged duration may differ from the evidence before it is worth a
# human look. Evidence windows are approximate by nature, so a tight threshold
# would flag every entry and a loose one would flag none.
TOLERANCIA = 0.25

VEREDITOS = ("corroborada", "divergente", "sem lastro", "fora do formato")


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
        return self.veredito != "corroborada"

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
class Auditoria:
    """A closing period, audited."""

    inicio: date
    fim: date
    achados: list[Achado] = field(default_factory=list)
    orfas: list[Orfa] = field(default_factory=list)

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
    def taxa_de_corroboracao(self) -> float:
        return len(self.corroboradas) / len(self.achados) if self.achados else 0.0


def _formato_ok(descricao: str) -> bool:
    d = (descricao or "").strip()
    return bool(d) and d.endswith(")")


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
    return aud


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

    linhas.append(
        "Nenhum veredito aqui acusa erro. 'Sem lastro' quer dizer que esta auditoria "
        "nao viu evidencia de maquina, e ela nao ve planejamento, ligacao nem conversa. "
        "As entradas corroboradas nao sao listadas de proposito: auditoria que imprime "
        "tudo e lida por cima, e ler por cima e o mesmo que nao auditar.")
    return "\n".join(linhas)
