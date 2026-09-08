"""The audit and the schedule follow-up.

Both modules are mostly about what they refuse to claim. The audit must not
call a missing trail an error, because it cannot see planning or a phone call,
and that is where 60% of the pilot's hours lived. The schedule agent must not
call silence abandonment, because silence in ClickUp is also what work looks
like when nobody logs it.
"""

from datetime import date, datetime, timedelta

import pytest

from soteria_pmo import auditor as A
from soteria_pmo import cronograma as C
from soteria_pmo.horas import Evidencia
from soteria_pmo.periodo import BRT, ms

DIA = date(2026, 9, 2)
INI, FIM = date(2026, 9, 1), date(2026, 9, 30)


def ev(tipo, dia, h1, h2, desc="commit abc"):
    return Evidencia(
        tipo=tipo,
        inicio=datetime.combine(dia, datetime.min.time(), tzinfo=BRT).replace(hour=h1),
        fim=datetime.combine(dia, datetime.min.time(), tzinfo=BRT).replace(hour=h2),
        descricao=desc,
    )


def entrada(dia, horas, desc="Desenvolvimento do coletor (Soteria)",
            faturavel=True, eid="te_1"):
    return {"id": eid, "start": ms(datetime.combine(dia, datetime.min.time(), tzinfo=BRT)),
            "duration": int(horas * 3_600_000), "description": desc,
            "billable": faturavel, "task": {"id": "t1"}}


def em(dia, hora, horas, desc="Ajuste no objeto vendedor (Soteria)",
       eid="te_1", task="t1"):
    """An entry that starts at a given hour, which is what the clock checks read."""
    comeco = datetime.combine(dia, datetime.min.time(), tzinfo=BRT).replace(hour=hora)
    return {"id": eid, "start": ms(comeco), "duration": int(horas * 3_600_000),
            "description": desc, "billable": True, "task": {"id": task}}


# ── auditor ──────────────────────────────────────────────────────────────────


def test_entrada_com_evidencia_batendo_e_corroborada():
    aud = A.auditar([entrada(DIA, 8)], [ev("commit", DIA, 9, 17)], INI, FIM)
    assert aud.achados[0].veredito == "corroborada"
    assert not aud.achados[0].precisa_de_olho


def test_entrada_sem_evidencia_e_sem_lastro_e_nao_erro():
    aud = A.auditar([entrada(DIA, 8)], [], INI, FIM)
    a = aud.achados[0]
    assert a.veredito == "sem lastro"
    assert any("nao quer dizer que nao houve trabalho" in o.lower() for o in a.observacoes)
    assert any("60%" in o for o in a.observacoes)


def test_o_relatorio_nunca_acusa_erro():
    texto = A.relatorio(A.auditar([entrada(DIA, 8)], [], INI, FIM))
    assert "Nenhum veredito aqui acusa erro" in texto
    for palavra in ("fraude", "irregular", "indevido"):
        assert palavra not in texto.lower()


def test_divergencia_grande_de_horas_e_sinalizada():
    aud = A.auditar([entrada(DIA, 8)], [ev("commit", DIA, 9, 11)], INI, FIM)
    a = aud.achados[0]
    assert a.veredito == "divergente" and a.diferenca == 6.0


def test_diferenca_pequena_nao_vira_excecao():
    """Janela de evidencia e aproximada por natureza."""
    aud = A.auditar([entrada(DIA, 8)], [ev("commit", DIA, 9, 16)], INI, FIM)
    assert aud.achados[0].veredito == "corroborada"


def test_entrada_sem_descricao_e_apontada_porque_some_do_relatorio():
    aud = A.auditar([entrada(DIA, 8, desc="")], [ev("commit", DIA, 9, 17)], INI, FIM)
    a = aud.achados[0]
    assert a.veredito == "fora do formato"
    assert any("some do relatorio" in o for o in a.observacoes)


