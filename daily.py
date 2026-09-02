"""Daily standup transcripts: the source that closes the gap.

The measurement that shapes the whole hours engine says machine evidence
captured 39,1h of 130,1h and 54h of 89,5h. What recovered the difference in the
second cycle was not another machine source, it was seven screenshots of a
standup transcript. Those transcripts now live in the vault, and this module
reads them.

The split is deliberate. Parsing the transcript and pulling out one person's
lines is **deterministic**: a regex over `[mm:ss] Nome: fala`, no judgement, no
model. Deciding what those lines say about a day's work is **interpretation**,
and that is the one place a model belongs. Sending the raw transcript to a model
and asking for hours would spend tokens on the parsing and put judgement where
arithmetic would do.

The transcripts do not record the time of day: no header in any of the 33 notes
carries it. The hour comes from the team instead, confirmed on 02/09/2026: the
standup is always at 14:00 and runs at most until 15:00. That makes
`HORA_DA_DAILY` a fact about this workspace rather than a guess, and it gives
the parser something to check, since a transcript measuring more than an hour
contradicts the rule and is worth saying out loud.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .horas import Fala

logger = logging.getLogger("pmo.daily")

# Fact about this workspace, from the team on 02/09/2026: the standup starts at
# 14:00 and runs at most one hour. No transcript records it, so this constant is
# the only place it lives. Changing it means the meeting moved, not that a knob
# was tuned.
HORA_DA_DAILY = 14
DURACAO_MAXIMA = timedelta(hours=1)

_DATA_NO_NOME = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_FALA = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s+([^:]{2,60}):\s*(.+)$")
_TITULO = re.compile(r'^title:\s*"?(.+?)"?\s*$', re.MULTILINE)


@dataclass(frozen=True)
class Linha:
    """One utterance: when into the meeting, who, what."""

    offset: timedelta
    quem: str
    texto: str


@dataclass
class Transcricao:
    """One meeting, parsed."""

    dia: date
    titulo: str
    falas: list[Linha]
    caminho: Path | None = None

    @property
    def duracao(self) -> timedelta:
        """How long the meeting ran, from its last marker. Measured."""
        return self.falas[-1].offset if self.falas else timedelta(0)

    @property
    def passou_da_hora(self) -> bool:
        """The standup is capped at an hour, so a longer one is a fact worth
        reporting: either the meeting ran over or the recording carries more
        than the standup. Either way it is not something to average away."""
        return self.duracao > DURACAO_MAXIMA

    def de(self, pessoa: str) -> list[Linha]:
        """This person's lines. Matching is loose on purpose.

        A transcript writes "Jordan Bernardes" and a config is as likely to say
        "Jordan", so requiring an exact match would silently return nothing,
        which reads exactly like a person who said nothing that day.
        """
        alvo = pessoa.strip().lower()
        if not alvo:
            return []
        return [l for l in self.falas
                if alvo in l.quem.lower() or l.quem.lower() in alvo]

    def participantes(self) -> list[str]:
        return sorted({l.quem for l in self.falas})


def ler_transcricao(caminho: str | Path) -> Transcricao | None:
    """Parse one vault transcript. Returns None when the file is not one.

    None rather than an exception: this runs over a whole folder, and a note
    that is not a transcript is the normal case, not an error.
    """
    caminho = Path(caminho)
    try:
        texto = caminho.read_text()
    except OSError as e:
        logger.warning("nao foi possivel ler %s: %s", caminho.name, e)
        return None

    # The LAST date in the filename, not the first. The vault names a note
    # "<data em que foi escrita>-<titulo>.md", and a transcript's title often
    # carries the meeting's own date, so a note written on 01/09 about a
    # meeting held on 31/08 is called
    # "2026-09-01-Cronograma Agentes de Gestao - 2026-08-31.md".
    # Reading the first date attributed 67 of one person's utterances to the
    # wrong day, which would move those hours a day forward.
    datas = _DATA_NO_NOME.findall(caminho.name)
    if not datas:
        return None
    try:
        dia = date(*(int(x) for x in datas[-1]))
    except ValueError:
        return None

    falas: list[Linha] = []
    for linha in texto.splitlines():
        f = _FALA.match(linha.strip())
        if not f:
            continue
        a, b, c, quem, fala = f.groups()
        # [h:mm:ss] past the first hour, [mm:ss] before it.
        offset = (timedelta(hours=int(a), minutes=int(b), seconds=int(c))
                  if c else timedelta(minutes=int(a), seconds=int(b)))
        falas.append(Linha(offset, quem.strip(), fala.strip()))

    if not falas:
        return None

    t = _TITULO.search(texto)
    titulo = t.group(1) if t else caminho.stem
    return Transcricao(dia=dia, titulo=titulo, falas=falas, caminho=caminho)


_FAIXA = re.compile(r"\b(\d{1,2}):(\d{2})\s*(?:as|às|a|até|-|ate)\s*\d{1,2}:\d{2}\b",
                    re.IGNORECASE)


def e_daily(t: "Transcricao") -> bool:
    """Whether this transcript is the team standup.

    Only the standup has a known hour, so this decides which transcripts get
    the 14:00 rule. Matching on the title rather than the filename because the
    title is what the note asserts about itself.
    """
    return "daily" in (t.titulo or "").lower() or "daily" in (
        t.caminho.name.lower() if t.caminho else "")


def horario_no_texto(t: "Transcricao") -> "time | None":
    """The meeting's start time when the note records it in prose.

    Seven of the vault's notes carry a range like "11:04 as 11:50". Reading it
    beats any convention, because it is the actual time.
    """
    if t.caminho is None:
        return None
    try:
        m = _FAIXA.search(t.caminho.read_text())
    except OSError:
        return None
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return time(hour=h, minute=mi) if 0 <= h < 24 and 0 <= mi < 60 else None


def transcricoes(pasta: str | Path, inicio: date, fim: date) -> list[Transcricao]:
    """Every transcript in a folder whose date falls in the window."""
    pasta = Path(pasta).expanduser()
    if not pasta.exists():
        logger.warning("pasta de transcricoes nao existe: %s", pasta)
        return []
    achadas = []
    for arquivo in sorted(pasta.glob("*.md")):
        t = ler_transcricao(arquivo)
        if t is not None and inicio <= t.dia <= fim:
            achadas.append(t)
    return achadas


# ── interpretacao ────────────────────────────────────────────────────────────

SISTEMA = (
    "Voce le trechos de uma reuniao diaria de equipe e extrai o que UMA pessoa "
    "disse que JA FEZ ou esta fazendo de trabalho. Responde em portugues do Brasil. "
    "NUNCA use travessao. Nao invente atividade que a pessoa nao mencionou, e "
    "nao transforme conversa social em trabalho. IGNORE o que a pessoa diz que "
    "VAI fazer: plano nao e hora trabalhada. Se as falas nao descreverem trabalho "
    "ja feito ou em curso, responda exatamente SEM TRABALHO."
)

TAREFA = (
    "Falas de {pessoa} na daily de {dia}.\n\n{falas}\n\n"
    "Liste as atividades de trabalho que ela descreveu, uma por linha, no formato:\n"
    "ATIVIDADE: <frase curta comecando com substantivo, ex: Desenvolvimento do coletor>\n"
    "QUANDO: <hoje|ontem|segunda|terca|quarta|quinta|sexta> conforme a fala indicar\n"
    "HORAS: <numero, se a pessoa disser quanto tempo levou; senao escreva ?>\n"
    "---\n"
    "Repita o bloco para cada atividade distinta. Maximo 4 atividades.\n"
    "Regras de QUANDO: escreva hoje quando a pessoa fala no presente do proprio "
    "dia. Escreva ontem so quando ela disser ontem. Escreva o nome do dia da "
    "semana quando ela citar o dia por nome E no passado, por exemplo "
    "'sexta-feira eu comecei'. Se ela citar um dia da semana no futuro, por "
    "exemplo 'vou apresentar segunda', isso e plano: nao liste a atividade.\n"
    "Se nao houver trabalho descrito, responda so SEM TRABALHO."
)

_BLOCO = re.compile(
    r"ATIVIDADE:\s*(?P<atividade>.+?)\s*$\s*"
    r"QUANDO:\s*(?P<quando>\w+)\s*$\s*"
    r"HORAS:\s*(?P<horas>[\d.,?]+)",
    re.MULTILINE | re.IGNORECASE)


_DIAS_DA_SEMANA = {"segunda": 0, "terca": 1, "terça": 1, "quarta": 2,
                   "quinta": 3, "sexta": 4, "sabado": 5, "sábado": 5, "domingo": 6}


def resolver_quando(marcador: str, dia_da_reuniao: date) -> date:
    """Turn the model's QUANDO into a date, walking backwards only.

    Weekday names show up in 9 of Jordan's 280 lines, a third as often as
    "ontem", so ignoring them loses real work. They are resolved to the most
    recent occurrence strictly before the meeting, because a standup that names
    a weekday in the past is talking about the one that just passed.

    Direction is not decided here. "vou apresentar segunda" is a plan and not
    an hour, and telling that from "sexta eu comecei" needs the verb, which is
    judgement: the model is instructed to drop plans, and this only does the
    calendar arithmetic on what survives.
    """
    m = marcador.strip().lower().replace("-feira", "").strip()
    if m.startswith("ontem"):
        return dia_da_reuniao - timedelta(days=1)
    alvo = _DIAS_DA_SEMANA.get(m)
    if alvo is None:
        return dia_da_reuniao
    # Walk back at most a week; same weekday as the meeting means seven days ago,
    # never today, since a standup does not report today by naming today.
    for atras in range(1, 8):
        candidato = dia_da_reuniao - timedelta(days=atras)
        if candidato.weekday() == alvo:
            return candidato
    return dia_da_reuniao


# What a period of the day is worth, when someone says they spent it on
# something. Measured against the transcripts: 21 of Jordan's 280 lines carry
# one of these, so this is real but small signal, and it is never a total.
PERIODOS = {
    "dia": 6.0,       # "passei o dia", ja descontando reunioes e intervalos
    "manha": 3.5,
    "tarde": 3.5,
    "parte": 3.0,     # "grande parte do dia"
}

_PERIODO = (
    (re.compile(r"\b(?:o dia (?:todo|inteiro)|dia inteiro|passei o dia)\b", re.I), "dia"),
    (re.compile(r"\b(?:manh[aã] (?:toda|inteira)|passei a manh[aã]|a manh[aã] (?:toda|inteira))\b", re.I), "manha"),
    (re.compile(r"\b(?:tarde (?:toda|inteira)|passei a tarde|a tarde (?:toda|inteira))\b", re.I), "tarde"),
    (re.compile(r"\b(?:grande|boa|maior) parte do dia\b", re.I), "parte"),
)


def duracao_no_texto(texto: str) -> float | None:
    """Hours implied by a phrase like "passei a manha nisso".

    Only matches phrases that assert a period was *spent*: "passei a tarde"
    counts, "hoje de tarde eu vou ver isso" does not, because the second is a
    plan and a plan is not an hour. That distinction is why the patterns
    require the verb or an explicit "toda/inteira" rather than just the noun.

    The values are conventions, not measurements, and they are deliberately
    short: a morning is 3,5h and not 4h because the day has a standup and
    interruptions in it, and overstating here bills time nobody worked.
    """
    for rx, chave in _PERIODO:
        if rx.search(texto):
            return PERIODOS[chave]
    return None


def _horas(bruto: str) -> float | None:
    bruto = bruto.strip().replace(",", ".")
    if bruto in ("?", "", "-"):
        return None
    try:
        h = float(bruto)
    except ValueError:
        return None
    # A standup statement of more than a working day is a parse artifact, not a
    # claim: dropping it costs one activity, believing it corrupts the total.
    return h if 0 < h <= 16 else None


class InterpreteLocal:
    """Turns a person's standup lines into `Fala` objects, using llama.cpp.

    Implements the `horas.Interprete` protocol. `chamar` is injected so the
    tests never need a GPU and so swapping the model is a constructor argument.
    """

    def __init__(self, pessoa: str, chamar=None, max_tokens: int = 700):
        self.pessoa = pessoa
        self.max_tokens = max_tokens
        self._chamar = chamar or self._chamar_llama
        # Whether the last call failed to reach the model, as opposed to the
        # model answering that there was no work.
        self.ultima_falhou = False

    @staticmethod
    def _chamar_llama(sistema: str, usuario: str, max_tokens: int) -> str:
        import json as _json
        import urllib.request
        corpo = _json.dumps({
            "messages": [{"role": "system", "content": sistema},
                         {"role": "user", "content": usuario}],
            "max_tokens": max_tokens, "temperature": 0.2,
            # Thinking off: measured at 2474 chars in 63s on, 5221 in 45s off,
            # and with it on the budget is spent before `content` is written.
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8181/v1/chat/completions", data=corpo,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            msg = _json.loads(r.read())["choices"][0]["message"]
        return (msg.get("content") or msg.get("reasoning_content") or "").strip()

    def falas_de_trabalho(self, texto: str, dia: date) -> list[Fala]:
        """The Interprete protocol. `texto` is already this person's lines."""
        if not texto.strip():
            return []
        texto_bruto = texto
        usuario = TAREFA.format(pessoa=self.pessoa, dia=f"{dia:%d/%m/%Y}", falas=texto)
        self.ultima_falhou = False
        try:
            resposta = self._chamar(SISTEMA, usuario, self.max_tokens)
        except Exception as e:
            # A model that cannot be reached must not look like a person who
            # said nothing: the day then has no transcript evidence and the gap
            # protocol asks about it, which is the correct outcome.
            logger.warning("interprete nao respondeu para %s: %s", dia, e)
            self.ultima_falhou = True
            return []

        if "SEM TRABALHO" in resposta.upper():
            return []

        falas: list[Fala] = []
        vistas: dict[str, Fala] = {}
        for m in _BLOCO.finditer(resposta):
            atividade = m.group("atividade").strip(" .*-")
            if not atividade:
                continue
            # The dating rule that cost a day of misattributed hours: present
            # continuous describes the project in progress, so the day only
            # moves on an explicit marker. `resolver_quando` also handles the
            # weekday names that the real transcripts turned out to use.
            quando = resolver_quando(m.group("quando"), dia)
            # The model reports an explicit number when the person gave one.
            # When it did not, the raw lines may still say "passei a manha",
            # which the manual process read as hours and this used to drop.
            declarada = _horas(m.group("horas"))
            if declarada is None:
                declarada = duracao_no_texto(texto_bruto)
            nova = Fala(
                texto=f"[daily {dia:%d/%m}] {atividade}",
                atividade=atividade,
                dia=quando,
                horas_declaradas=declarada,
            )
            # One activity, one entry. Observed on the real 25/08 standup: the
            # model emitted the same activity twice, dated to both the previous
            # day and the meeting day, which would have become two proposals for
            # one stretch of work. The earlier date wins, because turning one
            # statement into two days of work is the inflation this whole
            # module is built to avoid.
            chave = atividade.strip().lower()
            anterior = vistas.get(chave)
            if anterior is None:
                vistas[chave] = nova
                falas.append(nova)
            elif nova.dia < anterior.dia:
                logger.info("atividade repetida em %s, ficando com %s", dia, nova.dia)
                falas[falas.index(anterior)] = nova
                vistas[chave] = nova
        return falas[:4]


