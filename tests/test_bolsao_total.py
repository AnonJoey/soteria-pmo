"""O vigia do TOTAL de horas de um projeto.

O Abner explicou em 14/10/2026 que Reviver e Unimed nao tem teto mensal: o
projeto, como um todo, tem horas previstas, e o que ajuda e vigiar a porcentagem
consumida desse total. Os numeros abaixo sao sinteticos. O caso real, conferido em
15/10/2026 contra o ClickUp, foi este: a soma de `time_estimate` e a soma de
`time_spent` das tarefas da lista do projeto bateram, ao minuto, com o que o Abner
leu na tela. A soma do ESPACO inteiro nao bateu, e e por isso que o projeto se
declara por lista (`listas_total`) e nao por espaco.
"""

from datetime import date

import pytest

from soteria_pmo import bolsao as B

H = 3_600_000


def tarefa(tid, previsto=None, gasto=None, pai=None):
    """Como a API manda: `time_estimate` em string, `time_spent` em numero, e o
    campo ausente (nao zero) quando a tarefa nao tem."""
    t = {"id": str(tid), "name": f"tarefa {tid}", "parent": pai}
    if previsto is not None:
        t["time_estimate"] = str(int(previsto * H))
    if gasto is not None:
        t["time_spent"] = int(gasto * H)
    return t


def total(projeto="Projeto Exemplo", previstas=None, listas=("L1",)):
    return B.TotalProjeto(projeto=projeto, listas=tuple(listas), horas_previstas=previstas)


# ── apurar_total ─────────────────────────────────────────────────────────────


def test_soma_as_estimativas_e_o_tempo_lancado_das_tarefas_e_subtarefas():
    tarefas = [
        tarefa(1, previsto=100, gasto=30),
        tarefa(2, previsto=50, gasto=10.5, pai="1"),   # subtarefa: entra, uma vez
        tarefa(3),                                      # sem estimativa nem tempo: conta zero
    ]
    s = B.apurar_total(tarefas, total())
    assert s.horas_contratadas == 150.0
    assert s.horas_gastas == pytest.approx(40.5)
    assert s.percentual == pytest.approx(0.27)
    assert s.nivel == "ok" and s.alerta is False
    assert s.escopo == "total"
    assert "estimativas das tarefas" in s.origem_previsto


def test_tarefa_que_mora_em_duas_listas_conta_uma_vez():
    t = tarefa(1, previsto=100, gasto=40)
    s = B.apurar_total([t, dict(t), tarefa(2, previsto=100, gasto=10)], total())
    assert s.horas_contratadas == 200.0
    assert s.horas_gastas == pytest.approx(50.0)


def test_tarefa_sem_id_nao_entra_na_soma():
    """Sem id nao ha como saber se ja foi contada; melhor ficar de fora do que dobrar."""
    s = B.apurar_total([{"time_estimate": str(100 * H), "time_spent": 90 * H},
                        tarefa(1, previsto=100, gasto=10)], total())
    assert s.horas_contratadas == 100.0 and s.horas_gastas == pytest.approx(10.0)


@pytest.mark.parametrize("gasto,nivel", [
    (74.9, "ok"), (75.0, "atencao"), (89.9, "atencao"), (90.0, "critico"),
    (99.9, "critico"), (100.0, "estourado"), (130.0, "estourado"),
])
def test_as_faixas_do_total_sao_as_mesmas_do_teto_mensal(gasto, nivel):
    s = B.apurar_total([tarefa(1, previsto=100, gasto=gasto)], total())
    assert s.nivel == nivel


def test_horas_totais_do_config_vencem_a_soma_das_estimativas():
    s = B.apurar_total([tarefa(1, previsto=150, gasto=60)], total(previstas=200))
    assert s.horas_contratadas == 200.0
    assert s.percentual == pytest.approx(0.30)
    assert "config" in s.origem_previsto


def test_sem_estimativa_cai_na_tabela_de_referencia_e_diz_que_caiu():
    s = B.apurar_total([tarefa(1, gasto=39)], total("Unimed Londrina"))
    assert s.horas_contratadas == 390.0
    assert s.horas_gastas == pytest.approx(39.0)
    assert "tabela de referencia" in s.origem_previsto


def test_sem_nenhum_previsto_devolve_none_em_vez_de_inventar():
    assert B.apurar_total([tarefa(1, gasto=39)], total("Projeto Desconhecido")) is None
    assert B.apurar_total([], total("Projeto Desconhecido")) is None


