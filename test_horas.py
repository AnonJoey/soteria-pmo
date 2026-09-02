"""The hours engine, tested against the two measured cycles.

The numbers in these tests are the real ones: 39,1h of 130,1h in the first
cycle, 54h of 89,5h in the second, and days 04 and 05/08 that came back with no
evidence at all and were normal working days. Every assertion about "asks
instead of reporting zero" is that pair of days.
"""

from datetime import date, datetime, timedelta

import pytest

from delegation_core.pmo import horas as H
from delegation_core.pmo.clickup import Aprovacao
from delegation_core.pmo.periodo import BRT

SEG = date(2026, 8, 31)   # segunda
TER = date(2026, 9, 1)
QUA = date(2026, 9, 2)
SEX = date(2026, 9, 4)
SAB = date(2026, 9, 5)


def ev(tipo, dia, h1, h2, desc="trabalho"):
    return H.Evidencia(
        tipo=tipo,
        inicio=datetime.combine(dia, datetime.min.time(), tzinfo=BRT).replace(hour=h1),
        fim=datetime.combine(dia, datetime.min.time(), tzinfo=BRT).replace(hour=h2),
        descricao=desc,
    )


def fala(dia, texto="fiz o coletor", atividade="Desenvolvimento do coletor", hs=None):
    return H.Fala(texto=texto, atividade=atividade, dia=dia, horas_declaradas=hs)


# ── o protocolo de lacunas: o coracao do modulo ──────────────────────────────


def test_dia_sem_evidencia_vira_pergunta_e_nunca_zero():
    """04 e 05/08 do segundo ciclo: zero evidencia, dias normais de trabalho."""
    propostas, lacunas = H.apurar_dia(QUA, [], [], "t1", "Soteria", ("desenvolvimento",))
    assert propostas == []
    assert len(lacunas) == 1
    assert "O que voce fez" in lacunas[0].pergunta
    assert lacunas[0].horas_em_aberto == 8.0


def test_evidencia_parcial_pergunta_pelo_resto_do_dia():
    """A diferenca entre 39,1h e 130,1h e essa pergunta."""
    _, lacunas = H.apurar_dia(QUA, [ev("commit", QUA, 9, 12)], [],
                              "t1", "Soteria", ("desenvolvimento",))
    (l,) = [x for x in lacunas if x.motivo == "evidencia parcial"]
    assert l.horas_em_aberto == 5.0
    assert "outras 5.0h" in l.pergunta


def test_dia_cheio_nao_gera_lacuna_de_cobertura():
    _, lacunas = H.apurar_dia(QUA, [ev("commit", QUA, 9, 17)], [],
                              "t1", "Soteria", ("desenvolvimento",))
    assert [x for x in lacunas if x.motivo == "evidencia parcial"] == []


def test_faltando_menos_de_duas_horas_nao_incomoda():
    _, lacunas = H.apurar_dia(QUA, [ev("commit", QUA, 9, 16)], [],
                              "t1", "Soteria", ("desenvolvimento",))
    assert [x for x in lacunas if x.motivo == "evidencia parcial"] == []


def test_apuracao_com_lacuna_aberta_nao_esta_pronta_para_lancar():
    ap = H.apurar(QUA, QUA, [], [], "t1", "Soteria")
    assert not ap.pronta_para_lancar


def test_lancar_com_lacuna_aberta_levanta():
    ap = H.apurar(QUA, QUA, [], [], "t1", "Soteria")
    with pytest.raises(ValueError, match="lacuna"):
        H.lancar(object(), ap, Aprovacao.de("jordan", "x"))


def test_lancar_sem_proposta_nenhuma_tambem_e_recusado():
    ap = H.Apuracao(QUA, QUA)
    assert not ap.pronta_para_lancar


# ── cobertura: o numero que nao pode sumir ───────────────────────────────────


def test_cobertura_compara_com_o_esperado_e_nao_consigo_mesma():
    """Dividir o achado pelo achado da 100% sempre, que e o numero que enganou."""
    ap = H.apurar(SEG, SEX, [ev("commit", SEG, 9, 12)], [], "t1", "Soteria")
    assert ap.dias_uteis == 5 and ap.horas_esperadas == 40
    assert ap.horas_propostas == 3.0
    assert ap.cobertura == pytest.approx(3 / 40)


