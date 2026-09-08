"""Item 4: the hours engine.

This is the item with a measured track record, and the measurement is the whole
design. Reconstructing what one person did from machine evidence captured 39,1h
of 130,1h in the first cycle and 54h of 89,5h in the second. Days 04 and 05/08
came back as ZERO, with no commit, no session and no note, and they were normal
working days of planning and research.

So the engine is built to ASK, not to report a total. A day with no evidence
produces a question, never a zero, because those are the same shape in the data
and opposite in meaning. `Apuracao.cobertura` is always populated and the
renderer always prints it: a total presented without its coverage is the failure
mode this module exists to prevent, and it is a comfortable one, because the
number looks right.

The model appears in exactly one place: reading a transcript and saying what
work a sentence describes. Everything else, windows, sums, dating, billability,
description format, is deterministic. `Interprete` is a protocol so the tests
and the dry runs never need a GPU.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Protocol

from .clickup import (ATIVIDADE_NAO_FATURAVEL, NAO_FATURAVEL,
                      Aprovacao, Lancamento)
from .periodo import BRT, Intervalo, data_da_fala, fundir, horas as somar_horas, ms

logger = logging.getLogger("pmo.horas")

# What the description says when nothing named the activity. Deliberately not
# a guess: it is the row label in the billable hours report.
ATIVIDADE_DESCONHECIDA = "ATIVIDADE NAO IDENTIFICADA"

# Below this, a proposal is never written without a person looking at it first.
# Above it, it still is not written without approval: the threshold decides how
# loudly the proposal argues for itself, not whether a human is in the loop.
CONFIANCA_MINIMA = 0.5

# Evidence kinds, ranked by how well each supports a DURATION, which is what
# the confidence score is about and what ends up billed.
#
# These were first ranked by how directly each witnesses the *work*, which put
# a commit near the top. That is right for attribution and wrong here: a commit
# is an instant, and its window only exists because `coletor` clustered it with
# its neighbours. The sources that carry a measured span outrank the ones whose
# span had to be inferred, whatever they prove about the activity.
PESO_FONTE = {
    "reuniao": 0.90,     # duracao lida da propria transcricao, medida
    "sessao_ia": 0.75,   # muitos carimbos de tempo, agrupados com folga
    "commit": 0.60,      # instante: a janela e inferida dos vizinhos
    "nota_vault": 0.50,  # mtime, um instante por nota
    "arquivo": 0.45,
    "navegador": 0.30,   # prova que uma pagina estava aberta
    "transcricao": 0.55,  # a pessoa disse o que fez, e nao por quanto tempo
}


class Interprete(Protocol):
    """Turns a stretch of transcript into work statements.

    The only place a model is allowed in this module. Kept as a protocol so a
    fake serves every test, and so swapping the local model for another one is
    a constructor argument rather than an edit.
    """

    def falas_de_trabalho(self, texto: str, dia: date) -> list["Fala"]:
        ...


@dataclass(frozen=True)
class Fala:
    """One statement about work, as extracted from a transcript."""

    texto: str
    atividade: str
    dia: date
    horas_declaradas: float | None = None


@dataclass(frozen=True)
class Evidencia:
    """One thing the machine or a person witnessed.

    `inferida` separates a window that was observed from one that was derived.
    A meeting's length is read off its transcript; a lone commit at 14:32 has
    no length at all and only gets one because `coletor` applied a floor. Both
    are useful and only one is a measurement, so the difference travels with
    the evidence instead of being lost in a description string.
    """

    tipo: str
    inicio: datetime
    fim: datetime
    descricao: str
    tarefa_sugerida: str = ""
    inferida: bool = False

    @property
    def intervalo(self) -> Intervalo:
        return Intervalo(self.inicio, self.fim)

    @property
    def peso(self) -> float:
        return PESO_FONTE.get(self.tipo, 0.3)


@dataclass
class Proposta:
    """A time entry the engine suggests, with its reasons attached.

    `citacoes` is not decoration. A proposal a person cannot trace back to
    evidence is one they can only rubber-stamp, and rubber-stamping is how a
    wrong entry becomes an invoice.
    """

    dia: date
    task_id: str
    descricao: str
    horas: float
    faturavel: bool
    confianca: float
    tags: tuple[str, ...]
    citacoes: list[str] = field(default_factory=list)
    fontes: tuple[str, ...] = ()

    @property
    def duvidosa(self) -> bool:
        return self.confianca < CONFIANCA_MINIMA

    def para_lancamento(self, inicio: datetime) -> Lancamento:
        return Lancamento(
            task_id=self.task_id,
            inicio_ms=ms(inicio),
            duracao_ms=int(self.horas * 3_600_000),
            descricao=self.descricao,
            faturavel=self.faturavel,
            tags=self.tags,
        )


@dataclass
class Lacuna:
    """Something the evidence cannot answer, phrased as a question.

    The gap protocol is the reason the whole thing works. Days 04 and 05/08 of
    the second cycle had no evidence at all and were normal working days: an
    engine that reports zero for them is confidently wrong, and one that asks
    gets the hours back.
    """

    dia: date
    pergunta: str
    motivo: str
    horas_em_aberto: float | None = None


@dataclass
class Apuracao:
    """A window's proposals and, always, what the evidence did not see."""

    inicio: date
    fim: date
    propostas: list[Proposta] = field(default_factory=list)
    lacunas: list[Lacuna] = field(default_factory=list)
    horas_esperadas_por_dia: float = 8.0
    #: Feriados da janela. Sem eles a expectativa conta um dia que ninguem
    #: trabalhou, e como a cobertura e o proposto DIVIDIDO pelo esperado, um
    #: denominador inflado faz o metodo parecer pior do que e e dispara
    #: pergunta sobre um dia que nao existiu.
    feriados: frozenset[date] = frozenset()

    @property
    def horas_propostas(self) -> float:
        return round(sum(p.horas for p in self.propostas), 2)

    @property
    def dias_uteis(self) -> int:
        d, total = self.inicio, 0
        while d <= self.fim:
            if d.weekday() < 5 and d not in self.feriados:
                total += 1
            d += timedelta(days=1)
        return total

    @property
    def horas_esperadas(self) -> float:
        return self.dias_uteis * self.horas_esperadas_por_dia

    @property
    def cobertura(self) -> float:
        """Share of an expected workload the evidence accounts for.

        Deliberately compared against an expectation and not against the
        proposals themselves: dividing the found hours by the found hours is
        always 100% and is exactly the reassuring number that hid the gap in
        the first cycle.
        """
        if self.horas_esperadas <= 0:
            return 0.0
        return min(self.horas_propostas / self.horas_esperadas, 1.0)

    @property
    def dias_cegos(self) -> list[date]:
        """Working days with no proposal at all."""
        com_proposta = {p.dia for p in self.propostas}
        cegos, d = [], self.inicio
        while d <= self.fim:
            if d.weekday() < 5 and d not in com_proposta:
                cegos.append(d)
            d += timedelta(days=1)
        return cegos

    @property
    def pronta_para_lancar(self) -> bool:
        """Never true while a gap is open.

        A window with open questions is not finished, and letting it be written
        would bill a number the engine already knows is incomplete.
        """
        return not self.lacunas and bool(self.propostas)