def test_descricao_sem_cliente_entre_parenteses_NAO_e_apontada():
    """Medido sobre agosto fechado, 1506 entradas de 14 pessoas: so 7,6%
    terminam com o cliente entre parenteses. Era estilo tratado como formato, e
    reprovava 177 das 271 entradas do proprio autor do padrao."""
    aud = A.auditar([entrada(DIA, 8, desc="Desenvolvimento do coletor")],
                    [ev("commit", DIA, 9, 17)], INI, FIM)
    assert aud.achados[0].veredito == "corroborada"
    assert aud.achados[0].observacoes == []


def test_dia_com_evidencia_e_sem_lancamento_vira_orfa():
    """A metade da auditoria que recupera dinheiro em vez de questionar."""
    aud = A.auditar([], [ev("commit", DIA, 14, 18, "commit da tarde")], INI, FIM)
    assert len(aud.orfas) == 1
    assert aud.orfas[0].horas == 4.0 and aud.horas_orfas == 4.0


def test_orfa_fora_do_periodo_e_ignorada():
    fora = date(2026, 10, 5)
    aud = A.auditar([], [ev("commit", fora, 9, 17)], INI, FIM)
    assert aud.orfas == []


def test_dia_que_tem_lancamento_nao_vira_orfa():
    aud = A.auditar([entrada(DIA, 8)], [ev("commit", DIA, 9, 17)], INI, FIM)
    assert aud.orfas == []


def test_corroboradas_nao_sao_listadas_so_contadas():
    """Auditoria que imprime tudo e lida por cima.

    Precisa de pelo menos uma excecao junto: com tudo corroborado o bloco de
    excecoes nem chega a ser renderizado, e o teste passaria mesmo se o
    relatorio listasse todo mundo dentro dele.

    A assercao olha o bloco de excecoes, e nao o documento inteiro, desde 04/09:
    a secao de concentracao nomeia a tarefa pela descricao de proposito, porque
    a pergunta do Andre e "que tarefa e essa que tem 35 horas". O volume dela e
    limitado pelo numero de tarefas acima do corte, nao pelo de entradas, que e
    o que este teste existe para proteger.
    """
    outro = date(2026, 9, 3)
    entradas = [entrada(DIA, 8, desc=f"Desenvolvimento passo {i} (Soteria)", eid=f"te_{i}")
                for i in range(20)]
    entradas.append(entrada(outro, 8, desc="Excecao sem lastro (Soteria)", eid="te_x"))
    texto = A.relatorio(A.auditar(entradas, [ev("commit", DIA, 9, 17)], INI, FIM))

    assert "20 de 21" in texto
    assert "## Excecoes" in texto, "o bloco tem que existir para o teste valer"
    assert "Excecao sem lastro" in texto
    excecoes = texto.split("## Excecoes", 1)[1].split("\n## ", 1)[0]
    for i in range(20):
        assert f"Desenvolvimento passo {i} (Soteria)" not in excecoes


def test_dia_de_lancamentos_empilhados_nao_vira_uma_enxurrada_de_conflitos():
    """Vinte entradas no mesmo instante dao 190 pares, e nenhum deles e achado.

    O ClickUp carimba o inicio quando a pessoa clica, entao lancamento manual
    empilha no mesmo horario. O relatorio diz que a checagem nao rodou naquele
    dia, em vez de acusar cada par.
    """
    entradas = [entrada(DIA, 8, desc=f"Passo {i} (Soteria)", eid=f"te_{i}")
                for i in range(20)]
    aud = A.auditar(entradas, [], INI, FIM)
    assert aud.conflitos == []
    assert aud.sem_relogio == [DIA]
    assert "checagem de horario nao rodou" in A.relatorio(aud)


