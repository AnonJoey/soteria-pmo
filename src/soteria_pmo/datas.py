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

The one exception is work that is already finished. That is read from the
status TYPE ClickUp assigns, not from the status name, which changes from space
to space ("publicado/finalizado", "Done"). A finished card has no date left to
miss, so listing it as overdue is noise that buries the real ones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from .periodo import de_ms

logger = logging.getLogger("pmo.datas")

# Days out at which a date starts being worth mentioning.
HORIZONTE = 3

# Quantas linhas por grupo o guardiao imprime para um espaco de cliente. Um espaco de
# sustentacao carrega centenas de tarefas abertas, e o digest do dia nao e o lugar
# de listar todas: o corte e dito na ultima linha do grupo, nunca calado.
LIMITE_POR_GRUPO_NO_ESPACO = 15

# Status types ClickUp uses for finished work. `closed` is what this workspace
# returns for "publicado/finalizado"; `done` is the other finished type.
TIPOS_FINALIZADOS = frozenset({"closed", "done"})


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
    parent_id: str | None = None
    dependencias: tuple[str, ...] = ()

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


# "Cancelado" e o unico nome que conta como encerrado sem o tipo dizer. Medido em
# 26/10/2026 no espaco de um cliente: o status `cancelado` vem com type `custom`, como
# `desenvolvimento`, entao o ClickUp o devolve com as abertas, e 19 tarefas canceladas
# apareciam como vencidas ha ate 111 dias. E uma excecao de um nome so, por medida, e
# nao a volta do filtro por nome que o modulo recusa.
STATUS_CANCELADO = frozenset({"cancelado", "cancelada", "cancelled", "canceled"})


def _finalizada(t: dict) -> bool:
    """True when ClickUp itself says the task is finished, or the task was cancelled.

    A payload without a status type is not finished: guessing from the name
    would reintroduce the status filter this module refuses to have. The one
    exception is `STATUS_CANCELADO`, with the measurement that justifies it.
    """
    status = t.get("status")
    if not isinstance(status, dict):
        return False
    if str(status.get("status") or "").strip().lower() in STATUS_CANCELADO:
        return True
    return str(status.get("type") or "").lower() in TIPOS_FINALIZADOS


