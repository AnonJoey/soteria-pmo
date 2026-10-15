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
import os
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("pmo.rh")

# How many days ahead each kind of date starts being announced.
#
# Revisto em 08/09/2026 na reuniao de homologacao com o Max, que corrigiu os
# termos e os prazos. A versao anterior vinha de 24/06 e nao batia com o
# contrato real da Soteria.
ANTECEDENCIA = {
    "aniversario": 7,
    "tempo de casa": 7,
    "fim de contrato": 30,
    "interrupcao temporaria": 20,
    "feedback": 5,
}

# Os dois feedbacks do primeiro ano, contados do INICIO DO CONTRATO.
#
# Substitui o ciclo bimestral de 60 dias contado a partir do ultimo feedback.
# O Max, em 08/09: "primeiro feedback 45 dias, segundo feedback 90 dias, da
# para colocar 2 colunas assim, ja automatizando da data de inicio do contrato".
#
# A diferenca nao e so o numero: o ciclo antigo se ancorava numa data que
# alguem tinha de preencher a cada rodada, e sem ela nao disparava nada. Estes
# dois derivam de uma data que ja existe no cadastro.
FEEDBACKS_DIAS = (45, 90)

# Saldo de interrupcao temporaria por ano de contrato. Nao ha ferias CLT: o
# contrato preve uma interrupcao temporaria negociada, sem prejuizo do
# pagamento, de 20 dias a cada ano completo.
INTERRUPCAO_DIAS_POR_ANO = 20


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
    #: Data de inicio de contrato. Nao e admissao: nao ha vinculo CLT com
    #: ninguem, e o Max pediu explicitamente que o termo mudasse.
    inicio_contrato: date | None = None
    fim_contrato: date | None = None
    #: Inicio da interrupcao temporaria negociada. Nao e ferias.
    interrupcao_inicio: date | None = None
    #: Mantido para roster que ja registrava feedback avulso. Os dois feedbacks
    #: do primeiro ano saem de `inicio_contrato` e nao dependem deste campo.
    ultimo_feedback: date | None = None

    @property
    def admissao(self) -> date | None:
        """Nome antigo de `inicio_contrato`, mantido para nao quebrar chamador."""
        return self.inicio_contrato


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
            linhas = json.loads(p.read_text(encoding="utf-8"))
        else:
            with p.open(newline="", encoding="utf-8") as fh:
                linhas = list(csv.DictReader(fh))
    except Exception as e:
        raise RosterAusente(f"roster de RH ilegivel em {p}: {e}") from e

    pessoas = []
    for linha in linhas:
        nome = (linha.get("nome") or "").strip()
        if not nome:
            continue
        # Os nomes antigos continuam aceitos: o roster que o Max mandar pode vir
        # com qualquer um dos dois, e recusar a coluna antiga transformaria uma
        # planilha valida em silencio.
        pessoas.append(Pessoa(
            nome=nome,
            nascimento=_data(linha.get("nascimento")),
            inicio_contrato=_data(linha.get("inicio_contrato") or linha.get("admissao")),
            fim_contrato=_data(linha.get("fim_contrato")),
            interrupcao_inicio=_data(linha.get("interrupcao_inicio") or linha.get("ferias_inicio")),
            ultimo_feedback=_data(linha.get("ultimo_feedback") or linha.get("data_ultimo_feedback")),
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
    try:
        return quando.replace(year=hoje.year + 1)
    except ValueError:
        return date(hoje.year + 1, 3, 1)


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
        if p.inicio_contrato:
            q = _proxima_ocorrencia(p.inicio_contrato, hoje)
            d = (q - hoje).days
            if d <= ANTECEDENCIA["tempo de casa"]:
                anos = q.year - p.inicio_contrato.year
                if anos >= 1:
                    achados.append(Evento(p.nome, "tempo de casa", q, d,
                                          f"{anos} ano{'s' if anos > 1 else ''}, "
                                          f"{anos * INTERRUPCAO_DIAS_POR_ANO} dias de interrupcao acumulados"))

            # Os dois feedbacks do primeiro ano, derivados do inicio do contrato.
            for ordinal, dias in zip(("primeiro", "segundo"), FEEDBACKS_DIAS):
                quando = p.inicio_contrato + timedelta(days=dias)
                d = (quando - hoje).days
                if -30 <= d <= ANTECEDENCIA["feedback"]:
                    achados.append(Evento(p.nome, f"{ordinal} feedback", quando, d,
                                          f"{dias} dias de contrato"))

        # One-off dates. Past ones still surface: a contract end that passed
        # last week without anyone noticing is the case worth catching.
        for campo, tipo in (("fim_contrato", "fim de contrato"),
                            ("interrupcao_inicio", "interrupcao temporaria")):
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


# ── nascimento vindo da lista de cadastro do ClickUp ─────────────────────────

#: Nome do campo de data na lista de cadastro de pessoas do ClickUp, que traz o nascimento. Inicio e
#: fim de contrato e ultimo feedback nao estao la: vem de quem cuida dos contratos (confirmado em 14/10/2026).
CAMPO_NASCIMENTO = "Data de nascimento"
COLUNAS_ROSTER = ("nome", "nascimento", "inicio_contrato", "fim_contrato", "interrupcao_inicio", "ultimo_feedback")


def _chave(nome: str) -> str:
    base = unicodedata.normalize("NFKD", nome or "")
    return "".join(c for c in base if not unicodedata.combining(c)).casefold().strip()


def pessoas_do_clickup(tarefas: list[dict], campo: str = CAMPO_NASCIMENTO) -> tuple[list[Pessoa], list[str]]:
    """Nome e nascimento de cada tarefa de uma lista de cadastro. Devolve (pessoas, nomes sem data).

    So dois campos sao lidos: quem e a pessoa e o campo de nascimento. Na lista de cadastro real
    (visto em 15/10/2026) cada tarefa e UMA PESSOA: o nome da tarefa e o nome dela, e o
    responsavel da tarefa e a mesma pessoa para as 17 (quem cuida do cadastro), entao o
    responsavel nao serve para dizer quem e quem. A mesma lista guarda contato de emergencia, e-mail e
    telefone pessoais, endereco e respostas sobre saude; nada disso e lido nem sai daqui, e
    `tests/test_regras_do_abner.py` confere isso.

    O valor da data vem em milissegundos. O ClickUp grava a data sem hora como meia-noite do
    fuso de quem preencheu (visto em 15/10/2026: 03:00, 06:00 e 07:00 UTC), entao a data
    certa e a data em UTC, nunca a do dia anterior.
    """
    pessoas, sem_data = [], []
    for t in tarefas:
        nome = (t.get("name") or "").strip()
        if not nome:
            continue
        valor = next((f.get("value") for f in (t.get("custom_fields") or [])
                      if _chave(f.get("name") or "") == _chave(campo)), None)
        nascimento = None
        if valor not in (None, ""):
            try:
                nascimento = datetime.fromtimestamp(int(valor) / 1000, tz=timezone.utc).date()
            except (TypeError, ValueError, OverflowError, OSError):
                logger.warning("nascimento ilegivel na lista de cadastro de %s", nome)
        if nascimento is None:
            sem_data.append(nome)
        pessoas.append(Pessoa(nome=nome, nascimento=nascimento))
    return pessoas, sem_data


def mesclar(existentes: list[Pessoa], lidas: list[Pessoa]) -> list[Pessoa]:
    """O roster com o nascimento do ClickUp por cima. As outras datas de quem ja estava ficam.

    Casa por nome sem acento e sem caixa. Quem so existe no roster antigo continua nele, porque
    sair do cadastro do ClickUp nao diz que a pessoa saiu do time.
    """
    por_chave = {_chave(p.nome): p for p in existentes}
    for nova in lidas:
        velha = por_chave.get(_chave(nova.nome))
        if velha is None:
            por_chave[_chave(nova.nome)] = nova
        elif nova.nascimento is not None:
            por_chave[_chave(nova.nome)] = replace(velha, nascimento=nova.nascimento)
    return sorted(por_chave.values(), key=lambda p: _chave(p.nome))


def escrever_roster(pessoas: list[Pessoa], caminho: str | Path) -> Path:
    """Grava o roster em CSV com permissao 600, por arquivo temporario, sem deixar meio escrito."""
    destino = Path(caminho).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=".rh-", suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLUNAS_ROSTER)
            for p in pessoas:
                w.writerow([p.nome] + [d.isoformat() if d else "" for d in
                                       (p.nascimento, p.inicio_contrato, p.fim_contrato, p.interrupcao_inicio, p.ultimo_feedback)])
        os.chmod(tmp, 0o600)
        os.replace(tmp, destino)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return destino
