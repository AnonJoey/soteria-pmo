"""Item 5: the budget watch.

Reads hours already logged against a project's contracted budget and says how
close it is to the end, and when it will get there at the current pace.

Two decisions from the 31/08 meeting shape this module. The watch left real
time behind: a daily or every-other-day cadence was accepted, and that single
change is what removed the only requirement for dedicated infrastructure in
the whole project. And it runs entirely as a script: the data is already
structured in ClickUp, so putting a model in this path would spend credits to
restate arithmetic. The rule from the architecture holds here literally,
what already arrives structured does not pass through the model.

The projection is deliberately conservative about what it does not know. A
budget that has burned 80% with no historical pace is reported as 80% burned,
not as a date, because a date invented from one week of data reads as a
measurement and gets forwarded as one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from .periodo import BRT, de_ms, dias_uteis, janela

logger = logging.getLogger("pmo.bolsao")

# Where the alerts step up. Below the first threshold the watch stays quiet:
# an alert on every run is an alert nobody reads.
FAIXAS = ((1.00, "estourado"), (0.90, "critico"), (0.75, "atencao"))


@dataclass(frozen=True)
class Bolsao:
    """A project's contracted hours."""

    projeto: str
    list_id: str
    horas_contratadas: float

    def __post_init__(self) -> None:
        if self.horas_contratadas <= 0:
            raise ValueError(f"bolsao de {self.projeto} sem horas contratadas")


@dataclass
class Situacao:
    """Where a project's budget stands, and where it is heading."""

    projeto: str
    horas_contratadas: float
    horas_gastas: float
    faturaveis: float
    nao_faturaveis: float
    nivel: str
    dias_uteis_observados: int
    ritmo_diario: float | None
    data_estouro: date | None
    dias_ate_estourar: int | None

    @property
    def percentual(self) -> float:
        return self.horas_gastas / self.horas_contratadas

    @property
    def horas_restantes(self) -> float:
        return self.horas_contratadas - self.horas_gastas

    @property
    def alerta(self) -> bool:
        return self.nivel != "ok"

    def linha(self) -> str:
        """One line for the daily digest."""
        base = (f"{self.projeto}: {self.horas_gastas:.1f}h de "
                f"{self.horas_contratadas:.0f}h ({self.percentual:.0%}) [{self.nivel}]")
        if self.data_estouro is not None:
            return f"{base}, no ritmo atual estoura em {self.data_estouro:%d/%m}"
        if self.ritmo_diario is None:
            return f"{base}, sem ritmo medido ainda"
        return f"{base}, nao estoura no horizonte medido"


def _nivel(percentual: float) -> str:
    for limite, nome in FAIXAS:
        if percentual >= limite:
            return nome
    return "ok"


def apurar(entradas: list[dict], bolsao: Bolsao, inicio: date, fim: date,
           feriados: frozenset[date] = frozenset(),
           minimo_para_projetar: int = 5) -> Situacao:
    """Turn raw time entries into a budget position.

    `minimo_para_projetar` is the number of observed business days below which
    no exhaustion date is produced. Five is one working week: projecting from
    less than that turns a slow Monday into a deadline.
    """
    faturaveis = nao_faturaveis = 0.0
    for e in entradas:
        h = int(e.get("duration") or 0) / 3_600_000
        if e.get("billable"):
            faturaveis += h
        else:
            nao_faturaveis += h
    gastas = faturaveis + nao_faturaveis

    observados = dias_uteis(inicio, fim, feriados)
    ritmo = gastas / observados if observados >= minimo_para_projetar and gastas else None

    data_estouro = dias_restantes = None
    if ritmo:
        restantes = bolsao.horas_contratadas - gastas
        if restantes > 0:
            dias_restantes = max(int(restantes / ritmo), 0)
            # Walk business days rather than adding calendar days: a budget does
            # not burn on a Sunday, and adding raw days moves every alert two
            # days early each week.
            d, andados = fim, 0
            while andados < dias_restantes:
                d += timedelta(days=1)
                if d.weekday() < 5 and d not in feriados:
                    andados += 1
            data_estouro = d
        else:
            dias_restantes = 0
            data_estouro = fim

    return Situacao(
        projeto=bolsao.projeto,
        horas_contratadas=bolsao.horas_contratadas,
        horas_gastas=gastas,
        faturaveis=faturaveis,
        nao_faturaveis=nao_faturaveis,
        nivel=_nivel(gastas / bolsao.horas_contratadas),
        dias_uteis_observados=observados,
        ritmo_diario=ritmo,
        data_estouro=data_estouro,
        dias_ate_estourar=dias_restantes,
    )


def vigiar(cliente, bolsoes: list[Bolsao], inicio: date, fim: date,
           feriados: frozenset[date] = frozenset()) -> list[Situacao]:
    """Read the window once per project and report each position.

    Entries are fetched per project list rather than for the whole workspace
    because a time entry names its task, and mapping tasks back to projects
    workspace-wide costs one call per task.
    """
    ini_ms, fim_ms = janela(inicio, fim)
    situacoes = []
    for b in bolsoes:
        try:
            todas = cliente.entradas(ini_ms, fim_ms)
        except Exception as e:
            logger.warning("nao foi possivel ler as entradas de %s: %s", b.projeto, e)
            continue
        do_projeto = [e for e in todas
                      if (e.get("task_location") or {}).get("list_id") == b.list_id]
        situacoes.append(apurar(do_projeto, b, inicio, fim, feriados))
    return situacoes


def digest(situacoes: list[Situacao], so_alertas: bool = True) -> str:
    """The message the watch actually sends.

    Returns an empty string when nothing crossed a threshold. A watch that
    reports "everything fine" every day trains its readers to skip it, and
    then the one day it matters is skipped too.
    """
    linhas = [s.linha() for s in sorted(situacoes, key=lambda s: -s.percentual)
              if s.alerta or not so_alertas]
    if not linhas:
        return ""
    return "Vigia de bolsao\n" + "\n".join(f"  {l}" for l in linhas)
