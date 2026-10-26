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


def tarefa(nome, due=None, status="ideia", desc="", est=None, quem="Jordan", tipo=None):
    return {"id": "t1", "name": nome, "due_date": due, "description": desc,
            "time_estimate": est,
            "status": {"status": status, **({"type": tipo} if tipo else {})},
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


@pytest.mark.parametrize("tipo", ["closed", "done", "Closed"])
def test_tarefa_finalizada_nao_aparece_como_vencida(tipo):
    """Um card fechado nao tem data a perder: listar como vencido enterra os reais."""
    prazos = D.ler([tarefa("Card concluido", due=em(-18),
                           status="publicado/finalizado", tipo=tipo)])
    assert prazos == []
    assert D.digest(prazos, HOJE) == ""


@pytest.mark.parametrize("tipo", [None, "open", "custom"])
def test_status_aberto_continua_vigiado_mesmo_vencido(tipo):
    """So o tipo que o ClickUp marca como acabado sai; o nome do status nao decide."""
    saida = D.digest(D.ler([tarefa("3.4 Lancamento", due=em(-2), status="publicado/finalizado",
                                   tipo=tipo)]), HOJE)
    assert "3.4 Lancamento" in saida and "Vencidos" in saida


def test_finalizada_sai_tambem_da_higiene():
    """Card fechado sem estimativa e historia: nao entra na contagem do 'de N'."""
    prazos = D.ler([tarefa("aberta", due=em(10), desc="tem"),
                    tarefa("fechada", due=em(-18), status="publicado/finalizado", tipo="closed")])
    assert len(prazos) == 1
    assert D.higiene(prazos) == ["1 de 1 sem estimativa de tempo"]


def test_status_que_nao_e_dicionario_nao_conta_como_finalizado():
    t = tarefa("x", due=em(-3))
    t["status"] = "closed"
    assert len(D.ler([t])) == 1


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


def test_datas_vigiar_sobrevive_a_falha_de_leitura():
    class Quebrado:
        def tarefas_da_lista(self, *_a, **_k):
            raise RuntimeError("api fora")

    assert D.vigiar(Quebrado(), "901716443542", HOJE) == ""


class _ListasFalsas:
    """Cliente que devolve tarefas por lista e anota quais listas foram lidas."""

    def __init__(self, por_lista):
        self.por_lista = por_lista
        self.lidas = []

    def tarefas_da_lista(self, lista, **_k):
        self.lidas.append(lista)
        if isinstance(self.por_lista[lista], Exception):
            raise self.por_lista[lista]
        return self.por_lista[lista]

    def tarefas_do_espaco(self, espaco, **k):
        self.lidas.append(f"espaco:{espaco}")
        self.pedidos_de_espaco = getattr(self, "pedidos_de_espaco", []) + [dict(k)]
        achado = self.por_lista.get(f"espaco:{espaco}", [])
        if isinstance(achado, Exception):
            raise achado
        return achado


def test_montar_tarefas_liga_o_guardiao_a_todas_as_listas_do_config():
    """A ligacao pegava so o primeiro projeto com list_id; o segundo nunca era lido."""
    from soteria_pmo import cli
    c = _ListasFalsas({"L1": [tarefa("do primeiro", due=em(-4))],
                       "L2": [tarefa("do segundo", due=em(-2))]})
    cfg = {"projetos": [{"nome": "Alfa", "list_id": "L1"}, {"nome": "Beta", "space_id": "S"},
                        {"nome": "Gama", "list_id": "L2"}]}
    saida = cli.montar_tarefas(cfg, c, HOJE)["datas"]()
    # A lista do segundo projeto e lida, e o espaco do Beta tambem (so tinha space_id).
    assert c.lidas == ["L1", "espaco:S", "L2"] and "do segundo" in saida


def test_uma_lista_sozinha_sai_igual_ao_vigiar_de_sempre():
    tarefas = [tarefa("atrasada", due=em(-4))]
    c = _ListasFalsas({"L1": tarefas})
    assert D.vigiar_projetos(c, [{"nome": "A", "list_id": "L1"}], HOJE) == D.vigiar(
        _ListasFalsas({"L1": tarefas}), "L1", HOJE)
    assert c.lidas == ["L1"]


def test_cada_projeto_e_lido_e_o_bloco_leva_o_nome():
    """Retorno do Max, 26/10/2026: com onze projetos no config so um tinha `list_id`, e o
    resumo mostrava as datas de um projeto so. Quem tem so `space_id` agora e lido pelo espaco."""
    c = _ListasFalsas({"L1": [tarefa("do primeiro", due=em(-4))],
                       "L2": [tarefa("do segundo", due=em(-2))],
                       "espaco:S": [tarefa("do cliente", due=em(-6))]})
    projetos = [{"nome": "Alfa", "list_id": "L1"}, {"nome": "Beta", "space_id": "S"},
                {"nome": "Gama", "list_id": "L2"}]
    saida = D.vigiar_projetos(c, projetos, HOJE)
    assert c.lidas == ["L1", "espaco:S", "L2"]
    assert "Guardiao das datas, Alfa" in saida and "do primeiro" in saida
    assert "Guardiao das datas, Beta" in saida and "do cliente" in saida
    assert "Guardiao das datas, Gama" in saida and "do segundo" in saida


def test_tarefa_cancelada_nao_e_atraso_mesmo_com_tipo_custom():
    """Medido em 26/10/2026: `cancelado` vem com type `custom` e aparecia como vencido ha 111 dias."""
    cancelada = dict(tarefa("cancelada", due=em(-111)), status={"status": "Cancelado", "type": "custom"})
    viva = tarefa("viva", due=em(-3))
    assert [p.nome for p in D.ler([cancelada, viva])] == ["viva"]


def test_status_desconhecido_sem_tipo_continua_aberto():
    """A excecao e de um nome so: o resto segue sem filtro por nome."""
    t = dict(tarefa("x", due=em(-3)), status={"status": "publicado/finalizado"})
    assert [p.nome for p in D.ler([t])] == ["x"]


def test_espaco_e_lido_so_nas_tarefas_abertas_e_sem_engolir_erro():
    c = _ListasFalsas({"L1": [], "espaco:S": [tarefa("x", due=em(-1))]})
    D.vigiar_projetos(c, [{"nome": "Alfa", "list_id": "L1"}, {"nome": "Beta", "space_id": "S"}], HOJE)
    assert c.pedidos_de_espaco == [{"incluir_fechadas": False, "levantar_erro": True}]


def test_espaco_nao_traz_higiene_de_card():
    """Descricao e estimativa faltando em centenas de tarefas de cliente e ruido; o pedido e datas."""
    c = _ListasFalsas({"L1": [], "espaco:S": [tarefa("vencida", due=em(-2))]})
    saida = D.vigiar_projetos(c, [{"nome": "Alfa", "list_id": "L1"}, {"nome": "Beta", "space_id": "S"}], HOJE)
    assert "Higiene do card" not in saida.split("Guardiao das datas, Beta")[1]


def test_espaco_com_muito_atraso_e_cortado_e_o_corte_e_dito():
    muitas = [dict(tarefa(f"t{n}", due=em(-n - 1)), id=f"id{n}") for n in range(30)]
    c = _ListasFalsas({"espaco:S": muitas})
    saida = D.vigiar_projetos(c, [{"nome": "Beta", "space_id": "S"}, {"nome": "Gama", "space_id": "S2"}], HOJE)
    assert f"... e mais {30 - D.LIMITE_POR_GRUPO_NO_ESPACO}" in saida


def test_cliente_encerrado_fica_de_fora_como_no_bolsao():
    c = _ListasFalsas({"espaco:S": [tarefa("x", due=em(-1))]})
    assert D.vigiar_projetos(c, [{"nome": "Conta Azul", "space_id": "S"}], HOJE) == ""
    assert c.lidas == []


def test_espaco_que_nao_pode_ser_lido_e_dito_e_nao_vira_saude():
    c = _ListasFalsas({"L1": [tarefa("viva", due=em(-2))], "espaco:S": RuntimeError("api fora")})
    saida = D.vigiar_projetos(c, [{"nome": "Alfa", "list_id": "L1"}, {"nome": "Beta", "space_id": "S"}], HOJE)
    assert "viva" in saida
    assert "nao puderam ser lidos" in saida and "Beta" in saida


def test_sem_lista_nem_espaco_o_guardiao_nao_diz_nada():
    c = _ListasFalsas({})
    assert D.vigiar_projetos(c, [{"nome": "A"}], HOJE) == ""
    assert D.vigiar_projetos(c, [], HOJE) == "" and c.lidas == []


def test_espaco_repetido_no_config_e_lido_uma_vez():
    c = _ListasFalsas({"espaco:S": [tarefa("x", due=em(-1))]})
    D.vigiar_projetos(c, [{"nome": "A", "space_id": "S"}, {"nome": "B", "space_id": "S"}], HOJE)
    assert c.lidas == ["espaco:S"]


def test_lista_repetida_no_config_e_lida_uma_vez():
    c = _ListasFalsas({"L1": [tarefa("x", due=em(-1))]})
    D.vigiar_projetos(c, [{"nome": "A", "list_id": "L1"}, {"nome": "B", "list_id": "L1"}], HOJE)
    assert c.lidas == ["L1"]


def test_lista_que_falha_nao_derruba_a_outra():
    c = _ListasFalsas({"L1": RuntimeError("api fora"), "L2": [tarefa("viva", due=em(-2))]})
    saida = D.vigiar_projetos(
        c, [{"nome": "Alfa", "list_id": "L1"}, {"nome": "Gama", "list_id": "L2"}], HOJE)
    assert "viva" in saida and "Gama" in saida


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


def test_projeto_pessoal_de_nome_proprio_so_e_visto_se_o_config_disser():
    """O que passou pela lista fixa em agosto de 2026, e custou 10,53h.

    `palweave` e nome proprio de projeto pessoal: nao ha palavra a acrescentar
    na lista do pacote que o alcance sem alcancar tambem nome de cliente. Quem
    sabe quais sao os proprios projetos e o dono da maquina.
    """
    from datetime import datetime
    from soteria_pmo import coletor as C
    from soteria_pmo.horas import Evidencia

    d = datetime(2026, 9, 2, 9, tzinfo=BRT)
    ev = [Evidencia("sessao_ia", d, d.replace(hour=11),
                    "sessao a1b2c3d4 em ~/Projects/palweave: ajuste de spawn")]

    cliente, pessoal = C.separar_pessoal(ev)
    assert (len(cliente), len(pessoal)) == (1, 0), "sem config, nao ha como saber"

    cliente, pessoal = C.separar_pessoal(ev, ("~/Projects/palweave",))
    assert (len(cliente), len(pessoal)) == (0, 1)


def test_sessao_de_ia_leva_o_cwd_e_o_titulo_e_nao_o_nome_da_pasta(tmp_path):
    """Medido nesta maquina em 10/09/2026: as 60 sessoes estao sob duas pastas
    e o `cwd` das mensagens aponta para 20 lugares. Enquanto a descricao vinha
    da pasta, toda sessao se chamava "em -home-joey" e nao havia o que filtrar.
    """
    import json
    from pathlib import Path

    from soteria_pmo import coletor as C

    pasta = tmp_path / "-home-alguem"
    pasta.mkdir()
    linhas = [
        {"type": "ai-title", "aiTitle": "Ajuste de spawn"},
        {"timestamp": "2026-09-02T12:00:00Z", "cwd": f"{Path.home()}/Projects/palweave"},
        {"timestamp": "2026-09-02T12:20:00Z"},
        {"timestamp": "2026-09-02T12:40:00Z", "cwd": f"{Path.home()}/Projects/soteria-pmo"},
    ]
    (pasta / "a1b2c3d4-0000.jsonl").write_text(
        "\n".join(json.dumps(l) for l in linhas), encoding="utf-8")

    (ev,) = C.sessoes_ia(tmp_path, date(2026, 9, 2), date(2026, 9, 2))
    assert "~/Projects/palweave" in ev.descricao
    assert "Ajuste de spawn" in ev.descricao
    # A linha sem cwd herda o anterior em vez de virar um lugar desconhecido.
    assert "-home-alguem" not in ev.descricao
    assert C.parece_pessoal(ev.descricao, ("palweave",))


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


def test_teto_sugerido_traz_os_tetos_que_o_max_confirmou_em_08_09():
    assert B.teto_sugerido("China Gate Sustentacao") == 100.0
    assert B.teto_sugerido("Yoshii Imoveis") == 160.0
    assert B.teto_sugerido("Grupo Dimas") == 30.0
    assert B.teto_sugerido("Grupo Angelus") == 160.0
    assert B.teto_sugerido("APET") == 60.0
    assert B.teto_sugerido("Gazin") == 40.0
    assert B.teto_sugerido("Grupo BM2") == 100.0
    assert B.teto_sugerido("IoX") is None  # o Max, em 21/10: "nao existe esse cliente"
    assert B.teto_sugerido("Cliente Desconhecido") is None


def test_chave_curta_nao_casa_dentro_de_outra_palavra():
    """Busca por substring daria teto a quem nunca teve. O cliente e APET."""
    assert B.teto_sugerido("Analise de Competencia") is None
    assert B.teto_sugerido("Carpetes do Sul") is None
    assert B.teto_sugerido("APET Sustentacao") == 60.0
    assert B.teto_sugerido("PET") is None, "nao existe cliente chamado PET"


def test_total_de_projeto_nao_se_mistura_com_teto_mensal():
    """390h da Unimed e o total do projeto, nao um teto que reseta todo mes."""
    assert B.total_de_projeto("Unimed Londrina") == 390.0
    assert B.teto_sugerido("Unimed Londrina") is None


def test_cliente_encerrado_e_reconhecido_como_encerrado():
    assert B.encerrado("Conta Azul") is True
    assert B.encerrado("China Gate") is False


def test_cliente_sem_teto_fixado_nao_ganha_um_numero_inventado():
    """A Concessionaria Reviver e projeto, sem media de bolsao. O Abner confirmou
    em 14/10/2026 que nao ha teto mensal; ela se acompanha pelo total do projeto,
    e nao se inventa teto mensal para ela."""
    assert B.teto_sugerido("Concessionaria Reviver") is None
    assert "teto mensal" in B.teto_a_confirmar("Concessionaria Reviver")


def test_o_cliente_se_chama_angelus_e_nao_anjos():
    """A transcricao automatica moeu o nome. "Grupo Anjos" nao existe nos 12
    espacos lidos em 08/09, entao a chave errada nao pode casar com nada."""
    assert B.teto_sugerido("Grupo Anjos") is None
    assert B.teto_a_confirmar("Grupo Anjos") is None


def test_o_teto_do_angelus_e_160_e_nao_o_meio_termo_de_100():
    """Ate 08/09 o codigo carregou 100.0, um meio-termo entre 75 e 150 que
    ninguem disse. Na reuniao o Max disse 100 e o Andre corrigiu para 160."""
    assert B.teto_sugerido("Grupo Angelus") == 160.0


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
        {"nome": "Concessionaria Reviver", "space_id": "1"},
        {"nome": "Yoshii", "space_id": "2"},
    ])
    assert [b.projeto for b in bolsoes] == ["Yoshii"]
    assert any("Concessionaria Reviver" in t and "sem teto configurado" in t
               for t in sem_teto)
    assert any("teto mensal" in t and "listas_total" in t for t in sem_teto), "diz o que se sabe e o que falta"


