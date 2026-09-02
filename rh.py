"""Item 6: RH and dates.

Calendar rules over the team's dates: birthdays, work anniversaries, probation
milestones, contract ends and booked time off. Called trivial in the scope
discussion, and it is, which is exactly why it must not touch the model. A rule
that says "warn 30 days before a contract ends" is a subtraction; sending it
through an LLM spends credits to get a date arithmetic answer that a script
gives exactly, and it introduces a way for the answer to be wrong.

Its data does not live in ClickUp. The team's dates come from a file the HR
side maintains, so this module reads that file and refuses to guess when it is
missing: an empty roster produces no alerts and says so, rather than reporting
a quiet "nothing coming up" that looks identical to a healthy week.

Two rules carry a rolling window rather than one date, because they repeat every
year: birthday and work anniversary. The others fire once.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger("pmo.rh")

# How many days ahead each kind of date starts being announced. The contract
# end leads by a month because acting on it means a conversation, not a card.
ANTECEDENCIA = {
    "aniversario": 7,
    "tempo de casa": 7,
    "fim de experiencia": 15,
    "fim de contrato": 30,
    "ferias": 10,
}


class RosterAusente(RuntimeError):
    """The team file is missing or unreadable.

    Raised rather than returning an empty list: no roster and a roster with
    nothing coming up produce the same silence, and only one of them is fine.
    """


@dataclass(frozen=True)
class Pessoa:
    """One team member's dates. Everything except `nome` is optional."""

    nome: str
    nascimento: date | None = None
    admissao: date | None = None
    fim_experiencia: date | None = None
    fim_contrato: date | None = None
    ferias_inicio: date | None = None


@dataclass(frozen=True)
class Evento:
    """A date coming up, with enough context to act on it."""

    pessoa: str
    tipo: str
    quando: date
    dias: int
    detalhe: str = ""

    def linha(self) -> str:
        quando = ("hoje" if self.dias == 0
                  else f"em {self.dias}d" if self.dias > 0 else f"ha {-self.dias}d")
        base = f"{self.pessoa}: {self.tipo} {quando} ({self.quando:%d/%m})"
        return f"{base}, {self.detalhe}" if self.detalhe else base


def _data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip())
    except ValueError:
        logger.warning("data ilegivel no roster: %r", valor)
        return None


def carregar(caminho: str | Path) -> list[Pessoa]:
    """Read the team roster from CSV or JSON.

    Both formats use the same column names, so whichever the HR side already
    exports can be dropped in without a conversion step.
    """
    p = Path(caminho)
    if not p.exists():
        raise RosterAusente(f"roster de RH nao encontrado em {p}")
    try:
        if p.suffix.lower() == ".json":
            linhas = json.loads(p.read_text())
        else:
            with p.open(newline="") as fh:
                linhas = list(csv.DictReader(fh))
    except Exception as e:
        raise RosterAusente(f"roster de RH ilegivel em {p}: {e}") from e

    pessoas = []
    for linha in linhas:
        nome = (linha.get("nome") or "").strip()
        if not nome:
            continue
        pessoas.append(Pessoa(
            nome=nome,
            nascimento=_data(linha.get("nascimento")),
            admissao=_data(linha.get("admissao")),
            fim_experiencia=_data(linha.get("fim_experiencia")),
            fim_contrato=_data(linha.get("fim_contrato")),
            ferias_inicio=_data(linha.get("ferias_inicio")),
        ))
    return pessoas


def _proxima_ocorrencia(quando: date, hoje: date) -> date:
    """The next anniversary of a date, this year or next.

    Feb 29 falls back to Mar 1 in a common year rather than raising, which is
    what a calendar app does and what people expect.
    """
    for ano in (hoje.year, hoje.year + 1):
        try:
            candidata = quando.replace(year=ano)
        except ValueError:
            candidata = date(ano, 3, 1)
        if candidata >= hoje:
            return candidata
    return quando.replace(year=hoje.year + 1)


def eventos(pessoas: list[Pessoa], hoje: date) -> list[Evento]:
    """Every date worth announcing today, nearest first."""
    achados: list[Evento] = []

    for p in pessoas:
        # Repeating dates: next occurrence, this year or next.
        if p.nascimento:
            q = _proxima_ocorrencia(p.nascimento, hoje)
            d = (q - hoje).days
            if d <= ANTECEDENCIA["aniversario"]:
                achados.append(Evento(p.nome, "aniversario", q, d))
        if p.admissao:
            q = _proxima_ocorrencia(p.admissao, hoje)
            d = (q - hoje).days
            if d <= ANTECEDENCIA["tempo de casa"]:
                anos = q.year - p.admissao.year
                if anos >= 1:
                    achados.append(Evento(p.nome, "tempo de casa", q, d,
                                          f"{anos} ano{'s' if anos > 1 else ''}"))

        # One-off dates. Past ones still surface: a probation period that ended
        # last week without anyone noticing is the case worth catching.
        for campo, tipo in (("fim_experiencia", "fim de experiencia"),
                            ("fim_contrato", "fim de contrato"),
                            ("ferias_inicio", "ferias")):
            quando = getattr(p, campo)
            if quando is None:
                continue
            d = (quando - hoje).days
            if -30 <= d <= ANTECEDENCIA[tipo]:
                achados.append(Evento(p.nome, tipo, quando, d))

    return sorted(achados, key=lambda e: (e.dias, e.pessoa))


def digest(pessoas: list[Pessoa], hoje: date) -> str:
    """The RH message. Empty when the calendar has nothing this week."""
    achados = eventos(pessoas, hoje)
    if not achados:
        return ""
    vencidos = [e for e in achados if e.dias < 0]
    proximos = [e for e in achados if e.dias >= 0]
    partes = []
    if vencidos:
        partes.append("Passaram sem aviso:\n" +
                      "\n".join(f"  {e.linha()}" for e in vencidos))
    if proximos:
        partes.append("Chegando:\n" + "\n".join(f"  {e.linha()}" for e in proximos))
    return "RH e datas\n" + "\n\n".join(partes)


def rodar(caminho: str | Path, hoje: date) -> str:
    """Read the roster and produce today's message."""
    return digest(carregar(caminho), hoje)
