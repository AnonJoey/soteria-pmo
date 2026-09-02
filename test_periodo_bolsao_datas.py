"""Windows, the budget watch and the date guardian.

The cases that matter here are the ones that already went wrong once: hours
counted twice from two evidence sources covering the same stretch, a standup
sentence dated to the wrong day, and a projection that walked calendar days
through a weekend the team did not work.
"""

from datetime import date, datetime, timedelta

import pytest

from delegation_core.pmo import bolsao as B
from delegation_core.pmo import datas as D
from delegation_core.pmo.periodo import (
    BRT, Intervalo, data_da_fala, de_ms, dia, dias_uteis, fundir, horas, janela, ms,
)


# ── periodo ──────────────────────────────────────────────────────────────────


def test_ida_e_volta_de_milissegundos_preserva_o_horario_de_brasilia():
    d = datetime(2026, 9, 2, 14, 30, tzinfo=BRT)
    assert de_ms(ms(d)) == d


def test_de_ms_aceita_string_porque_o_clickup_manda_string():
    assert de_ms("1788332400000") == de_ms(1788332400000)


def test_de_ms_devolve_none_em_vez_de_explodir():
    for lixo in (None, "", "null", "abc", []):
        assert de_ms(lixo) is None


def test_dia_cobre_do_primeiro_ao_ultimo_milissegundo():
    ini, fim = dia(date(2026, 9, 2))
    assert de_ms(ini).hour == 0 and de_ms(ini).minute == 0
    assert de_ms(fim).hour == 23 and de_ms(fim).minute == 59
    assert fim - ini == 86_400_000 - 1


def test_janela_inclui_os_dois_extremos():
    ini, fim = janela(date(2026, 9, 1), date(2026, 9, 3))
    assert de_ms(ini).date() == date(2026, 9, 1)
    assert de_ms(fim).date() == date(2026, 9, 3)


def test_dias_uteis_pula_fim_de_semana():
    # 01/09/2026 e terca; 07/09 e a segunda seguinte.
    assert dias_uteis(date(2026, 9, 1), date(2026, 9, 7)) == 5


def test_dias_uteis_pula_feriado():
    feriado = frozenset({date(2026, 9, 7)})
    assert dias_uteis(date(2026, 9, 7), date(2026, 9, 7), feriado) == 0


def test_dias_uteis_de_intervalo_invertido_e_zero():
    assert dias_uteis(date(2026, 9, 5), date(2026, 9, 1)) == 0


# ── a regra de datacao que ja custou um dia de horas ─────────────────────────


def test_presente_continuo_na_daily_data_o_proprio_dia():
    reuniao = date(2026, 9, 2)
    assert data_da_fala("estou fazendo o coletor de horas", reuniao) == reuniao


def test_so_a_marca_ontem_move_para_o_dia_anterior():
    reuniao = date(2026, 9, 2)
    assert data_da_fala("ontem terminei o coletor", reuniao) == reuniao - timedelta(days=1)
    assert data_da_fala("ONTEM foi reuniao o dia todo", reuniao) == reuniao - timedelta(days=1)


def test_ontem_dentro_de_outra_palavra_nao_conta():
    reuniao = date(2026, 9, 2)
    assert data_da_fala("plantonteme nada", reuniao) == reuniao


# ── janelas sobrepostas: a dupla contagem do piloto ──────────────────────────


def h(inicio, fim):
    return Intervalo(datetime(2026, 9, 2, inicio, tzinfo=BRT),
                     datetime(2026, 9, 2, fim, tzinfo=BRT))


def test_duas_fontes_cobrindo_a_mesma_hora_contam_uma_vez():
    assert horas([h(9, 12), h(10, 13)]) == 4.0


def test_janelas_separadas_somam():
    assert horas([h(9, 11), h(14, 16)]) == 4.0


def test_fundir_junta_encostadas_e_preserva_a_ordem():
    fundidos = fundir([h(14, 16), h(9, 11), h(10, 12)])
    assert len(fundidos) == 2
    assert fundidos[0].horas == 3.0 and fundidos[1].horas == 2.0


def test_sobrepoe_e_simetrico():
    a, b = h(9, 12), h(10, 13)
    assert a.sobrepoe(b) and b.sobrepoe(a)
    assert not h(9, 10).sobrepoe(h(10, 11)), "encostar nao e sobrepor"


def test_intervalo_invertido_nao_da_hora_negativa():
    assert h(12, 9).horas == 0.0


# ── bolsao ───────────────────────────────────────────────────────────────────


def entrada(horas_, faturavel=True, list_id="901716443542"):
    return {"duration": int(horas_ * 3_600_000), "billable": faturavel,
            "task_location": {"list_id": list_id}}


BOLSAO = B.Bolsao("Soteria", "901716443542", horas_contratadas=100)


def test_bolsao_sem_horas_contratadas_e_recusado():
    with pytest.raises(ValueError):
        B.Bolsao("x", "1", 0)


def test_apurar_separa_faturavel_de_nao_faturavel():
    s = B.apurar([entrada(10), entrada(2, faturavel=False)], BOLSAO,
                 date(2026, 9, 1), date(2026, 9, 7))
    assert s.horas_gastas == 12 and s.faturaveis == 10 and s.nao_faturaveis == 2


@pytest.mark.parametrize("gasto,nivel", [
    (10, "ok"), (74, "ok"), (75, "atencao"), (89, "atencao"),
    (90, "critico"), (99, "critico"), (100, "estourado"), (120, "estourado"),
])
def test_faixas_de_alerta(gasto, nivel):
    s = B.apurar([entrada(gasto)], BOLSAO, date(2026, 9, 1), date(2026, 9, 7))
    assert s.nivel == nivel


