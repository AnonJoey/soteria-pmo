"""The four write controls, tested against the failures that produced them.

Every test here names a real incident or a real API behaviour: the four ghost
entries from a retried call, the 16 wrongly billed hours, the tags that never
stuck on the pilot's 97 entries, and the entries that vanished from the report
because they had no description. A control that passes its test but not its
incident is not a control.

Nothing talks to ClickUp: httpx.MockTransport answers every call.
"""

import json

import httpx
import pytest

from delegation_core.pmo.clickup import (
    Aprovacao,
    AprovacaoAusente,
    ClickUp,
    ConferenciaFalhou,
    Lancamento,
    TAGS_DA_CASA,
)

APROVADO = Aprovacao.de("jordan", "lancamento de 02/09")


def bom(**over) -> Lancamento:
    base = dict(task_id="86e31gx8v", inicio_ms=1788332400000, duracao_ms=3_600_000,
                descricao="Desenvolvimento do coletor (Soteria)", faturavel=True,
                tags=("desenvolvimento",))
    base.update(over)
    return Lancamento(**base)


def cliente(handler, *, dry_run=False) -> ClickUp:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, headers={"Authorization": "tok"})
    return ClickUp("tok", "9007", dry_run=dry_run, client=http)


def servidor(*, entry=None, post_status=200, put_status=200, delete_status=200,
             registro=None):
    """A ClickUp that stores one entry and reports what it was asked to do."""
    estado = {"entry": entry, "chamadas": registro if registro is not None else []}

    def handler(request: httpx.Request) -> httpx.Response:
        estado["chamadas"].append((request.method, request.url.path))
        if request.method == "POST" and "time_entries" in request.url.path:
            corpo = json.loads(request.content)
            estado["entry"] = {
                "id": "te_1", "description": corpo.get("description"),
                "billable": corpo.get("billable"), "duration": corpo.get("duration"),
                "tags": [], "task": {"id": corpo.get("tid")},
            }
            return httpx.Response(post_status, json={"data": {"id": "te_1"}})
        if request.method == "PUT":
            corpo = json.loads(request.content)
            if estado["entry"] is not None and put_status < 400:
                if "tags" in corpo:
                    estado["entry"]["tags"] = corpo["tags"]
                for campo, chave in (("description", "description"), ("billable", "billable")):
                    if campo in corpo:
                        estado["entry"][chave] = corpo[campo]
            return httpx.Response(put_status, json={"data": estado["entry"]})
        if request.method == "DELETE":
            if delete_status < 400:
                estado["entry"] = None
            return httpx.Response(delete_status, json={})
        if request.method == "GET":
            if estado["entry"] is None:
                return httpx.Response(404, json={"err": "nao existe"})
            return httpx.Response(200, json={"data": estado["entry"]})
        return httpx.Response(404, json={})

    return handler, estado


# ── controle 1: conferencia obrigatoria depois de escrever ───────────────────