def ler(tarefas: list[dict]) -> list[Prazo]:
    """Turn ClickUp task payloads into deadlines, leaving finished work out.

    Finished tasks leave every count, the hygiene totals included: a closed
    card without an estimate is history, and nobody can fix it.
    """
    prazos = []
    for t in tarefas:
        if _finalizada(t):
            continue
        vence = de_ms(t.get("due_date"))
        responsaveis = t.get("assignees") or []
        pid = t.get("parent")
        parent_id = str(pid) if pid and str(pid).strip() not in ("None", "null", "") else None
        deps = []
        for dep in t.get("dependencies") or []:
            dep_id = dep.get("depends_on") or dep.get("task_id")
            if dep_id:
                deps.append(str(dep_id))
        prazos.append(Prazo(
            task_id=str(t.get("id")),
            nome=t.get("name") or "(sem nome)",
            responsavel=(responsaveis[0].get("username") if responsaveis else "sem responsavel"),
            vence_em=vence.date() if vence else None,
            status=((t.get("status") or {}).get("status")
                    if isinstance(t.get("status"), dict) else t.get("status")) or "?",
            tem_descricao=bool((t.get("description") or t.get("text_content") or "").strip()),
            tem_estimativa=t.get("time_estimate") not in (None, 0, "0"),
            parent_id=parent_id,
            dependencias=tuple(deps),
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

    # Inversoes de hierarquia (tarefa-mae vencendo antes de subtarefa)
    por_id = {p.task_id: p for p in prazos}
    for p in prazos:
        if p.parent_id and p.parent_id in por_id:
            pai = por_id[p.parent_id]
            if pai.vence_em and p.vence_em and pai.vence_em < p.vence_em:
                problemas.append(
                    f"inversao de datas: tarefa-mae '{pai.nome}' vence em {pai.vence_em:%d/%m}, "
                    f"antes da subtarefa '{p.nome}' ({p.vence_em:%d/%m})"
                )

    return problemas


def _recolher_filhas(grupo: list[Prazo]) -> dict:
    """Subtarefas que vencem no mesmo dia que a tarefa mae, e a mae esta no mesmo grupo.

    Quando um replanejamento inteiro espera aprovacao, cada nivel da arvore vence
    junto, e listar os dezenove esconde o unico que e diferente dos outros. A
    filha some da lista e a raiz diz quantas ela cobre. So se recolhe quando a
    data e identica: uma subtarefa com data propria continua aparecendo.
    """
    por_id = {p.task_id: p for p in grupo}

    def raiz(p: Prazo) -> Prazo:
        atual = p
        while atual.parent_id in por_id and por_id[atual.parent_id].vence_em == p.vence_em:
            atual = por_id[atual.parent_id]
        return atual

    escondidas: set[str] = set()
    por_raiz: dict[str, int] = {}
    for p in grupo:
        r = raiz(p)
        if r.task_id != p.task_id:
            escondidas.add(p.task_id)
            por_raiz[r.task_id] = por_raiz.get(r.task_id, 0) + 1
    return {"escondidas": escondidas, "por_raiz": por_raiz}


def digest(prazos: list[Prazo], hoje: date, incluir_higiene: bool = True,
           limite_por_grupo: int | None = None) -> str:
    """The guardian's message. Empty when there is nothing to say.

    `limite_por_grupo` corta cada grupo (vencidos, hoje, proximos) e diz quantos
    ficaram de fora; sem ele o digest sai inteiro, como sempre saiu."""
    grupos = guardar(prazos, hoje)
    partes: list[str] = []

    for chave, titulo in (("vencido", "Vencidos"),
                          ("vence hoje", "Vencem hoje"),
                          ("proximo", f"Vencem em ate {HORIZONTE} dias")):
        if not grupos[chave]:
            continue
        linhas = []
        filhas = _recolher_filhas(grupos[chave])
        for p in grupos[chave]:
            if p.task_id in filhas["escondidas"]:
                continue
            d = p.dias(hoje)
            quando = (f"ha {-d}d" if d is not None and d < 0
                      else "hoje" if d == 0 else f"em {d}d")
            n = filhas["por_raiz"].get(p.task_id, 0)
            resto = (f", mais {n} subtarefa{'s' if n != 1 else ''} com a mesma data" if n else "")
            linhas.append(f"  {p.nome} ({p.responsavel}, {p.status}) {quando}{resto}")
        if limite_por_grupo is not None and len(linhas) > limite_por_grupo:
            sobra = len(linhas) - limite_por_grupo
            linhas = linhas[:limite_por_grupo] + [f"  ... e mais {sobra}, as menos atrasadas"]
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


def vigiar_espaco(cliente, space_id: str, hoje: date) -> str:
    """O guardiao sobre um espaco inteiro, que e a unidade de um cliente.

    Le so as tarefas abertas e deixa a falha de leitura subir: um espaco que nao
    pode ser lido nao pode virar o mesmo texto vazio de um espaco sem atraso.
    Sem higiene do card: apontar descricao e estimativa faltando em centenas de
    tarefas de cliente seria ruido, e o que se pede aqui sao as datas."""
    tarefas = cliente.tarefas_do_espaco(space_id, incluir_fechadas=False, levantar_erro=True)
    return digest(ler(tarefas), hoje, incluir_higiene=False,
                  limite_por_grupo=LIMITE_POR_GRUPO_NO_ESPACO)


def vigiar_projetos(cliente, projetos: list[dict], hoje: date) -> str:
    """The guardian over every configured project: the lists, and the client spaces.

    Um projeto com `list_id` e lido por essa lista, como sempre. Um projeto so com
    `space_id` e lido pelo espaco inteiro, porque o trabalho de um cliente se
    espalha por dezenas de listas e ler "a lista" do config era ler uma fatia, ou
    nenhuma: com onze projetos no config, so um tinha `list_id` e o resumo do dia
    mostrava as datas de um projeto so (retorno do Max, 26/10/2026). Cliente que
    nao e mais cliente fica de fora, como no bolsao.

    Com uma fonte so a saida e a de `vigiar`; com varias, cada bloco leva o nome do
    projeto, porque o nome de uma tarefa nao diz de quem ela e. Uma lista ou um
    espaco citado duas vezes e lido uma vez. Quem nao pode ser lido e dito no fim,
    nunca omitido: ausencia de alerta e indistinguivel de projeto saudavel.
    """
    from .bolsao import encerrado                    # import local: evita ciclo

    fontes: list[tuple[str, str, str]] = []          # (tipo, nome, id)
    vistas: set[tuple[str, str]] = set()
    for p in projetos:
        nome = p.get("nome") or ""
        lista = str(p.get("list_id") or "").strip()
        espaco = str(p.get("space_id") or "").strip()
        if lista:
            if ("lista", lista) not in vistas:
                vistas.add(("lista", lista))
                fontes.append(("lista", nome or lista, lista))
        elif espaco and ("espaco", espaco) not in vistas and not encerrado(nome):
            vistas.add(("espaco", espaco))
            fontes.append(("espaco", nome or espaco, espaco))
    if not fontes:
        return ""
    if len(fontes) == 1 and fontes[0][0] == "lista":
        return vigiar(cliente, fontes[0][2], hoje)

    blocos: list[str] = []
    falhas: list[str] = []
    for tipo, nome, ident in fontes:
        try:
            texto = (vigiar(cliente, ident, hoje) if tipo == "lista"
                     else vigiar_espaco(cliente, ident, hoje))
        except Exception as e:
            logger.warning("nao foi possivel ler %s: %s", nome, e)
            falhas.append(f"{nome}: {type(e).__name__}: {e}")
            continue
        if texto:
            blocos.append(texto.replace("Guardiao das datas", f"Guardiao das datas, {nome}", 1))
    if falhas:
        blocos.append("Guardiao das datas, projetos que nao puderam ser lidos e por isso nao foram avaliados:\n"
                      + "\n".join(f"  {f}" for f in falhas))
    return "\n\n".join(blocos)
