"""Item 1: the client report.

Fills a template from structured ClickUp data. The plan moved this off the
model deliberately: everything the report says is already a field or a sum, so
a model here would be paid to paraphrase numbers, and paraphrase is exactly
where a report to a client can go wrong without anyone noticing.

The delivery level is fixed at 2, agreed on 24/06 and never revised: the report
is produced and handed to Max, who validates and sends. Level 3, sending
straight to the client, was refused. `Reporte.destino` records that so the
boundary is visible in the artifact and not only in a meeting transcript.

What the report does NOT do is judge. It says a task moved or did not, and how
many hours went where. It does not say whether that is good, because that
judgement needs context the card does not hold and it is the part Max is
validating.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .clickup import concluida as _concluida, status_normalizado
from .periodo import campo_objeto, de_ms, janela

logger = logging.getLogger("pmo.reporte")

# The status vocabulary lives in clickup.py, next to the tag vocabulary, because
# both have to match this workspace exactly and both were guessed once.


@dataclass
class Linha:
    """One task's week."""

    task_id: str
    nome: str
    status: str
    responsavel: str
    horas: float
    concluida: bool
    vence_em: date | None

    @property
    def andou(self) -> bool:
        return self.horas > 0


@dataclass
class Reporte:
    """A week's report, at delivery level 2: produced here, sent by a person."""

    projeto: str
    inicio: date
    fim: date
    linhas: list[Linha] = field(default_factory=list)
    horas_faturaveis: float = 0.0
    horas_nao_faturaveis: float = 0.0
    # Level 2 was agreed on 24/06 and level 3 explicitly refused. It is a field
    # so the boundary travels with the artifact.
    destino: str = "Max valida e envia (nivel 2)"

    @property
    def horas_totais(self) -> float:
        return self.horas_faturaveis + self.horas_nao_faturaveis

    @property
    def concluidas(self) -> list[Linha]:
        return [l for l in self.linhas if l.concluida]

    @property
    def em_andamento(self) -> list[Linha]:
        return [l for l in self.linhas if not l.concluida and l.andou]

    @property
    def paradas(self) -> list[Linha]:
        """Open tasks with no hours in the window.

        Reported as "no hours logged", never as "stopped". The report cannot
        tell a task nobody worked on from one that was worked on and not
        logged, and stating either would be inventing the difference.
        """
        return [l for l in self.linhas if not l.concluida and not l.andou]


def montar(tarefas: list[dict], entradas: list[dict], projeto: str,
           inicio: date, fim: date) -> Reporte:
    """Build the week from the two raw payloads."""
    horas_por_tarefa: dict[str, float] = defaultdict(float)
    faturaveis = nao_faturaveis = 0.0
    for e in entradas:
        h = int(e.get("duration") or 0) / 3_600_000
        tid = str(campo_objeto(e, "task").get("id") or "")
        if tid:
            horas_por_tarefa[tid] += h
        if e.get("billable"):
            faturaveis += h
        else:
            nao_faturaveis += h

    linhas = []
    for t in tarefas:
        tid = str(t.get("id"))
        nome_status = status_normalizado(t.get("status")) or "?"
        responsaveis = t.get("assignees") or []
        vence = de_ms(t.get("due_date"))
        linhas.append(Linha(
            task_id=tid,
            nome=t.get("name") or "(sem nome)",
            status=nome_status,
            responsavel=(responsaveis[0].get("username") if responsaveis
                         else "sem responsavel"),
            horas=round(horas_por_tarefa.get(tid, 0.0), 2),
            concluida=_concluida(t.get("status")),
            vence_em=vence.date() if vence else None,
        ))

    return Reporte(projeto=projeto, inicio=inicio, fim=fim, linhas=linhas,
                   horas_faturaveis=round(faturaveis, 2),
                   horas_nao_faturaveis=round(nao_faturaveis, 2))


