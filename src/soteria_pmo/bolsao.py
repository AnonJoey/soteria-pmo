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
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .periodo import campo_objeto, dias_uteis, janela

logger = logging.getLogger("pmo.bolsao")

# Where the alerts step up. Below the first threshold the watch stays quiet:
# an alert on every run is an alert nobody reads.
FAIXAS = ((1.00, "estourado"), (0.90, "critico"), (0.75, "atencao"))

# Tetos mensais de sustentacao, confirmados pelo cliente interno na reuniao de
# homologacao de 08/09/2026. Substituem a lista parcial de 03/09, que vinha de
# uma conversa e trazia so os numeros ditos com firmeza.
#
# So entra aqui numero dito de forma inequivoca. O que ficou incerto vai para
# TETOS_A_CONFIRMAR e nao vira teto: um teto errado nao levanta erro, so move a
# faixa de alerta, e a projecao de estouro sai confiante sobre um numero
# inventado. Sem teto o vigia diz que nao tem teto, que e verdade.
TETOS_DE_REFERENCIA: dict[str, float] = {
    "china gate": 100.0,
    "chinagate": 100.0,
    "yoshii": 160.0,
    "yoshi": 160.0,
    "apet": 60.0,
    "grupo dimas": 30.0,
    "dimas": 30.0,
    "angelus": 160.0,
    "gazin": 40.0,
    "bm2": 100.0,
    "grupo bm2": 100.0,
}

# Tetos mensais de sustentacao, confirmados pelo Max na reuniao de homologacao
# de 08/09/2026. Substituem a lista parcial que vinha da conversa de 03/09.
#
# O Angelus entrou aqui por correcao ao vivo: o Max disse 100 e o Andre corrigiu
# para 160 de sustentacao, "o resto e projeto". O valor de 100.0 que este arquivo
# carregou ate 08/09 sob a chave errada "grupo anjos" era um meio-termo entre 75
# e 150 que ninguem disse, e "Grupo Anjos" nao existe no workspace: a transcricao
# automatica moeu "Angelus".
#
# O Max falou "a PET" em 08/09 e o cliente do workspace se chama APET. Nao ha
# cliente chamado PET: sao o mesmo, confirmado em 09/09. A chave e "apet", e a
# busca por palavra inteira e o que impede "pet" de casar dentro de outro nome.
#
# BM2 nao tem bolsao contratado. Os 100.0 sao o numero base que o Max pediu para
# usar como gatilho, porque "se passar de 100 horas e poucas, certamente o
# William vai chiar". Um gatilho sem contrato ainda e melhor que silencio.
# O Abner confirmou em 14/10/2026: "100h e uma media, nao necessariamente o
# limite. Mas e bom sermos alertados quando passamos de 100h".
#
# Conferidos pelo Abner em 14/10/2026: Angelus 160, China Gate 100 (sustentacao),
# A.Yoshii, Apet e Dimas como estao aqui. O Gazin ele nao conhece: a informacao
# de 40h veio do Max ou do Andre, e segue sem segunda confirmacao.

# Totais de PROJETO, nao mensais. Ficam separados de proposito: somar um total
# de implantacao junto com um teto mensal de sustentacao daria um alerta que
# dispara no mes errado.
#
# Esta tabela e o ULTIMO recurso. O previsto de um projeto mora no ClickUp, nas
# estimativas das tarefas, e e la que `apurar_total` o le primeiro. O Abner
# confirmou em 14/10/2026 que Reviver e Unimed nao tem teto mensal e que o
# acompanhamento e pelo total do projeto.
#
# O Max confirmou em 21/10/2026 os totais oficiais: Unimed 390 h e Reviver 2.950 h.
# O Reviver NAO e a soma das estimativas das nove fases no ClickUp (3.510 h): o
# oficial vale, e `horas_totais` no config tem a mesma precedencia que esta tabela.
TOTAIS_DE_PROJETO: dict[str, float] = {
    "unimed londrina": 390.0,
    "unimed": 390.0,
    "concessionaria reviver": 2950.0,
    "reviver": 2950.0,
}

