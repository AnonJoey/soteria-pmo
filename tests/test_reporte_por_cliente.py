"""Relatorio semanal por cliente: um HTML por cliente, sem dado dos outros (decisao de 10/11/2026).

Nenhum dado real: tudo aqui e inventado.
"""
from __future__ import annotations

from datetime import date

from soteria_pmo import reporte as R
from soteria_pmo.periodo import janela

INI, FIM = date(2026, 11, 16), date(2026, 11, 19)


def _tarefa(tid: str, nome: str, lista: str) -> dict:
    return {"id": tid, "name": nome, "status": {"status": "em andamento"}, "assignees": [],
            "time_spent": 0, "date_updated": "1795000000000", "list": {"id": f"L-{lista}", "name": lista},
            "folder": {"name": ""}}


class Cliente:
    def __init__(self, ruim: str = ""):
        self.ruim = ruim

    def membros(self):
        return []

    def entradas(self, *_a, **_k):
        inicio = janela(date(2026, 11, 17), date(2026, 11, 17))[0] + 10 * 3_600_000
        return [{"id": "e1", "start": str(inicio), "duration": str(3 * 3_600_000), "billable": True,
                 "user": {"username": "Pessoa"}, "description": "trabalho",
                 "task": {"id": "a1", "name": "Tarefa secreta do Alfa", "status": {"status": "em andamento"}},
                 "task_location": {"space_id": "sA", "list_id": "L-Implantacao"}}]

    def tarefas_do_espaco(self, space_id, desde_ms=None, **_):
        if space_id == self.ruim:
            raise RuntimeError("api fora")
        return {"sA": [_tarefa("a1", "Tarefa secreta do Alfa", "Implantacao")],
                "sB": [_tarefa("b1", "Tarefa secreta do Beta", "Sustentacao")]}.get(space_id, [])

    def _get(self, *_a, **_k):
        return {"folders": [], "lists": []}


PROJETOS = [{"nome": "Alfa", "space_id": "sA"}, {"nome": "Beta", "space_id": "sB"}, {"nome": "Gama", "space_id": "sG"}]


def test_cada_cliente_recebe_um_html_so_com_o_dado_dele():
    s = R.gerar_por_cliente(Cliente(), PROJETOS, INI, FIM)
    por = {r["cliente"]: r["html"] for r in s["relatorios"]}
    assert set(por) == {"Alfa", "Beta"}
    # o que importa: o HTML de um cliente nao leva nome, tarefa nem hora do outro
    assert "Alfa" in por["Alfa"] and "Beta" not in por["Alfa"]
    assert "Beta" in por["Beta"] and "Alfa" not in por["Beta"]
    assert next(r["horas"] for r in s["relatorios"] if r["cliente"] == "Alfa") == 3.0
    assert all(h.lstrip().startswith("<!DOCTYPE html>") for h in por.values())
    assert s["sem_movimento"] == ["Gama"] and s["falhas"] == []
    assert (s["inicio"], s["fim"]) == ("2026-11-16", "2026-11-19")


def test_bolsao_que_entra_e_so_o_do_cliente():
    bolsoes = {"Alfa": {"linha": "Alfa: 10h de 30h"}, "Beta": {"linha": "Beta: 90h de 100h"}}
    s = R.gerar_por_cliente(Cliente(), PROJETOS[:2], INI, FIM, bolsoes=bolsoes)
    alfa = next(r["html"] for r in s["relatorios"] if r["cliente"] == "Alfa")
    assert "90h de 100h" not in alfa


def test_cliente_que_falha_sai_nomeado_e_nao_cala_os_outros():
    s = R.gerar_por_cliente(Cliente(ruim="sA"), PROJETOS, INI, FIM)
    assert [r["cliente"] for r in s["relatorios"]] == ["Beta"]
    assert len(s["falhas"]) == 1 and s["falhas"][0].startswith("Alfa: RuntimeError")


def test_sem_projetos_nao_le_nada():
    assert R.gerar_por_cliente(Cliente(), [], INI, FIM)["relatorios"] == []
