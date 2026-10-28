"""O painel da carteira: o objeto de dados do modelo e a troca do marcador.

Nenhum dado real: tudo aqui e inventado. O cliente de mentira devolve entradas
de tempo, listas e tarefas no formato que o ClickUp devolve.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from soteria_pmo import painel

HOJE = date(2026, 10, 21)  # quarta


def _ms(d: date, hora: int = 10) -> int:
    return painel.janela(d, d)[0] + hora * 3_600_000


def _entrada(d: date, horas: float, lista: str, espaco: str = "S1", pessoa: str = "Ana",
             fat: bool = True, tarefa: str = "t1") -> dict:
    return {
        "id": f"e-{d}-{lista}-{horas}", "start": str(_ms(d)), "duration": str(int(horas * 3_600_000)),
        "billable": fat, "user": {"username": pessoa},
        "task": {"id": tarefa, "name": f"Tarefa {tarefa}", "status": {"status": "desenvolvimento"}},
        "task_location": {"space_id": espaco, "list_id": lista},
    }


class Falso:
    def __init__(self, entradas, tarefas=None):
        self._entradas, self._tarefas = entradas, tarefas or []

    def membros(self):
        return [{"id": 1}, {"id": 2}]

    def entradas(self, ini, fim, assignee=None):
        return self._entradas

    def _get(self, caminho, **_):
        if caminho.endswith("/folder"):
            return {"folders": [{"name": "Chamados", "lists": [{"id": "L-sust", "name": "Sustentação"}]}]}
        return {"lists": [{"id": "L-proj", "name": "Projeto novo"}]}

    def tarefas_do_espaco(self, space_id, desde_ms=None):
        return self._tarefas


def _tarefa(tid, nome, venc: date, status="desenvolvimento", tipo="open"):
    return {"id": tid, "name": nome, "due_date": str(_ms(venc)), "list": {"name": "Projeto novo"},
            "status": {"status": status, "type": tipo}, "assignees": [{"username": "Ana"}]}


PROJETOS = [{"nome": "Cliente A", "space_id": "S1", "horas_contratadas": 100, "tipo": "chamado"}]


def test_dados_somam_o_mes_e_separam_sustentacao_de_implantacao():
    entradas = [_entrada(HOJE, 3, "L-sust"), _entrada(HOJE - timedelta(days=1), 2, "L-proj"),
                _entrada(date(2026, 9, 15), 5, "L-sust")]  # setembro: fora do mes, dentro das 12 semanas
    D = painel.montar_dados(Falso(entradas), PROJETOS, HOJE)
    c = D["clientes"][0]
    assert c["nome"] == "Cliente A" and c["teto"] == 100.0
    assert c["mes"]["total"] == 5.0 and c["mes"]["sust"] == 3.0 and c["mes"]["impl"] == 2.0
    assert len(c["semanas"]) == painel.SEMANAS
    assert sum(s["sust"] + s["impl"] for s in c["semanas"]) == 10.0  # as 12 semanas incluem setembro
    assert c["ultima_hora"] == HOJE.isoformat() and c["dias_uteis_sem_hora"] == 0
    assert D["mes"]["dias_uteis_mes"] == 22 and D["entradas_lidas"] == 3 and D["equipe_consultada"] == 2


def test_lista_declarada_no_config_manda_sobre_o_tipo_do_cliente():
    """Cliente do tipo chamado com listas_sustentacao: so a lista nomeada e sustentacao."""
    projetos = [dict(PROJETOS[0], listas_sustentacao=["L-sust"])]
    entradas = [_entrada(HOJE, 4, "L-sust"), _entrada(HOJE, 6, "L-proj")]
    c = painel.montar_dados(Falso(entradas), projetos, HOJE)["clientes"][0]
    assert c["base_fixa"] == "sust"
    assert c["mes"]["sust"] == 4.0 and c["mes"]["impl"] == 6.0


def test_total_de_projeto_no_lugar_do_teto():
    projetos = [{"nome": "Cliente B", "space_id": "S1", "tipo": "chamado", "listas_total": ["L1"], "horas_totais": 390}]
    c = painel.montar_dados(Falso([]), projetos, HOJE)["clientes"][0]
    assert c["teto"] == 0.0 and c["total_projeto"] == 390.0


def test_cliente_encerrado_fica_fora():
    projetos = PROJETOS + [{"nome": "Conta Azul", "space_id": "S9", "tipo": "chamado"}]
    nomes = [c["nome"] for c in painel.montar_dados(Falso([]), projetos, HOJE)["clientes"]]
    assert nomes == ["Cliente A"]


def test_prazos_vencidos_a_vencer_e_em_espera():
    tarefas = [
        _tarefa("a", "Vencida em andamento", HOJE - timedelta(days=3)),
        _tarefa("b", "Vencida em homologação", HOJE - timedelta(days=10), status="homologação"),
        _tarefa("c", "Vence em 5 dias", HOJE + timedelta(days=5)),
        _tarefa("d", "Longe", HOJE + timedelta(days=30)),
        _tarefa("e", "Finalizada", HOJE - timedelta(days=3), status="publicado/finalizado", tipo="closed"),
    ]
    t = painel.montar_dados(Falso([], tarefas), PROJETOS, HOJE)["clientes"][0]["tarefas"]
    assert t["vencidas"] == 2 and t["vencidas_espera"] == 1 and t["a_vencer_7d"] == 1
    assert [i["tarefa"] for i in t["lista_vencidas"]] == ["Vencida em andamento", "Vencida em homologação"]  # espera por ultimo


def test_pessoas_somam_o_mes_por_cliente():
    entradas = [_entrada(HOJE, 3, "L-sust", pessoa="Ana"), _entrada(HOJE, 1, "L-proj", pessoa="Bia")]
    D = painel.montar_dados(Falso(entradas), PROJETOS, HOJE)
    assert [p["nome"] for p in D["pessoas"]] == ["Ana", "Bia"]
    assert D["pessoas"][0]["clientes"] == {"Cliente A": 3.0}


def test_renderizar_troca_o_marcador_e_nao_deixa_fechar_o_script():
    D = {"gerado_em": "x", "clientes": [{"nome": "</script><b>"}]}
    html = painel.renderizar(D)
    assert painel.MARCADOR not in html
    assert "</script><b>" not in html.split("const D = ", 1)[1].split("\n", 1)[0]
    assert "<\\/script>" in html


def test_renderizar_aceita_o_modelo_com_objeto_embutido(tmp_path):
    modelo = tmp_path / "m.html"
    modelo.write_text('<script>\nconst D = {"velho": 1, "lista": [1,2]};\nfim();\n</script>', encoding="utf-8")
    html = painel.renderizar({"novo": 2}, modelo)
    assert 'const D = {"novo": 2};' in html and "velho" not in html and "fim();" in html


def test_modelo_do_pacote_nao_leva_dado_nem_marca():
    texto = painel.CAMINHO_MODELO.read_text(encoding="utf-8")
    assert painel.MARCADOR in texto
    assert "data:font" not in texto and "base64" not in texto.lower()
    assert "<svg class=\"logo\"" not in texto


def test_dados_serializam_em_json():
    entradas = [_entrada(HOJE, 3, "L-sust")]
    json.dumps(painel.montar_dados(Falso(entradas), PROJETOS, HOJE))


def test_prazos_carteira_consolida_vencidas_e_a_vencer_de_todos_os_clientes():
    class MultiFalso(Falso):
        def __init__(self, por_espaco):
            super().__init__([])
            self._por_espaco = por_espaco

        def tarefas_do_espaco(self, space_id, desde_ms=None):
            return self._por_espaco.get(space_id, [])

    projetos = [
        {"nome": "Cliente A", "space_id": "S1", "horas_contratadas": 100, "tipo": "chamado"},
        {"nome": "Cliente B", "space_id": "S2", "horas_contratadas": 80, "tipo": "projeto"},
    ]
    por_espaco = {
        "S1": [
            _tarefa("a1", "Vencida em homologacao A", HOJE - timedelta(days=12), status="homologação"),
            _tarefa("a2", "Vence em 2 dias A", HOJE + timedelta(days=2)),
        ],
        "S2": [
            _tarefa("b1", "Vencida ativa B", HOJE - timedelta(days=4)),
            _tarefa("b2", "Vence hoje B", HOJE),
        ],
    }
    D = painel.montar_dados(MultiFalso(por_espaco), projetos, HOJE)
    pc = D["prazos_carteira"]
    assert pc["vencidas"] == 2
    assert pc["vencidas_espera"] == 1
    assert pc["a_vencer_7d"] == 2
    # Ativa em desenvolvimento vem antes da tarefa em espera, mesmo sendo menos antiga
    assert [(i["cliente"], i["tarefa"], i["dias_atraso"]) for i in pc["lista_vencidas"]] == [
        ("Cliente B", "Vencida ativa B", 4),
        ("Cliente A", "Vencida em homologacao A", 12),
    ]
    assert [(i["cliente"], i["tarefa"], i["dias_para_vencer"]) for i in pc["lista_a_vencer"]] == [
        ("Cliente B", "Vence hoje B", 0),
        ("Cliente A", "Vence em 2 dias A", 2),
    ]


def test_painel_html_inclui_secao_unificada_prazos_carteira_na_primeira_tela():
    tarefas = [_tarefa("a", "Vencida critica", HOJE - timedelta(days=3))]
    html = painel.gerar(Falso([], tarefas), PROJETOS, HOJE)
    pos_carteira = html.index('<section id="carteira"')
    pos_prazos_cart = html.index('id="prazos-carteira-painel"')
    pos_cliente = html.index('<section id="cliente"')
    assert pos_carteira < pos_prazos_cart < pos_cliente
    assert 'id="b-pz-todas"' in html
    assert 'id="b-pz-venc"' in html
    assert 'id="b-pz-7d"' in html
    assert "prazosCarteira()" in html
