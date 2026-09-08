"""Windows, the budget watch and the date guardian.

The cases that matter here are the ones that already went wrong once: hours
counted twice from two evidence sources covering the same stretch, a standup
sentence dated to the wrong day, and a projection that walked calendar days
through a weekend the team did not work.
"""

from datetime import date, datetime, timedelta

import pytest

from soteria_pmo import bolsao as B
from soteria_pmo import datas as D
from soteria_pmo.periodo import (
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
        def membros(self):
            return [{"id": "1"}, {"id": "2"}]

        def entradas(self, *_a, **_k):
            return [entrada(10), entrada(90, list_id="outra")]

    (s,) = B.vigiar(Falso(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7)).situacoes
    assert s.horas_gastas == 10, "somou horas de outro projeto"


def test_vigiar_sobrevive_a_falha_de_leitura():
    class Quebrado:
        def membros(self):
            return [{"id": "1"}]

        def entradas(self, *_a, **_k):
            raise RuntimeError("api fora")

    v = B.vigiar(Quebrado(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7))
    assert v.situacoes == [] and v.falhas


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


# ── defeitos que a revisao do modelo local encontrou ─────────────────────────


def test_falha_de_leitura_aparece_no_digest_em_vez_de_virar_silencio():
    """API fora do ar e semana saudavel produziam a mesma saida vazia."""
    class Quebrado:
        def membros(self):
            return [{"id": "1"}]

        def entradas(self, *_a, **_k):
            raise RuntimeError("api fora")

    v = B.vigiar(Quebrado(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7))
    assert v.situacoes == [] and len(v.falhas) == 1
    saida = B.digest(v)
    assert saida != "", "silencio aqui e indistinguivel de tudo bem"
    assert "Nao foi possivel ler" in saida and "Soteria" in saida
    assert "nao quer dizer que estejam bem" in saida


def test_vigilancia_sem_falha_e_sem_alerta_continua_silenciosa():
    class Ok:
        def membros(self):
            return [{"id": "1"}]

        def entradas(self, *_a, **_k):
            return [entrada(10)]

    v = B.vigiar(Ok(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7))
    assert v.falhas == [] and B.digest(v) == ""


def test_digest_ainda_aceita_lista_pura_de_situacoes():
    s = B.apurar([entrada(95)], BOLSAO, date(2026, 9, 1), date(2026, 9, 7))
    assert "Soteria" in B.digest([s])


def test_percentual_nao_divide_por_zero_se_a_situacao_for_construida_na_mao():
    s = B.Situacao("x", 0, 10, 10, 0, "ok", 5, None, None, None)
    assert s.percentual == 0.0


# ── evidencia pessoal separada da de cliente ─────────────────────────────────


def test_evidencia_pessoal_e_separada_da_de_cliente():
    """A maquina mistura as duas: o vault tem nota sobre Conan Exiles e sobre
    ClickUp, e o historico tem Discord e SharePoint. Cobrar a primeira e a
    mesma classe das 16h indevidas."""
    from datetime import datetime
    from soteria_pmo import coletor as C
    from soteria_pmo.horas import Evidencia

    def e(desc):
        d = datetime(2026, 9, 2, 9, tzinfo=BRT)
        return Evidencia("nota_vault", d, d, desc)

    cliente, pessoal = C.separar_pessoal([
        e("nota: Cronograma dos Agentes PMO"),
        e("nota: Conan Exiles UE5 travamentos"),
        e("app.clickup.com: Inbox Soteria"),
        e("nota: Discord travado sob ProtonVPN"),
    ])
    assert len(cliente) == 2 and len(pessoal) == 2
    assert all("clickup" in c.descricao.lower() or "PMO" in c.descricao for c in cliente)


def test_o_resumo_diz_quanto_foi_separado_como_pessoal():
    from datetime import datetime
    from soteria_pmo import coletor as C
    from soteria_pmo.horas import Evidencia
    d = datetime(2026, 9, 2, 9, tzinfo=BRT)
    ev = [Evidencia("nota_vault", d, d.replace(hour=11), "nota: Palworld crash")]
    texto = C.resumo(ev, [])
    assert "provavelmente pessoais" in texto and "confira" in texto


def test_falha_ao_listar_a_equipe_e_reportada_e_nao_impede_a_leitura():
    """O bolsao e da equipe toda, entao ele precisa nomear todo mundo. Se a
    lista falhar, isso vira falha visivel em vez de virar leitura estreita
    passando por leitura completa."""
    class SemMembros:
        def membros(self):
            raise RuntimeError("sem permissao")

        def entradas(self, *_a, **_k):
            return [entrada(10)]

    v = B.vigiar(SemMembros(), [BOLSAO], date(2026, 9, 1), date(2026, 9, 7))
    assert any("membros" in f for f in v.falhas)


def test_git_e_consultado_com_hora_explicita(tmp_path, monkeypatch):
    """Git le uma data sem hora como aquele dia NA HORA ATUAL, entao as 16:11
    um --since de hoje descarta tudo que foi commitado antes das 16:11 de hoje.
    Medido: 0 commits com a data nua contra 18 com T00:00:00, no mesmo repo."""
    import subprocess
    from soteria_pmo import coletor as C

    (tmp_path / ".git").mkdir()
    visto = {}

    class R:
        stdout = ""

    def fake_run(cmd, **kw):
        visto["cmd"] = cmd
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    C.commits([tmp_path], date(2026, 9, 2), date(2026, 9, 2))

    cmd = " ".join(visto["cmd"])
    assert "--since=2026-09-02T00:00:00" in cmd
    assert "--until=2026-09-02T23:59:59" in cmd


def test_teto_sugerido_traz_so_os_tetos_ditos_com_firmeza():
    assert B.teto_sugerido("China Gate Sustentacao") == 100.0
    assert B.teto_sugerido("Yoshii Imoveis") == 160.0
    assert B.teto_sugerido("Grupo Dimas") == 30.0
    assert B.teto_sugerido("Cliente Desconhecido") is None


def test_cliente_sem_teto_fixado_nao_ganha_um_numero_inventado():
    """O Grupo Angelus foi dito como "sem limite rigido, algo em torno de 150,
    75", e o codigo carregava 100.0, o meio-termo que ninguem falou."""
    assert B.teto_sugerido("Grupo Angelus") is None
    assert "75" in B.teto_a_confirmar("Grupo Angelus")


def test_o_cliente_se_chama_angelus_e_nao_anjos():
    """A transcricao automatica moeu o nome, e a chave antiga nunca casaria:
    os 12 espacos foram lidos do workspace em 08/09 e nenhum e "Grupo Anjos"."""
    assert B.teto_a_confirmar("Grupo Anjos") is None
    assert B.teto_a_confirmar("Grupo Angelus") is not None


def test_o_que_e_incerto_e_dito_como_incerto_e_nao_calado():
    assert B.teto_a_confirmar("Cliente Desconhecido") is None


def test_carregar_bolsoes_de_config_ou_lista():
    cfg = {
        "bolsoes": [
            {"projeto": "China Gate", "list_id": "lg_1", "horas_contratadas": 100.0},
            {"projeto": "Yoshii", "list_id": "lg_2"},  # Usa teto sugerido 160h
        ]
    }
    bolsoes, _sem_teto = B.carregar_bolsoes(cfg)
    assert len(bolsoes) == 2
    assert bolsoes[0].horas_contratadas == 100.0
    assert bolsoes[1].horas_contratadas == 160.0


def test_higiene_pega_inversao_de_data_entre_mae_e_filha():
    # Caso real registrado em 02/09: tarefa-mae com data vencendo antes da subtarefa
    tarefas = [
        {"id": "mae", "name": "3. Desenvolvimento", "due_date": ms(datetime(2026, 9, 3, tzinfo=BRT)),
         "parent": None, "assignees": [{"username": "Jordan"}], "description": "mae", "time_estimate": 1000},
        {"id": "filha", "name": "3.1 Coleta de Evidencia", "due_date": ms(datetime(2026, 9, 8, tzinfo=BRT)),
         "parent": "mae", "assignees": [{"username": "Jordan"}], "description": "filha", "time_estimate": 1000},
    ]
    prazos = D.ler(tarefas)
    probs = D.higiene(prazos)
    assert any("inversao de datas" in p.lower() for p in probs)
    assert any("3. Desenvolvimento" in p and "3.1 Coleta de Evidencia" in p for p in probs)



def test_projeto_sem_teto_sai_nomeado_em_vez_de_sumir_do_digest():
    """Ausencia do digest e indistinguivel de projeto saudavel. Ate 08/09 um
    projeto sem teto era descartado calado em carregar_bolsoes."""
    bolsoes, sem_teto = B.carregar_bolsoes([
        {"nome": "Grupo Angelus", "space_id": "1"},
        {"nome": "Yoshii", "space_id": "2"},
    ])
    assert [b.projeto for b in bolsoes] == ["Yoshii"]
    assert any("Grupo Angelus" in t and "sem teto configurado" in t for t in sem_teto)
    assert any("75" in t for t in sem_teto), "diz o que se sabe, mesmo incerto"


def test_o_digest_conta_quem_ficou_fora_da_projecao():
    v = B.Vigilancia(sem_teto=["Grupo Anjos: sem teto configurado"])
    saida = B.digest(v)
    assert "Sem teto para medir contra" in saida
    assert "Grupo Anjos" in saida
    assert "fora da projecao de estouro" in saida


def test_o_bolsao_de_um_cliente_e_o_espaco_e_nao_uma_lista():
    """Medido no workspace em 08/09: o trabalho de um cliente se espalha por
    dezenas de listas do espaco dele. Casar por uma lista mede uma fatia."""
    b = B.Bolsao(projeto="China Gate", list_id="", horas_contratadas=100.0,
                 space_id="90070091337")
    sustentacao = {"task_location": {"list_id": "901704356465",
                                     "space_id": "90070091337"}}
    sprint = {"task_location": {"list_id": "901716501450",
                                "space_id": "90070091337"}}
    outro_cliente = {"task_location": {"list_id": "900902364226",
                                       "space_id": "90090493842"}}
    assert b.pertence(sustentacao) and b.pertence(sprint)
    assert not b.pertence(outro_cliente)


def test_sem_espaco_o_bolsao_ainda_vigia_uma_lista_so():
    b = B.Bolsao(projeto="Uma frente", list_id="123", horas_contratadas=10.0)
    assert b.pertence({"task_location": {"list_id": "123", "space_id": "9"}})
    assert not b.pertence({"task_location": {"list_id": "456", "space_id": "9"}})


def test_bolsao_sem_lista_nem_espaco_e_recusado_na_construcao():
    with pytest.raises(ValueError):
        B.Bolsao(projeto="Nenhum lugar", list_id="", horas_contratadas=10.0)