# ── formato da casa ──────────────────────────────────────────────────────────


def _sem_acento(texto: str) -> str:
    """Fold accents and case for comparison.

    The activity name reaches this code from a transcript as often as from
    ClickUp, and "Lancamento" and "Lançamento" are the same activity to
    everyone except a string comparison.
    """
    normalizado = unicodedata.normalize("NFKD", texto.strip().lower())
    return "".join(c for c in normalizado if not unicodedata.combining(c))

_CLIENTE = re.compile(r"\(([^)]+)\)\s*$")


def descricao_da_casa(atividade: str, cliente: str, progressao: str = "") -> str:
    """The house pattern: explicit progression, client in parentheses at the end.

    The time entry's description is the row label in the billable hours report.
    The pilot's first 18 entries had none, so the work was invisible to whoever
    read that report, which is what triggered the whole relaunch.
    """
    corpo = f"{atividade} {progressao}".strip() if progressao else atividade.strip()
    return f"{corpo} ({cliente})"


def confere_formato(descricao: str) -> list[str]:
    problemas = []
    if not descricao.strip():
        problemas.append("descricao vazia")
    if not _CLIENTE.search(descricao.strip()):
        problemas.append("sem cliente entre parenteses no fim")
    return problemas


def classificar_faturavel(tags: tuple[str, ...], atividade: str = "") -> bool:
    """Billability follows the activity, never a uniform default.

    Marking a whole batch billable is how the pilot billed 16 hours it should
    not have. `daily` and `reuniao interna` are never billed.

    The activity matters and not only the tag, because of one case the house
    convention treats specially: logging hours carries the `planejamento` tag
    and is not billable, while everything else tagged `planejamento` is. Deciding
    on the tag alone bills the act of billing.
    """
    if set(tags) & NAO_FATURAVEL:
        return False
    if _sem_acento(ATIVIDADE_NAO_FATURAVEL) in _sem_acento(atividade):
        return False
    return True