def falas_da_pessoa(pasta: str | Path, pessoa: str, inicio: date, fim: date,
                    interprete: InterpreteLocal | None = None,
                    falhas: list[str] | None = None) -> list[Fala]:
    """Read the window's transcripts and interpret one person's lines.

    Deterministic all the way to the model: the transcripts are parsed, the
    person's lines are filtered, and only then is anything interpreted. A day
    where the person said nothing produces no Fala, which the gap protocol
    turns into a question rather than a zero.
    """
    interprete = interprete or InterpreteLocal(pessoa)
    todas: list[Fala] = []
    for t in transcricoes(pasta, inicio, fim):
        minhas = t.de(pessoa)
        if not minhas:
            continue
        texto = "\n".join(f"[{int(l.offset.total_seconds() // 60)}min] {l.texto}"
                          for l in minhas)
        extraidas = interprete.falas_de_trabalho(texto, t.dia)
        # A day where the person spoke and nothing came back is either a day
        # of small talk or a model that did not answer, and those are opposite
        # things. Returning the count lets a caller tell them apart: a silent
        # degradation corrupted a whole measurement run of this module before
        # this line existed, giving the machine-evidence baseline while looking
        # like a complete result.
        if not extraidas and falhas is not None and interprete.ultima_falhou:
            falhas.append(f"{t.dia:%d/%m}: interprete nao respondeu")
        todas.extend(extraidas)
    return todas