def test_cliente_encerrado_nao_e_vigiado_nem_cobrado_por_teto():
    """`encerrado()` existia, passava no teste unitario, e nunca era chamada.

    O teste que existia media a funcao isolada. Nada a ligava ao caminho que
    roda, entao a suite ficava verde enquanto o digest real pedia ao Max o
    teto da Conta Azul, que ele declarou encerrada em 08/09/2026. Este teste
    cobre a ligacao, que e onde o defeito estava.
    """
    bolsoes, sem_teto = B.carregar_bolsoes([
        {"nome": "Conta Azul", "space_id": "1"},
        {"nome": "China Gate", "space_id": "2"},
    ])
    assert [b.projeto for b in bolsoes] == ["China Gate"]

    linha = next(t for t in sem_teto if "Conta Azul" in t)
    assert "encerrado" in linha
    assert "sem teto configurado" not in linha, (
        "pedir teto de cliente encerrado e pedir numero que o Max ja disse nao existir")


def test_cliente_encerrado_com_teto_no_config_continua_fora():
    """Encerrado vence o teto: quem saiu da carteira nao volta por causa de um
    numero esquecido no config."""
    bolsoes, sem_teto = B.carregar_bolsoes([
        {"nome": "Conta Azul", "space_id": "1", "horas_contratadas": 120},
    ])
    assert bolsoes == []
    assert any("Conta Azul" in t and "encerrado" in t for t in sem_teto)


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