def test_projeto_sem_nenhuma_hora_lancada_aparece_em_zero_e_nao_some():
    """A Unimed estava, em 15/10/2026, sem uma hora lancada. 0% e uma resposta."""
    s = B.apurar_total([], total("Unimed Londrina"))
    assert s.horas_gastas == 0.0 and s.percentual == 0.0 and s.nivel == "ok"


# ── a linha do digest ────────────────────────────────────────────────────────


def test_a_linha_do_total_nao_promete_data_de_estouro():
    """Um previsto de milhares de horas, num ritmo mensal, daria uma data de anos
    adiante escrita como dia e mes, e isso se leria como prazo."""
    s = B.apurar_total([tarefa(1, previsto=1000, gasto=800)], total())
    linha = s.linha()
    assert "(total do projeto)" in linha and "800.0h de 1000h previstas (80%) [atencao]" in linha
    assert "estoura em" not in linha and "ritmo" not in linha


def test_a_linha_diz_quando_ja_passou_do_previsto():
    s = B.apurar_total([tarefa(1, previsto=100, gasto=112.5)], total())
    linha = s.linha()
    assert "ja passou do previsto em 12.5h" in linha
    assert "estoura em" not in linha and "ritmo" not in linha, "quem ja passou nao tem data de estouro"


def test_a_linha_do_teto_mensal_nao_mudou():
    """Mexer em `linha` para o total nao pode mexer no caso de sempre."""
    s = B.Situacao(projeto="China Gate", horas_contratadas=100, horas_gastas=80, faturaveis=80,
                   nao_faturaveis=0, nivel="atencao", dias_uteis_observados=10, ritmo_diario=8.0,
                   data_estouro=date(2026, 10, 20), dias_ate_estourar=2)
    assert s.escopo == "mes"
    assert s.linha() == "China Gate: 80.0h de 100h (80%) [atencao], no ritmo atual estoura em 20/10"


# ── vigiar ───────────────────────────────────────────────────────────────────


class ClienteFalso:
    """So o que `vigiar` toca: membros, entradas e tarefas de uma lista."""

    def __init__(self, listas=None, entradas=None, falha_em=()):
        self.listas = listas or {}
        self._entradas = entradas or []
        self.falha_em = set(falha_em)
        self.listas_lidas = []

    def membros(self):
        return [{"id": 1}, {"id": 2}]

    def entradas(self, ini_ms, fim_ms, assignee=None):
        return list(self._entradas)

    def tarefas_da_lista(self, lista, incluir_fechadas=True, subtarefas=True, max_paginas=100):
        self.listas_lidas.append((lista, incluir_fechadas, subtarefas))
        if lista in self.falha_em:
            raise RuntimeError("API fora do ar")
        return self.listas.get(lista, [])


HOJE = date(2026, 10, 15)


def vigiar(cliente, totais, bolsoes=(), sem_teto=None):
    return B.vigiar(cliente, list(bolsoes), HOJE.replace(day=1), HOJE, sem_teto=sem_teto, totais=totais)


def test_vigiar_le_as_listas_com_fechadas_e_subtarefas():
    c = ClienteFalso({"L1": [tarefa(1, previsto=100, gasto=10)], "L2": [tarefa(2, previsto=100, gasto=20)]})
    v = vigiar(c, [total(listas=("L1", "L2"))])
    assert c.listas_lidas == [("L1", True, True), ("L2", True, True)]
    assert v.situacoes[0].horas_contratadas == 200.0 and v.situacoes[0].horas_gastas == pytest.approx(30.0)


def test_total_dentro_da_faixa_nao_polui_o_digest():
    c = ClienteFalso({"L1": [tarefa(1, previsto=100, gasto=33)]})
    v = vigiar(c, [total()])
    assert B.digest(v) == ""
    assert "33.0h de 100h previstas (33%)" in B.digest(v, so_alertas=False)


def test_total_acima_da_faixa_aparece_no_digest():
    c = ClienteFalso({"L1": [tarefa(1, previsto=100, gasto=91)]})
    texto = B.digest(vigiar(c, [total("Reviver Exemplo")]))
    assert "Vigia de bolsao" in texto and "Reviver Exemplo (total do projeto)" in texto and "[critico]" in texto


