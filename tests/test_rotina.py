"""The routine: what runs when, and what happens when one item breaks.

The behaviour that matters most is that a failure is loud. A routine where one
broken API call silences the other six is worse than no routine, because the
silence is indistinguishable from a quiet week.
"""

import json
from datetime import date

import pytest

from soteria_pmo import rotina as R

SEG = date(2026, 9, 7)    # segunda
TER = date(2026, 9, 1)    # terca, e o primeiro dia util de setembro
QUA = date(2026, 9, 2)
SAB = date(2026, 9, 5)
DOM = date(2026, 9, 6)


def test_cada_item_tem_cadencia_declarada():
    assert set(R.CADENCIAS) == {"reporte", "cronograma", "auditor", "fechamento",
                                "horas", "bolsao", "rh", "datas", "painel"}
    assert set(R.CADENCIAS.values()) == {R.DIARIA, R.SEMANAL, R.MENSAL, R.CONTINUA}


@pytest.mark.parametrize("item", ["horas", "bolsao", "rh", "cronograma", "datas"])
def test_diarios_e_continuos_rodam_em_dia_util(item):
    assert R.devido(item, QUA)


@pytest.mark.parametrize("dia", [SAB, DOM])
def test_nada_roda_no_fim_de_semana(dia):
    assert not any(R.devido(i, dia) for i in R.CADENCIAS)


def test_semanal_so_na_segunda():
    assert R.devido("reporte", SEG)
    assert not R.devido("reporte", QUA)


def test_mensal_no_primeiro_dia_util_do_mes():
    assert R.devido("fechamento", TER), "01/09/2026 e terca, primeiro dia util"
    assert not R.devido("fechamento", QUA)


def test_mensal_nao_repete_no_mesmo_mes():
    """Rodar a rotina duas vezes no mesmo dia nao audita o mes duas vezes."""
    assert not R.devido("fechamento", TER, ultimo_mensal=date(2026, 9, 1))
    assert R.devido("fechamento", TER, ultimo_mensal=date(2026, 8, 3))


def test_item_desconhecido_nunca_e_devido():
    assert not R.devido("inventado", QUA)


# ── execucao ─────────────────────────────────────────────────────────────────


def test_so_os_devidos_rodam():
    chamados = []

    def marca(nome):
        return lambda: (chamados.append(nome), f"saida de {nome}")[1]

    R.rodar(QUA, {"horas": marca("horas"), "reporte": marca("reporte")})
    assert chamados == ["horas"], "quarta nao e dia de reporte semanal"


def test_forcar_dispara_fora_da_cadencia():
    """O reporte foi especificado com disparo manual: o Max pede e sai."""
    d = R.rodar(QUA, {"reporte": lambda: "reporte semanal"}, forcar=frozenset({"reporte"}))
    assert [s.item for s in d.falantes] == ["reporte"]


def test_um_item_que_quebra_nao_cala_os_outros():
    def explode():
        raise RuntimeError("api fora do ar")

    d = R.rodar(QUA, {"horas": explode, "bolsao": lambda: "bolsao falou"})
    assert [s.item for s in d.erros] == ["horas"]
    assert [s.item for s in d.falantes] == ["bolsao"]
    assert "bolsao falou" in d.texto()


def test_o_erro_aparece_no_texto_em_vez_de_sumir():
    d = R.rodar(QUA, {"horas": lambda: (_ for _ in ()).throw(ValueError("sem token"))})
    texto = d.texto()
    assert "Itens que nao rodaram" in texto
    assert "ValueError: sem token" in texto


def test_item_silencioso_e_declarado_e_nao_confundido_com_quem_nao_rodou():
    """Um item calado e um que nunca rodou sao iguais para quem le."""
    d = R.rodar(QUA, {"bolsao": lambda: "", "rh": lambda: "rh falou"})
    assert [s.item for s in d.silenciosos] == ["bolsao"]
    assert "Rodaram e nao tinham nada a dizer: bolsao." in d.texto()


def test_dia_sem_nada_diz_que_nao_ha_nada():
    d = R.rodar(QUA, {"bolsao": lambda: "", "rh": lambda: ""})
    assert "Nada a reportar hoje." not in d.texto(), "houve item silencioso, entao ele e citado"
    d2 = R.rodar(SAB, {"bolsao": lambda: "x"})
    assert "Nada a reportar hoje." in d2.texto()


def test_item_nao_devido_nao_conta_como_silencioso():
    d = R.rodar(QUA, {"reporte": lambda: "nunca chamado"})
    assert d.silenciosos == [] and d.falantes == [] and d.erros == []