def test_chamada_que_falha_mas_grava_e_detectada_em_vez_de_retentada():
    """The incident: the call errored, the entry existed, the retry made a ghost.

    The POST answers 500 and records the entry anyway. A client that trusts the
    status code reports failure, the caller retries, and now there are two.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(500, json={"err": "boom"})
        if request.method == "GET" and request.url.path.endswith("/time_entries"):
            # The entry the failed call wrote anyway.
            return httpx.Response(200, json={"data": [
                {"id": "fantasma_1", "duration": 3_600_000,
                 "task": {"id": "86e31gx8v"}},
            ]})
        return httpx.Response(200, json={"data": {
            "id": "fantasma_1", "description": "Desenvolvimento do coletor (Soteria)",
            "billable": True, "tags": [{"name": "desenvolvimento"}],
        }})

    r = cliente(handler).lancar(bom(), APROVADO)
    assert r.entry_id == "fantasma_1"
    assert r.escrito, "a entrada existe: reportar falha convidaria a retentativa"


def test_entrada_que_nao_le_de_volta_levanta_em_vez_de_retornar():
    handler, estado = servidor()

    def some_depois_do_post(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "te_1"}})
        return httpx.Response(404, json={"err": "sumiu"})

    with pytest.raises(ConferenciaFalhou) as e:
        cliente(some_depois_do_post).lancar(bom(), APROVADO)
    assert e.value.entry_id == "te_1", "o id tem que vir junto para permitir conserto"


def test_divergencia_entre_pedido_e_gravado_aparece_no_resultado():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "te_1"}})
        if request.method == "PUT":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"data": {
            "id": "te_1", "description": "outra coisa", "billable": False, "tags": [],
        }})

    r = cliente(handler).lancar(bom(), APROVADO)
    assert r.escrito and not r.conferido
    assert any("descricao" in d for d in r.divergencias)
    assert any("faturavel" in d for d in r.divergencias)
    assert any("tags" in d for d in r.divergencias)


# ── controle 2: faturavel sempre explicito ───────────────────────────────────


def test_faturavel_nao_tem_default():
    """Omitting billable in the API records non-billable, invisibly."""
    with pytest.raises(TypeError):
        Lancamento(task_id="t", inicio_ms=0, duracao_ms=1000,
                   descricao="x", tags=())  # type: ignore[call-arg]


def test_billable_vai_no_corpo_do_post_sempre():
    enviado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            enviado.update(json.loads(request.content))
            return httpx.Response(200, json={"data": {"id": "te_1"}})
        if request.method == "PUT":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"data": {
            "id": "te_1", "description": bom().descricao, "billable": True,
            "tags": [{"name": "desenvolvimento"}]}})

    cliente(handler).lancar(bom(), APROVADO)
    assert "billable" in enviado and enviado["billable"] is True


def test_daily_marcada_faturavel_e_recusada_antes_de_sair():
    r = cliente(lambda rq: httpx.Response(500)).lancar(
        bom(tags=("daily",), faturavel=True), APROVADO)
    assert not r.escrito
    assert any("nao faturavel" in d for d in r.divergencias)


# ── controle 3: escrita precedida de aprovacao ───────────────────────────────


def test_lancar_sem_aprovacao_levanta():
    with pytest.raises(AprovacaoAusente):
        cliente(lambda rq: httpx.Response(200)).lancar(bom(), None)


def test_corrigir_e_remover_tambem_exigem_aprovacao():
    c = cliente(lambda rq: httpx.Response(200))
    with pytest.raises(AprovacaoAusente):
        c.corrigir("te_1", None, descricao="x")
    with pytest.raises(AprovacaoAusente):
        c.remover("te_1", None)


def test_aprovacao_registra_quem_e_o_escopo():
    a = Aprovacao.de("jordan", "periodo 15/07 a 07/08")
    assert a.quem == "jordan" and a.escopo == "periodo 15/07 a 07/08"
    with pytest.raises(Exception):
        a.quem = "outro"  # type: ignore[misc]


# ── controle 4: tags em etapa separada, no formato que grava ─────────────────


def test_tags_vao_num_put_separado_como_objeto_nao_string():
    """Strings are what made tags silently not stick on the pilot's 97 entries."""
    handler, estado = servidor()
    c = cliente(handler)
    c.lancar(bom(tags=("desenvolvimento",)), APROVADO)
    assert estado["entry"]["tags"] == [
        {"name": "desenvolvimento", "tag_fg": "#FFFFFF", "tag_bg": "#BF55EC"}
    ]
    assert ("PUT", "/api/v2/team/9007/time_entries/te_1") in estado["chamadas"]


