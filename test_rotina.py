"""The routine: what runs when, and what happens when one item breaks.

The behaviour that matters most is that a failure is loud. A routine where one
broken API call silences the other six is worse than no routine, because the
silence is indistinguishable from a quiet week.
"""

from datetime import date

import pytest

from delegation_core.pmo import rotina as R

SEG = date(2026, 9, 7)    # segunda
TER = date(2026, 9, 1)    # terca, e o primeiro dia util de setembro
QUA = date(2026, 9, 2)
SAB = date(2026, 9, 5)
DOM = date(2026, 9, 6)


def test_os_sete_itens_tem_cadencia_declarada():
    assert set(R.CADENCIAS) == {"reporte", "cronograma", "auditor",
                                "horas", "bolsao", "rh", "datas"}
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
    assert R.devido("auditor", TER), "01/09/2026 e terca, primeiro dia util"
    assert not R.devido("auditor", QUA)


def test_mensal_nao_repete_no_mesmo_mes():
    """Rodar a rotina duas vezes no mesmo dia nao audita o mes duas vezes."""
    assert not R.devido("auditor", TER, ultimo_mensal=date(2026, 9, 1))
    assert R.devido("auditor", TER, ultimo_mensal=date(2026, 8, 3))


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
    assert not R.devido("auditor", jan1, feriados=feriados)
    assert R.devido("auditor", jan4, feriados=feriados)


def test_rodar_respeita_feriado():
    chamados = []
    R.rodar(SETE, {"bolsao": lambda: chamados.append("x")}, feriados=FERIADO)
    assert chamados == []