def test_dois_lancamentos_no_mesmo_instante_ainda_sao_duplicidade():
    # O corte e tres: um par continua sendo um par, nao um dia sem relogio.
    aud = A.auditar([em(DIA, 14, 2, eid="a"), em(DIA, 14, 2, eid="b")], [], INI, FIM)
    assert aud.sem_relogio == []
    assert [c.tipo for c in aud.conflitos] == ["duplicidade"]


def test_excecoes_aparecem_com_a_evidencia_ao_lado():
    texto = A.relatorio(A.auditar([entrada(DIA, 8)],
                                  [ev("commit", DIA, 9, 11, "commit abc123")], INI, FIM))
    assert "commit abc123" in texto


def test_totais_separam_faturavel():
    aud = A.auditar([entrada(DIA, 6), entrada(DIA, 2, faturavel=False, eid="te_2")],
                    [ev("commit", DIA, 9, 17)], INI, FIM)
    assert aud.total_lancado == 8.0 and aud.total_faturavel == 6.0


def test_taxa_de_corroboracao_com_periodo_vazio_e_zero():
    assert A.auditar([], [], INI, FIM).taxa_de_corroboracao == 0.0


def test_entrada_sem_start_e_pulada_em_vez_de_explodir():
    aud = A.auditar([{"id": "x", "duration": 100, "start": None}], [], INI, FIM)
    assert aud.achados == []


# ── auditor: as entradas contra elas mesmas (04/09) ──────────────────────────
#
# Os dois primeiros casos que o Andre abriu na tela em 04/09 nao sao visiveis
# para uma checagem que so compara entrada contra evidencia do dia: 3h que
# engolem outra tarefa, e 40 minutos contidos dentro de outro bloco.


def test_bloco_lancado_duas_vezes_vira_duplicidade():
    entradas = [em(DIA, 18, 3, eid="a"), em(DIA, 18, 3, eid="b")]
    (c,) = A.conflitos(entradas)
    assert c.tipo == "duplicidade"
    assert c.horas == 3.0
    assert set(c.entradas) == {"a", "b"}


def test_entrada_contida_em_outra_e_contencao():
    # Os 40 minutos do caso do Andre, dentro de um bloco de tres horas.
    entradas = [em(DIA, 18, 3, eid="grande"), em(DIA, 19, 40 / 60, eid="dentro")]
    (c,) = A.conflitos(entradas)
    assert c.tipo == "contencao"
    assert c.horas == pytest.approx(0.67, abs=0.01)


def test_sobreposicao_parcial_conta_so_o_trecho_disputado():
    entradas = [em(DIA, 18, 3, eid="a"), em(DIA, 20, 2, eid="b")]
    (c,) = A.conflitos(entradas)
    assert c.tipo == "sobreposicao"
    assert c.horas == 1.0, "das 20h as 21h, nao as cinco horas somadas"


def test_entradas_encostadas_sem_cruzar_nao_geram_conflito():
    assert A.conflitos([em(DIA, 9, 2, eid="a"), em(DIA, 11, 2, eid="b")]) == []


def test_conflito_e_achado_sem_nenhuma_evidencia_de_maquina():
    # A auditoria diaria roda em maquina sem coletor configurado, e o cruzamento
    # de horario e aritmetica de relogio: nao depende de lastro.
    aud = A.auditar([em(DIA, 18, 3, eid="a"), em(DIA, 19, 1, eid="b")], [], INI, FIM)
    assert len(aud.conflitos) == 1
    assert aud.horas_em_conflito == 1.0


def test_entrada_em_conflito_aparece_nas_excecoes_mesmo_corroborada():
    # As horas batem com a evidencia do dia; sem a marcacao, o bloco cobrado em
    # dobro seria contado como corroborado e nunca listado.
    entradas = [em(DIA, 9, 4, eid="a"), em(DIA, 9, 4, eid="b")]
    aud = A.auditar(entradas, [ev("commit", DIA, 9, 13)], INI, FIM)
    assert all(a.precisa_de_olho for a in aud.achados)
    assert any("duplicidade" in o for a in aud.achados for o in a.observacoes)