def markdown(r: Reporte) -> str:
    """Render the report. Text document first, as agreed on 31/08."""
    def bloco(titulo: str, linhas: list[Linha], mostrar_horas: bool = True) -> str:
        if not linhas:
            return ""
        itens = []
        for l in sorted(linhas, key=lambda x: -x.horas):
            sufixo = f" ({l.horas:.1f}h)" if mostrar_horas and l.horas else ""
            itens.append(f"- {l.nome}{sufixo} [{l.responsavel}]")
        return f"\n### {titulo}\n" + "\n".join(itens) + "\n"

    cabecalho = (
        f"# {r.projeto}\n"
        f"Periodo: {r.inicio:%d/%m/%Y} a {r.fim:%d/%m/%Y}\n\n"
        f"Horas no periodo: {r.horas_totais:.1f}h "
        f"({r.horas_faturaveis:.1f}h faturaveis, "
        f"{r.horas_nao_faturaveis:.1f}h nao faturaveis)\n"
        f"Tarefas: {len(r.concluidas)} concluidas, "
        f"{len(r.em_andamento)} em andamento, {len(r.paradas)} sem horas no periodo\n"
    )

    corpo = (bloco("Concluido no periodo", r.concluidas)
             + bloco("Em andamento", r.em_andamento)
             + bloco("Sem horas lancadas no periodo", r.paradas, mostrar_horas=False))

    rodape = (
        f"\n---\n{r.destino}. "
        "Tarefas sem horas no periodo aparecem como tal, e nao como paradas: "
        "o dado nao distingue uma tarefa nao trabalhada de uma trabalhada e "
        "nao apontada.\n"
    )
    return cabecalho + corpo + rodape


def gerar(cliente, list_id: str, projeto: str, inicio: date, fim: date) -> str:
    """Read the week from ClickUp and render it."""
    ini_ms, fim_ms = janela(inicio, fim)
    try:
        tarefas = cliente.tarefas_da_lista(list_id)
        entradas = cliente.entradas(ini_ms, fim_ms)
    except Exception as e:
        logger.warning("nao foi possivel montar o reporte de %s: %s", projeto, e)
        return ""
    return markdown(montar(tarefas, entradas, projeto, inicio, fim))


@dataclass
class ReporteCliente:
    """Consolidated client report separating Implantação from Sustentação.

    Directly implements the 24/06 specification: consolidates the whole client
    (e.g. Grupo Angelus), separating active implementation projects from support
    queues/tickets, at executive level.
    """

    cliente: str
    inicio: date
    fim: date
    implantacao: list[Reporte] = field(default_factory=list)
    sustentacao: list[Reporte] = field(default_factory=list)
    destino: str = "Max valida e envia (nivel 2)"

    @property
    def total_horas(self) -> float:
        return round(sum(r.horas_totais for r in self.implantacao + self.sustentacao), 2)

    @property
    def total_faturavel(self) -> float:
        return round(sum(r.horas_faturaveis for r in self.implantacao + self.sustentacao), 2)

    @property
    def total_nao_faturavel(self) -> float:
        return round(sum(r.horas_nao_faturaveis for r in self.implantacao + self.sustentacao), 2)


def markdown_consolidado(rc: ReporteCliente) -> str:
    """Render the executive consolidated client report."""
    linhas = [
        f"# Reporte Executivo: {rc.cliente}",
        f"Periodo: {rc.inicio:%d/%m/%Y} a {rc.fim:%d/%m/%Y}",
        "",
        f"**Consolidado de Horas**: {rc.total_horas:.1f}h totais "
        f"({rc.total_faturavel:.1f}h faturaveis, {rc.total_nao_faturavel:.1f}h nao faturaveis)",
        "",
    ]

    if rc.implantacao:
        linhas.append("## Projetos de Implantacao")
        for rep in rc.implantacao:
            linhas.append(f"\n### {rep.projeto} ({rep.horas_totais:.1f}h)")
            linhas.append(f"- Concluidas: {len(rep.concluidas)} | Em andamento: {len(rep.em_andamento)} | Sem horas no periodo: {len(rep.paradas)}")
            for t in rep.concluidas:
                linhas.append(f"  * [Concluida] {t.nome} ({t.horas:.1f}h) [{t.responsavel}]")
            for t in rep.em_andamento:
                v = f", vence {t.vence_em:%d/%m}" if t.vence_em else ""
                linhas.append(f"  * [Andamento] {t.nome} ({t.horas:.1f}h){v} [{t.responsavel}]")

    if rc.sustentacao:
        linhas.append("\n## Chamados e Sustentacao")
        for rep in rc.sustentacao:
            linhas.append(f"\n### {rep.projeto} ({rep.horas_totais:.1f}h)")
            linhas.append(f"- Concluidos: {len(rep.concluidas)} | Em atendimento: {len(rep.em_andamento)} | Sem horas: {len(rep.paradas)}")
            for t in rep.concluidas:
                linhas.append(f"  * [Resolvido] {t.nome} ({t.horas:.1f}h) [{t.responsavel}]")
            for t in rep.em_andamento:
                linhas.append(f"  * [Aberto] {t.nome} ({t.horas:.1f}h) [{t.responsavel}]")

    linhas.append(f"\n---\n{rc.destino}. Documento executivo para aprovacao previa.")
    return "\n".join(linhas) + "\n"