def test_o_post_nao_leva_tags():
    """The create call's accepted shape and the tags' shape are not the same."""
    enviado = {}
    handler, _ = servidor()

    def espiao(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            enviado.update(json.loads(request.content))
        return handler(request)

    cliente(espiao).lancar(bom(), APROVADO)
    assert "tags" not in enviado


def test_tag_fora_do_vocabulario_da_casa_e_recusada():
    r = cliente(lambda rq: httpx.Response(500)).lancar(bom(tags=("gambiarra",)), APROVADO)
    assert not r.escrito
    assert any("vocabulario" in d for d in r.divergencias)


def test_o_vocabulario_tem_as_13_tags():
    assert len(TAGS_DA_CASA) == 13


# ── validacao antes de qualquer chamada ──────────────────────────────────────


def test_descricao_vazia_e_recusada_porque_some_do_relatorio():
    r = cliente(lambda rq: httpx.Response(500)).lancar(bom(descricao="   "), APROVADO)
    assert not r.escrito
    assert any("relatorio" in d for d in r.divergencias)


def test_duracao_zero_ou_negativa_e_recusada():
    for d in (0, -1000):
        r = cliente(lambda rq: httpx.Response(500)).lancar(bom(duracao_ms=d), APROVADO)
        assert not r.escrito


def test_lancamento_invalido_nao_faz_nenhuma_chamada():
    chamadas = []
    cliente(lambda rq: (chamadas.append(rq.method), httpx.Response(500))[1]).lancar(
        bom(descricao=""), APROVADO)
    assert chamadas == []


# ── dry run: o padrao ────────────────────────────────────────────────────────


def test_dry_run_e_o_padrao_e_nao_faz_chamada():
    chamadas = []
    http = httpx.Client(transport=httpx.MockTransport(
        lambda rq: (chamadas.append(rq.method), httpx.Response(200, json={}))[1]))
    c = ClickUp("tok", "9007", client=http)
    assert c.dry_run is True
    r = c.lancar(bom(), APROVADO)
    assert not r.escrito and "dry_run" in r.detalhe
    assert chamadas == []


# ── o caminho de correcao que a premissa antiga dizia nao existir ────────────


def test_corrigir_grava_descricao_e_confere():
    handler, estado = servidor(entry={
        "id": "te_1", "description": "", "billable": False, "tags": []})
    r = cliente(handler).corrigir("te_1", APROVADO, descricao="Daily (Soteria)")
    assert r.escrito and r.conferido
    assert estado["entry"]["description"] == "Daily (Soteria)"


def test_corrigir_aplica_tags_no_formato_de_objeto():
    handler, estado = servidor(entry={
        "id": "te_1", "description": "x", "billable": True, "tags": []})
    r = cliente(handler).corrigir("te_1", APROVADO, tags=("daily",))
    assert r.escrito
    assert estado["entry"]["tags"][0]["name"] == "daily"


def test_corrigir_recusa_tag_invalida_sem_chamar():
    chamadas = []
    handler, _ = servidor(entry={"id": "te_1", "description": "x",
                                 "billable": True, "tags": []}, registro=chamadas)
    r = cliente(handler).corrigir("te_1", APROVADO, tags=("inventada",))
    assert not r.escrito
    assert chamadas == []


def test_remover_confere_que_sumiu():
    handler, estado = servidor(entry={"id": "te_1", "description": "x",
                                      "billable": True, "tags": []})
    r = cliente(handler).remover("te_1", APROVADO)
    assert r.escrito and r.conferido
    assert estado["entry"] is None


def test_remover_que_nao_removeu_levanta():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"data": {"id": "te_1"}})  # continua la

    with pytest.raises(ConferenciaFalhou):
        cliente(handler).remover("te_1", APROVADO)


def test_corrigir_sem_nada_para_mudar_nao_chama():
    chamadas = []
    handler, _ = servidor(entry={"id": "te_1"}, registro=chamadas)
    r = cliente(handler).corrigir("te_1", APROVADO)
    assert not r.escrito and "nada a corrigir" in r.detalhe
    assert chamadas == []


# ── leitura ──────────────────────────────────────────────────────────────────




def test_tarefas_da_lista_segue_a_paginacao_ate_o_fim():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", 0))
        if page == 0:
            return httpx.Response(200, json={"tasks": [{"id": f"t{i}"} for i in range(100)],
                                             "last_page": False})
        return httpx.Response(200, json={"tasks": [{"id": "t100"}], "last_page": True})

    assert len(cliente(handler).tarefas_da_lista("901716443542")) == 101


# ── defeitos que a revisao do modelo local encontrou ─────────────────────────


def test_falha_nas_tags_nao_escapa_com_a_entrada_ja_gravada():
    """O fantasma de novo, por outra porta.

    Nesta altura a entrada existe. Deixar o timeout do PUT subir entrega ao
    chamador uma excecao sem id nenhum, que e exatamente o estado em que uma
    escrita aconteceu e ninguem sabe: o proximo passo e retentar e duplicar.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "te_1"}})
        if request.method == "PUT":
            raise httpx.TimeoutException("timeout no PUT de tags")
        return httpx.Response(200, json={"data": {
            "id": "te_1", "description": bom().descricao, "billable": True, "tags": []}})

    r = cliente(handler).lancar(bom(), APROVADO)
    assert r.entry_id == "te_1", "o chamador precisa do id para conferir ou consertar"
    assert r.escrito and not r.conferido
    assert any("tags" in d for d in r.divergencias)


def test_paginacao_sem_last_page_para_em_vez_de_girar_para_sempre():
    """O unico jeito de sair do laco era last_page ou lote vazio."""
    paginas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        paginas["n"] += 1
        return httpx.Response(200, json={"tasks": [{"id": f"t{paginas['n']}"}]})

    tarefas = cliente(handler).tarefas_da_lista("901716443542", max_paginas=5)
    assert paginas["n"] == 5 and len(tarefas) == 5