# Clientes que sairam. Guardado em vez de apagado: um projeto que reaparece num
# extrato antigo deve ser reconhecido como encerrado, nao como desconhecido.
NAO_MAIS_CLIENTE: frozenset[str] = frozenset({"conta azul", "contaazul"})

# Citados sem numero fechado. Nao viram teto: existem para que o vigia diga
# "ha uma referencia nao confirmada" em vez de calar sobre um cliente citado.
#
# O Angelus saiu daqui em 08/09: o Max e o Andre fecharam 160h de sustentacao
# na reuniao, e o valor foi para TETOS_DE_REFERENCIA.
TETOS_A_CONFIRMAR: dict[str, str] = {
    "reviver": ("projeto, sem teto mensal (o Abner confirmou em 14/10/2026); "
                "acompanha-se pelo total de horas: ponha em `listas_total` a lista "
                "do projeto para o vigia ler o previsto e o lancado"),
}


#: Chaves curtas casariam dentro de outra palavra num nome de projeto. "pet"
#: dentro de "competencia" daria um teto de 60h a um cliente que nunca teve um.
#: Por isso a busca e por palavra inteira, e nao por substring.
_SEPARADOR = re.compile(r"[^a-z0-9]+")


def _palavras(texto: str) -> set[str]:
    return {t for t in _SEPARADOR.split((texto or "").strip().lower()) if t}


def _casa(chave: str, projeto: str) -> bool:
    """Se a chave aparece no nome do projeto como palavra (ou sequencia delas)."""
    alvo = _palavras(projeto)
    return _palavras(chave).issubset(alvo) if alvo else False


def teto_sugerido(projeto: str) -> float | None:
    """Benchmark monthly hours for the clients stated firmly, or None.

    None is the honest answer for a client whose ceiling was never fixed, and
    the caller turns it into "no ceiling configured" instead of a projection
    against a number nobody gave.
    """
    for k, v in TETOS_DE_REFERENCIA.items():
        if _casa(k, projeto):
            return v
    return None


def total_de_projeto(projeto: str) -> float | None:
    """Total de horas de um projeto de implantacao, quando ha um.

    Separado de `teto_sugerido` porque a unidade e outra: um total de projeto
    nao reseta na virada do mes, e compara-lo com o consumo mensal produziria
    um alerta que nunca dispara ou que dispara sempre.
    """
    for k, v in TOTAIS_DE_PROJETO.items():
        if _casa(k, projeto):
            return v
    return None


def encerrado(projeto: str) -> bool:
    """Se este projeto e de um cliente que nao e mais cliente."""
    return any(_casa(k, projeto) for k in NAO_MAIS_CLIENTE)


def teto_a_confirmar(projeto: str) -> str | None:
    """What is known but unconfirmed about this client's ceiling, if anything."""
    for k, v in TETOS_A_CONFIRMAR.items():
        if _casa(k, projeto):
            return v
    return None