def test_o_digest_traz_a_data_e_o_texto_de_cada_item():
    d = R.rodar(QUA, {"bolsao": lambda: "Vigia de bolsao\n  Soteria: 90%",
                      "rh": lambda: "RH e datas\n  Ana: aniversario"})
    texto = d.texto()
    assert "02/09/2026" in texto
    assert "Vigia de bolsao" in texto and "RH e datas" in texto


def test_a_rotina_nao_tem_caminho_de_escrita():
    """A fronteira do pacote inteiro: producao de texto, aprovacao humana a parte."""
    fonte = (R.__file__)
    with open(fonte) as fh:
        codigo = fh.read()
    for proibido in ("lancar(", "corrigir(", "remover(", "requests.", "httpx."):
        assert proibido not in codigo, f"a rotina nao deveria alcancar {proibido}"


# ── feriado, achado ao rodar o CLI contra o calendario real ──────────────────


SETE = date(2026, 9, 7)   # segunda, e feriado da Independencia
FERIADO = frozenset({SETE})


def test_feriado_para_tudo_inclusive_o_semanal_que_cai_nele():
    """07/09/2026 cai numa segunda, que e o dia do reporte semanal.

    Sem isso o reporte sai num feriado, o que produz um documento que ninguem
    abre e ainda desloca a janela da semana seguinte.
    """
    assert R.devido("reporte", SETE), "sem feriados declarados, roda"
    assert not R.devido("reporte", SETE, feriados=FERIADO)
    assert not any(R.devido(i, SETE, feriados=FERIADO) for i in R.CADENCIAS)


def test_mensal_pula_para_o_proximo_dia_util_se_o_primeiro_for_feriado():
    jan1 = date(2027, 1, 1)      # sexta, feriado
    jan4 = date(2027, 1, 4)      # segunda
    feriados = frozenset({jan1})
    assert not R.devido("fechamento", jan1, feriados=feriados)
    assert R.devido("fechamento", jan4, feriados=feriados)


def test_rodar_respeita_feriado():
    chamados = []
    R.rodar(SETE, {"bolsao": lambda: chamados.append("x")}, feriados=FERIADO)
    assert chamados == []


# ── Item 3.2.2.1: variaveis de ambiente e modo --json ─────────────────────────


def test_carregar_config_por_variaveis_de_ambiente_sem_arquivo_no_disco(tmp_path, monkeypatch):
    from soteria_pmo import cli

    inexistente = tmp_path / "nao_existe" / "pmo.json"
    monkeypatch.setenv("SOTERIA_PMO_CLICKUP_TOKEN", "pk_env_123")
    monkeypatch.setenv("SOTERIA_PMO_TEAM_ID", "9007999")
    monkeypatch.setenv("SOTERIA_PMO_PROJETOS", json.dumps([{"nome": "Cliente Nuvem", "space_id": "S1"}]))
    monkeypatch.setenv("SOTERIA_PMO_FERIADOS", "2026-09-07, 2026-10-12")

    cfg = cli.carregar_config(inexistente)
    assert cfg["token"] == "pk_env_123"
    assert cfg["team_id"] == "9007999"
    assert cfg["projetos"] == [{"nome": "Cliente Nuvem", "space_id": "S1"}]
    assert cfg["feriados"] == ["2026-09-07", "2026-10-12"]


def test_carregar_config_aceita_soteria_pmo_config_json_inline(monkeypatch):
    from soteria_pmo import cli

    inline = json.dumps({"token": "pk_inline", "team_id": "42", "projetos": [{"nome": "X", "list_id": "L1"}]})
    monkeypatch.setenv("SOTERIA_PMO_CONFIG", inline)
    cfg = cli.carregar_config()
    assert cfg["token"] == "pk_inline"
    assert cfg["team_id"] == "42"
    assert cfg["projetos"][0]["nome"] == "X"


def test_carregar_config_variaveis_de_ambiente_sobrepoem_arquivo(tmp_path, monkeypatch):
    from soteria_pmo import cli

    arq = tmp_path / "pmo.json"
    arq.write_text(json.dumps({"token": "pk_antigo", "team_id": "111", "projetos": []}), encoding="utf-8")
    monkeypatch.setenv("CLICKUP_TOKEN", "pk_novo")
    monkeypatch.setenv("CLICKUP_TEAM_ID", "222")
    cfg = cli.carregar_config(arq)
    assert cfg["token"] == "pk_novo"
    assert cfg["team_id"] == "222"


