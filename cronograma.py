"""Item 2: schedule follow-up.

Watches whether work is moving and raises escalating alerts when it is not.
Two constraints from the meetings shape it, and both are about not crying wolf.

The first is that **cadence is not uniform across developers**. Each one has
their own rhythm, and with a single ruler the agent marks as abandoned a task
that is simply following another pace. So a Cadencia is per person, and a
person with no calibration yet gets alerts labelled as uncalibrated rather than
a default ruler applied silently. Confirming the calibration with Abner is
still open, so `CADENCIA_PADRAO` is a placeholder that says so in its own
docstring rather than a number pretending to be measured.

The second is that this agent cannot tell "the task stopped" from "the task
moved and nobody logged it". Both look like silence in ClickUp. Every alert
therefore states the ambiguity it could not resolve instead of picking the
accusatory reading, because an alert that says "abandoned" about someone who
was working is the fastest way to get the whole system turned off.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from .periodo import de_ms, dias_uteis

logger = logging.getLogger("pmo.cronograma")

# Escalation, in business days of silence. Levels rather than one threshold so
# a first nudge is cheap and a real escalation is rare.
NIVEIS = ((10, "escalar"), (5, "cobranca"), (3, "lembrete"))

# Placeholder, NOT a measurement. The real per-person calibration is an open
# question with Abner. Anything scored against this is reported as
# uncalibrated so nobody mistakes the default for a measured pace.
CADENCIA_PADRAO_DIAS = 3


@dataclass(frozen=True)
class Cadencia:
    """One person's working rhythm, as calibrated with them.

    `dias_entre_toques` is how long this person normally goes between touching
    a task before it means anything. Someone who batches a week of work into
    Friday is not late on Wednesday.
    """

    pessoa: str
    dias_entre_toques: int
    calibrada: bool = True
    observacao: str = ""

    @classmethod
    def nao_calibrada(cls, pessoa: str) -> "Cadencia":
        return cls(pessoa=pessoa, dias_entre_toques=CADENCIA_PADRAO_DIAS,
                   calibrada=False,
                   observacao="sem calibragem: regua padrao aplicada, "
                              "confirmar o ritmo desta pessoa com o Abner")


@dataclass
class Divergencia:
    """A task that has gone quiet, with what the data cannot say about it."""

    task_id: str
    nome: str
    pessoa: str
    status: str
    dias_em_silencio: int
    nivel: str
    cadencia: Cadencia
    vence_em: date | None = None
    ambiguidade: str = ""
    notas: list[str] = field(default_factory=list)

    @property
    def atrasada(self) -> bool:
        return self.vence_em is not None and self.vence_em < date.today()

    def linha(self) -> str:
        base = (f"[{self.nivel}] {self.nome} ({self.pessoa}, {self.status}): "
                f"{self.dias_em_silencio} dias uteis sem toque")
        if not self.cadencia.calibrada:
            base += " [ritmo nao calibrado]"
        if self.vence_em:
            base += f", vence {self.vence_em:%d/%m}"
        return base


def _nivel(silencio: int, cadencia: Cadencia) -> str | None:
    """Escalation level, scaled by this person's own rhythm.

    The thresholds are multiples of the person's cadence rather than fixed
    days: three days of silence means something different for someone who
    touches a task daily and someone who batches weekly.
    """
    fator = max(cadencia.dias_entre_toques, 1) / CADENCIA_PADRAO_DIAS
    for limite, nome in NIVEIS:
        if silencio >= limite * fator:
            return nome
    return None


def avaliar(tarefas: list[dict], cadencias: dict[str, Cadencia], hoje: date,
            feriados: frozenset[date] = frozenset()) -> list[Divergencia]:
    """Score every open task against its owner's rhythm."""
    divergencias: list[Divergencia] = []

    for t in tarefas:
        status = t.get("status")
        nome_status = (status.get("status") if isinstance(status, dict) else status) or "?"
        if nome_status.strip().lower() in {"complete", "concluido", "done", "closed"}:
            continue

        responsaveis = t.get("assignees") or []
        pessoa = responsaveis[0].get("username") if responsaveis else "sem responsavel"
        cadencia = cadencias.get(pessoa) or Cadencia.nao_calibrada(pessoa)

        tocado = de_ms(t.get("date_updated")) or de_ms(t.get("date_created"))
        if tocado is None:
            continue
        silencio = max(dias_uteis(tocado.date(), hoje, feriados) - 1, 0)

        nivel = _nivel(silencio, cadencia)
        if nivel is None:
            continue

        vence = de_ms(t.get("due_date"))
        notas = []
        if not cadencia.calibrada:
            notas.append(cadencia.observacao)
        if t.get("time_estimate") in (None, 0, "0"):
            notas.append("sem estimativa de tempo: nao da para dizer se o silencio "
                         "e compativel com o tamanho da tarefa")

        divergencias.append(Divergencia(
            task_id=str(t.get("id")),
            nome=t.get("name") or "(sem nome)",
            pessoa=pessoa,
            status=nome_status,
            dias_em_silencio=silencio,
            nivel=nivel,
            cadencia=cadencia,
            vence_em=vence.date() if vence else None,
            # Stated on every alert, never resolved by guessing.
            ambiguidade="o card ficou parado; isso pode ser trabalho que nao "
                        "andou ou trabalho que andou e nao foi apontado, e este "
                        "agente nao consegue separar os dois",
            notas=notas,
        ))

    ordem = {"escalar": 0, "cobranca": 1, "lembrete": 2}
    return sorted(divergencias, key=lambda d: (ordem[d.nivel], -d.dias_em_silencio))


def log_de_divergencias(divergencias: list[Divergencia], hoje: date) -> str:
    """The simple divergence log the plan settled on, not a dashboard."""
    if not divergencias:
        return ""
    linhas = [f"Acompanhamento de cronograma, {hoje:%d/%m}", ""]
    for d in divergencias:
        linhas.append(f"  {d.linha()}")
        for n in d.notas:
            linhas.append(f"      {n}")
    nao_calibradas = {d.pessoa for d in divergencias if not d.cadencia.calibrada}
    linhas.append("")
    linhas.append(f"  Leitura: {divergencias[0].ambiguidade}.")
    if nao_calibradas:
        linhas.append(f"  Sem ritmo calibrado: {', '.join(sorted(nao_calibradas))}. "
                      "Ate calibrar, estes alertas usam a regua padrao e podem estar "
                      "cobrando quem so trabalha em outro ritmo.")
    return "\n".join(linhas)


def acompanhar(cliente, list_id: str, cadencias: dict[str, Cadencia], hoje: date,
               feriados: frozenset[date] = frozenset()) -> str:
    """Read a list and produce today's divergence log."""
    try:
        tarefas = cliente.tarefas_da_lista(list_id)
    except Exception as e:
        logger.warning("nao foi possivel ler a lista %s: %s", list_id, e)
        return ""
    return log_de_divergencias(avaliar(tarefas, cadencias, hoje, feriados), hoje)