@dataclass(frozen=True)
class Bolsao:
    """As horas contratadas de um cliente, e onde o consumo delas mora.

    `space_id` existe porque a unidade errada era a lista. Medido no workspace
    em 08/09/2026: o trabalho de um cliente se espalha por dezenas de listas
    dentro do espaco dele, o China Gate tem 42 sprints mais chamados,
    sustentacao e oito cronogramas. Casar o consumo por uma lista so mede uma
    fatia e chama de bolsao. A entrada de tempo carrega
    `task_location.space_id`, entao o espaco e uma chave que existe no dado.

    Quando os dois estao presentes o espaco vence, e `list_id` sozinho continua
    servindo para vigiar uma frente especifica de propositode.

    `listas_projeto` e `listas_sustentacao` permitem segregar na raiz o que sao
    horas de projeto vs. sustentacao em espacos que abrigam ambos (ex.: Grupo
    Angelus tem 160h de sustentacao, com projetos correndo no mesmo espaco).
    """

    projeto: str
    list_id: str
    horas_contratadas: float
    space_id: str = ""
    listas_sustentacao: tuple[str, ...] = ()
    listas_projeto: tuple[str, ...] = ()
    tipo: str = "sustentacao"

    def __post_init__(self) -> None:
        if self.horas_contratadas <= 0:
            raise ValueError(f"bolsao de {self.projeto} sem horas contratadas")
        if not (self.list_id or self.space_id):
            raise ValueError(f"bolsao de {self.projeto} sem lista nem espaco")

    def pertence(self, entrada: dict) -> bool:
        """Se esta entrada de tempo consome este bolsao."""
        onde = campo_objeto(entrada, "task_location")
        lid = str(onde.get("list_id") or "")
        sid = str(onde.get("space_id") or "")
        if self.space_id:
            if sid != str(self.space_id):
                return False
        elif self.list_id:
            if lid != str(self.list_id):
                return False
        else:
            return False

        if self.listas_projeto and lid in self.listas_projeto:
            return False
        if self.listas_sustentacao and lid not in self.listas_sustentacao:
            return False
        return True


@dataclass(frozen=True)
class TotalProjeto:
    """Um projeto que se acompanha pelo TOTAL de horas, nao por teto mensal.

    O Abner explicou em 14/10/2026 que Reviver e Unimed nao tem limite mensal:
    o projeto, como um todo, tem uma quantidade de horas previstas, e o que
    ajuda e vigiar a porcentagem consumida desse total.

    `listas` e quem manda no que e "o projeto": as listas do ClickUp cujas
    tarefas carregam o previsto e o lancado. Nao se usa o espaco inteiro porque
    ele mistura frentes. Medido em 15/10/2026 no espaco do Reviver: o espaco
    todo soma bem mais horas lancadas que a lista do projeto, e so a
    soma da lista bate com o numero que o Abner le na tela.

    `horas_previstas` vazio quer dizer "ler das estimativas das tarefas".
    """

    projeto: str
    listas: tuple[str, ...]
    horas_previstas: float | None = None

    def __post_init__(self) -> None:
        if not self.listas:
            raise ValueError(f"total de {self.projeto} sem lista do projeto")
        if self.horas_previstas is not None and self.horas_previstas <= 0:
            raise ValueError(f"total de {self.projeto} com horas previstas nao positivas")


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
    #: Projetos citados no config sem teto contra o que medir, com o motivo.
    #: Mesma razao de `falhas`: sumir do digest e parecer saudavel.
    sem_teto: list[str] = field(default_factory=list)


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
    #: Ultimo dia do ciclo a que o teto se refere. Os tetos que o Abner passou
    #: em 03/09 sao MENSAIS, e um teto mensal so quer dizer alguma coisa
    #: comparado com o consumo do proprio mes. Sem isto, uma projecao pode
    #: apontar estouro para depois da virada, quando o bolsao ja resetou.
    fim_do_ciclo: date | None = None
    #: "mes" (teto mensal, o caso de sempre) ou "total" (total de horas de um
    #: projeto inteiro, sem janela e sem projecao de data).
    escopo: str = "mes"
    #: De onde veio o previsto de um total: soma das estimativas das tarefas,
    #: `horas_totais` do config ou a tabela de referencia.
    origem_previsto: str = ""

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
        if self.escopo == "total":
            return self._linha_total()
        base = (f"{self.projeto}: {self.horas_gastas:.1f}h de "
                f"{self.horas_contratadas:.0f}h ({self.percentual:.0%}) [{self.nivel}]")
        # Quem ja passou do teto nao "estoura em" data nenhuma: a data que a
        # projecao daria e o proprio dia da leitura, e dizer "estoura em 13/10"
        # de um bolsao a 280% faz parecer que ainda ha o que evitar.
        if self.horas_gastas > self.horas_contratadas:
            acima = self.horas_gastas - self.horas_contratadas
            return f"{base}, ja passou do teto em {acima:.1f}h"
        if self.horas_gastas == self.horas_contratadas:
            return f"{base}, no teto exato"
        if self.data_estouro is not None:
            if self.fim_do_ciclo and self.data_estouro > self.fim_do_ciclo:
                return f"{base}, no ritmo atual nao estoura ate o fim do mes"
            return f"{base}, no ritmo atual estoura em {self.data_estouro:%d/%m}"
        if self.ritmo_diario is None:
            return f"{base}, sem ritmo medido ainda"
        return f"{base}, nao estoura no horizonte medido"


    def _linha_total(self) -> str:
        """Total de um projeto: sem data de estouro. Um previsto de milhares de
        horas, a um ritmo mensal, daria uma data de anos adiante escrita como
        dia e mes, e isso se leria como prazo."""
        base = (f"{self.projeto} (total do projeto): {self.horas_gastas:.1f}h de "
                f"{self.horas_contratadas:.0f}h previstas ({self.percentual:.0%}) [{self.nivel}]")
        if self.horas_gastas > self.horas_contratadas:
            return f"{base}, ja passou do previsto em {self.horas_gastas - self.horas_contratadas:.1f}h"
        if self.origem_previsto:
            return f"{base}; previsto: {self.origem_previsto}"
        return base


