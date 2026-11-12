"""Os dois quadros por pessoa do painel: quem nao lancou e o cronograma por pessoa.

Nenhum dado real: tudo aqui e inventado.
"""
from __future__ import annotations

from datetime import date, timedelta

from soteria_pmo import cronograma as C
from soteria_pmo import lancamentos, painel
from soteria_pmo.clickup import BLOQUEADOS, CONCLUIDOS

HOJE = date(2026, 10, 21)  # quarta
ONTEM = HOJE - timedelta(days=1)
PROJETOS = [{"nome": "Cliente A", "space_id": "S1", "horas_contratadas": 100, "tipo": "chamado"}]


def _ms(d: date, hora: int = 10) -> int:
    return painel.janela(d, d)[0] + hora * 3_600_000


def _entrada(d: date, pessoa: str, horas: float = 1.0) -> dict:
    return {
        "id": f"e-{d}-{pessoa}-{horas}", "start": str(_ms(d)), "duration": str(int(horas * 3_600_000)),
        "billable": True, "user": {"username": pessoa},
        "task": {"id": "t1", "name": "Tarefa", "status": {"status": "desenvolvimento"}},
        "task_location": {"space_id": "S1", "list_id": "L-sust"},
    }


def _tarefa(tid: str, pessoas: list[str], status: str = "desenvolvimento", vence: date | None = None) -> dict:
    t = {"id": tid, "name": f"Tarefa {tid}", "status": {"status": status, "type": "custom"},
         "assignees": [{"username": p} for p in pessoas], "list": {"name": "Lista"}}
    if vence:
        t["due_date"] = str(_ms(vence))
    return t


class Falso:
    def __init__(self, entradas=(), tarefas=()):
        self._entradas, self._tarefas = list(entradas), list(tarefas)

    def membros(self):
        return [{"id": 1}, {"id": 2}]

    def entradas(self, ini, fim, assignee=None):
        return self._entradas

    def _get(self, caminho, **_):
        return {"folders": [], "lists": []}

    def tarefas_do_espaco(self, space_id, desde_ms=None):
        return self._tarefas


class SemEquipe(Falso):
    def membros(self):
        raise RuntimeError("fora do ar")


# ── Quem nao lancou ─────────────────────────────────────────────────────────


def test_quem_nao_lancou_olha_o_dia_util_anterior_e_a_lista_do_config():
    entradas = [_entrada(ONTEM, "Ana"), _entrada(HOJE, "Bia")]
    q = painel.montar_dados(Falso(entradas), PROJETOS, HOJE, esperados=["Ana", "Bia", "Cid"])["sem_lancamento"]
    assert q["dia"] == "2026-10-20" and q["total"] == 3 and q["lancaram"] == 1
    assert q["faltam"] == ["Bia", "Cid"]  # Bia lancou hoje, nao no dia util anterior
    assert "equipe_lancamento" in q["origem"]


def test_na_segunda_olha_a_sexta_e_pula_feriado():
    segunda, sexta = date(2026, 10, 26), date(2026, 10, 23)
    entradas = [_entrada(sexta, "Ana")]
    assert painel.montar_dados(Falso(entradas), PROJETOS, segunda, esperados=["Ana"])["sem_lancamento"]["faltam"] == []
    q = painel.montar_dados(Falso(entradas), PROJETOS, segunda, frozenset({sexta}), esperados=["Ana"])["sem_lancamento"]
    assert q["dia"] == "2026-10-22" and q["faltam"] == ["Ana"]


def test_sem_lista_no_config_esperados_sao_os_ultimos_30_dias():
    entradas = [_entrada(ONTEM, "Ana"), _entrada(HOJE - timedelta(days=10), "Bia"),
                _entrada(HOJE - timedelta(days=45), "Cid")]  # dentro das 12 semanas, fora dos 30 dias
    q = painel.montar_dados(Falso(entradas), PROJETOS, HOJE)["sem_lancamento"]
    assert q["total"] == 2 and q["faltam"] == ["Bia"]
    assert "30 dias" in q["origem"]


def test_quem_nao_lancou_bate_com_o_resumo_diario():
    esperados = ["Ana", "Bia", "Cid"]
    entradas = [_entrada(ONTEM, "Ana")]
    q = painel.montar_dados(Falso(entradas), PROJETOS, HOJE, esperados=esperados)["sem_lancamento"]
    resumo = lancamentos.formatar_resumo(lancamentos.apurar(entradas, [ONTEM], esperados),
                                         lancamentos.apurar(entradas, [ONTEM], esperados))
    assert f"Sem lancamento: {', '.join(q['faltam'])}." in resumo


def test_ninguem_esperado_some_em_vez_de_dizer_que_todos_lancaram():
    assert painel.montar_dados(Falso(), PROJETOS, HOJE)["sem_lancamento"] is None


def test_sem_ler_a_equipe_o_painel_nao_acusa_ninguem():
    D = painel.montar_dados(SemEquipe([_entrada(ONTEM, "Ana")], [_tarefa("1", ["Bia"])]), PROJETOS, HOJE,
                            esperados=["Ana", "Bia"])
    assert D["sem_lancamento"] is None and D["cronograma_pessoas"] == []


# ── Cronograma por pessoa ───────────────────────────────────────────────────


def test_conta_em_andamento_e_vencidas_e_ignora_fechada_e_bloqueada():
    tarefas = [_tarefa("1", ["Ana"]), _tarefa("2", ["Ana"], vence=HOJE - timedelta(days=1)),
               _tarefa("3", ["Ana"], vence=HOJE),  # vence hoje ainda nao venceu
               _tarefa("4", ["Ana"], status=next(iter(BLOQUEADOS)), vence=HOJE - timedelta(days=9)),
               _tarefa("5", ["Ana"], status=next(iter(CONCLUIDOS)), vence=HOJE - timedelta(days=9))]
    assert C.abertas_por_pessoa(tarefas, HOJE) == {"Ana": {"em_andamento": 3, "vencidas": 1}}