def test_cobertura_do_primeiro_ciclo_reproduzida():
    """39,1h de 130,1h reais deu 30%."""
    ap = H.Apuracao(SEG, SEX)
    ap.horas_esperadas_por_dia = 130.1 / 5
    ap.propostas = [H.Proposta(SEG, "t1", "x (Soteria)", 39.1, True, 1.0, ())]
    assert ap.cobertura == pytest.approx(0.30, abs=0.005)


def test_cobertura_nao_passa_de_100_por_cento():
    ap = H.apurar(QUA, QUA, [ev("commit", QUA, 0, 23)], [], "t1", "Soteria")
    assert ap.cobertura == 1.0


def test_relatorio_sempre_imprime_a_cobertura():
    for evid in ([], [ev("commit", QUA, 9, 17)]):
        texto = H.relatorio(H.apurar(QUA, QUA, evid, [], "t1", "Soteria"))
        assert "Cobertura da evidencia:" in texto


def test_dias_cegos_sao_listados_no_relatorio():
    ap = H.apurar(SEG, SEX, [ev("commit", SEG, 9, 17)], [], "t1", "Soteria")
    assert len(ap.dias_cegos) == 4
    assert "Dias sem nenhuma evidencia" in H.relatorio(ap)


def test_fim_de_semana_nao_conta_como_dia_cego():
    ap = H.apurar(SEX, SAB, [ev("commit", SEX, 9, 17)], [], "t1", "Soteria")
    assert ap.dias_cegos == []


# ── confianca e citacao ──────────────────────────────────────────────────────


def test_transcricao_vale_mais_que_pilha_de_abas():
    so_navegador = H._confianca([ev("navegador", QUA, 9, 12)] * 3, tem_fala=False)
    so_fala = H._confianca([], tem_fala=True)
    assert so_fala > so_navegador


def test_a_confianca_e_sobre_as_horas_e_nao_sobre_a_atividade():
    """Na primeira versao isso devolvia 1.00 para as cinco propostas de uma
    semana real, porque fala existe quase todo dia e a transcricao pesa mais
    que tudo. Score que nao varia nao e score."""
    sem_hora = H._confianca([ev("commit", QUA, 9, 12)], tem_fala=True,
                            horas_declaradas=False)
    com_hora = H._confianca([ev("commit", QUA, 9, 12)], tem_fala=True,
                            horas_declaradas=True)
    assert com_hora == 1.0
    assert sem_hora < 1.0, "fala sem hora nao certifica duracao"


def test_sem_hora_declarada_nunca_chega_a_1():
    """O teto sem hora declarada e 0.95: sobra sempre a duvida da duracao."""
    tudo = [ev(t, QUA, 9, 12) for t in
            ("commit", "sessao_ia", "nota_vault", "reuniao", "arquivo", "navegador")]
    assert H._confianca(tudo, tem_fala=True, horas_declaradas=False) <= 0.95


def test_fala_sozinha_sustenta_pouco_a_duracao():
    """Ela prova que o dia foi trabalhado, nao quanto."""
    assert H._confianca([], tem_fala=True, horas_declaradas=False) == 0.55


def test_fontes_independentes_somam_pouco_e_com_teto():
    uma = H._confianca([ev("commit", QUA, 9, 10)], tem_fala=False)
    varias = H._confianca([ev("commit", QUA, 9, 10), ev("nota_vault", QUA, 10, 11),
                           ev("arquivo", QUA, 11, 12)], tem_fala=False)
    assert varias > uma and varias <= 0.95


def test_fonte_com_duracao_medida_vence_fonte_de_instante():
    """Reuniao traz a duracao lida da transcricao; commit e um instante cuja
    janela so existe porque o coletor agrupou os vizinhos."""
    reuniao = H._confianca([ev("reuniao", QUA, 14, 15)], tem_fala=False)
    commit = H._confianca([ev("commit", QUA, 9, 10)], tem_fala=False)
    navegador = H._confianca([ev("navegador", QUA, 9, 10)], tem_fala=False)
    assert reuniao > commit > navegador


def test_sem_nenhuma_fonte_a_confianca_e_zero():
    assert H._confianca([], tem_fala=False) == 0.0


def test_confianca_baixa_gera_pergunta_de_confirmacao():
    propostas, lacunas = H.apurar_dia(QUA, [ev("navegador", QUA, 9, 17)], [],
                                      "t1", "Soteria", ("desenvolvimento",))
    assert propostas[0].duvidosa
    assert any("Confirma" in l.pergunta for l in lacunas)