def test_cmd_rodar_json_retorna_contrato_estruturado_sem_gravar_no_disco(tmp_path, monkeypatch, capsys):
    from soteria_pmo import cli

    class ClickUpFalso:
        def __init__(self, token, team_id, dry_run=True):
            self.token = token
            self.team_id = team_id

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def membros(self):
            return [{"id": 1, "username": "Ana"}]

        def entradas(self, ini, fim, assignee=None):
            return [{
                "id": "e1",
                "start": str(ini + 3600_000),
                "duration": str(95 * 3600_000),
                "billable": True,
                "user": {"id": 1, "username": "Ana"},
                "task": {"id": "t1", "name": " Manutencao", "status": {"status": "em andamento"}},
                "task_location": {"space_id": "S1", "list_id": "L1"},
            }]

        def tarefas_da_lista(self, lid, **k):
            return []

        def tarefas_do_espaco(self, sid, **k):
            return []

        def _get(self, caminho, **_):
            return {"folders": [], "lists": [{"id": "L1", "name": "Sustentacao"}]}

    monkeypatch.setattr(cli, "ClickUp", ClickUpFalso)
    monkeypatch.setenv("SOTERIA_PMO_CLICKUP_TOKEN", "pk_nuvem")
    monkeypatch.setenv("SOTERIA_PMO_TEAM_ID", "9007")
    monkeypatch.setenv("SOTERIA_PMO_PROJETOS", json.dumps([
        {"nome": "Cliente Alfa", "space_id": "S1", "list_id": "L1", "horas_contratadas": 100, "tipo": "chamado"}
    ]))

    codigo = cli.main(["rodar", "--json", "--dia", "2026-10-16"])
    saida = capsys.readouterr().out
    assert codigo == 0
    dados = json.loads(saida)
    assert dados["dia"] == "2026-10-16"
    assert dados["ok"] is True
    assert dados["itens_com_erro"] == []
    assert "<!doctype html>" in dados["html"].lower()
    assert dados["resumo"]["horas_faturadas"] == 95.0
    assert any("Cliente Alfa" in b for b in dados["resumo"]["bolsoes_em_risco"])
    assert any("Cliente Alfa" in a for a in dados["resumo"]["alertas_criticos"])
    assert isinstance(dados["saidas"], list) and len(dados["saidas"]) > 0
    assert not (cli.CONFIG_HOME / "relatorios").exists()
    assert not (cli.CONFIG_HOME / "reportes").exists()


def test_cmd_reporte_json_retorna_contrato_estruturado(monkeypatch, capsys):
    from soteria_pmo import cli

    class ClickUpFalso:
        def __init__(self, token, team_id, dry_run=True):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def membros(self):
            return [{"id": 1, "username": "Ana"}]

        def entradas(self, ini, fim, assignee=None):
            return [{
                "id": "e1",
                "start": str(ini + 3600_000),
                "duration": str(12 * 3600_000),
                "billable": True,
                "user": {"id": 1, "username": "Ana"},
                "task": {"id": "t1", "name": "Entrega 1", "status": {"status": "concluido", "type": "closed"}},
                "task_location": {"space_id": "S1", "list_id": "L1"},
            }]

        def tarefas_do_espaco(self, sid, **k):
            return [{
                "id": "t1",
                "name": "Entrega 1",
                "status": {"status": "concluido", "type": "closed"},
                "list": {"id": "L1", "name": "Sustentacao"},
                "folder": {"name": "Suporte"},
                "assignees": [{"username": "Ana"}],
            }]

    monkeypatch.setattr(cli, "ClickUp", ClickUpFalso)
    monkeypatch.setenv("SOTERIA_PMO_CLICKUP_TOKEN", "pk_nuvem")
    monkeypatch.setenv("SOTERIA_PMO_TEAM_ID", "9007")
    monkeypatch.setenv("SOTERIA_PMO_PROJETOS", json.dumps([
        {"nome": "Cliente Alfa", "space_id": "S1", "horas_contratadas": 100, "tipo": "chamado"}
    ]))

    codigo = cli.main(["reporte", "--json", "--dia", "2026-10-16"])
    saida = capsys.readouterr().out
    assert codigo == 0
    dados = json.loads(saida)
    assert dados["dia"] == "2026-10-16"
    assert dados["ok"] is True
    assert dados["formato"] == "html"
    assert "<html" in dados["html"].lower()
    assert dados["resumo"]["horas_faturadas"] == 12.0
    assert dados["resumo"]["clientes_ativos"] == 1
    assert dados["clientes"][0]["cliente"] == "Cliente Alfa"
    assert dados["itens_com_erro"] == []