# ── o motor ──────────────────────────────────────────────────────────────────


def _confianca(evidencias: list[Evidencia], tem_fala: bool,
               horas_declaradas: bool = False) -> float:
    """How much to trust the proposed HOURS, which is what gets billed.

    The first version scored the activity instead, and on real data it returned
    1.00 for every single proposal of a week: a standup statement exists on
    almost every day, transcription is the heaviest source, and the score
    pinned at the ceiling and stopped discriminating. A number that never
    varies is not a number.

    So the question here is narrower: how well is the *duration* supported?
    Someone saying "I worked on the collector" pins the activity and says
    nothing about how long, and the hours in that case come from clustered
    points, which is the weak part. A statement that does name the hours is a
    different thing, and only then does the transcript carry the full weight.
    """
    if not evidencias and not tem_fala:
        return 0.0
    if tem_fala and horas_declaradas:
        # The person said what they did and for how long. Nothing beats it.
        return 1.0

    melhor = max((e.peso for e in evidencias), default=0.0)
    if tem_fala:
        # The statement corroborates that the day was worked, so it lifts a
        # weak duration, but it cannot certify a duration it never mentioned.
        melhor = max(melhor, PESO_FONTE["transcricao"])

    tipos = {e.tipo for e in evidencias}
    score = melhor + 0.04 * max(len(tipos) - 1, 0)

    # How much of the day's evidence rests on windows nobody observed. On this
    # machine every day carries all five sources, so counting sources
    # discriminates nothing and the score pinned at its ceiling for a whole
    # week. This is what actually varies: a day held up by floored windows
    # around isolated commits is weaker than one held up by a meeting whose
    # length was read off its own transcript.
    if evidencias:
        span = sum((e.fim - e.inicio).total_seconds() for e in evidencias)
        inferido = sum((e.fim - e.inicio).total_seconds()
                       for e in evidencias if e.inferida)
        if span > 0:
            score -= 0.45 * (inferido / span)

    return round(max(min(score, 0.95), 0.05), 2)