def test_fim_do_mes_inclusive_dezembro():
    from soteria_pmo.periodo import fim_do_mes
    assert fim_do_mes(date(2026, 9, 8)) == date(2026, 9, 30)
    assert fim_do_mes(date(2026, 2, 3)) == date(2026, 2, 28)
    assert fim_do_mes(date(2026, 12, 1)) == date(2026, 12, 31)


def test_projecao_que_cai_depois_da_virada_nao_e_estouro():
    """Teto mensal reseta. Uma data de estouro em outubro nao quer dizer que
    estoura: quer dizer que nao estoura em setembro."""
    s = B.Situacao(projeto="China Gate", horas_contratadas=100.0, horas_gastas=32.8,
                   faturaveis=32.8, nao_faturaveis=0.0, nivel="ok",
                   dias_uteis_observados=6, ritmo_diario=5.5,
                   data_estouro=date(2026, 10, 14), dias_ate_estourar=12,
                   fim_do_ciclo=date(2026, 9, 30))
    assert "nao estoura ate o fim do mes" in s.linha()


def test_estouro_dentro_do_ciclo_continua_datado():
    s = B.Situacao(projeto="Grupo Dimas", horas_contratadas=30.0, horas_gastas=28.0,
                   faturaveis=28.0, nao_faturaveis=0.0, nivel="critico",
                   dias_uteis_observados=6, ritmo_diario=4.6,
                   data_estouro=date(2026, 9, 10), dias_ate_estourar=2,
                   fim_do_ciclo=date(2026, 9, 30))
    assert "estoura em 10/09" in s.linha()