def test_o_relatorio_lista_o_horario_cruzado_e_nao_le_intencao():
    aud = A.auditar([em(DIA, 18, 3, eid="a"), em(DIA, 19, 1, eid="b")], [], INI, FIM)
    texto = A.relatorio(aud)
    assert "Horarios que se cruzam" in texto
    assert "aritmetica de relogio" in texto
    assert "fraude" not in texto.lower() and "erro de lancamento" not in texto.lower()


# ── auditor: concentracao ────────────────────────────────────────────────────


def test_oito_horas_numa_tarefa_so_no_mesmo_dia_e_apontada():
    (c,) = A.concentracoes([em(DIA, 9, 8, task="t9")])
    assert c.escopo == "dia" and c.horas == 8.0 and c.task_id == "t9"


def test_dia_normal_nao_vira_concentracao():
    assert A.concentracoes([em(DIA, 9, 6, task="t9")]) == []


def test_tarefa_que_soma_muito_no_periodo_e_apontada():
    dias = [date(2026, 9, d) for d in range(1, 8)]
    entradas = [em(d, 9, 5, eid=f"e{i}", task="generica") for i, d in enumerate(dias)]
    periodo = [c for c in A.concentracoes(entradas) if c.escopo == "periodo"]
    assert len(periodo) == 1 and periodo[0].horas == 35.0


def test_concentracao_nao_muda_o_veredito_da_entrada():
    # E um tamanho declarado, nao um julgamento: oito horas legitimas num dia
    # continuam corroboradas pela evidencia.
    aud = A.auditar([em(DIA, 9, 8)], [ev("commit", DIA, 9, 17)], INI, FIM)
    assert aud.achados[0].veredito == "corroborada"
    assert aud.concentracoes


# ── auditor: data provavel trocada ───────────────────────────────────────────


def test_sem_lastro_ao_lado_de_orfa_do_mesmo_tamanho_sugere_data_trocada():
    ontem = DIA - timedelta(days=1)
    aud = A.auditar([em(DIA, 9, 4)], [ev("commit", ontem, 9, 13)], INI, FIM)
    (a,) = aud.achados
    assert a.veredito == "sem lastro", "o veredito nao muda: continua sendo o que se viu"
    assert any("possivel data trocada" in o for o in a.observacoes)
    assert f"{ontem:%d/%m}" in " ".join(a.observacoes)


def test_orfa_de_outro_tamanho_nao_vira_sugestao_de_data_trocada():
    ontem = DIA - timedelta(days=1)
    aud = A.auditar([em(DIA, 9, 4)], [ev("commit", ontem, 9, 20)], INI, FIM)
    assert not any("data trocada" in o for o in aud.achados[0].observacoes)


def test_orfa_distante_nao_vira_sugestao_de_data_trocada():
    longe = DIA - timedelta(days=5)
    aud = A.auditar([em(DIA, 9, 4)], [ev("commit", longe, 9, 13)], INI, FIM)
    assert not any("data trocada" in o for o in aud.achados[0].observacoes)


def test_cada_entrada_sem_lastro_recebe_sua_propria_sugestao():
    # A primeira versao devolvia da funcao inteira no primeiro par encontrado,
    # o que silenciava todas as entradas seguintes.
    d1, d2 = date(2026, 9, 10), date(2026, 9, 20)
    entradas = [em(d1, 9, 4, eid="a"), em(d2, 9, 4, eid="b")]
    evid = [ev("commit", d1 - timedelta(days=1), 9, 13),
            ev("commit", d2 - timedelta(days=1), 9, 13)]
    aud = A.auditar(entradas, evid, INI, FIM)
    assert all(any("data trocada" in o for o in a.observacoes) for a in aud.achados)


# ── cronograma ───────────────────────────────────────────────────────────────


HOJE = date(2026, 9, 2)