def apurar_dia(dia: date, evidencias: list[Evidencia], falas: list[Fala],
               task_id: str, cliente: str, tags: tuple[str, ...],
               horas_esperadas: float = 8.0) -> tuple[list[Proposta], list[Lacuna]]:
    """Propose the day's entries and name what stayed unexplained."""
    do_dia = [e for e in evidencias if e.inicio.date() == dia]
    falas_do_dia = [f for f in falas if f.dia == dia]

    if not do_dia and not falas_do_dia:
        return [], [Lacuna(
            dia=dia,
            pergunta=f"O que voce fez em {dia:%d/%m}?",
            motivo="nenhuma evidencia encontrada neste dia",
            horas_em_aberto=horas_esperadas,
        )]

    janelas = fundir([e.intervalo for e in do_dia])
    horas_evidencia = round(somar_horas([e.intervalo for e in do_dia]), 2)
    declaradas = sum(f.horas_declaradas or 0 for f in falas_do_dia)
    # A statement of hours outranks the windows: the person was there.
    horas = round(declaradas or horas_evidencia, 2)

    lacunas: list[Lacuna] = []
    if horas <= 0:
        return [], [Lacuna(dia, f"O que voce fez em {dia:%d/%m}?",
                           "evidencia sem duracao aproveitavel", horas_esperadas)]

    # Without a statement the engine knows that time passed and not what was
    # done, and it must not fill that in. Running with --sem-modelo it used to
    # paste the first evidence's raw text, producing descriptions like
    # "soteriaonline-my.sharepoint.com: Gravacao de Reuniao.mp4" as the
    # activity name. That string is the row label in the billable hours report,
    # the exact field whose emptiness forced the pilot to be relaunched, so
    # inventing it from a URL is worse than admitting it is unknown.
    if falas_do_dia:
        atividade = falas_do_dia[0].atividade
        atividade_conhecida = True
    else:
        atividade = ATIVIDADE_DESCONHECIDA
        atividade_conhecida = False
    progressao = (f"{len(janelas)} janelas" if len(janelas) > 1 else "")
    proposta = Proposta(
        dia=dia,
        task_id=task_id,
        descricao=descricao_da_casa(atividade, cliente, progressao),
        horas=horas,
        faturavel=classificar_faturavel(tags, atividade),
        confianca=_confianca(do_dia, bool(falas_do_dia), bool(declaradas)),
        tags=tags,
        citacoes=[f.texto for f in falas_do_dia] + [e.descricao for e in do_dia],
        fontes=tuple(sorted({e.tipo for e in do_dia} | ({"transcricao"} if falas_do_dia else set()))),
    )

    faltando = horas_esperadas - horas
    if faltando >= 2:
        # Not an error: the evidence simply does not reach the rest of the day.
        # Saying so is the difference between 39,1h and 130,1h.
        lacunas.append(Lacuna(
            dia=dia,
            pergunta=f"A evidencia de {dia:%d/%m} cobre {horas:.1f}h. "
                     f"O que ocupou as outras {faltando:.1f}h?",
            motivo="evidencia parcial",
            horas_em_aberto=round(faltando, 2),
        ))
    if not atividade_conhecida:
        lacunas.append(Lacuna(
            dia=dia,
            pergunta=f"A evidencia mostra {horas:.1f}h em {dia:%d/%m} mas nada "
                     f"diz o que foi feito. Qual foi a atividade?",
            motivo="sem fala na daily: houve tempo, falta o que",
            horas_em_aberto=horas,
        ))
    if proposta.duvidosa:
        lacunas.append(Lacuna(
            dia=dia,
            pergunta=f"Confirma que {dia:%d/%m} foi {atividade}?",
            motivo=f"confianca baixa ({proposta.confianca:.2f}), "
                   f"fontes: {', '.join(proposta.fontes) or 'nenhuma'}",
        ))
    return [proposta], lacunas


def apurar(inicio: date, fim: date, evidencias: list[Evidencia], falas: list[Fala],
           task_id: str, cliente: str, tags: tuple[str, ...] = ("desenvolvimento",),
           horas_esperadas_por_dia: float = 8.0,
           feriados: frozenset[date] = frozenset()) -> Apuracao:
    """Walk a window day by day, proposing and questioning.

    Feriado e fim de semana nao sao pulados: sao percorridos e o que aparecer
    neles vira PERGUNTA em vez de proposta faturavel. Medido em 08/09/2026 na
    primeira apuracao com dado proprio: o feriado de 07/09 rendeu uma proposta
    de 6,6h faturaveis, e o trabalho daquele dia era pessoal. Pular o dia
    esconderia a hora; propor calado a cobraria. Perguntar e a unica das tres
    que nao erra sozinha.
    """
    ap = Apuracao(inicio=inicio, fim=fim,
                  horas_esperadas_por_dia=horas_esperadas_por_dia,
                  feriados=frozenset(feriados))
    dias_percorridos: set[date] = set()
    d = inicio
    while d <= fim:
        util = d.weekday() < 5 and d not in ap.feriados
        if util:
            dias_percorridos.add(d)
            propostas, lacunas = apurar_dia(
                d, evidencias, falas, task_id, cliente, tags, horas_esperadas_por_dia)
            ap.propostas.extend(propostas)
            ap.lacunas.extend(lacunas)
        else:
            fora = [e for e in evidencias if e.inicio.date() == d]
            if fora:
                que_dia = "feriado" if d in ap.feriados else "fim de semana"
                horas_brutas = round(somar_horas(fundir([e.intervalo for e in fora])), 2)
                ap.lacunas.append(Lacuna(
                    dia=d,
                    pergunta=(f"Ha evidencia de {horas_brutas:.1f}h em {d:%d/%m}, que e "
                              f"{que_dia}. Isso foi trabalho de cliente, trabalho "
                              f"interno ou pessoal?"),
                    motivo=f"{que_dia} com evidencia: nada aqui e faturavel sem voce dizer",
                    horas_em_aberto=horas_brutas,
                ))
        d += timedelta(days=1)

    # Statements that landed on a day the walk never visits. This happens for
    # real: a Monday standup saying "ontem" dates to Sunday, and a weekday name
    # can reach back past `inicio`. The walk skips weekends and stops at the
    # window, so those falas would be consumed by nobody and vanish without a
    # line anywhere. Losing declared work in silence is the exact failure this
    # module exists to prevent, so it becomes a question instead.
    for f in falas:
        if f.dia in dias_percorridos:
            continue
        fora = ("fim de semana" if f.dia.weekday() >= 5
                else "fora da janela apurada")
        ap.lacunas.append(Lacuna(
            dia=f.dia,
            pergunta=f"A daily aponta trabalho em {f.dia:%d/%m} ({fora}): "
                     f"{f.atividade}. Isso deve ser lancado?",
            motivo=f"fala datada em dia que a apuracao nao percorre ({fora})",
            horas_em_aberto=f.horas_declaradas,
        ))
    return ap


