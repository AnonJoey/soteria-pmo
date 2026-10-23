"""test_faturaveis_e_resiliencia.py — Testes das correções de resiliência e filtro faturável."""

import httpx
import pytest
from datetime import date

from soteria_pmo.clickup import ClickUp, ClickUpError
from soteria_pmo.bolsao import Bolsao, apurar, Situacao
from soteria_pmo import painel


def test_clickup_get_retry_em_timeout_e_sucesso_na_segunda_tentativa():
    tentativas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tentativas
        tentativas += 1
        if tentativas == 1:
            raise httpx.ReadTimeout("The read operation timed out")
        return httpx.Response(200, json={"teams": [{"id": "9007", "members": [{"user": {"id": "1", "username": "max"}}]}]})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    c = ClickUp("token_fake", "9007", dry_run=True, client=http)

    membros = c.membros()
    assert len(membros) == 1
    assert membros[0]["username"] == "max"
    assert tentativas == 2  # Provou que retentou e recuperou do timeout


def test_bolsao_somente_faturaveis_ignora_horas_nao_faturaveis_do_abner():
    bolsao = Bolsao(projeto="Grupo Angelus", list_id="900902364226", horas_contratadas=160.0)
    inicio = date(2026, 10, 1)
    fim = date(2026, 10, 23)

    entradas = [
        # 100h faturáveis de devs
        {"duration": str(int(100 * 3_600_000)), "billable": True, "task": {"list_id": "900902364226"}},
        # 36h não faturáveis lançadas pelo Abner
        {"duration": str(int(36 * 3_600_000)), "billable": False, "task": {"list_id": "900902364226"}},
    ]

    # Sem filtro (comportamento anterior): 136h (85%) [atencao]
    sit_todas = apurar(entradas, bolsao, inicio, fim, somente_faturaveis=False)
    assert sit_todas.horas_gastas == 136.0
    assert sit_todas.nivel == "atencao"

    # Com filtro somente_faturaveis (novo): 100h (62.5%) [ok]
    sit_fat = apurar(entradas, bolsao, inicio, fim, somente_faturaveis=True)
    assert sit_fat.horas_gastas == 100.0
    assert sit_fat.nivel == "ok"
    assert "h faturáveis de 160h" in sit_fat.linha()


def test_painel_dados_separam_sust_fat_e_impl_fat():
    from datetime import datetime, timezone
    hoje = date(2026, 10, 23)
    start_ms = str(int(datetime(2026, 10, 15, 12, tzinfo=timezone.utc).timestamp() * 1000))
    projeto = {
        "nome": "Cliente Teste",
        "space_id": "123",
        "horas_contratadas": 100,
        "tipo": "chamado",
        "listas_sustentacao": ["list_sust"]
    }

    class FakeClient:
        def membros(self):
            return [{"id": "1", "username": "dev1"}]
        def entradas(self, *args, **kwargs):
            return [
                {
                    "start": start_ms,
                    "duration": str(int(10 * 3_600_000)),
                    "billable": True,
                    "task_location": {"space_id": "123", "list_id": "list_sust"},
                    "user": {"username": "dev1"}
                },
                {
                    "start": start_ms,
                    "duration": str(int(5 * 3_600_000)),
                    "billable": False,
                    "task_location": {"space_id": "123", "list_id": "list_sust"},
                    "user": {"username": "dev1"}
                }
            ]
        def tarefas_do_espaco(self, *args, **kwargs):
            return []
        def _get(self, *args, **kwargs):
            return {"folders": [], "lists": []}

    dados = painel.montar_dados(FakeClient(), [projeto], hoje)
    c = dados["clientes"][0]

    assert c["mes"]["sust"] == 15.0
    assert c["mes"]["sust_fat"] == 10.0
    assert c["mes"]["sust_naofat"] == 5.0
    assert c["mes"]["fat"] == 10.0
    assert c["mes"]["total"] == 15.0