def tarefa(nome="3.4 Lancamento", quem="Jordan", status="ideia",
           tocado_ha=0, due=None, est=None):
    d = HOJE - timedelta(days=tocado_ha)
    return {"id": "t1", "name": nome, "status": {"status": status},
            "assignees": [{"username": quem}] if quem else [],
            "date_updated": ms(datetime.combine(d, datetime.min.time(), tzinfo=BRT)),
            "due_date": due, "time_estimate": est}


def proj(tarefas, entradas=(), tipo=C.TIPO_PROJETO, nome="Implantacao CRM",
         list_id="list_1", hoje=HOJE):
    """Avalia um projeto, que e a unidade do item 2 desde 03/09/2026."""
    return C.avaliar_projeto(projeto=nome, list_id=list_id, tarefas=tarefas,
                             entradas=list(entradas), tipo=tipo, hoje=hoje)


def test_projeto_com_horas_de_hoje_nao_gera_divergencia():
    assert proj([tarefa(tocado_ha=0)], [entrada(HOJE, 4.0)]) is None


def test_dev_que_troca_de_tarefa_dentro_do_projeto_nao_e_projeto_parado():
    """O motivo de a unidade ter deixado de ser a tarefa em 03/09.

    A tarefa antiga esta parada ha muito tempo, a nova foi tocada hoje e ha
    hora lancada no projeto. Pela regua por tarefa isso era alerta; pela regua
    por projeto nao e, e essa e exatamente a diferenca acordada com o Abner.
    """
    parada = tarefa(nome="3.4 antiga", tocado_ha=20, status="desenvolvimento")
    andando = tarefa(nome="3.5 nova", tocado_ha=0, status="desenvolvimento")
    assert proj([parada, andando], [entrada(HOJE, 6.0)]) is None


def test_silencio_longo_escala():
    d = proj([tarefa(tocado_ha=20)])
    assert d.nivel == "escalar"


def test_a_escalada_e_multiplo_da_regua_e_acompanha_o_tipo_de_trabalho():
    """Chamado tem regua de 2 dias, entao escala com menos silencio que projeto.

    O que amarra os dois e o multiplo, nao um numero de dias solto: mexer na
    regua leva a escalada junto.
    """
    mesmo_silencio = [tarefa(tocado_ha=7, status="desenvolvimento")]
    assert proj(mesmo_silencio, tipo=C.TIPO_CHAMADO).nivel == "cobranca"
    assert proj(mesmo_silencio, tipo=C.TIPO_PROJETO).nivel == "lembrete"


def test_todo_alerta_declara_a_ambiguidade_que_nao_consegue_resolver():
    d = proj([tarefa(tocado_ha=20)])
    assert "nao foi apontado" in d.ambiguidade
    assert "nao consegue separar" in d.ambiguidade


def test_o_log_nunca_usa_a_palavra_abandonada():
    log = C.log_de_divergencias_projetos([proj([tarefa(tocado_ha=20)])], HOJE)
    for palavra in ("abandonada", "abandonado", "parou de trabalhar"):
        assert palavra not in log.lower()
    assert "nao andou ou trabalho que andou e nao foi apontado" in log


def test_projeto_so_com_tarefa_concluida_sai_do_radar():
    assert proj([tarefa(tocado_ha=30, status="publicado/finalizado")]) is None


def test_projeto_so_com_tarefa_bloqueada_sai_do_radar():
    """Bloqueado nao e negligencia. Cobrar quem tem o card poe o alerta na
    pessoa errada: quem bloqueia nao e quem e dono."""
    assert proj([tarefa(tocado_ha=30, status="bloqueado")]) is None


@pytest.mark.parametrize("status", ["ideia", "desenvolvimento", "homologação",
                                    "aguardando deploy", "backlog"])
def test_estados_intermediarios_do_workflow_real_continuam_no_radar(status):
    assert proj([tarefa(tocado_ha=30, status=status)]) is not None