def test_bolsao_exclui_listas_de_projeto_do_mesmo_espaco():
    """Grupo Angelus tem 160h de sustentacao no espaco, mas frentes de projeto
    no mesmo espaco nao devem abater do bolsao."""
    b = B.Bolsao(projeto="Grupo Angelus", list_id="", horas_contratadas=160.0,
                 space_id="sp_angelus",
                 listas_projeto=("list_proj_1", "list_proj_2"))

    entrada_chamado = {"task_location": {"space_id": "sp_angelus", "list_id": "list_chamados"}}
    entrada_projeto = {"task_location": {"space_id": "sp_angelus", "list_id": "list_proj_1"}}
    entrada_outro = {"task_location": {"space_id": "sp_outro", "list_id": "list_chamados"}}

    assert b.pertence(entrada_chamado), "entrada de sustentacao deve pertencer ao bolsao"
    assert not b.pertence(entrada_projeto), "entrada de projeto nao deve consumir bolsao de sustentacao"
    assert not b.pertence(entrada_outro), "entrada de outro espaco nao deve pertencer"


def test_bolsao_filtra_listas_sustentacao_se_especificadas():
    b = B.Bolsao(projeto="Grupo Dimas", list_id="", horas_contratadas=30.0,
                 space_id="sp_dimas",
                 listas_sustentacao=("list_sust_oficial",))

    entrada_sust = {"task_location": {"space_id": "sp_dimas", "list_id": "list_sust_oficial"}}
    entrada_avulsa = {"task_location": {"space_id": "sp_dimas", "list_id": "list_outra"}}

    assert b.pertence(entrada_sust)
    assert not b.pertence(entrada_avulsa)


