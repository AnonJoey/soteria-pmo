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

from .periodo import BRT, campo_objeto, de_ms, dias_uteis, janela

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
    "iox": 160.0,
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

# Totais de PROJETO, nao mensais. Ficam separados de proposito: somar um total
# de implantacao junto com um teto mensal de sustentacao daria um alerta que
# dispara no mes errado.
TOTAIS_DE_PROJETO: dict[str, float] = {
    "unimed londrina": 390.0,
    "unimed": 390.0,
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
    "reviver": ("projeto, sem media de bolsao; o Max tem uma previsao mensal de "
                "horas e ficou de mandar o cronograma"),
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
    """

    projeto: str
    list_id: str
    horas_contratadas: float
    space_id: str = ""

    def __post_init__(self) -> None:
        if self.horas_contratadas <= 0:
            raise ValueError(f"bolsao de {self.projeto} sem horas contratadas")
        if not (self.list_id or self.space_id):
            raise ValueError(f"bolsao de {self.projeto} sem lista nem espaco")

    def pertence(self, entrada: dict) -> bool:
        """Se esta entrada de tempo consome este bolsao."""
        onde = campo_objeto(entrada, "task_location")
        if self.space_id:
            return str(onde.get("space_id") or "") == str(self.space_id)
        return str(onde.get("list_id") or "") == str(self.list_id)


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
            if self.fim_do_ciclo and self.data_estouro > self.fim_do_ciclo:
                return f"{base}, no ritmo atual nao estoura ate o fim do mes"
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


def vigiar(cliente, bolsoes: list[Bolsao], inicio: date, fim: date,
           feriados: frozenset[date] = frozenset(),
           sem_teto: list[str] | None = None,
           fim_do_ciclo: date | None = None) -> Vigilancia:
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
        partes.append("  Enquanto o teto nao vier por escrito, estes ficam fora "
                      "da projecao de estouro.")
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
        horas = float(item.get("horas_contratadas") or item.get("horas")
                      or teto_sugerido(nome) or 0.0)
        if not (nome and (lid or sid)):
            continue
        if horas > 0:
            resultado.append(Bolsao(projeto=nome, list_id=lid,
                                    horas_contratadas=horas, space_id=sid))
            continue
        incerto = teto_a_confirmar(nome)
        sem_teto.append(f"{nome}: sem teto configurado"
                        + (f"; {incerto}" if incerto else ""))
    return resultado, sem_teto

