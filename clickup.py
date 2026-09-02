"""ClickUp client for the PMO agents, with the write controls built into the type.

Four controls came out of a real incident: retrying a call that had failed on
its tag step created four ghost entries and 16 wrongly billed hours. They are
not comments here, they are the shape of the API. A caller cannot write an
entry without saying whether it is billable, cannot write without an approval,
and cannot get a "written" result back without the read-back having happened.

One premise the project carried since 07/08 is wrong and is corrected here.
"There is no editing or deleting a time entry" described the MCP connector, not
ClickUp: `PUT` and `DELETE` on /v2/team/{team}/time_entries/{id} both exist, and
the PUT takes description, billable and tags. So a wrong entry is repairable,
and `update_time_entry`/`delete_time_entry` are the repair path. Human approval
before writing stays required, for the reason that actually holds: hours become
an invoice, and the person is the only source for the share of them that machine
evidence never sees. Not because a mistake would be permanent.

Nothing here writes unless `dry_run` is False. The default is True.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

import httpx

logger = logging.getLogger("pmo.clickup")

API = "https://api.clickup.com/api/v2"

# The house vocabulary, copied verbatim from Marcos Claudio's entries as
# recorded in Reference/2026-07-30-Formato de lancamento de atividades no
# ClickUp. Accents included, because these strings have to match what is in
# ClickUp and not merely look like it. Closed on purpose: a tag outside this
# set is a typo, and a typo silently makes an entry invisible in the report
# everyone reads.
TAGS_DA_CASA = frozenset({
    "desenvolvimento", "ajustes em qas", "análise", "atividade de qas",
    "apoio técnico", "alinhamento técnico", "planejamento", "reunião interna",
    "reunião com o cliente", "daily", "elaboração de material técnico",
    "deploy", "bug",
})

# Tags the house never bills. Diverging from this shows up in the comparison
# between reports, which is where it gets noticed and costs credibility.
NAO_FATURAVEL = frozenset({"daily", "reunião interna"})

# Explicitly billable, recorded because the first reading of the convention
# guessed wrong on these three: meeting a client, a technical alignment and
# technical support are all billed.
FATURAVEL = frozenset({"reunião com o cliente", "alinhamento técnico", "apoio técnico"})

# The one activity whose tag does not decide it. Logging hours carries the
# `planejamento` tag and is not billable, while everything else tagged
# `planejamento` is. A tag-only rule bills the act of billing.
ATIVIDADE_NAO_FATURAVEL = "lançamento clickup"

# The status workflow of the "AI - Claude" folder, in order, as recorded in
# Reference/2026-07-30-Formato de lancamento de atividades no ClickUp. It is a
# development workflow and not a generic activity one, so the terminal state is
# `publicado/finalizado` and nothing here is called "done" or "complete".
#
# Worth stating because the first version of this file guessed: it used
# complete/concluido/done/closed, none of which exist in this workspace, which
# would have reported every finished task as open and kept the schedule agent
# chasing work that shipped.
WORKFLOW = (
    "ideia", "proposta de solução", "aprovação com cliente", "planejamento técnico",
    "backlog", "desenvolvimento", "homologação", "bloqueado",
    "aguardando deploy", "publicado/finalizado",
)

# Work is over here and nowhere earlier.
CONCLUIDOS = frozenset({"publicado/finalizado"})

# Not late, waiting on something. A blocked task going quiet is expected, so
# the schedule agent must not read it as neglect.
BLOQUEADOS = frozenset({"bloqueado"})


def status_normalizado(status) -> str:
    """The status name, from either shape ClickUp uses, lowercased.

    ClickUp returns a dict on a task and a bare string in some listings, and
    picking one shape is how a status silently becomes "?".
    """
    if isinstance(status, dict):
        status = status.get("status")
    return (status or "").strip().lower()


def concluida(status) -> bool:
    return status_normalizado(status) in CONCLUIDOS


def bloqueada(status) -> bool:
    return status_normalizado(status) in BLOQUEADOS


class ClickUpError(RuntimeError):
    """A call that failed in a way the caller has to see."""


class AprovacaoAusente(ClickUpError):
    """A write was attempted with no human approval attached."""


class ConferenciaFalhou(ClickUpError):
    """The entry was written but did not read back as expected.

    Raised rather than returned: a caller that ignores a return value would
    leave exactly the ghost this class exists to surface. The entry id is on
    the exception so the caller can repair instead of guessing.
    """

    def __init__(self, msg: str, entry_id: str | None = None):
        super().__init__(msg)
        self.entry_id = entry_id


@dataclass(frozen=True)
class Aprovacao:
    """Evidence that a person said yes to this specific write.

    Frozen and carrying who and when, so an approval cannot be built once and
    quietly reused for a different entry: `escopo` names what was approved.
    """

    quem: str
    quando: float
    escopo: str

    @classmethod
    def de(cls, quem: str, escopo: str) -> "Aprovacao":
        return cls(quem=quem, quando=time.time(), escopo=escopo)


@dataclass(frozen=True)
class Lancamento:
    """One time entry to be written. `faturavel` has no default on purpose.

    Omitting billable in the ClickUp API records the entry as non-billable, and
    that default is invisible: the entry appears, the hours do not bill, and
    nobody finds out until the month closes. Making it a required field moves
    that decision to where it is being made.
    """

    task_id: str
    inicio_ms: int
    duracao_ms: int
    descricao: str
    faturavel: bool
    tags: tuple[str, ...] = ()

    def problemas(self) -> list[str]:
        """Everything wrong with this entry, before anything is sent."""
        erros: list[str] = []
        if not self.descricao.strip():
            # The time entry's description is the row label in the billable
            # hours report. Without it the work is invisible to whoever reads
            # that report, which is how the first pilot lost its early days.
            erros.append("descricao vazia: a entrada some do relatorio de horas")
        if self.duracao_ms <= 0:
            erros.append(f"duracao invalida: {self.duracao_ms}ms")
        desconhecidas = set(self.tags) - TAGS_DA_CASA
        if desconhecidas:
            erros.append(f"tags fora do vocabulario da casa: {sorted(desconhecidas)}")
        cobrando_o_que_nao_cobra = set(self.tags) & NAO_FATURAVEL
        if self.faturavel and cobrando_o_que_nao_cobra:
            erros.append(
                f"marcado faturavel com tag nao faturavel: {sorted(cobrando_o_que_nao_cobra)}"
            )
        return erros


@dataclass
class Resultado:
    """What a write actually did, including whether it was read back."""

    entry_id: str | None
    escrito: bool
    conferido: bool
    detalhe: str = ""
    divergencias: list[str] = field(default_factory=list)


def _tag_payload(nomes: Iterable[str]) -> list[dict[str, str]]:
    """ClickUp wants tag objects, not strings.

    Sending strings is what made tags silently not stick on the pilot's 97
    entries. The colours are required by the schema and carry no meaning here.
    """
    return [{"name": n, "tag_fg": "#FFFFFF", "tag_bg": "#BF55EC"} for n in nomes]


class ClickUp:
    """Thin client. Reads freely, writes only under the four controls."""

    def __init__(self, token: str, team_id: str, *, dry_run: bool = True,
                 client: httpx.Client | None = None, timeout: float = 30.0):
        if not token:
            raise ValueError("token do ClickUp vazio")
        self.team_id = team_id
        self.dry_run = dry_run
        self._own_client = client is None
        self._c = client or httpx.Client(
            timeout=timeout,
            headers={"Authorization": token, "Content-Type": "application/json"},
        )

    def close(self) -> None:
        if self._own_client:
            self._c.close()

    def __enter__(self) -> "ClickUp":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── leitura ──────────────────────────────────────────────────────────────

    def _get(self, path: str, **params) -> dict[str, Any]:
        r = self._c.get(f"{API}{path}", params=params or None)
        if r.status_code >= 400:
            raise ClickUpError(f"GET {path} devolveu {r.status_code}: {r.text[:300]}")
        return r.json()

    def entradas(self, inicio_ms: int, fim_ms: int,
                 assignee: str = "any") -> list[dict[str, Any]]:
        """Time entries in a window.

        `assignee="any"` by default: without it the API answers with only the
        authenticated user's entries, which reads as "the team logged nothing"
        rather than as a filter that was applied.
        """
        data = self._get(f"/team/{self.team_id}/time_entries",
                         start_date=inicio_ms, end_date=fim_ms, assignee=assignee)
        return data.get("data", [])

    def entrada(self, entry_id: str) -> dict[str, Any] | None:
        try:
            return self._get(f"/team/{self.team_id}/time_entries/{entry_id}").get("data")
        except ClickUpError:
            return None

    def tarefa(self, task_id: str) -> dict[str, Any]:
        return self._get(f"/task/{task_id}")

    def tarefas_da_lista(self, list_id: str, incluir_fechadas: bool = True,
                         subtarefas: bool = True,
                         max_paginas: int = 100) -> list[dict[str, Any]]:
        """Every task in a list, following pagination to the end.

        The endpoint pages at 100 and answers `last_page`. Reading only the
        first page is the kind of bug that looks like a small list.

        `max_paginas` bounds the walk. The loop's only exits are `last_page`
        and an empty batch, so an endpoint that stops sending `last_page` while
        still answering with rows spins forever, and it does it against a
        remote API. Ten thousand tasks is far past any real list here, so
        hitting the cap means something is wrong and it is logged as such.
        """
        tarefas: list[dict[str, Any]] = []
        for page in range(max_paginas):
            data = self._get(f"/list/{list_id}/task", page=page,
                             include_closed=str(incluir_fechadas).lower(),
                             subtasks=str(subtarefas).lower())
            lote = data.get("tasks", [])
            tarefas.extend(lote)
            if data.get("last_page") or not lote:
                return tarefas
        logger.warning(
            "lista %s passou de %d paginas sem sinalizar last_page: parando em %d "
            "tarefas, o resultado pode estar incompleto",
            list_id, max_paginas, len(tarefas))
        return tarefas

    # ── escrita, sob os quatro controles ─────────────────────────────────────

    def lancar(self, l: Lancamento, aprovacao: Aprovacao | None) -> Resultado:
        """Write one time entry: validate, approve, write, read back.

        The read-back is the control that matters most, because a call that
        fails partway still records the entry. Without reading it back, a
        failed call and a successful one are indistinguishable from here, and
        retrying the "failed" one is what produced the ghosts.
        """
        problemas = l.problemas()
        if problemas:
            return Resultado(None, False, False,
                             detalhe="lancamento invalido", divergencias=problemas)

        if aprovacao is None:
            raise AprovacaoAusente(
                f"lancamento em {l.task_id} sem aprovacao: horas viram cobranca, "
                "a escrita exige uma pessoa dizendo sim"
            )

        if self.dry_run:
            return Resultado(None, False, False,
                             detalhe=f"dry_run: escreveria {l.duracao_ms}ms em {l.task_id} "
                                     f"(faturavel={l.faturavel}, aprovado por {aprovacao.quem})")

        corpo = {
            "tid": l.task_id,
            "start": l.inicio_ms,
            "duration": l.duracao_ms,
            "description": l.descricao,
            # Always sent. Omitting it is recorded as non-billable, silently.
            "billable": l.faturavel,
        }
        r = self._c.post(f"{API}/team/{self.team_id}/time_entries", json=corpo)
        # Deliberately not raising on a bad status: a failed call may still have
        # written. The read-back below is what decides, not the status code.
        entry_id = None
        try:
            entry_id = (r.json().get("data") or {}).get("id")
        except Exception:
            pass
        if r.status_code >= 400 and entry_id is None:
            entry_id = self._procurar_entrada(l)

        if entry_id is None:
            return Resultado(None, False, False,
                             detalhe=f"POST devolveu {r.status_code} e nada foi encontrado "
                                     f"na conferencia: provavelmente nao gravou")

        # Tags in a separate step, and only after the entry exists: the format
        # the create call accepts and the one tags need are not the same, and a
        # create that fails on its tags still writes the entry.
        #
        # The failure here must not escape. By this line the entry is written,
        # so letting a timeout propagate hands the caller an exception carrying
        # no entry id, which is exactly the state that produced the four ghosts:
        # the write happened and the caller has no way to know. Swallow it into
        # the read-back, which reports what is actually there.
        if l.tags:
            try:
                self._aplicar_tags(entry_id, l.tags)
            except Exception as e:
                logger.warning("entrada %s gravada mas as tags falharam: %s", entry_id, e)

        return self._conferir(entry_id, l)

    def _procurar_entrada(self, l: Lancamento) -> str | None:
        """Look for an entry a failed call may have written anyway."""
        try:
            janela = self.entradas(l.inicio_ms - 60_000, l.inicio_ms + l.duracao_ms + 60_000)
        except ClickUpError:
            return None
        for e in janela:
            if (e.get("task") or {}).get("id") == l.task_id and \
                    abs(int(e.get("duration", 0)) - l.duracao_ms) < 1000:
                logger.warning("chamada falhou mas a entrada %s existe", e.get("id"))
                return str(e.get("id"))
        return None

    def _aplicar_tags(self, entry_id: str, tags: Iterable[str]) -> None:
        self._c.put(
            f"{API}/team/{self.team_id}/time_entries/{entry_id}",
            json={"tags": _tag_payload(tags), "tag_action": "replace"},
        )

    def _conferir(self, entry_id: str, l: Lancamento) -> Resultado:
        """Read the entry back and compare it to what was asked for."""
        lido = self.entrada(entry_id)
        if lido is None:
            raise ConferenciaFalhou(
                f"entrada {entry_id} nao foi encontrada na conferencia", entry_id)

        divergencias: list[str] = []
        if (lido.get("description") or "").strip() != l.descricao.strip():
            divergencias.append(
                f"descricao gravada {lido.get('description')!r} != {l.descricao!r}")
        if bool(lido.get("billable")) != l.faturavel:
            divergencias.append(
                f"faturavel gravado {lido.get('billable')} != {l.faturavel}")
        gravadas = {t.get("name") for t in (lido.get("tags") or [])}
        if set(l.tags) - gravadas:
            divergencias.append(f"tags nao gravadas: {sorted(set(l.tags) - gravadas)}")

        return Resultado(entry_id, escrito=True, conferido=not divergencias,
                         detalhe="gravado e conferido" if not divergencias
                                 else "gravado com divergencia",
                         divergencias=divergencias)

    def corrigir(self, entry_id: str, aprovacao: Aprovacao | None, *,
                 descricao: str | None = None, faturavel: bool | None = None,
                 tags: tuple[str, ...] | None = None,
                 acao_tags: Literal["replace", "add", "remove"] = "replace") -> Resultado:
        """Repair an entry that was written wrong. This is the path that the
        "the API cannot edit" premise wrongly said did not exist."""
        if aprovacao is None:
            raise AprovacaoAusente(f"correcao de {entry_id} sem aprovacao")
        corpo: dict[str, Any] = {}
        if descricao is not None:
            corpo["description"] = descricao
        if faturavel is not None:
            corpo["billable"] = faturavel
        if tags is not None:
            desconhecidas = set(tags) - TAGS_DA_CASA
            if desconhecidas:
                return Resultado(entry_id, False, False, detalhe="tags invalidas",
                                 divergencias=[f"fora do vocabulario: {sorted(desconhecidas)}"])
            corpo["tags"] = _tag_payload(tags)
            corpo["tag_action"] = acao_tags
        if not corpo:
            return Resultado(entry_id, False, False, detalhe="nada a corrigir")

        if self.dry_run:
            return Resultado(entry_id, False, False,
                             detalhe=f"dry_run: corrigiria {entry_id} com {sorted(corpo)}")

        r = self._c.put(f"{API}/team/{self.team_id}/time_entries/{entry_id}", json=corpo)
        if r.status_code >= 400:
            return Resultado(entry_id, False, False,
                             detalhe=f"PUT devolveu {r.status_code}: {r.text[:200]}")
        lido = self.entrada(entry_id)
        if lido is None:
            raise ConferenciaFalhou(f"entrada {entry_id} sumiu depois da correcao", entry_id)
        divergencias = []
        if descricao is not None and (lido.get("description") or "").strip() != descricao.strip():
            divergencias.append("descricao nao gravou")
        if faturavel is not None and bool(lido.get("billable")) != faturavel:
            divergencias.append("faturavel nao gravou")
        return Resultado(entry_id, True, not divergencias,
                         detalhe="corrigido", divergencias=divergencias)

    def remover(self, entry_id: str, aprovacao: Aprovacao | None) -> Resultado:
        """Delete an entry. Used to clear a ghost, never as routine cleanup."""
        if aprovacao is None:
            raise AprovacaoAusente(f"remocao de {entry_id} sem aprovacao")
        if self.dry_run:
            return Resultado(entry_id, False, False, detalhe=f"dry_run: removeria {entry_id}")
        r = self._c.delete(f"{API}/team/{self.team_id}/time_entries/{entry_id}")
        if r.status_code >= 400:
            return Resultado(entry_id, False, False,
                             detalhe=f"DELETE devolveu {r.status_code}")
        if self.entrada(entry_id) is not None:
            raise ConferenciaFalhou(f"entrada {entry_id} ainda existe apos o DELETE", entry_id)
        return Resultado(entry_id, True, True, detalhe="removido e conferido")