def test_proposta_carrega_as_citacoes_que_a_sustentam():
    p, _ = H.apurar_dia(QUA, [ev("commit", QUA, 9, 17, "commit abc123")],
                        [fala(QUA, "terminei o coletor")], "t1", "Soteria",
                        ("desenvolvimento",))
    assert "terminei o coletor" in p[0].citacoes
    assert "commit abc123" in p[0].citacoes


def test_relatorio_mostra_as_citacoes():
    ap = H.apurar(QUA, QUA, [ev("commit", QUA, 9, 17, "commit abc123")],
                  [fala(QUA)], "t1", "Soteria")
    assert "> " in H.relatorio(ap)


# ── janelas e horas declaradas ───────────────────────────────────────────────


def test_janelas_sobrepostas_de_duas_fontes_contam_uma_vez():
    p, _ = H.apurar_dia(QUA, [ev("commit", QUA, 9, 12), ev("sessao_ia", QUA, 10, 13)],
                        [], "t1", "Soteria", ("desenvolvimento",))
    assert p[0].horas == 4.0


def test_hora_declarada_na_fala_vence_a_janela_de_evidencia():
    """A pessoa estava la; a maquina so viu parte."""
    p, _ = H.apurar_dia(QUA, [ev("commit", QUA, 9, 10)], [fala(QUA, hs=7.5)],
                        "t1", "Soteria", ("desenvolvimento",))
    assert p[0].horas == 7.5


def test_evidencia_de_outro_dia_nao_entra():
    p, _ = H.apurar_dia(QUA, [ev("commit", TER, 9, 17)], [fala(QUA, hs=8)],
                        "t1", "Soteria", ("desenvolvimento",))
    assert p[0].horas == 8.0
    assert "commit" not in p[0].fontes


def test_evidencia_de_duracao_zero_vira_pergunta():
    p, l = H.apurar_dia(QUA, [ev("commit", QUA, 9, 9)], [], "t1", "Soteria",
                        ("desenvolvimento",))
    assert p == [] and l[0].motivo == "evidencia sem duracao aproveitavel"


# ── formato da casa e faturamento ────────────────────────────────────────────


def test_descricao_termina_com_o_cliente_entre_parenteses():
    d = H.descricao_da_casa("Desenvolvimento do coletor", "Soteria")
    assert d.endswith("(Soteria)")
    assert H.confere_formato(d) == []


def test_descricao_sem_cliente_e_apontada():
    assert "sem cliente" in " ".join(H.confere_formato("Desenvolvimento do coletor"))


def test_descricao_vazia_e_apontada():
    assert "vazia" in " ".join(H.confere_formato("   "))


def test_progressao_entra_antes_do_cliente():
    d = H.descricao_da_casa("Desenvolvimento", "Soteria", "2 janelas")
    assert d == "Desenvolvimento 2 janelas (Soteria)"


@pytest.mark.parametrize("tags,esperado", [
    (("desenvolvimento",), True),
    (("reunião com o cliente",), True),
    (("alinhamento técnico",), True),
    (("apoio técnico",), True),
    (("planejamento",), True),
    (("daily",), False),
    (("reunião interna",), False),
    (("desenvolvimento", "daily"), False),
])
def test_faturamento_segue_a_atividade_e_nao_um_default(tags, esperado):
    """Marcar o lote inteiro como faturavel foi o que cobrou 16h indevidas.

    O vocabulario aqui e o da casa, copiado da nota de referencia. Uma versao
    anterior deste teste usava tags plausiveis e inventadas, o que o fazia
    passar contra um vocabulario que nao existe no ClickUp.
    """
    assert H.classificar_faturavel(tags) is esperado


def test_o_lancamento_de_horas_nao_e_faturavel_apesar_da_tag_planejamento():
    """A unica atividade cuja tag nao decide.

    Lancar horas leva a tag planejamento e nao e faturavel; todo o resto com
    planejamento e. Decidir so pela tag cobra o proprio ato de cobrar.
    """
    assert H.classificar_faturavel(("planejamento",), "Lancamento ClickUp") is False
    assert H.classificar_faturavel(("planejamento",), "Planejamento do sprint") is True


def test_as_13_tags_da_casa_sao_as_reais():
    from delegation_core.pmo.clickup import TAGS_DA_CASA
    assert TAGS_DA_CASA == {
        "desenvolvimento", "ajustes em qas", "análise", "atividade de qas",
        "apoio técnico", "alinhamento técnico", "planejamento", "reunião interna",
        "reunião com o cliente", "daily", "elaboração de material técnico",
        "deploy", "bug",
    }


