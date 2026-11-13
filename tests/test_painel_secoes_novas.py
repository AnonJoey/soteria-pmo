"""Secoes do painel pedidas pelo Max em 10/11/2026: menu dos sete itens, cronograma, conferencia de
horas, datas da equipe, links para o ClickUp e colunas ordenaveis.

Nenhum dado real: tudo aqui e inventado.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from soteria_pmo import cli, cronograma as C, painel
from soteria_pmo.rh import Pessoa

HOJE = date(2026, 11, 13)  # sexta
PROJETOS = [{"nome": "Cliente A", "space_id": "S1", "horas_contratadas": 100, "tipo": "chamado"}]
MODELO = Path(painel.__file__).with_name("painel_modelo.html").read_text(encoding="utf-8")


def _ms(d: date, hora: int = 10) -> int:
    return painel.janela(d, d)[0] + hora * 3_600_000


def _entrada(d: date, pessoa: str, horas: float = 1.0, descricao: str = "ajuste do fluxo de cadastro",
             n: int = 0) -> dict:
    return {
        "id": f"e-{d}-{pessoa}-{horas}-{n}", "start": str(_ms(d)), "duration": str(int(horas * 3_600_000)),
        "billable": True, "user": {"username": pessoa}, "description": descricao,
        "task": {"id": "t1", "name": "Tarefa", "status": {"status": "desenvolvimento"}},
        "task_location": {"space_id": "S1", "list_id": "L-sust"},
    }


def _tarefa(tid: str, vence: date, url: str | None = None) -> dict:
    t = {"id": tid, "name": f"Tarefa {tid}", "status": {"status": "desenvolvimento", "type": "custom"},
         "assignees": [{"username": "Ana"}], "list": {"name": "Lista"}, "due_date": str(_ms(vence))}
    if url is not None:
        t["url"] = url
    return t


class Falso:
    def __init__(self, entradas=(), tarefas=(), cadastro=()):
        self._entradas, self._tarefas, self._cadastro = list(entradas), list(tarefas), list(cadastro)
        self.listas_lidas: list[str] = []

    def membros(self):
        return [{"id": 1}, {"id": 2}]

    def entradas(self, ini, fim, assignee=None):
        return self._entradas

    def _get(self, caminho, **_):
        return {"folders": [], "lists": []}

    def tarefas_do_espaco(self, space_id, desde_ms=None, **_):
        return self._tarefas

    def tarefas_da_lista(self, list_id, **_):
        self.listas_lidas.append(list_id)
        return self._cadastro


class SemEquipe(Falso):
    def membros(self):
        raise RuntimeError("fora do ar")


# ── Links para o ClickUp ────────────────────────────────────────────────────


def test_prazo_traz_o_link_da_api_ou_o_endereco_curto_pelo_id():
    tarefas = [_tarefa("a1", HOJE - timedelta(days=3), url="https://app.clickup.com/t/a1"),
               _tarefa("b2", HOJE - timedelta(days=2))]
    D = painel.montar_dados(Falso(tarefas=tarefas), PROJETOS, HOJE)
    urls = {t["tarefa"]: t["url"] for t in D["clientes"][0]["tarefas"]["lista_vencidas"]}
    assert urls == {"Tarefa a1": "https://app.clickup.com/t/a1", "Tarefa b2": "https://app.clickup.com/t/b2"}


def test_link_que_nao_e_https_nao_entra():
    assert painel.url_da_tarefa({"id": "x9", "url": "javascript:alert(1)"}) == "https://app.clickup.com/t/x9"
    assert painel.url_da_tarefa({}) == ""


def test_modelo_poe_o_link_com_escape_e_em_aba_nova():
    assert 'const tk=t=>t.url?`<a class="tk" href="${esc(t.url)}" target="_blank" rel="noopener">' in MODELO
    # o clique no link nao pode trocar o cliente selecionado na tabela da carteira
    assert "if(e.target.closest('a,th')) return;" in MODELO


# ── Conferencia de horas ────────────────────────────────────────────────────


def test_grade_tem_os_sete_dias_ate_ontem_e_conta_descricao_curta():
    ontem = HOJE - timedelta(days=1)
    entradas = [_entrada(ontem, "Ana", 2.0), _entrada(ontem, "Ana", 1.0, descricao="ok", n=1),
                _entrada(ontem, "Ana", 0.5, descricao="", n=2), _entrada(HOJE, "Bia", 3.0)]
    g = painel.montar_dados(Falso(entradas), PROJETOS, HOJE, esperados=["Ana", "Bia"])["grade_horas"]
    assert [d["dia"] for d in g["dias"]] == [(HOJE - timedelta(days=i)).isoformat() for i in range(7, 0, -1)]
    ana = next(l for l in g["linhas"] if l["nome"] == "Ana")
    assert ana["dias"][-1] == {"h": 3.5, "entradas": 3, "curtas": 2}
    bia = next(l for l in g["linhas"] if l["nome"] == "Bia")
    assert bia["semana_h"] == 0.0  # a hora de hoje fica fora da grade, que termina ontem


def test_percentual_do_mes_conta_dias_uteis_ate_ontem_e_pula_feriado():
    feriado = date(2026, 11, 2)
    entradas = [_entrada(date(2026, 11, 3), "Ana"), _entrada(date(2026, 11, 7), "Ana")]  # 07/11 e sabado
    g = painel.montar_dados(Falso(entradas), PROJETOS, HOJE, frozenset({feriado}),
                            esperados=["Ana"])["grade_horas"]
    # dias uteis de 01 a 12/11 sem o feriado de 02/11: 03, 04, 05, 06, 09, 10, 11, 12
    assert g["uteis_no_mes"] == 8
    ana = g["linhas"][0]
    assert ana["mes_dias_lancados"] == 1 and ana["mes_pct"] == 0.125


def test_meta_so_aparece_quando_o_config_a_traz():
    D = painel.montar_dados(Falso([_entrada(HOJE - timedelta(days=1), "Ana")]), PROJETOS, HOJE, esperados=["Ana"])
    assert D["grade_horas"]["meta"] is None
    D = painel.montar_dados(Falso([_entrada(HOJE - timedelta(days=1), "Ana")]), PROJETOS, HOJE,
                            esperados=["Ana"], meta_dias_lancados=0.9)
    assert D["grade_horas"]["meta"] == 0.9


def test_sem_ler_a_equipe_a_grade_some_para_nao_acusar_ninguem():
    D = painel.montar_dados(SemEquipe([_entrada(HOJE - timedelta(days=1), "Ana")]), PROJETOS, HOJE,
                            esperados=["Ana", "Bia"])
    assert D["grade_horas"] is None


# ── Datas da equipe ─────────────────────────────────────────────────────────


def test_aniversario_desta_semana_e_da_proxima_sem_o_ano():
    pessoas = [Pessoa("Ana", date(1990, 11, 13)), Pessoa("Bia", date(1985, 11, 10)),
               Pessoa("Cid", date(1999, 11, 18)), Pessoa("Duda", date(2000, 12, 25)), Pessoa("Eva")]
    a = painel.montar_dados(Falso(), PROJETOS, HOJE, pessoas_rh=pessoas)["aniversarios"]
    assert [(x["nome"], x["dia"], x["hoje"], x["passou"]) for x in a["semana"]] == [
        ("Bia", "2026-11-10", False, True), ("Ana", "2026-11-13", True, False)]
    assert [x["nome"] for x in a["proxima"]] == ["Cid"]
    assert a["total"] == 5 and a["sem_data"] == 1 and a["com_inicio_contrato"] == 0
    assert "1990" not in str(a) and "1985" not in str(a)


def test_virada_do_ano_entra_na_semana_certa():
    hoje = date(2026, 12, 30)  # quarta; a semana vai de 28/12 a 03/01
    a = painel.montar_dados(Falso(), PROJETOS, hoje, pessoas_rh=[Pessoa("Ana", date(1990, 1, 2))])["aniversarios"]
    assert [x["dia"] for x in a["semana"]] == ["2027-01-02"]


def test_inicio_de_contrato_traz_tempo_de_casa_e_feedback():
    pessoas = [Pessoa("Ana", inicio_contrato=date(2025, 11, 16)), Pessoa("Bia", inicio_contrato=date(2026, 9, 29))]
    a = painel.montar_dados(Falso(), PROJETOS, HOJE, pessoas_rh=pessoas)["aniversarios"]
    tipos = {(e["pessoa"], e["tipo"]) for e in a["outros"]}
    assert ("Ana", "tempo de casa") in tipos and ("Bia", "primeiro feedback") in tipos
    assert a["com_inicio_contrato"] == 2


def test_sem_fonte_de_datas_a_secao_diz_isso_em_vez_de_ninguem():
    assert painel.montar_dados(Falso(), PROJETOS, HOJE)["aniversarios"] is None
    assert "Sem fonte de datas da equipe" in MODELO


def test_da_lista_de_cadastro_sai_so_nome_e_nascimento(tmp_path):
    cadastro = [{"name": "Ana", "custom_fields": [
        {"name": "Data de nascimento", "value": str(_ms(date(1990, 11, 13)))},
        {"name": "Telefone pessoal", "value": "99999-0000"},
        {"name": "Endereço", "value": "Rua Inventada, 1"}]}]
    falso = Falso(cadastro=cadastro)
    pessoas = cli._pessoas_rh_do_painel(falso, {"rh_lista": "L-RH", "roster_rh": str(tmp_path / "nao-existe.csv")})
    assert falso.listas_lidas == ["L-RH"]
    assert [(p.nome, p.nascimento) for p in pessoas] == [("Ana", date(1990, 11, 13))]
    D = painel.montar_dados(falso, PROJETOS, HOJE, pessoas_rh=pessoas)
    texto = str(D)
    assert "99999" not in texto and "Inventada" not in texto


def test_sem_roster_e_sem_lista_nao_le_nada():
    falso = Falso()
    assert cli._pessoas_rh_do_painel(falso, {}) is None and falso.listas_lidas == []


# ── Cronograma como secao ───────────────────────────────────────────────────


def test_o_cronograma_guarda_a_leitura_para_o_painel_sem_ler_de_novo():
    tarefas = [{"id": "t1", "name": "Tarefa", "status": {"status": "desenvolvimento", "type": "custom"},
                "assignees": [{"username": "Ana"}], "date_updated": str(_ms(HOJE - timedelta(days=20)))}]
    falso = Falso(entradas=[], tarefas=tarefas)
    log = C.acompanhar_projetos(falso, PROJETOS, HOJE)
    guardado = falso._ultimo_cronograma
    assert guardado["dia"] == HOJE.isoformat() and guardado["falhas"] == []
    # a secao e o texto do e-mail contam a mesma coisa
    d = guardado["divergencias"]
    assert len(d) == 1 and d[0]["nivel"] == "escalar" and d[0]["regua_dias"] == 2
    assert f"[escalar] Cliente A (Ana) (chamado): {d[0]['dias_sem_horas']} dias uteis" in log
    D = painel.montar_dados(falso, PROJETOS, HOJE)
    assert D["cronograma"] is guardado


def test_sem_o_cronograma_rodar_a_secao_diz_que_nao_rodou():
    assert painel.montar_dados(Falso(), PROJETOS, HOJE)["cronograma"] is None
    assert "O acompanhamento de cronograma não rodou nesta geração" in MODELO


# ── Menu, ordenacao e o modelo sem JavaScript ───────────────────────────────


def test_menu_tem_os_sete_itens_e_cada_link_aponta_para_um_id_que_existe():
    menu = re.search(r'<nav class="menu".*?</nav>', MODELO, re.S).group(0)
    rotulos = re.findall(r">(\d) · ", menu)
    assert rotulos == ["1", "2", "3", "4", "5", "6", "7"]
    for alvo in re.findall(r'href="#([\w-]+)"', menu):
        assert f'id="{alvo}"' in MODELO, alvo


def test_tabelas_novas_sao_ordenaveis_e_a_ordem_volta_depois_do_redesenho():
    for container in ("#prazos-carteira", "#semana", "#grade", "#cronograma-projetos", "#cronograma-pessoas"):
        assert f"reordenar('{container}')" in MODELO, container
    assert "reordenar(el);" in MODELO  # prazos por cliente


def test_painel_oculto_fica_oculto_mesmo_com_display_grid():
    # .panel tem display:grid; sem esta regra o atributo hidden nao escondia nada
    assert "[hidden]{display:none!important}" in MODELO


def test_aviso_para_visualizador_que_nao_executa_o_painel():
    assert "<noscript>" in MODELO and "Abra o arquivo no Chrome ou no Edge" in MODELO


def test_modelo_sem_travessao():
    assert "—" not in MODELO and "–" not in MODELO