def test_bloqueada_no_meio_de_tarefas_ativas_vira_nota_e_nao_some():
    d = proj([tarefa(nome="ativa", tocado_ha=20),
              tarefa(nome="travada", tocado_ha=20, status="bloqueado")])
    assert d.tarefas_bloqueadas == 1
    assert any("bloqueadas" in n for n in d.notas)


def test_sem_estimativa_o_alerta_diz_que_nao_da_para_julgar_o_tamanho():
    d = proj([tarefa(tocado_ha=20, est=None)])
    assert any("sem estimativa" in n for n in d.notas)


def test_com_estimativa_essa_nota_some():
    d = proj([tarefa(tocado_ha=20, est=3600000)])
    assert not any("sem estimativa" in n for n in d.notas)


def test_tarefa_sem_responsavel_nao_quebra():
    d = proj([tarefa(quem=None, tocado_ha=20)])
    assert d.responsaveis == []


def test_log_vazio_quando_nada_divergiu():
    assert C.log_de_divergencias_projetos([], HOJE) == ""


# ── acompanhar_projetos, a porta que a rotina chama ─────────────────────────


class ClienteFalso:
    """Cliente de mentira com o minimo que `acompanhar_projetos` consome."""

    def __init__(self, por_lista, entradas=(), quebra_em=()):
        self.por_lista = por_lista
        self._entradas = list(entradas)
        self.quebra_em = set(quebra_em)

    def membros(self):
        return [{"id": "1"}, {"id": "2"}]

    def tarefas_da_lista(self, list_id, *_a, **_k):
        if list_id in self.quebra_em:
            raise RuntimeError("api fora")
        return self.por_lista[list_id]

    def entradas(self, *_a, **_k):
        return self._entradas


def test_acompanhar_projetos_le_todos_os_projetos_e_nao_so_o_primeiro():
    cliente = ClienteFalso({"a": [tarefa(nome="A", tocado_ha=20)],
                            "b": [tarefa(nome="B", tocado_ha=20)]})
    log = C.acompanhar_projetos(cliente, [{"nome": "Alfa", "list_id": "a"},
                                          {"nome": "Beta", "list_id": "b"}], HOJE)
    assert "Alfa" in log and "Beta" in log


def test_acompanhar_projetos_ordena_escalar_antes_de_lembrete():
    """Os dois com horas lancadas, em datas diferentes, para o nivel sair do
    silencio de cada um e nao da janela comum a todos."""
    recente = dict(entrada(HOJE - timedelta(days=3), 4.0),
                   task_location={"list_id": "a"})
    antigo = dict(entrada(HOJE - timedelta(days=25), 4.0),
                  task_location={"list_id": "b"})
    cliente = ClienteFalso({"a": [tarefa(nome="A", tocado_ha=3)],
                            "b": [tarefa(nome="B", tocado_ha=25)]},
                           entradas=[recente, antigo])
    log = C.acompanhar_projetos(cliente, [{"nome": "Recente", "list_id": "a",
                                           "tipo": C.TIPO_CHAMADO},
                                          {"nome": "Antigo", "list_id": "b"}], HOJE)
    assert log.index("Antigo") < log.index("Recente")


def test_acompanhar_projetos_conta_so_as_horas_do_proprio_projeto():
    """Uma entrada de outra lista nao pode calar o alerta deste projeto."""
    de_outra = dict(entrada(HOJE, 8.0), task_location={"list_id": "outra"})
    cliente = ClienteFalso({"a": [tarefa(tocado_ha=20)]}, entradas=[de_outra])
    assert "Alfa" in C.acompanhar_projetos(cliente, [{"nome": "Alfa", "list_id": "a"}], HOJE)


