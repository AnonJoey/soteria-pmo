"""Time windows, in the timezone the team actually works in.

ClickUp speaks epoch milliseconds and the team speaks Brasilia time. Every bug
in the pilot's dating came from mixing the two, so the conversion lives here
and nowhere else.

One dating rule is encoded rather than remembered, because getting it wrong
already cost a day of wrongly attributed hours: in a daily standup, the present
continuous describes the project in progress, not yesterday. Only an explicit
"ontem" dates the previous day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

BRT = timezone(timedelta(hours=-3))

# Only this marker moves a statement to the previous day. "estou fazendo X"
# in a standup is about the project, not about yesterday.
_MARCA_ONTEM = re.compile(r"\bontem\b", re.IGNORECASE)


def ms(dt: datetime) -> int:
    """Epoch milliseconds, from an aware or naive-as-BRT datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BRT)
    return int(dt.timestamp() * 1000)


def de_ms(valor: int | str | None) -> datetime | None:
    """A BRT datetime from epoch milliseconds. None passes through.

    ClickUp returns these as strings about as often as numbers, and a silent
    TypeError here becomes a task with no due date rather than a crash.
    """
    if valor in (None, "", "null"):
        return None
    try:
        return datetime.fromtimestamp(int(valor) / 1000, BRT)
    except (TypeError, ValueError):
        return None


def dia(d: date) -> tuple[int, int]:
    """The (start, end) millisecond bounds of one calendar day in BRT."""
    inicio = datetime.combine(d, time.min, tzinfo=BRT)
    return ms(inicio), ms(inicio + timedelta(days=1)) - 1


def janela(inicio: date, fim: date) -> tuple[int, int]:
    """Millisecond bounds covering both endpoint days, inclusive."""
    return dia(inicio)[0], dia(fim)[1]


def dias_uteis(inicio: date, fim: date, feriados: frozenset[date] = frozenset()) -> int:
    """Business days between two dates, inclusive, skipping weekends and holidays.

    Used to project when a budget runs out. Counting calendar days there reads
    a project as burning through its hours on weekends, which moves the alert
    forward by two days every week.
    """
    if fim < inicio:
        return 0
    total = 0
    d = inicio
    while d <= fim:
        if d.weekday() < 5 and d not in feriados:
            total += 1
        d += timedelta(days=1)
    return total


def data_da_fala(texto: str, dia_da_reuniao: date) -> date:
    """Which day a standup statement is about.

    The rule that cost a day of misattributed hours: present continuous
    describes the project in progress, so it dates to the meeting itself.
    Only an explicit "ontem" moves it back.
    """
    return dia_da_reuniao - timedelta(days=1) if _MARCA_ONTEM.search(texto) else dia_da_reuniao


@dataclass(frozen=True)
class Intervalo:
    """A worked window, with the arithmetic the reports need."""

    inicio: datetime
    fim: datetime

    @property
    def horas(self) -> float:
        return max((self.fim - self.inicio).total_seconds() / 3600, 0.0)

    @property
    def duracao_ms(self) -> int:
        return max(int((self.fim - self.inicio).total_seconds() * 1000), 0)

    def sobrepoe(self, outro: "Intervalo") -> bool:
        """Whether two windows overlap.

        The pilot double-counted hours by summing overlapping windows from two
        different evidence sources for the same stretch of work.
        """
        return self.inicio < outro.fim and outro.inicio < self.fim


def fundir(intervalos: list[Intervalo]) -> list[Intervalo]:
    """Merge overlapping windows so the same hour is never counted twice."""
    if not intervalos:
        return []
    ordenados = sorted(intervalos, key=lambda i: i.inicio)
    fundidos = [ordenados[0]]
    for atual in ordenados[1:]:
        ultimo = fundidos[-1]
        if atual.inicio <= ultimo.fim:
            fundidos[-1] = Intervalo(ultimo.inicio, max(ultimo.fim, atual.fim))
        else:
            fundidos.append(atual)
    return fundidos


def horas(intervalos: list[Intervalo]) -> float:
    """Total hours across windows, counting overlaps once."""
    return sum(i.horas for i in fundir(intervalos))
