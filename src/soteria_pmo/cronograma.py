"""Item 2: schedule follow-up.

Watches whether work is moving and raises escalating alerts when it is not.
Two constraints from the meetings shape it, and both are about not crying wolf.

The first is the ruler, and it changed once. The module was built around a
**per-person cadence**, on the reasoning that a single ruler marks as abandoned
a task that is simply following another pace. Asked to calibrate it on
03/09/2026, Abner said he cannot pin down how many days each dev goes without
touching a task, and that individualising it would cause trouble. What he
agreed instead is a ruler **by type of work**: four business days without
logged hours for an implementation project, two for support and tickets, with
the alert raised **per project rather than per task**, because a developer
moving between tasks of the same project is not a stalled project.

The per-person path was deleted on 08/09/2026 rather than left beside the new
one. It had survived four days after being rejected, still printing "confirm
this person's rhythm with Abner" in real runs, which is what keeping both costs.

The second constraint is that this agent cannot tell "the project stopped" from
"the project moved and nobody logged it". Both look like silence in ClickUp.
Every alert therefore states the ambiguity it could not resolve instead of
picking the accusatory reading, because an alert that says "abandoned" about
someone who was working is the fastest way to get the whole system turned off.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from .clickup import bloqueada, concluida
from .periodo import campo_objeto, de_ms, dias_uteis

logger = logging.getLogger("pmo.cronograma")

# Escalada, em MULTIPLOS da regua do tipo de trabalho. Niveis em vez de um
# limite so para que o primeiro toque seja barato e a escalada seja rara.
# Escolha de desenho, sem verdade externa: o Abner acordou a regua, nao a
# escalada. Errar aqui produz alerta cedo ou tarde demais, nao numero errado.
MULTIPLOS = ((3.0, "escalar"), (2.0, "cobranca"), (1.0, "lembrete"))

# Regua acordada com Abner em 03/09/2026 por tipo de trabalho:
# - Projetos de implantacao: 4 dias uteis sem lancamento de horas
# - Chamados / sustentacao: 2 dias uteis sem lancamento de horas
REGUA_PROJETO_DIAS = 4
REGUA_CHAMADO_DIAS = 2

TIPO_PROJETO = "projeto"
TIPO_CHAMADO = "chamado"

# ── Acompanhamento por projeto, a regra acordada em 03/09/2026 com o Abner ──


@dataclass
class DivergenciaProjeto:
    """A project or ticket queue that has gone quiet without logged hours."""

    projeto: str
    list_id: str
    tipo: str  # "projeto" ou "chamado"
    regua_dias: int
    dias_sem_horas: int
    horas_no_periodo: float
    tarefas_em_desenvolvimento: int
    tarefas_bloqueadas: int
    tarefas_concluidas: int
    responsaveis: list[str] = field(default_factory=list)
    ambiguidade: str = (
        "o projeto ficou sem horas apontadas no periodo; isso pode ser trabalho "
        "que nao andou ou trabalho que andou e nao foi apontado, e este agente "
        "nao consegue separar os dois"
    )
    notas: list[str] = field(default_factory=list)

    @property
    def precisa_de_alerta(self) -> bool:
        return self.dias_sem_horas >= self.regua_dias and self.tarefas_em_desenvolvimento > 0

    @property
    def nivel(self) -> str:
        """Lembrete, cobranca ou escalar, contado em multiplos da regua.

        A regua tem fonte, o Abner em 03/09. A escalada nao tem, e por isso e
        multiplo dela em vez de dias soltos: mudar a regua leva a escalada
        junto, e nao sobra um numero de tres dias que ninguem sabe de onde veio.
        """
        razao = self.dias_sem_horas / max(self.regua_dias, 1)
        for corte, nome in MULTIPLOS:
            if razao >= corte:
                return nome
        return "lembrete"

    def linha(self) -> str:
        resp = f" ({', '.join(self.responsaveis)})" if self.responsaveis else ""
        return (
            f"[{self.nivel}] {self.projeto}{resp} ({self.tipo}): "
            f"{self.dias_sem_horas} dias uteis sem horas apontadas "
            f"(limite: {self.regua_dias}d, "
            f"{self.tarefas_em_desenvolvimento} tarefas em andamento)"
        )


def avaliar_projeto(
    projeto: str,
    list_id: str,
    tarefas: list[dict],
    entradas: list[dict],
    tipo: str = TIPO_PROJETO,
    hoje: date | None = None,
    feriados: frozenset[date] = frozenset(),
    inicio: date | None = None,
) -> DivergenciaProjeto | None:
    """Evaluate a project as a whole against the 4-day / 2-day work type ruler.

    Agreed on 03/09/2026: a developer switching tasks within the same project is
    not a stalled project. The concrete signal is **absence of hours logged**
    against the project in the period.

    `inicio` is the start of the window the entries came from, and it exists
    because of a false negative measured against the real workspace on
    08/09/2026. With no entries at all, the silence used to be counted from the
    most recent task update, so a project with zero hours logged in thirty days
    stayed quiet as long as somebody edited a card. That is the opposite of the
    agreed signal, and it hid a real case: the audit was reporting 63,4h of
    evidenced work with nothing logged while this item said nothing.

    So no entries means the silence spans the whole window. The one exception
    is a project too young to judge: if every open task was created within the
    ruler, there has not been time to log anything yet, and it stays quiet.
    """
    if hoje is None:
        hoje = date.today()
    regua = REGUA_CHAMADO_DIAS if tipo == TIPO_CHAMADO else REGUA_PROJETO_DIAS

    em_dev = 0
    bloq = 0
    conc = 0
    sem_estimativa = 0
    responsaveis_set = set()

    for t in tarefas:
        st = t.get("status")
        if concluida(st):
            conc += 1
            continue
        if bloqueada(st):
            bloq += 1
            continue
        # Toda tarefa aberta e ativa conta como em andamento, esteja o status
        # nomeado como desenvolvimento ou nao.
        em_dev += 1
        if not t.get("time_estimate"):
            sem_estimativa += 1
        for a in t.get("assignees") or []:
            if a.get("username"):
                responsaveis_set.add(a["username"])

    if em_dev == 0:
        return None

    # Encontrar a data da entrada mais recente
    datas_entradas: list[date] = []
    total_horas = 0.0
    for e in entradas:
        dur_ms = int(e.get("duration") or 0)
        total_horas += dur_ms / 3_600_000
        start = de_ms(e.get("start"))
        if start:
            datas_entradas.append(start.date())

    nota_de_janela = ""
    if datas_entradas:
        mais_recente = max(datas_entradas)
        silencio = max(dias_uteis(mais_recente, hoje, feriados) - 1, 0)
    else:
        # Projeto novo demais para julgar: nenhuma tarefa aberta e mais velha
        # que a propria regua, entao nao houve tempo de lancar nada.
        criacoes = [d for d in (de_ms(t.get("date_created")) for t in tarefas
                                if not concluida(t.get("status"))
                                and not bloqueada(t.get("status"))) if d]
        if criacoes:
            idade = max(dias_uteis(min(c.date() for c in criacoes), hoje, feriados) - 1, 0)
            if idade < regua:
                return None
        # Duas medidas do mesmo silencio, e vale a maior. A janela e a do sinal
        # acordado, horas lancadas, e so existe quando o chamador diz de onde
        # as entradas vieram. A data de toque das tarefas e o proxy que sobra
        # quando ela nao existe, e por si so mascarava o caso de trinta dias
        # sem hora nenhuma com um card editado ontem.
        candidatos: list[int] = []
        if inicio:
            candidatos.append(max(dias_uteis(inicio, hoje, feriados) - 1, 0))
            nota_de_janela = (
                f"nenhuma hora lancada no projeto na janela lida, de "
                f"{inicio:%d/%m} a {hoje:%d/%m}")
        toques = [d for d in (de_ms(t.get("date_updated")) or de_ms(t.get("date_created"))
                              for t in tarefas
                              if not concluida(t.get("status"))
                              and not bloqueada(t.get("status"))) if d]
        if toques:
            candidatos.append(max(dias_uteis(max(t.date() for t in toques),
                                             hoje, feriados) - 1, 0))
        silencio = max(candidatos) if candidatos else regua

    divergencia = DivergenciaProjeto(
        projeto=projeto,
        list_id=list_id,
        tipo=tipo,
        regua_dias=regua,
        dias_sem_horas=silencio,
        horas_no_periodo=round(total_horas, 2),
        tarefas_em_desenvolvimento=em_dev,
        tarefas_bloqueadas=bloq,
        tarefas_concluidas=conc,
        responsaveis=sorted(responsaveis_set),
    )

    if nota_de_janela:
        divergencia.notas.append(nota_de_janela)
    if bloq > 0:
        divergencia.notas.append(f"{bloq} tarefas bloqueadas aguardando resolucao externa")
    if sem_estimativa:
        divergencia.notas.append(
            f"{sem_estimativa} das {em_dev} tarefas em andamento estao sem estimativa: "
            "nao da para dizer se o silencio e compativel com o tamanho do trabalho")

    return divergencia if divergencia.precisa_de_alerta else None


def log_de_divergencias_projetos(divergencias: list[DivergenciaProjeto], hoje: date) -> str:
    """Format project-level divergences into a digest."""
    if not divergencias:
        return ""
    linhas = [f"Acompanhamento de cronograma por projeto, {hoje:%d/%m}", ""]
    for d in divergencias:
        linhas.append(f"  {d.linha()}")
        for n in d.notas:
            linhas.append(f"      {n}")
    linhas.append("")
    linhas.append(f"  Leitura: {divergencias[0].ambiguidade}.")
    return "\n".join(linhas)



def acompanhar_projetos(cliente, projetos: list[dict], hoje: date,
                        feriados: frozenset[date] = frozenset(),
                        janela_dias: int = 30) -> str:
    """A porta do item 2: le cada projeto e devolve o log das divergencias.

    Le a equipe uma vez e as entradas de tempo por projeto, porque uma entrada
    nomeia a sua tarefa e mapear tarefa para projeto no workspace inteiro custa
    uma chamada por tarefa. E o mesmo caminho que `bolsao.vigiar` ja usa, pela
    mesma razao, incluindo nomear a equipe em vez de pedir `assignee=any`, que
    responde 500 num workspace deste tamanho.

    Um projeto que nao pode ser lido nao derruba os outros e tambem nao some em
    silencio: ausencia de alerta e indistinguivel de projeto saudavel, entao a
    falha e dita no proprio log.
    """
    if not projetos:
        return ""

    inicio = hoje - timedelta(days=janela_dias)
    from .periodo import janela as _janela          # import local: evita ciclo
    ini_ms, fim_ms = _janela(inicio, hoje)

    try:
        equipe = tuple(str(m["id"]) for m in cliente.membros() if m.get("id"))
    except Exception as e:
        logger.warning("nao foi possivel listar a equipe: %s", e)
        equipe = None

    divergencias: list[DivergenciaProjeto] = []
    falhas: list[str] = []

    for proj in projetos:
        nome = proj.get("nome") or proj.get("list_id", "")
        list_id = proj.get("list_id")
        if not list_id:
            continue
        tipo = proj.get("tipo") or TIPO_PROJETO
        try:
            tarefas = cliente.tarefas_da_lista(list_id)
            todas = cliente.entradas(ini_ms, fim_ms, assignee=equipe)
        except Exception as e:
            logger.warning("nao foi possivel ler %s: %s", nome, e)
            falhas.append(f"{nome}: {type(e).__name__}: {e}")
            continue
        do_projeto = [e for e in todas
                      if campo_objeto(e, "task_location").get("list_id") == list_id]
        d = avaliar_projeto(nome, list_id, tarefas, do_projeto,
                            tipo=tipo, hoje=hoje, feriados=feriados, inicio=inicio)
        if d:
            divergencias.append(d)

    ordem = {"escalar": 0, "cobranca": 1, "lembrete": 2}
    divergencias.sort(key=lambda d: (ordem[d.nivel], -d.dias_sem_horas))

    log = log_de_divergencias_projetos(divergencias, hoje)
    if falhas:
        aviso = ["", "  Projetos que nao puderam ser lidos, e por isso nao foram avaliados:"]
        aviso += [f"      {f}" for f in falhas]
        log = (log or f"Acompanhamento de cronograma por projeto, {hoje:%d/%m}") + "\n".join(aviso)
    return log
