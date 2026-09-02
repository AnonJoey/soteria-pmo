"""What runs when: the seven items on their four cadences.

The planning up to 28/08 treated the six items as one delivery, and the gap
that surfaced on 30/08 was that they do not share a frequency. Cadence is what
decides infrastructure, and once the budget watch left real time behind, no
item needed a dedicated machine. That is the finding this module makes
operational: the cadences live in one table instead of in whoever remembers to
run things.

Nothing here writes to ClickUp. The routine produces text for a person to read
and, for hours, a proposal for a person to approve. That boundary is the same
one the whole package is built on and it is enforced here by simply not having
a write path: `rodar` returns a Digest.

An item that fails is reported as failed and the rest still run. A routine
where one broken API call silences the other six is worse than no routine,
because the silence looks exactly like a quiet week.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger("pmo.rotina")

DIARIA, SEMANAL, MENSAL, CONTINUA = "diaria", "semanal", "mensal", "continua"

# Item to cadence. Taken from the cadence map of 30/08, with the budget watch
# already moved off real time by the 31/08 meeting.
CADENCIAS: dict[str, str] = {
    "reporte": SEMANAL,        # item 1, mais disparo manual
    "cronograma": CONTINUA,    # item 2, alerta escalonado
    "auditor": MENSAL,         # item 3, no fechamento
    "horas": DIARIA,           # item 4, sempre com aprovacao humana
    "bolsao": DIARIA,          # item 5, era tempo real ate 31/08
    "rh": DIARIA,              # item 6, regra de calendario
    "datas": CONTINUA,         # item 7, guardiao das datas
}

# Which weekday the weekly items fire on. Monday, so the week starts with the
# report of the one that ended.
DIA_DO_SEMANAL = 0


@dataclass
class Saida:
    """One item's turn: what it said, or why it could not say anything."""

    item: str
    cadencia: str
    rodou: bool
    texto: str = ""
    erro: str = ""

    @property
    def falou(self) -> bool:
        return self.rodou and bool(self.texto.strip())


@dataclass
class Digest:
    """Everything the routine has to say today."""

    dia: date
    saidas: list[Saida] = field(default_factory=list)

    @property
    def falantes(self) -> list[Saida]:
        return [s for s in self.saidas if s.falou]

    @property
    def erros(self) -> list[Saida]:
        return [s for s in self.saidas if s.erro]

    @property
    def silenciosos(self) -> list[Saida]:
        return [s for s in self.saidas if s.rodou and not s.falou and not s.erro]

    def texto(self) -> str:
        partes = [f"# Agentes PMO, {self.dia:%d/%m/%Y}", ""]
        for s in self.falantes:
            partes.append(s.texto.rstrip())
            partes.append("")
        if self.erros:
            partes.append("## Itens que nao rodaram")
            for s in self.erros:
                partes.append(f"- {s.item}: {s.erro}")
            partes.append("")
        # Said out loud rather than left implicit: a silent item and an item
        # that never ran look identical to whoever reads this.
        if self.silenciosos:
            nomes = ", ".join(s.item for s in self.silenciosos)
            partes.append(f"Rodaram e nao tinham nada a dizer: {nomes}.")
        # Only when nothing ran at all. With silent items the line above has
        # already said more than this one would, and saying both reads as a
        # contradiction: they ran and had nothing, versus there was nothing.
        if not self.falantes and not self.erros and not self.silenciosos:
            partes.append("Nada a reportar hoje.")
        return "\n".join(partes).rstrip() + "\n"


def devido(item: str, hoje: date, ultimo_mensal: date | None = None) -> bool:
    """Whether an item runs today, by its own cadence.

    Monthly fires on the first business day of the month rather than on day 1,
    because closing happens on a working day and a Saturday run reports into
    nobody's inbox. `ultimo_mensal` makes it idempotent: running the routine
    twice on the same day does not audit the month twice.
    """
    cadencia = CADENCIAS.get(item)
    if cadencia is None:
        return False
    if cadencia in (DIARIA, CONTINUA):
        return hoje.weekday() < 5
    if cadencia == SEMANAL:
        return hoje.weekday() == DIA_DO_SEMANAL
    # MENSAL
    if hoje.weekday() >= 5:
        return False
    if ultimo_mensal is not None and (ultimo_mensal.year, ultimo_mensal.month) == \
            (hoje.year, hoje.month):
        return False
    # First business day of the month: no earlier weekday exists this month.
    primeiro_util = date(hoje.year, hoje.month, 1)
    while primeiro_util.weekday() >= 5:
        primeiro_util = primeiro_util.replace(day=primeiro_util.day + 1)
    return hoje == primeiro_util


def rodar(hoje: date, tarefas: dict[str, callable], *,
          ultimo_mensal: date | None = None,
          forcar: frozenset[str] = frozenset()) -> Digest:
    """Run whichever items are due, plus anything in `forcar`.

    `tarefas` maps an item name to a zero-argument callable returning its text.
    Wiring lives at the call site so this module depends on no client, which is
    what lets the whole routine be tested without a network.

    `forcar` is the manual trigger the report item was specified with: Max asks
    for it out of cycle and it runs.
    """
    digest = Digest(dia=hoje)
    for item, fn in tarefas.items():
        cadencia = CADENCIAS.get(item, "?")
        if item not in forcar and not devido(item, hoje, ultimo_mensal):
            digest.saidas.append(Saida(item, cadencia, rodou=False))
            continue
        try:
            texto = fn() or ""
        except Exception as e:
            # One broken item must not silence the other six: silence reads as
            # a quiet week, which is the one thing this must never fake.
            logger.warning("item %s falhou: %s", item, e)
            logger.debug("%s", traceback.format_exc())
            digest.saidas.append(Saida(item, cadencia, rodou=True,
                                       erro=f"{type(e).__name__}: {e}"))
            continue
        digest.saidas.append(Saida(item, cadencia, rodou=True, texto=texto))
    return digest