def test_carregar_bolsoes_propaga_listas_projeto_e_sustentacao():
    cfg = [
        {
            "nome": "Grupo Angelus",
            "space_id": "sp_angelus",
            "horas_contratadas": 160,
            "tipo": "sustentacao",
            "listas_projeto": ["list_proj_1"],
            "listas_sustentacao": ["list_chamados"],
        }
    ]
    bolsoes, sem_teto = B.carregar_bolsoes(cfg)
    assert len(bolsoes) == 1
    assert bolsoes[0].listas_projeto == ("list_proj_1",)
    assert bolsoes[0].listas_sustentacao == ("list_chamados",)
    assert bolsoes[0].tipo == "sustentacao"



def test_bolsao_que_ja_passou_do_teto_nao_projeta_estouro():
    """13/10: o Dimas aparecia a 280% com 'no ritmo atual estoura em 13/10',
    como se ainda houvesse o que evitar."""
    s = B.Situacao(projeto="Grupo Dimas", horas_contratadas=30.0, horas_gastas=84.0,
                   faturaveis=84.0, nao_faturaveis=0.0, nivel="estourado",
                   dias_uteis_observados=8, ritmo_diario=10.5,
                   data_estouro=date(2026, 10, 13), dias_ate_estourar=0,
                   fim_do_ciclo=date(2026, 10, 31))
    assert "ja passou do teto em 54.0h" in s.linha()
    assert "estoura em" not in s.linha()