def test_projeto_que_nao_pode_ser_lido_e_dito_e_nao_some_em_silencio():
    """Ausencia de alerta e indistinguivel de projeto saudavel, entao falhar
    calado seria reportar saude que ninguem verificou."""
    cliente = ClienteFalso({"a": []}, quebra_em={"a"})
    log = C.acompanhar_projetos(cliente, [{"nome": "Alfa", "list_id": "a"}], HOJE)
    assert "nao puderam ser lidos" in log
    assert "Alfa" in log


def test_acompanhar_projetos_sem_projeto_nenhum_e_silencioso():
    assert C.acompanhar_projetos(ClienteFalso({}), [], HOJE) == ""


# ── testes da regra de 03/09 por tipo de trabalho ───────────────────────────


def test_avaliar_projeto_implantacao_dispara_com_4_dias_sem_horas():
    t_ativa = tarefa(nome="Desenvolvimento API", tocado_ha=6, status="desenvolvimento")
    div = C.avaliar_projeto(
        projeto="Implantacao CRM",
        list_id="list_1",
        tarefas=[t_ativa],
        entradas=[],  # Nenhuma hora lancada
        tipo=C.TIPO_PROJETO,
        hoje=HOJE,
    )
    assert div is not None
    assert div.precisa_de_alerta
    assert div.regua_dias == 4
    assert div.tipo == "projeto"
    assert "4 dias uteis sem horas apontadas" in div.linha()


def test_avaliar_projeto_chamado_dispara_com_2_dias_sem_horas():
    t_chamado = tarefa(nome="Correcao Bug", tocado_ha=4, status="desenvolvimento")
    div = C.avaliar_projeto(
        projeto="Sustentacao Geral",
        list_id="list_2",
        tarefas=[t_chamado],
        entradas=[],
        tipo=C.TIPO_CHAMADO,
        hoje=HOJE,
    )
    assert div is not None
    assert div.precisa_de_alerta
    assert div.regua_dias == 2
    assert div.tipo == "chamado"


def test_avaliar_projeto_com_horas_recentes_nao_dispara_alerta():
    t_ativa = tarefa(nome="Desenvolvimento API", tocado_ha=1, status="desenvolvimento")
    e_recente = entrada(HOJE, 4.0)
    div = C.avaliar_projeto(
        projeto="Implantacao CRM",
        list_id="list_1",
        tarefas=[t_ativa],
        entradas=[e_recente],
        tipo=C.TIPO_PROJETO,
        hoje=HOJE,
    )
    assert div is None


def test_avaliar_projeto_com_tarefas_concluidas_ou_bloqueadas_nao_dispara():
    t_conc = tarefa(nome="Done", tocado_ha=10, status="publicado/finalizado")
    t_bloq = tarefa(nome="Blocked", tocado_ha=10, status="bloqueado")
    div = C.avaliar_projeto(
        projeto="Projeto Parado",
        list_id="list_3",
        tarefas=[t_conc, t_bloq],
        entradas=[],
        tipo=C.TIPO_PROJETO,
        hoje=HOJE,
    )
    assert div is None


def test_log_de_divergencias_projetos_formata_saida():
    div = C.DivergenciaProjeto(
        projeto="Projeto Alpha",
        list_id="list_1",
        tipo="projeto",
        regua_dias=4,
        dias_sem_horas=5,
        horas_no_periodo=0.0,
        tarefas_em_desenvolvimento=2,
        tarefas_bloqueadas=1,
        tarefas_concluidas=3,
        responsaveis=["Jordan", "Abner"],
        notas=["1 tarefas bloqueadas aguardando resolucao externa"],
    )
    log = C.log_de_divergencias_projetos([div], HOJE)
    assert "Acompanhamento de cronograma por projeto" in log
    assert "[lembrete] Projeto Alpha" in log
    assert "Jordan, Abner" in log
    assert "1 tarefas bloqueadas" in log
    assert div.ambiguidade in log