def test_projecao_anda_por_dias_uteis_e_nao_por_dias_corridos():
    """Cinco dias uteis, 50h gastas, ritmo 10h/dia, restam 50h logo 5 dias uteis.

    01/09 e terca e a janela vai ate 07/09 (segunda). Cinco dias uteis a frente
    de 07/09 e 14/09, nao 12/09: andar em dias corridos atravessaria o fim de
    semana e adiantaria o alerta.
    """
    s = B.apurar([entrada(50)], BOLSAO, date(2026, 9, 1), date(2026, 9, 7))
    assert s.ritmo_diario == 10.0
    assert s.dias_ate_estourar == 5
    assert s.data_estouro == date(2026, 9, 14)
    assert s.data_estouro.weekday() < 5


def test_sem_dias_suficientes_nao_inventa_data():
    """Uma segunda lenta nao e um prazo."""
    s = B.apurar([entrada(80)], BOLSAO, date(2026, 9, 1), date(2026, 9, 2))
    assert s.ritmo_diario is None and s.data_estouro is None
    assert s.nivel == "atencao", "o percentual continua sendo reportado"


def test_bolsao_ja_estourado_nao_projeta_para_o_futuro():
    s = B.apurar([entrada(120)], BOLSAO, date(2026, 9, 1), date(2026, 9, 7))
    assert s.dias_ate_estourar == 0 and s.data_estouro == date(2026, 9, 7)


def test_percentual_e_horas_restantes():
    s = B.apurar([entrada(25)], BOLSAO, date(2026, 9, 1), date(2026, 9, 7))
    assert s.percentual == 0.25 and s.horas_restantes == 75


def test_digest_silencia_quando_nada_cruzou_a_faixa():
    s = B.apurar([entrada(10)], BOLSAO, date(2026, 9, 1), date(2026, 9, 7))
    assert B.digest([s]) == ""


def test_digest_ordena_do_mais_estourado_para_o_menos():
    a = B.apurar([entrada(95)], B.Bolsao("A", "1", 100), date(2026, 9, 1), date(2026, 9, 7))
    b = B.apurar([entrada(80)], B.Bolsao("B", "2", 100), date(2026, 9, 1), date(2026, 9, 7))
    saida = B.digest([b, a])
    assert saida.index("A:") < saida.index("B:")


def test_vigiar_filtra_entradas_pela_lista_do_projeto():
    class Falso:
        def entradas(self, *_a, **_k):
            return [entrada(10), entrada(90, list_id="outra")]

    (s,) = B.vigiar(Falso(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7))
    assert s.horas_gastas == 10, "somou horas de outro projeto"


def test_vigiar_sobrevive_a_falha_de_leitura():
    class Quebrado:
        def entradas(self, *_a, **_k):
            raise RuntimeError("api fora")

    assert B.vigiar(Quebrado(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7)) == []


# ── guardiao das datas ───────────────────────────────────────────────────────


def tarefa(nome, due=None, status="ideia", desc="", est=None, quem="Jordan"):
    return {"id": "t1", "name": nome, "due_date": due, "description": desc,
            "time_estimate": est, "status": {"status": status},
            "assignees": [{"username": quem}] if quem else []}


HOJE = date(2026, 9, 2)


def em(dias):
    return ms(datetime.combine(HOJE + timedelta(days=dias),
                               datetime.min.time(), tzinfo=BRT))


@pytest.mark.parametrize("dias,esperado", [
    (-3, "vencido"), (-1, "vencido"), (0, "vence hoje"),
    (1, "proximo"), (3, "proximo"), (4, "ok"), (30, "ok"),
])
def test_situacao_por_distancia_da_data(dias, esperado):
    (p,) = D.ler([tarefa("x", due=em(dias))])
    assert p.situacao(HOJE) == esperado


def test_tarefa_sem_data_e_reportada_como_sem_data():
    (p,) = D.ler([tarefa("x", due=None)])
    assert p.situacao(HOJE) == "sem data" and p.dias(HOJE) is None


def test_status_ideia_perto_do_prazo_nao_e_filtrado():
    """E exatamente a tarefa que vale sinalizar."""
    saida = D.digest(D.ler([tarefa("3.4 Lancamento", due=em(1), status="ideia")]), HOJE)
    assert "3.4 Lancamento" in saida and "ideia" in saida


def test_vencidos_saem_do_mais_atrasado_para_o_menos():
    prazos = D.ler([tarefa("recente", due=em(-1)), tarefa("antigo", due=em(-5))])
    saida = D.digest(prazos, HOJE)
    assert saida.index("antigo") < saida.index("recente")


def test_higiene_conta_descricao_estimativa_e_data():
    prazos = D.ler([tarefa("a"), tarefa("b", desc="tem", est=3600000, due=em(5))])
    problemas = D.higiene(prazos)
    assert any("sem descricao" in p for p in problemas)
    assert any("sem estimativa" in p for p in problemas)
    assert any("sem data" in p for p in problemas)


def test_digest_vazio_quando_tudo_esta_longe_e_limpo():
    prazos = D.ler([tarefa("a", due=em(30), desc="tem", est=1)])
    assert D.digest(prazos, HOJE) == ""


def test_ler_aguenta_tarefa_sem_responsavel_e_sem_nome():
    (p,) = D.ler([{"id": "t", "due_date": None, "assignees": []}])
    assert p.responsavel == "sem responsavel" and p.nome == "(sem nome)"


def test_vigiar_sobrevive_a_falha_de_leitura():
    class Quebrado:
        def tarefas_da_lista(self, *_a, **_k):
            raise RuntimeError("api fora")

    assert D.vigiar(Quebrado(), "901716443542", HOJE) == ""
