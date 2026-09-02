"""Item 7 (3.2.1): the team's date guardian.

Watches due dates in ClickUp and says which ones are about to be missed or
already were. It is a skill and not an agent, by the criterion the team agreed
on: the whole flow is a written-down comparison between a date and today, with
nothing to decide per case.

It exists as its own module rather than inside the schedule agent because it
answers a different question. The schedule agent asks whether work is moving.
This one asks whether a date is coming, which is true even for a task nobody
has touched and false for one that is late but already re-planned.

A deliberate omission: this does not read task status to guess whether a date
still matters. A task in `ideia` two days before its due date is exactly the
one worth flagging, and filtering by status would hide it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from .periodo import BRT, de_ms

logger = logging.getLogger("pmo.datas")

# Days out at which a date starts being worth mentioning.
HORIZONTE = 3


@dataclass(frozen=True)
class Prazo:
    """One task's date, as the guardian sees it."""

    task_id: str
    nome: str
    responsavel: str
    vence_em: date | None
    status: str
    tem_descricao: bool
    tem_estimativa: bool

    def dias(self, hoje: date) -> int | None:
        return None if self.vence_em is None else (self.vence_em - hoje).days

    def situacao(self, hoje: date) -> str:
        d = self.dias(hoje)
        if d is None:
            return "sem data"
        if d < 0:
            return "vencido"
        if d == 0:
            return "vence hoje"
        return "proximo" if d <= HORIZONTE else "ok"


def ler(tarefas: list[dict]) -> list[Prazo]:
    """Turn ClickUp task payloads into deadlines."""
    prazos = []
    for t in tarefas:
        vence = de_ms(t.get("due_date"))
        responsaveis = t.get("assignees") or []
        prazos.append(Prazo(
            task_id=str(t.get("id")),
            nome=t.get("name") or "(sem nome)",
            responsavel=(responsaveis[0].get("username") if responsaveis else "sem responsavel"),
            vence_em=vence.date() if vence else None,
            status=((t.get("status") or {}).get("status")
                    if isinstance(t.get("status"), dict) else t.get("status")) or "?",
            tem_descricao=bool((t.get("description") or t.get("text_content") or "").strip()),
            tem_estimativa=t.get("time_estimate") not in (None, 0, "0"),
        ))
    return prazos


def guardar(prazos: list[Prazo], hoje: date) -> dict[str, list[Prazo]]:
    """Group deadlines by how urgent they are."""
    grupos: dict[str, list[Prazo]] = {
        "vencido": [], "vence hoje": [], "proximo": [], "sem data": [], "ok": []}
    for p in prazos:
        grupos[p.situacao(hoje)].append(p)
    for chave in ("vencido", "vence hoje", "proximo"):
        # Most overdue first: a task three days late outranks one an hour late.
        grupos[chave].sort(key=lambda p: p.dias(hoje) if p.dias(hoje) is not None else 0)
    return grupos


def higiene(prazos: list[Prazo]) -> list[str]:
    """Card problems that are not about dates but block everything downstream.

    A task with no description is invisible to whoever reads the report, and a
    task with no estimate cannot be capacity-planned. Both were true of all
    twelve tasks on the Agentes PMO list when this was written, which is why
    the guardian reports them instead of assuming someone noticed.
    """
    problemas = []
    sem_descricao = [p for p in prazos if not p.tem_descricao]
    sem_estimativa = [p for p in prazos if not p.tem_estimativa]
    sem_data = [p for p in prazos if p.vence_em is None]
    if sem_descricao:
        problemas.append(f"{len(sem_descricao)} de {len(prazos)} tarefas sem descricao")
    if sem_estimativa:
        problemas.append(f"{len(sem_estimativa)} de {len(prazos)} sem estimativa de tempo")
    if sem_data:
        problemas.append(f"{len(sem_data)} sem data de entrega")
    return problemas


def digest(prazos: list[Prazo], hoje: date, incluir_higiene: bool = True) -> str:
    """The guardian's message. Empty when there is nothing to say."""
    grupos = guardar(prazos, hoje)
    partes: list[str] = []

    for chave, titulo in (("vencido", "Vencidos"),
                          ("vence hoje", "Vencem hoje"),
                          ("proximo", f"Vencem em ate {HORIZONTE} dias")):
        if not grupos[chave]:
            continue
        linhas = []
        for p in grupos[chave]:
            d = p.dias(hoje)
            quando = (f"ha {-d}d" if d is not None and d < 0
                      else "hoje" if d == 0 else f"em {d}d")
            linhas.append(f"  {p.nome} ({p.responsavel}, {p.status}) {quando}")
        partes.append(f"{titulo}:\n" + "\n".join(linhas))

    if incluir_higiene:
        problemas = higiene(prazos)
        if problemas:
            partes.append("Higiene do card:\n" + "\n".join(f"  {p}" for p in problemas))

    return "Guardiao das datas\n" + "\n\n".join(partes) if partes else ""


def vigiar(cliente, list_id: str, hoje: date) -> str:
    """Read a list and produce the guardian's message for today."""
    try:
        tarefas = cliente.tarefas_da_lista(list_id)
    except Exception as e:
        logger.warning("nao foi possivel ler a lista %s: %s", list_id, e)
        return ""
    return digest(ler(tarefas), hoje)