def test_trinta_dias_sem_hora_nenhuma_nao_fica_calado_por_card_editado_ontem():
    """O falso negativo medido contra o workspace real em 08/09/2026.

    Antes, sem entrada nenhuma, o silencio vinha da data de toque das tarefas,
    entao editar um card zerava o alarme de um projeto que nao tinha uma hora
    lancada em trinta dias. O sinal acordado com o Abner e hora lancada.
    """
    tocado_hoje = tarefa(nome="editado agora", tocado_ha=0, status="desenvolvimento")
    tocado_hoje["date_created"] = ms(datetime.combine(
        HOJE - timedelta(days=90), datetime.min.time(), tzinfo=BRT))
    d = C.avaliar_projeto("Soteria", "l", [tocado_hoje], [],
                          hoje=HOJE, inicio=HOJE - timedelta(days=30))
    assert d is not None and d.nivel == "escalar"
    assert any("nenhuma hora lancada" in n for n in d.notas)


def test_projeto_novo_demais_para_julgar_fica_quieto():
    """Sem tarefa mais velha que a propria regua nao houve tempo de lancar
    nada, e cobrar quem acabou de comecar e o mesmo erro por outra porta."""
    nova = tarefa(nome="comecou ontem", tocado_ha=0, status="desenvolvimento")
    nova["date_created"] = ms(datetime.combine(
        HOJE - timedelta(days=1), datetime.min.time(), tzinfo=BRT))
    assert C.avaliar_projeto("Novo", "l", [nova], [], hoje=HOJE,
                             inicio=HOJE - timedelta(days=30)) is None


def test_task_como_string_nao_derruba_a_auditoria():
    """Forma real, achada auditando agosto fechado do time com a suite verde:
    o ClickUp devolve `task` como string em parte das entradas, e `or {}` deixa
    a string passar porque string nao vazia e verdadeira."""
    torta = dict(entrada(DIA, 4), task="apenas-um-id")
    aud = A.auditar([torta], [], INI, FIM, com_evidencia=False)
    assert len(aud.achados) == 1
    assert aud.achados[0].task_id == "?"


def test_auditoria_de_outra_pessoa_nao_emite_veredito_de_lastro():
    """Sem a maquina dela nao ha o que comparar, e marcar tudo como sem lastro
    e verdadeiro e inutil: imprime a lista inteira."""
    aud = A.auditar([entrada(DIA, 4)], [], INI, FIM, com_evidencia=False)
    assert aud.achados[0].veredito == "sem veredito de lastro"
    assert aud.excecoes == []
    assert "nao foi procurada" in A.relatorio(aud)


def test_entradas_sem_tarefa_nao_viram_uma_tarefa_gigante():
    """Com "?" no lugar do id, todas as entradas sem tarefa somavam entre si.
    Medido sobre agosto do time: um achado de 293,8h "numa tarefa so" que eram
    240 entradas de onze pessoas empilhadas num id inventado."""
    sem_tarefa = [dict(em(DIA, 8 + i, 3.0, eid=f"e{i}"), task=None) for i in range(6)]
    assert A.concentracoes(sem_tarefa) == []


def test_concentracao_soma_por_pessoa_e_nao_pelo_time():
    """Os cortes do Andre descrevem UMA pessoa numa tarefa. Somar o time
    transforma trabalho paralelo normal em alerta."""
    mesma_tarefa = [
        dict(em(DIA, 9, 5.0, eid="a", task="t9"), user={"username": "Ana"}),
        dict(em(DIA, 9, 5.0, eid="b", task="t9"), user={"username": "Bia"}),
    ]
    assert A.concentracoes(mesma_tarefa) == []
    sozinha = [
        dict(em(DIA, 9, 5.0, eid="a", task="t9"), user={"username": "Ana"}),
        dict(em(DIA, 15, 5.0, eid="b", task="t9"), user={"username": "Ana"}),
    ]
    assert any(c.escopo == "dia" for c in A.concentracoes(sozinha))
