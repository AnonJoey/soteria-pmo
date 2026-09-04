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
from dataclasses import dataclass, field
from datetime import date, timedelta

from .periodo import BRT, de_ms, dias_uteis, janela

logger = logging.getLogger("pmo.bolsao")

# Where the alerts step up. Below the first threshold the watch stays quiet:
# an alert on every run is an alert nobody reads.
FAIXAS = ((1.00, "estourado"), (0.90, "critico"), (0.75, "atencao"))

# Tetos mensais de referencia levantados na reuniao de 03/09 com Abner:
# (China Gate: 100h sustentacao, Yoshii: 160h, Grupo Dimas: 30h, Grupo Anjos: ~100h)
TETOS_DE_REFERENCIA: dict[str, float] = {
    "china gate": 100.0,
    "chinagate": 100.0,
    "yoshii": 160.0,
    "yoshi": 160.0,
    "grupo dimas": 30.0,
    "dimas": 30.0,
    "grupo anjos": 100.0,
    "anjos": 100.0,
}


def teto_sugerido(projeto: str) -> float | None:
    """Return benchmark monthly hours for known clients when unconfigured."""
    p = (projeto or "").strip().lower()
    for k, v in TETOS_DE_REFERENCIA.items():
        if k in p:
            return v
    return None


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
class Vigilancia:
    """A watch pass: what it saw, and what it could not read.

    `falhas` exists because the alternative is the failure mode this whole
    package argues against elsewhere: vigiar() swallowing a read error and
    digest() returning nothing makes an API outage and a healthy week produce
    byte-identical silence. rotina.py already says a routine where one broken
    call silences the rest is worse than no routine, and this module was
    quietly doing it.
    """

    situacoes: list["Situacao"] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)


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
        # Guarded rather than assumed: Bolsao rejects a zero budget, but
        # Situacao is a plain dataclass anyone can build directly.
        if self.horas_contratadas <= 0:
            return 0.0
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
           feriados: frozenset[date] = frozenset()) -> Vigilancia:
    """Read the window once per project and report each position.

    Entries are fetched per project list rather than for the whole workspace
    because a time entry names its task, and mapping tasks back to projects
    workspace-wide costs one call per task.
    """
    ini_ms, fim_ms = janela(inicio, fim)
    v = Vigilancia()
    try:
        equipe = tuple(str(m["id"]) for m in cliente.membros() if m.get("id"))
    except Exception as e:
        logger.warning("nao foi possivel listar a equipe: %s", e)
        v.falhas.append(f"lista de membros: {type(e).__name__}: {e}")
        equipe = None
    for b in bolsoes:
        try:
            # The budget is the whole team's, so this is one of the few callers
            # that genuinely needs everyone. Naming them beats assignee=any,
            # which 500s on a workspace this size.
            todas = cliente.entradas(ini_ms, fim_ms, assignee=equipe)
        except Exception as e:
            logger.warning("nao foi possivel ler as entradas de %s: %s", b.projeto, e)
            v.falhas.append(f"{b.projeto}: {type(e).__name__}: {e}")
            continue
        do_projeto = [e for e in todas
                      if (e.get("task_location") or {}).get("list_id") == b.list_id]
        v.situacoes.append(apurar(do_projeto, b, inicio, fim, feriados))
    return v


def digest(vigilancia: "Vigilancia | list[Situacao]",
           so_alertas: bool = True) -> str:
    """The message the watch actually sends.

    Silent when nothing crossed a threshold, because a watch that reports
    "everything fine" every day trains its readers to skip it, and then the one
    day it matters is skipped too. But never silent about a project it could
    not read: that is not good news, it is no news.
    """
    if isinstance(vigilancia, Vigilancia):
        situacoes, falhas = vigilancia.situacoes, vigilancia.falhas
    else:
        situacoes, falhas = list(vigilancia), []

    linhas = [s.linha() for s in sorted(situacoes, key=lambda s: -s.percentual)
              if s.alerta or not so_alertas]
    if not linhas and not falhas:
        return ""
    partes = ["Vigia de bolsao"]
    partes.extend(f"  {l}" for l in linhas)
    if falhas:
        partes.append("  Nao foi possivel ler:")
        partes.extend(f"    {f}" for f in falhas)
        partes.append("  Estes projetos estao sem vigia hoje, o que nao quer dizer "
                      "que estejam bem.")
    return "\n".join(partes)


def carregar_bolsoes(dados: list[dict] | dict) -> list[Bolsao]:
    """Parse Bolsao instances from configuration data (list or dict)."""
    itens = dados.get("bolsoes", []) if isinstance(dados, dict) else dados
    resultado: list[Bolsao] = []
    for item in itens:
        nome = item.get("projeto") or item.get("nome") or ""
        lid = str(item.get("list_id") or "")
        horas = float(item.get("horas_contratadas") or item.get("horas") or teto_sugerido(nome) or 0.0)
        if nome and lid and horas > 0:
            resultado.append(Bolsao(projeto=nome, list_id=lid, horas_contratadas=horas))
    return resultado

