"""Lancar uma proposta aprovada: sobreposicao, duplicata e parada na falha."""

import json

import httpx
import pytest

from soteria_pmo import lancamento as L
from soteria_pmo.clickup import Aprovacao, ClickUp

APROVADO = Aprovacao.de("Jordan Bernardes", "teste")


def item(ini, fim, task="t1", dia="2026-09-25", fat=True):
    return L.Item(dia=dia, ini=ini, fim=fim, task=task, desc=f"Trabalho {ini} (Soteria)",
                  fat=fat, tags=("desenvolvimento",))


class Api:
    """Um ClickUp que guarda entradas e filtra a janela como a API real:
    os dois limites exclusivos (medido em 02/10/2026)."""

    def __init__(self, existentes=(), falhar_conferencia_em=None):
        self.entradas = list(existentes)
        self.posts = 0
        self.falhar_em = falhar_conferencia_em

    def handler(self, request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if request.method == "GET" and p.endswith("/time_entries"):
            a, b = int(request.url.params["start_date"]), int(request.url.params["end_date"])
            return httpx.Response(200, json={"data": [
                e for e in self.entradas if a < int(e["start"]) < b]})
        if request.method == "POST" and p.endswith("/time_entries/tags"):
            corpo = json.loads(request.content)
            for e in self.entradas:
                if e["id"] in corpo["time_entry_ids"]:
                    e["tags"] = corpo["tags"]
            return httpx.Response(200, json={})
        if request.method == "POST" and p.endswith("/time_entries"):
            self.posts += 1
            c = json.loads(request.content)
            e = {"id": f"e{self.posts}", "start": str(c["start"]), "duration": c["duration"],
                 "description": c["description"], "billable": c["billable"],
                 "task": {"id": c["tid"]}, "tags": []}
            if self.posts == self.falhar_em:
                e["description"] = "outra coisa"
            self.entradas.append(e)
            return httpx.Response(200, json={"data": {"id": e["id"]}})
        if request.method == "GET" and "/time_entries/" in p:
            eid = p.rsplit("/", 1)[-1]
            e = next((x for x in self.entradas if x["id"] == eid), None)
            return httpx.Response(200 if e else 404, json={"data": e})
        return httpx.Response(404, json={})

    def cliente(self, dry_run=False):
        http = httpx.Client(transport=httpx.MockTransport(self.handler))
        return ClickUp("tok", "9007", dry_run=dry_run, client=http)


def test_sobreposicao_e_recusada_antes_de_qualquer_chamada():
    api = Api()
    with pytest.raises(ValueError, match="sobreposicao"):
        L.lancar(api.cliente(), [item("09:00", "10:00"), item("09:30", "11:00")], APROVADO)
    assert api.posts == 0


def test_simulacao_nao_escreve():
    api = Api()
    rel = L.lancar(api.cliente(dry_run=True), [item("09:00", "10:00")], APROVADO)
    assert api.posts == 0
    assert len(rel[0].escritos) == 1


def test_escreve_confere_e_pula_o_que_ja_existe_inclusive_a_meia_noite():
    """Rodar de novo depois de um lote parcial nao pode duplicar. A entrada que
    comeca a 00:00 e o caso que a janela exclusiva da API escondia."""
    api = Api()
    itens = [item("00:00", "08:07"), item("08:42", "09:13")]
    L.lancar(api.cliente(), itens, APROVADO)
    assert api.posts == 2
    rel = L.lancar(api.cliente(), itens, APROVADO)
    assert api.posts == 2
    assert len(rel[0].pulados) == 2


def test_para_no_primeiro_resultado_nao_conferido_sem_retentar():
    api = Api(falhar_conferencia_em=1)
    rel = L.lancar(api.cliente(), [item("09:00", "10:00"), item("10:00", "11:00")], APROVADO)
    assert api.posts == 1
    assert rel[-1].parado_em is not None


def test_proposta_sem_faturavel_e_recusada(tmp_path):
    arq = tmp_path / "p.json"
    arq.write_text(json.dumps([{"dia": "2026-09-25", "ini": "09:00", "fim": "10:00",
                                "task": "t1", "desc": "x (Soteria)", "tag": "daily"}]))
    with pytest.raises(ValueError, match="fat"):
        L.ler_proposta(arq)
