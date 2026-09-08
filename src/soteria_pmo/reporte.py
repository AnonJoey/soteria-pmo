"""Item 1: the client report.

Fills a template from structured ClickUp data. The plan moved this off the
model deliberately: everything the report says is already a field or a sum, so
a model here would be paid to paraphrase numbers, and paraphrase is exactly
where a report to a client can go wrong without anyone noticing.

The delivery level is fixed at 2, agreed on 24/06 and never revised: the report
is produced and handed to Max, who validates and sends. Level 3, sending
straight to the client, was refused. `Reporte.destino` records that so the
boundary is visible in the artifact and not only in a meeting transcript.

What this MODULE does not do is judge. It says a task moved or did not, and how
many hours went where. It does not say whether that is good, because that
judgement needs context the card does not hold.

The pre-analysis exists as of 08/09/2026, and it lives one layer up. Andre
suggested it on 04/09 and Max said yes. It is written by the agent through the
`pmo-reporte` skill, from this report and nothing else, and it arrives as a
clearly labelled block on top of a body that stays deterministic. Keeping the
two apart is the point: the numbers are auditable and the reading is signed as
a reading, so validating the report never means re-checking arithmetic mixed
with opinion.
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
    def bloco(titulo: str, linhas: list[Linha], mostrar_horas: bool = True,
              teto: int | None = None) -> str:
        if not linhas:
            return ""
        ordenadas = sorted(linhas, key=lambda x: -x.horas)
        cortadas = ordenadas[:teto] if teto else ordenadas
        itens = []
        for l in cortadas:
            sufixo = f" ({l.horas:.1f}h)" if mostrar_horas and l.horas else ""
            itens.append(f"- {l.nome}{sufixo} [{l.responsavel}]")
        if teto and len(ordenadas) > teto:
            itens.append(f"- e mais {len(ordenadas) - teto} tarefas abertas sem "
                         "horas no periodo, nao listadas uma a uma")
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
             # Teto porque uma lista de sustentacao carrega o backlog inteiro:
             # medido em 08/09, o relatorio de um cliente listava 370 tarefas
             # abertas sem horas, e o que aconteceu na semana sumia no meio.
             + bloco("Sem horas lancadas no periodo", r.paradas,
                     mostrar_horas=False, teto=TETO_DE_PARADAS))

    rodape = (
        f"\n---\n{r.destino}. "
        "Tarefas sem horas no periodo aparecem como tal, e nao como paradas: "
        "o dado nao distingue uma tarefa nao trabalhada de uma trabalhada e "
        "nao apontada.\n"
    )
    return cabecalho + corpo + rodape


#: Quantas tarefas abertas sem horas o relatorio lista antes de resumir o resto.
#: Escolha de desenho, sem verdade externa: errar aqui deixa o relatorio longo
#: ou curto demais, nao errado.
TETO_DE_PARADAS = 15

#: Cabecalho do bloco de leitura. Fixo, para que quem le saiba, sempre no mesmo
#: lugar e com as mesmas palavras, onde termina o numero e comeca a opiniao.
CABECALHO_PRE_ANALISE = "## Leitura do periodo"

RODAPE_PRE_ANALISE = (
    "Esta leitura foi escrita a partir dos numeros acima e de mais nada. "
    "E uma proposta de interpretacao para o Max validar, nao um fato apurado."
)


def com_pre_analise(corpo: str, analise: str) -> str:
    """Monta o reporte com a leitura por cima, marcada como leitura.

    A analise entra ANTES do corpo porque e o que uma pessoa le primeiro, e sai
    entre um cabecalho e um rodape fixos porque a fronteira entre o que foi
    contado e o que foi interpretado nao pode depender de como o texto ficou
    redigido naquele dia.

    Sem analise, devolve o corpo intacto: o reporte continua valendo sozinho, e
    uma falha na etapa de escrita nao pode tirar do ar o item inteiro.
    """
    texto = (analise or "").strip()
    if not texto:
        return corpo
    return (f"{CABECALHO_PRE_ANALISE}\n\n{texto}\n\n"
            f"_{RODAPE_PRE_ANALISE}_\n\n---\n\n{corpo}")


def gerar(cliente, list_id: str, projeto: str, inicio: date, fim: date) -> str:
    """Read the week from ClickUp and render it.

    Dois cuidados que a primeira execucao real, em 08/09/2026, mostrou serem
    necessarios, porque sem eles o reporte de um cliente saiu com 0,0h numa
    semana em que houve trabalho:

    1. **As entradas sao do time.** `entradas()` sem `assignee` devolve as do
       usuario autenticado, que num relatorio de cliente e a pessoa errada por
       definicao. Nomear a equipe bate `assignee=any`, que responde 500 num
       workspace deste tamanho.
    2. **As entradas sao filtradas para esta lista.** A janela devolve o
       workspace inteiro, entao sem filtro as horas de todos os clientes
       entravam no relatorio de um.
    """
    ini_ms, fim_ms = janela(inicio, fim)
    try:
        tarefas = cliente.tarefas_da_lista(list_id)
        try:
            equipe = tuple(str(m["id"]) for m in cliente.membros() if m.get("id"))
        except Exception as e:
            logger.warning("nao foi possivel listar a equipe para %s: %s", projeto, e)
            equipe = None
        todas = cliente.entradas(ini_ms, fim_ms, assignee=equipe)
    except Exception as e:
        logger.warning("nao foi possivel montar o reporte de %s: %s", projeto, e)
        return ""
    ids = {str(t.get("id")) for t in tarefas}
    entradas = [e for e in todas
                if str(campo_objeto(e, "task_location").get("list_id") or "") == str(list_id)
                or str(campo_objeto(e, "task").get("id") or "") in ids]
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