def _prazo(tid, nome, dia_, parent=None):
    return D.Prazo(task_id=tid, nome=nome, responsavel="Jordan", vence_em=dia_,
                   status="desenvolvimento", tem_descricao=True, tem_estimativa=True,
                   parent_id=parent)


def test_datas_recolhe_subtarefas_com_a_mesma_data_da_mae():
    hoje = date(2026, 10, 13)
    v = date(2026, 10, 8)
    prazos = [_prazo("m", "5. Fase 2", v), _prazo("a", "5.1", v, "m"),
              _prazo("b", "5.2", v, "m"), _prazo("c", "5.2.1", v, "b"),
              _prazo("x", "Card avulso", date(2026, 9, 28))]
    txt = D.digest(prazos, hoje, incluir_higiene=False)
    assert "mais 3 subtarefas com a mesma data" in txt
    assert "5.1" not in txt and "5.2.1" not in txt
    assert "Card avulso" in txt


def test_datas_subtarefa_com_data_propria_continua_aparecendo():
    hoje = date(2026, 10, 13)
    prazos = [_prazo("m", "Mae", date(2026, 10, 8)),
              _prazo("a", "Filha com outra data", date(2026, 10, 10), "m")]
    txt = D.digest(prazos, hoje, incluir_higiene=False)
    assert "Filha com outra data" in txt and "subtarefa" not in txt


def test_bolsao_no_teto_exato_nao_diz_que_passou():
    s = B.Situacao(projeto="X", horas_contratadas=30.0, horas_gastas=30.0,
                   faturaveis=30.0, nao_faturaveis=0.0, nivel="estourado",
                   dias_uteis_observados=8, ritmo_diario=3.75,
                   data_estouro=date(2026, 10, 13), dias_ate_estourar=0,
                   fim_do_ciclo=date(2026, 10, 31))
    assert "no teto exato" in s.linha()
    assert "ja passou" not in s.linha()


def test_datas_uma_subtarefa_fica_no_singular():
    hoje = date(2026, 10, 13)
    v = date(2026, 10, 8)
    txt = D.digest([_prazo("m", "Mae", v), _prazo("a", "Filha", v, "m")], hoje, incluir_higiene=False)
    assert "mais 1 subtarefa com a mesma data" in txt
    assert "1 subtarefas" not in txt