def test_a_proposta_leva_o_faturamento_da_atividade():
    p, _ = H.apurar_dia(QUA, [ev("reuniao", QUA, 9, 17)], [], "t1", "Soteria", ("daily",))
    assert p[0].faturavel is False


# ── conversao para lancamento ────────────────────────────────────────────────


def test_para_lancamento_preserva_tudo_e_valida():
    p = H.Proposta(QUA, "t1", "Desenvolvimento (Soteria)", 3.5, True, 0.95,
                   ("desenvolvimento",))
    l = p.para_lancamento(datetime.combine(QUA, datetime.min.time(), tzinfo=BRT))
    assert l.duracao_ms == int(3.5 * 3_600_000)
    assert l.faturavel is True and l.tags == ("desenvolvimento",)
    assert l.problemas() == []


def test_lancar_janela_limpa_chama_o_cliente_uma_vez_por_proposta():
    chamadas = []

    class FalsoClickUp:
        def lancar(self, lanc, aprov):
            chamadas.append((lanc.task_id, lanc.duracao_ms, aprov.quem))
            return "ok"

    ap = H.apurar(QUA, QUA, [ev("commit", QUA, 9, 17)], [fala(QUA, hs=8)],
                  "t1", "Soteria")
    assert ap.pronta_para_lancar
    H.lancar(FalsoClickUp(), ap, Aprovacao.de("jordan", "02/09"))
    assert chamadas == [("t1", 8 * 3_600_000, "jordan")]


# ── o interprete e um protocolo, nao um modelo ───────────────────────────────


def test_um_interprete_falso_serve_o_motor_inteiro():
    class Falso:
        def falas_de_trabalho(self, texto, dia):
            return [H.Fala(texto, "Planejamento", dia, 6.0)]

    falas = Falso().falas_de_trabalho("planejei o dia todo", QUA)
    ap = H.apurar(QUA, QUA, [], falas, "t1", "Soteria")
    assert ap.horas_propostas == 6.0
    assert "transcricao" in ap.propostas[0].fontes


def test_lancamento_clickup_e_reconhecido_com_ou_sem_acento():
    """A atividade chega de transcricao tanto quanto do ClickUp."""
    for escrito in ("Lançamento ClickUp", "Lancamento ClickUp",
                    "lancamento clickup", "LANÇAMENTO CLICKUP",
                    "Lançamento ClickUp do periodo (Soteria)"):
        assert H.classificar_faturavel(("planejamento",), escrito) is False


# ── falas que caem fora dos dias percorridos ─────────────────────────────────


def test_fala_datada_em_fim_de_semana_vira_pergunta_em_vez_de_sumir():
    """Numa segunda, "ontem" resolve para domingo. O apurar so percorre dias
    uteis, entao sem isso a fala seria consumida por ninguem."""
    domingo = date(2026, 8, 30)
    seg, sex = date(2026, 8, 31), date(2026, 9, 4)
    ap = H.apurar(seg, sex, [], [fala(domingo, atividade="Ajuste do coletor", hs=3)],
                  "t1", "Soteria")
    orfas = [l for l in ap.lacunas if "nao percorre" in l.motivo]
    assert len(orfas) == 1
    assert orfas[0].dia == domingo
    assert "fim de semana" in orfas[0].motivo
    assert orfas[0].horas_em_aberto == 3
    assert not ap.pronta_para_lancar


def test_fala_datada_antes_da_janela_tambem_vira_pergunta():
    """Um nome de dia da semana pode alcancar antes do inicio apurado."""
    antes = date(2026, 8, 28)
    ap = H.apurar(date(2026, 8, 31), date(2026, 9, 4), [],
                  [fala(antes, atividade="Pesquisa de MCP")], "t1", "Soteria")
    assert any("fora da janela" in l.motivo for l in ap.lacunas)


def test_fala_dentro_da_janela_nao_gera_lacuna_de_orfa():
    ap = H.apurar(QUA, QUA, [ev("commit", QUA, 9, 17)], [fala(QUA, hs=8)], "t1", "Soteria")
    assert [l for l in ap.lacunas if "nao percorre" in l.motivo] == []


# ── o interprete das dailies ─────────────────────────────────────────────────