def test_tarefa_com_dois_responsaveis_conta_para_os_dois_e_repetida_conta_uma_vez():
    tarefas = [_tarefa("1", ["Ana", "Bia"]), _tarefa("1", ["Ana", "Bia"])]
    assert C.abertas_por_pessoa(tarefas, HOJE) == {"Ana": {"em_andamento": 1, "vencidas": 0},
                                                   "Bia": {"em_andamento": 1, "vencidas": 0}}


def test_soma_entre_clientes_e_sai_em_ordem_alfabetica():
    por_cliente = {"X": {"bia": {"em_andamento": 1, "vencidas": 1}, "Ana": {"em_andamento": 2, "vencidas": 0}},
                   "Y": {"Ana": {"em_andamento": 3, "vencidas": 2}}}
    linhas = C.leitura_por_pessoa(por_cliente, {}, HOJE)
    assert [l["nome"] for l in linhas] == ["Ana", "bia"]
    assert linhas[0]["clientes"] == ["X", "Y"]
    assert (linhas[0]["em_andamento"], linhas[0]["vencidas"]) == (5, 2)


def test_dias_sem_hora_nao_contam_hoje_fim_de_semana_nem_feriado():
    conta = {"C": {"Ana": {"em_andamento": 1, "vencidas": 0}}}
    segunda = date(2026, 10, 26)

    def dias(ultima, feriados=frozenset()):
        return C.leitura_por_pessoa(conta, {"Ana": ultima}, segunda, feriados)[0]["dias_sem_hora"]

    assert dias(date(2026, 10, 23)) == 0   # sexta: nao passou nenhum dia util inteiro
    assert dias(date(2026, 10, 22)) == 1   # quinta: a sexta ficou sem hora
    assert dias(date(2026, 10, 22), frozenset({date(2026, 10, 23)})) == 0   # a sexta foi feriado


def test_quem_nao_lancou_nada_na_janela_fica_sem_data_e_sem_numero():
    linha = C.leitura_por_pessoa({"C": {"Ana": {"em_andamento": 1, "vencidas": 0}}}, {}, HOJE)[0]
    assert linha["ultima_hora"] is None and linha["dias_sem_hora"] is None


def test_a_linha_nao_traz_regua_nem_nivel():
    linha = C.leitura_por_pessoa({"C": {"Ana": {"em_andamento": 1, "vencidas": 0}}}, {"Ana": ONTEM}, HOJE)[0]
    assert set(linha) == {"nome", "clientes", "em_andamento", "vencidas", "ultima_hora", "dias_sem_hora"}


def test_painel_junta_tarefas_e_ultima_hora_da_pessoa_em_qualquer_lancamento():
    entradas = [_entrada(HOJE - timedelta(days=8), "Ana"), _entrada(ONTEM, "Ana"),
                _entrada(HOJE + timedelta(days=2), "Bia"),  # futuro nao conta
                {**_entrada(ONTEM, "Bia"), "duration": "-1000"}]  # cronometro rodando nao conta
    tarefas = [_tarefa("1", ["Ana"], vence=HOJE - timedelta(days=3)), _tarefa("2", ["Bia"])]
    linhas = painel.montar_dados(Falso(entradas, tarefas), PROJETOS, HOJE)["cronograma_pessoas"]
    assert linhas == [
        {"nome": "Ana", "clientes": ["Cliente A"], "em_andamento": 1, "vencidas": 1,
         "ultima_hora": "2026-10-20", "dias_sem_hora": 0},
        {"nome": "Bia", "clientes": ["Cliente A"], "em_andamento": 1, "vencidas": 0,
         "ultima_hora": None, "dias_sem_hora": None},
    ]


def test_cliente_encerrado_nao_entra_no_cronograma_por_pessoa():
    projetos = [{"nome": "Conta Azul", "space_id": "S1", "tipo": "chamado"}]
    assert painel.montar_dados(Falso([], [_tarefa("1", ["Ana"])]), projetos, HOJE)["cronograma_pessoas"] == []


def test_o_quadro_nao_muda_o_alerta_por_projeto():
    """Sem divergencia o item 2 continua calado: a leitura por pessoa nao vira linha do log diario."""

    class Cli(Falso):
        def tarefas_da_lista(self, list_id):
            return []

    assert C.acompanhar_projetos(Cli(), [{"nome": "X", "list_id": "a"}], HOJE) == ""


# ── O modelo ────────────────────────────────────────────────────────────────


def test_modelo_liga_os_dois_quadros_e_esconde_sem_dado():
    html = painel.gerar(Falso(), PROJETOS, HOJE)
    assert 'id="sem-lancamento-painel" hidden' in html and 'id="cronograma-pessoas-painel" hidden' in html
    tudo = next(ln for ln in html.splitlines() if ln.startswith("function tudo()"))
    assert "semLancamento();" in tudo and "cronogramaPessoas();" in tudo
    assert "if(!q||!q.total){ box.hidden=true; return; }" in html
    assert "if(!ps||!ps.length){ box.hidden=true; return; }" in html


def test_modelo_declara_a_ambiguidade_e_nao_acusa():
    modelo = painel.CAMINHO_MODELO.read_text(encoding="utf-8")
    assert "Leitura, não alerta" in modelo and "não foi apontado" in modelo
    assert "abandon" not in modelo.lower()