def test_falha_de_leitura_do_total_sai_nomeada_e_nao_calada():
    c = ClienteFalso({"L1": [tarefa(1, previsto=100, gasto=10)]}, falha_em={"L2"})
    v = vigiar(c, [total("Projeto A", listas=("L1",)), total("Projeto B", listas=("L1", "L2"))])
    assert [s.projeto for s in v.situacoes] == ["Projeto A"]
    assert any("Projeto B (total do projeto)" in f and "RuntimeError" in f for f in v.falhas)
    assert "Nao foi possivel ler" in B.digest(v)


def test_total_sem_previsto_sai_nomeado_em_sem_teto():
    c = ClienteFalso({"L1": [tarefa(1, gasto=10)]})
    v = vigiar(c, [total("Projeto Desconhecido")])
    assert v.situacoes == []
    assert any("Projeto Desconhecido" in t and "sem previsto" in t for t in v.sem_teto)


def test_o_teto_mensal_continua_sendo_vigiado_junto_com_o_total():
    entradas = [{"duration": 30 * H, "billable": True, "task_location": {"space_id": "S1", "list_id": "X"}}]
    c = ClienteFalso({"L1": [tarefa(1, previsto=100, gasto=80)]}, entradas=entradas)
    mensal = B.Bolsao(projeto="China Gate", list_id="", horas_contratadas=100.0, space_id="S1")
    v = vigiar(c, [total("Reviver Exemplo")], bolsoes=[mensal])
    por = {s.projeto: s for s in v.situacoes}
    assert por["China Gate"].escopo == "mes" and por["China Gate"].horas_gastas == pytest.approx(30.0)
    assert por["Reviver Exemplo"].escopo == "total" and por["Reviver Exemplo"].nivel == "atencao"


def test_sem_totais_o_comportamento_de_antes_e_o_mesmo():
    v = vigiar(ClienteFalso(), None)
    assert v.situacoes == [] and v.falhas == [] and v.sem_teto == []


# ── o config ─────────────────────────────────────────────────────────────────


def test_carregar_totais_so_pega_quem_declara_a_lista_do_projeto():
    totais = B.carregar_totais([
        {"nome": "Reviver Exemplo", "space_id": "1", "listas_total": ["L9", 77]},
        {"nome": "China Gate", "space_id": "2", "horas_contratadas": 100},
        {"nome": "Unimed Londrina", "space_id": "3"},                      # tem referencia, nao tem lista
        {"nome": "Outro", "space_id": "4", "listas_total": ["L1"], "horas_totais": 500},
        {"nome": "Conta Azul", "space_id": "5", "listas_total": ["L1"]},   # cliente que saiu
    ])
    assert [(t.projeto, t.listas, t.horas_previstas) for t in totais] == [
        ("Reviver Exemplo", ("L9", "77"), None), ("Outro", ("L1",), 500.0)]


def test_projeto_acompanhado_pelo_total_nao_e_cobrado_por_teto_mensal():
    bolsoes, sem_teto = B.carregar_bolsoes([
        {"nome": "Concessionaria Reviver", "space_id": "1", "listas_total": ["L1"]}])
    assert bolsoes == [] and sem_teto == []


def test_projeto_sem_teto_e_sem_lista_diz_o_que_falta():
    _, sem_teto = B.carregar_bolsoes([{"nome": "Concessionaria Reviver", "space_id": "1"}])
    assert any("Concessionaria Reviver" in t and "sem teto configurado" in t and "listas_total" in t
               for t in sem_teto)


def test_unimed_com_total_de_referencia_mas_sem_lista_diz_que_nao_da_para_ler():
    _, sem_teto = B.carregar_bolsoes([{"nome": "Unimed Londrina", "space_id": "1"}])
    linha = next(t for t in sem_teto if "Unimed Londrina" in t)
    assert "390h" in linha and "listas_total" in linha


def test_total_com_horas_nao_positivas_e_recusado_na_construcao():
    with pytest.raises(ValueError):
        B.TotalProjeto(projeto="X", listas=("L1",), horas_previstas=-1)
    with pytest.raises(ValueError):
        B.TotalProjeto(projeto="X", listas=())


@pytest.mark.parametrize("bruto", [-5, "abc", [], {"x": 1}])
def test_horas_totais_torto_nao_derruba_a_rotina_e_cai_nas_estimativas(bruto):
    totais = B.carregar_totais([{"nome": "Reviver Exemplo", "space_id": "1", "listas_total": ["L1"],
                                 "horas_totais": bruto}])
    assert [(t.projeto, t.horas_previstas) for t in totais] == [("Reviver Exemplo", None)]