def test_atividade_repetida_na_mesma_daily_vira_uma_so():
    """Visto na daily real de 25/08: o modelo devolveu a mesma atividade
    datada em dois dias, o que viraria duas propostas para um trabalho so."""
    from delegation_core.pmo.daily import InterpreteLocal
    resposta = (
        "ATIVIDADE: Finalizacao do documento\nQUANDO: ontem\nHORAS: ?\n---\n"
        "ATIVIDADE: Finalizacao do documento\nQUANDO: hoje\nHORAS: ?\n")
    i = InterpreteLocal("Jordan", chamar=lambda *a: resposta)
    falas = i.falas_de_trabalho("qualquer coisa", QUA)
    assert len(falas) == 1
    assert falas[0].dia == TER, "fica com a data mais antiga"


def test_sem_trabalho_devolve_lista_vazia():
    from delegation_core.pmo.daily import InterpreteLocal
    i = InterpreteLocal("Jordan", chamar=lambda *a: "SEM TRABALHO")
    assert i.falas_de_trabalho("bom dia galera", QUA) == []


def test_modelo_fora_do_ar_nao_vira_dia_sem_trabalho():
    """Tem que cair no protocolo de lacunas, nao virar silencio."""
    from delegation_core.pmo.daily import InterpreteLocal

    def explode(*a):
        raise RuntimeError("llama fora")

    i = InterpreteLocal("Jordan", chamar=explode)
    assert i.falas_de_trabalho("falou bastante", QUA) == []
    ap = H.apurar(QUA, QUA, [], [], "t1", "Soteria")
    assert not ap.pronta_para_lancar and ap.lacunas


def test_hora_declarada_absurda_e_descartada():
    from delegation_core.pmo.daily import InterpreteLocal
    r = "ATIVIDADE: Maratona\nQUANDO: hoje\nHORAS: 40\n"
    i = InterpreteLocal("Jordan", chamar=lambda *a: r)
    assert i.falas_de_trabalho("x", QUA)[0].horas_declaradas is None


def test_janela_inferida_derruba_a_confianca():
    """O que de fato varia entre os dias: quanto das horas se apoia em janela
    que ninguem observou. Contar fontes nao discriminava nada nesta maquina."""
    medida = H.Evidencia("commit", ev("commit", QUA, 9, 12).inicio,
                         ev("commit", QUA, 9, 12).fim, "x", inferida=False)
    inferida = H.Evidencia("commit", ev("commit", QUA, 9, 12).inicio,
                           ev("commit", QUA, 9, 12).fim, "x", inferida=True)
    assert H._confianca([medida], tem_fala=True) > H._confianca([inferida], tem_fala=True)


def test_confianca_nunca_zera_por_inferencia_sozinha():
    inferida = H.Evidencia("navegador", ev("navegador", QUA, 9, 10).inicio,
                           ev("navegador", QUA, 9, 10).fim, "x", inferida=True)
    assert H._confianca([inferida], tem_fala=False) >= 0.05


# ── nao inventar o que nao se sabe ───────────────────────────────────────────


def test_sem_fala_a_atividade_nao_e_inventada_a_partir_da_evidencia():
    """Rodando so com evidencia de maquina, a versao anterior colava o texto
    cru da primeira evidencia como nome da atividade, produzindo coisas como
    "sharepoint.com: Gravacao de Reuniao.mp4". Esse campo e o rotulo da linha
    no relatorio de horas faturaveis."""
    p, lacunas = H.apurar_dia(QUA, [ev("navegador", QUA, 9, 17,
                                       "sharepoint.com: Gravacao.mp4")],
                              [], "t1", "Soteria", ("desenvolvimento",))
    assert H.ATIVIDADE_DESCONHECIDA in p[0].descricao
    assert "sharepoint" not in p[0].descricao.lower()
    assert any("falta o que" in l.motivo for l in lacunas)


def test_atividade_desconhecida_impede_o_lancamento():
    ap = H.apurar(QUA, QUA, [ev("commit", QUA, 9, 17)], [], "t1", "Soteria")
    assert not ap.pronta_para_lancar


def test_com_fala_a_atividade_vem_dela():
    p, lacunas = H.apurar_dia(QUA, [ev("navegador", QUA, 9, 17, "sharepoint.com: x")],
                              [fala(QUA, atividade="Desenvolvimento do coletor")],
                              "t1", "Soteria", ("desenvolvimento",))
    assert "Desenvolvimento do coletor" in p[0].descricao
    assert not any("falta o que" in l.motivo for l in lacunas)
