"""Bandeira do total do projeto e do cliente parado no painel (decisao do Jordan de 09/11/2026:
o relatorio levanta a bandeira e o Max e o Andre decidem).

Nenhum dado real: tudo aqui e inventado.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from soteria_pmo import bolsao, painel

HOJE = date(2026, 11, 13)
MODELO = Path(painel.__file__).with_name("painel_modelo.html").read_text(encoding="utf-8")
PROJETO_TOTAL = {"nome": "Cliente T", "space_id": "S1", "listas_total": ["L-proj"], "horas_totais": 100}


def _tarefa(tid: str, gasto_h: float, estimado_h: float = 0.0) -> dict:
    return {"id": tid, "name": f"T{tid}", "time_spent": int(gasto_h * 3_600_000),
            "time_estimate": int(estimado_h * 3_600_000), "status": {"status": "feito", "type": "closed"}}


class Falso:
    def __init__(self, da_lista=(), erro=None):
        self._lista, self._erro = list(da_lista), erro
        self.pedidos: list[tuple] = []

    def membros(self):
        return [{"id": 1}]

    def entradas(self, ini, fim, assignee=None):
        return []

    def _get(self, caminho, **_):
        return {"folders": [], "lists": []}

    def tarefas_do_espaco(self, space_id, desde_ms=None, **_):
        return []

    def tarefas_da_lista(self, list_id, **kw):
        self.pedidos.append((list_id, kw.get("incluir_fechadas"), kw.get("subtarefas")))
        if self._erro:
            raise self._erro
        return self._lista


def test_total_do_projeto_usa_a_mesma_conta_do_vigia():
    tarefas = [_tarefa("1", 60), _tarefa("2", 42), _tarefa("2", 42)]  # a repetida conta uma vez
    falso = Falso(tarefas)
    c = painel.montar_dados(falso, [PROJETO_TOTAL], HOJE)["clientes"][0]
    vigia = bolsao.apurar_total(tarefas, bolsao.carregar_totais([PROJETO_TOTAL])[0])
    assert c["total"]["lancado"] == round(vigia.horas_gastas, 2) == 102.0
    assert c["total"]["previsto"] == 100.0 and c["total"]["nivel"] == vigia.nivel == "estourado"
    assert falso.pedidos == [("L-proj", True, True)]  # fechadas e subtarefas, como o vigia


def test_projeto_com_teto_mensal_nao_le_o_total():
    falso = Falso([_tarefa("1", 10)])
    c = painel.montar_dados(falso, [{**PROJETO_TOTAL, "horas_contratadas": 30}], HOJE)["clientes"][0]
    assert c["total"] is None and falso.pedidos == []


def test_falha_de_leitura_aparece_no_dado_em_vez_de_calar():
    c = painel.montar_dados(Falso(erro=RuntimeError("fora do ar")), [PROJETO_TOTAL], HOJE)["clientes"][0]
    assert "fora do ar" in c["total"]["erro"]
    assert "total do projeto não lido" in MODELO


def test_modelo_mostra_o_nivel_contra_o_total_e_o_cliente_parado():
    for trecho in ("const temTotal=", "'estourou o total'", "passou do total do projeto",
                   "const parado=c=>(c.dias_uteis_sem_hora??0)>=4;", "<span class=\"u\">parado</span>"):
        assert trecho in MODELO, trecho
    # o nivel pelo total vem antes do "sem teto": sem isso o projeto seguia como sem teto
    assert MODELO.index("if(temTotal(c)) return nivelTotal(c);") < MODELO.index("if(!temTeto(c)) return {k:'sem teto'")