def _nivel(percentual: float) -> str:
    for limite, nome in FAIXAS:
        if percentual >= limite:
            return nome
    return "ok"


def apurar(entradas: list[dict], bolsao: Bolsao, inicio: date, fim: date,
           feriados: frozenset[date] = frozenset(),
           minimo_para_projetar: int = 5,
           fim_do_ciclo: date | None = None) -> Situacao:
    """Turn raw time entries into a budget position.

    `minimo_para_projetar` is the number of observed business days below which
    no exhaustion date is produced. Five is one working week: projecting from
    less than that turns a slow Monday into a deadline.

    **A janela tem que ser a do proprio teto.** Os tetos passados pelo Abner em
    03/09 sao mensais, e a rotina media trinta dias corridos, que atravessam a
    virada do mes. Medido em 08/09/2026: o China Gate saiu como 206,4h de 100h,
    "estourado", quando no proprio mes tinha usado 32,8h de 100h. Dois clientes
    apareceram estourados sem estarem, que e o alarme falso que este modulo
    inteiro argumenta contra.
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
        fim_do_ciclo=fim_do_ciclo,
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


def apurar_total(tarefas: list[dict], total: TotalProjeto) -> Situacao | None:
    """O total de um projeto, lido das tarefas dele no ClickUp.

    Soma `time_estimate` (o previsto) e `time_spent` (o lancado) das tarefas e
    das subtarefas, uma vez cada: uma tarefa que mora em duas listas entra uma
    vez so. Medido em 15/10/2026 numa lista de projeto do Reviver: a soma
    das estimativas e a soma do tempo lancado bateram, as duas, ao minuto, com os
    numeros que o Abner leu na tela em 14/10. O `time_spent` da API e o da propria
    tarefa, nao o das subtarefas somado, senao a soma contaria duas vezes.

    O previsto vem, nesta ordem, de `horas_previstas` do config, da tabela de
    referencia (o total oficial que o Max confirmou em 21/10/2026: Unimed 390 h e
    Reviver 2.950 h) e da soma das estimativas. A tabela vem antes das estimativas
    de proposito: o total oficial do Reviver (2.950 h) nao e a soma das nove fases
    no ClickUp (3.510 h), e o vigia da maquina do Max nao tem `horas_totais` no
    config. Devolve None quando nenhum dos tres existe: sem previsto nao ha contra
    o que medir, e o chamador diz isso.

    Nao projeta data de estouro: ver `Situacao._linha_total`.
    """
    por_id: dict[str, dict] = {}
    for tarefa in tarefas:
        if tarefa.get("id"):
            por_id[str(tarefa["id"])] = tarefa
    lancado = sum(int(t.get("time_spent") or 0) for t in por_id.values()) / 3_600_000
    estimado = sum(int(t.get("time_estimate") or 0) for t in por_id.values()) / 3_600_000

    if total.horas_previstas:
        previsto, origem = total.horas_previstas, "horas_totais do config"
    elif (ref := total_de_projeto(total.projeto)):
        previsto, origem = ref, "tabela de referencia (total oficial confirmado pelo Max em 21/10/2026)"
    elif estimado > 0:
        previsto, origem = estimado, "soma das estimativas das tarefas no ClickUp"
    else:
        return None
    return Situacao(
        projeto=total.projeto, horas_contratadas=previsto, horas_gastas=lancado,
        faturaveis=0.0, nao_faturaveis=0.0,  # `time_spent` nao separa
        nivel=_nivel(lancado / previsto), dias_uteis_observados=0, ritmo_diario=None,
        data_estouro=None, dias_ate_estourar=None, escopo="total", origem_previsto=origem)


def vigiar(cliente, bolsoes: list[Bolsao], inicio: date, fim: date,
           feriados: frozenset[date] = frozenset(),
           sem_teto: list[str] | None = None,
           fim_do_ciclo: date | None = None,
           totais: list[TotalProjeto] | None = None) -> Vigilancia:
    """Read the window once per project and report each position.

    Entries are fetched per project list rather than for the whole workspace
    because a time entry names its task, and mapping tasks back to projects
    workspace-wide costs one call per task.
    """
    ini_ms, fim_ms = janela(inicio, fim)
    v = Vigilancia(sem_teto=list(sem_teto or ()))
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
        do_projeto = [e for e in todas if b.pertence(e)]
        v.situacoes.append(apurar(do_projeto, b, inicio, fim, feriados,
                                  fim_do_ciclo=fim_do_ciclo))
    for tp in totais or ():
        # Uma falha de leitura sai nomeada, como no caso mensal: projeto que some
        # do digest e indistinguivel de projeto saudavel.
        try:
            tarefas: list[dict] = []
            for lista in tp.listas:
                tarefas.extend(cliente.tarefas_da_lista(lista, incluir_fechadas=True,
                                                        subtarefas=True))
            situacao = apurar_total(tarefas, tp)
        except Exception as e:
            logger.warning("nao foi possivel ler o total de %s: %s", tp.projeto, e)
            v.falhas.append(f"{tp.projeto} (total do projeto): {type(e).__name__}: {e}")
            continue
        if situacao is None:
            v.sem_teto.append(f"{tp.projeto}: total do projeto sem previsto; as tarefas das "
                              f"listas configuradas nao tem estimativa e o config nao "
                              f"traz `horas_totais`")
            continue
        v.situacoes.append(situacao)
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
        sem_teto = list(vigilancia.sem_teto)
    else:
        situacoes, falhas, sem_teto = list(vigilancia), [], []

    linhas = [s.linha() for s in sorted(situacoes, key=lambda s: -s.percentual)
              if s.alerta or not so_alertas]
    if not linhas and not falhas and not sem_teto:
        return ""
    partes = ["Vigia de bolsao"]
    partes.extend(f"  {l}" for l in linhas)
    if falhas:
        partes.append("  Nao foi possivel ler:")
        partes.extend(f"    {f}" for f in falhas)
        partes.append("  Estes projetos estao sem vigia hoje, o que nao quer dizer "
                      "que estejam bem.")
    if sem_teto:
        partes.append("  Sem teto para medir contra:")
        partes.extend(f"    {t}" for t in sem_teto)
        # Cada linha carrega o proprio motivo, porque os motivos passaram a ser
        # diferentes: um cliente encerrado nao esta esperando teto nenhum.
        partes.append("  Estes ficam fora da projecao de estouro, pela razao "
                      "dita em cada linha.")
    return "\n".join(partes)


def carregar_bolsoes(dados: list[dict] | dict) -> tuple[list[Bolsao], list[str]]:
    """Os bolsoes que dao para vigiar, e os que ficaram de fora com o motivo.

    Um projeto sem teto nao pode ser vigiado, porque nao ha contra o que medir
    o consumo. Ate 08/09/2026 ele era simplesmente descartado aqui, e um
    projeto ausente do digest e indistinguivel de um projeto saudavel. Agora
    sai nomeado, com a razao, pelo mesmo motivo que uma leitura que falhou sai:
    ausencia de alerta nao e boa noticia, e falta de noticia.
    """
    itens = dados.get("bolsoes", []) if isinstance(dados, dict) else dados
    resultado: list[Bolsao] = []
    sem_teto: list[str] = []
    for item in itens:
        nome = item.get("projeto") or item.get("nome") or ""
        lid = str(item.get("list_id") or "")
        sid = str(item.get("space_id") or "")
        tipo = str(item.get("tipo") or "sustentacao")
        listas_sust = tuple(str(x) for x in (item.get("listas_sustentacao") or ()))
        listas_proj = tuple(str(x) for x in (item.get("listas_projeto") or ()))
        horas = float(item.get("horas_contratadas") or item.get("horas")
                      or teto_sugerido(nome) or 0.0)
        if not (nome and (lid or sid)):
            continue
        # Cliente encerrado sai antes do teto, e nao depois. `encerrado()` e
        # `NAO_MAIS_CLIENTE` existiam desde 08/09/2026 e nunca eram
        # consultados aqui: a Conta Azul, que o Max declarou encerrada naquela
        # reuniao, aparecia no digest como "sem teto configurado", que e o
        # sistema pedindo ao Max um numero que ele ja disse nao existir mais.
        # Sai nomeado, e nao calado, pela razao do docstring: projeto ausente
        # do digest e indistinguivel de projeto saudavel.
        if encerrado(nome):
            sem_teto.append(f"{nome}: encerrado como cliente, fora da vigia; "
                            f"nao ha teto a confirmar")
            continue
        if horas > 0:
            resultado.append(Bolsao(projeto=nome, list_id=lid,
                                    horas_contratadas=horas, space_id=sid,
                                    listas_sustentacao=listas_sust,
                                    listas_projeto=listas_proj,
                                    tipo=tipo))
            continue
        if item.get("listas_total"):
            continue  # acompanhado pelo total do projeto: ver carregar_totais
        incerto = teto_a_confirmar(nome)
        total_ref = total_de_projeto(nome)
        if total_ref and not incerto:
            incerto = (f"total do projeto de {total_ref:.0f}h (tabela de referencia), "
                       f"mas sem `listas_total` no config: nao ha de onde ler o lancado")
        sem_teto.append(f"{nome}: sem teto configurado"
                        + (f"; {incerto}" if incerto else ""))
    return resultado, sem_teto


def carregar_totais(dados: list[dict] | dict) -> list[TotalProjeto]:
    """Os projetos do config que se acompanham pelo total de horas.

    Entra quem traz `listas_total` (as listas do ClickUp que formam o projeto) e
    nao tem teto mensal. `horas_totais` e opcional: sem ele o previsto e a soma
    das estimativas das tarefas. Um projeto com as duas coisas, teto mensal e
    lista de total, e vigiado nas duas; so entra aqui o que declara a lista.
    """
    itens = dados.get("bolsoes", []) if isinstance(dados, dict) else dados
    resultado: list[TotalProjeto] = []
    for item in itens:
        nome = item.get("projeto") or item.get("nome") or ""
        listas = tuple(str(x) for x in (item.get("listas_total") or ()))
        if not (nome and listas) or encerrado(nome):
            continue
        bruto = item.get("horas_totais")
        try:
            previstas = float(bruto) if bruto else None
        except (TypeError, ValueError):
            previstas = None
        if previstas is not None and previstas <= 0:
            previstas = None
        if bruto and previstas is None:
            # Config torto nao derruba a rotina inteira, mas tambem nao passa calado:
            # o previsto cai para a soma das estimativas, e o digest diz de onde veio.
            logger.warning("horas_totais invalido para %s (%r): o previsto vem das estimativas", nome, bruto)
        resultado.append(TotalProjeto(projeto=nome, listas=listas, horas_previstas=previstas))
    return resultado