def relatorio(ap: Apuracao) -> str:
    """Render the window. Coverage is never omitted, whatever it says."""
    linhas = [
        f"# Apuracao de horas: {ap.inicio:%d/%m} a {ap.fim:%d/%m}",
        "",
        f"Propostas: {ap.horas_propostas:.1f}h em {len(ap.propostas)} lancamentos",
        f"Esperado no periodo: {ap.horas_esperadas:.0f}h "
        f"({ap.dias_uteis} dias uteis x {ap.horas_esperadas_por_dia:.0f}h)",
        f"Cobertura da evidencia: {ap.cobertura:.0%}",
    ]
    if ap.dias_cegos:
        linhas.append(f"Dias sem nenhuma evidencia: "
                      f"{', '.join(d.strftime('%d/%m') for d in ap.dias_cegos)}")
    linhas.append("")

    if ap.propostas:
        linhas.append("## Propostas")
        for p in sorted(ap.propostas, key=lambda x: x.dia):
            marca = " [CONFIANCA BAIXA]" if p.duvidosa else ""
            linhas.append(
                f"- {p.dia:%d/%m} {p.horas:.1f}h {p.descricao}{marca}\n"
                f"    faturavel={p.faturavel} confianca={p.confianca:.2f} "
                f"fontes={', '.join(p.fontes) or 'nenhuma'}")
            for c in p.citacoes[:3]:
                linhas.append(f"    > {c[:120]}")
        linhas.append("")

    if ap.lacunas:
        linhas.append("## Perguntas que precisam de resposta antes de lancar")
        for l in sorted(ap.lacunas, key=lambda x: x.dia):
            aberto = (f" (~{l.horas_em_aberto:.1f}h em aberto)"
                      if l.horas_em_aberto else "")
            linhas.append(f"- {l.dia:%d/%m}: {l.pergunta}{aberto}\n    motivo: {l.motivo}")
        linhas.append("")
        linhas.append("Nada e lancado enquanto houver pergunta aberta. A leitura so por "
                      "artefato mediu 39,1h de 130,1h reais no primeiro ciclo e 54h de "
                      "89,5h no segundo: o que fecha a diferenca e a resposta, nao o total.")
    else:
        linhas.append("Sem lacunas: a apuracao esta pronta para revisao e aprovacao.")
    return "\n".join(linhas)


def lancar(cliente_clickup, ap: Apuracao, aprovacao: Aprovacao | None,
           hora_inicial: int = 9) -> list:
    """Write an approved window. Refuses while any question is open."""
    if not ap.pronta_para_lancar:
        raise ValueError(
            f"apuracao com {len(ap.lacunas)} lacuna(s) aberta(s): responda antes de lancar")
    resultados = []
    for p in sorted(ap.propostas, key=lambda x: x.dia):
        inicio = datetime.combine(p.dia, datetime.min.time(), tzinfo=BRT) \
            .replace(hour=hora_inicial)
        resultados.append(cliente_clickup.lancar(p.para_lancamento(inicio), aprovacao))
    return resultados
