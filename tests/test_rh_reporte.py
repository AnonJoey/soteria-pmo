"""RH dates and the client report.

The distinctions under test are the ones that would be invisible if wrong: a
missing roster reading as a quiet week, a task with no logged hours reported as
stopped, and the delivery level of a report that was explicitly capped at 2.
"""

import json
from datetime import date

import pytest

from soteria_pmo import reporte as R
from soteria_pmo import rh
from soteria_pmo.periodo import BRT, ms

HOJE = date(2026, 9, 2)


# ── RH ───────────────────────────────────────────────────────────────────────


def test_roster_ausente_levanta_em_vez_de_devolver_vazio():
    """Sem roster e roster sem eventos produzem o mesmo silencio, e so um deles
    esta certo."""
    with pytest.raises(rh.RosterAusente):
        rh.carregar("/nao/existe/roster.csv")


def test_roster_ilegivel_tambem_levanta(tmp_path):
    p = tmp_path / "roster.json"
    p.write_text("{isso nao e json")
    with pytest.raises(rh.RosterAusente):
        rh.carregar(p)


def test_carrega_csv_e_json_com_as_mesmas_colunas(tmp_path):
    linhas = [{"nome": "Ana", "nascimento": "1994-09-05", "admissao": "2023-09-04"}]
    j = tmp_path / "r.json"
    j.write_text(json.dumps(linhas))
    c = tmp_path / "r.csv"
    c.write_text("nome,nascimento,admissao\nAna,1994-09-05,2023-09-04\n")
    assert rh.carregar(j) == rh.carregar(c)


def test_linha_sem_nome_e_ignorada(tmp_path):
    c = tmp_path / "r.csv"
    c.write_text("nome,nascimento\n,1994-09-05\nAna,1994-09-05\n")
    assert [p.nome for p in rh.carregar(c)] == ["Ana"]


def test_data_ilegivel_vira_none_sem_derrubar_a_pessoa(tmp_path):
    c = tmp_path / "r.csv"
    c.write_text("nome,nascimento\nAna,05/09/1994\n")
    (p,) = rh.carregar(c)
    assert p.nome == "Ana" and p.nascimento is None


def test_aniversario_dentro_da_antecedencia_aparece():
    p = rh.Pessoa("Ana", nascimento=date(1994, 9, 5))
    (e,) = [x for x in rh.eventos([p], HOJE) if x.tipo == "aniversario"]
    assert e.dias == 3 and e.quando == date(2026, 9, 5)


def test_aniversario_ja_passado_no_ano_vai_para_o_ano_seguinte():
    p = rh.Pessoa("Ana", nascimento=date(1994, 1, 10))
    assert rh.eventos([p], HOJE) == [], "10/01 esta longe demais para anunciar"
    assert rh._proxima_ocorrencia(date(1994, 1, 10), HOJE).year == 2027


def test_29_de_fevereiro_em_ano_comum_cai_para_1_de_marco():
    assert rh._proxima_ocorrencia(date(2000, 2, 29), date(2027, 2, 1)) == date(2027, 3, 1)


def test_tempo_de_casa_conta_anos_e_ignora_o_primeiro_dia():
    p = rh.Pessoa("Ana", inicio_contrato=date(2023, 9, 4))
    (e,) = [x for x in rh.eventos([p], HOJE) if x.tipo == "tempo de casa"]
    assert "3 anos" in e.detalhe


def test_inicio_de_contrato_no_mesmo_ano_nao_vira_tempo_de_casa():
    p = rh.Pessoa("Ana", inicio_contrato=date(2026, 9, 4))
    assert [x for x in rh.eventos([p], HOJE) if x.tipo == "tempo de casa"] == []


def test_fim_de_contrato_avisa_com_30_dias():
    perto = rh.Pessoa("Ana", fim_contrato=date(2026, 10, 1))
    longe = rh.Pessoa("Bia", fim_contrato=date(2026, 11, 1))
    tipos = {(e.pessoa, e.tipo) for e in rh.eventos([perto, longe], HOJE)}
    assert ("Ana", "fim de contrato") in tipos
    assert ("Bia", "fim de contrato") not in tipos


def test_data_que_ja_passou_sem_ninguem_ver_ainda_aparece():
    """Uma interrupcao que comecou semana passada e o caso que vale pegar."""
    p = rh.Pessoa("Ana", interrupcao_inicio=date(2026, 8, 26))
    (e,) = [x for x in rh.eventos([p], HOJE) if x.tipo == "interrupcao temporaria"]
    assert e.dias == -7


def test_evento_muito_antigo_para_de_aparecer():
    p = rh.Pessoa("Ana", interrupcao_inicio=date(2026, 6, 1))
    assert rh.eventos([p], HOJE) == []


def test_eventos_saem_do_mais_urgente_para_o_menos():
    pessoas = [rh.Pessoa("Bia", fim_contrato=date(2026, 9, 20)),
               rh.Pessoa("Ana", fim_contrato=date(2026, 9, 5))]
    assert [e.pessoa for e in rh.eventos(pessoas, HOJE)] == ["Ana", "Bia"]


def test_digest_separa_o_que_passou_do_que_vem():
    pessoas = [rh.Pessoa("Ana", interrupcao_inicio=date(2026, 8, 26)),
               rh.Pessoa("Bia", fim_contrato=date(2026, 9, 20))]
    saida = rh.digest(pessoas, HOJE)
    assert "Passaram sem aviso" in saida and "Chegando" in saida


def test_digest_vazio_quando_nao_ha_nada():
    assert rh.digest([rh.Pessoa("Ana")], HOJE) == ""


# ── reporte ──────────────────────────────────────────────────────────────────


def tarefa(tid, nome, status="em andamento", quem="Jordan", due=None):
    return {"id": tid, "name": nome, "status": {"status": status},
            "assignees": [{"username": quem}], "due_date": due}


def entrada(tid, horas, faturavel=True):
    return {"duration": int(horas * 3_600_000), "billable": faturavel,
            "task": {"id": tid}}


INI, FIM = date(2026, 8, 31), date(2026, 9, 6)


def test_horas_somam_por_tarefa():
    r = R.montar([tarefa("t1", "A")], [entrada("t1", 3), entrada("t1", 2)],
                 "Soteria", INI, FIM)
    assert r.linhas[0].horas == 5.0


def test_faturavel_e_nao_faturavel_somam_separado():
    r = R.montar([tarefa("t1", "A")],
                 [entrada("t1", 3), entrada("t1", 1, faturavel=False)],
                 "Soteria", INI, FIM)
    assert r.horas_faturaveis == 3.0 and r.horas_nao_faturaveis == 1.0
    assert r.horas_totais == 4.0


def test_tarefa_sem_horas_e_reportada_como_sem_horas_e_nunca_como_parada():
    """O dado nao distingue nao trabalhada de trabalhada e nao apontada."""
    r = R.montar([tarefa("t1", "A")], [], "Soteria", INI, FIM)
    assert r.paradas and not r.em_andamento
    texto = R.markdown(r)
    assert "Sem horas lancadas no periodo" in texto
    assert "parada" not in texto.lower().split("---")[0]


@pytest.mark.parametrize("status", [
    "publicado/finalizado", "Publicado/Finalizado", "PUBLICADO/FINALIZADO",
])
def test_o_estado_terminal_real_e_reconhecido_sem_ligar_para_caixa(status):
    """O workflow da pasta AI - Claude termina em publicado/finalizado.

    Uma versao anterior deste teste afirmava complete, done, concluido e
    fechado, nenhum dos quais existe neste workspace. Passava verde contra um
    vocabulario inventado, que e pior que falhar.
    """
    r = R.montar([tarefa("t1", "A", status=status)], [], "Soteria", INI, FIM)
    assert r.concluidas and not r.paradas


@pytest.mark.parametrize("status", [
    "ideia", "desenvolvimento", "homologação", "aguardando deploy", "bloqueado",
    "complete", "done",
])
def test_nenhum_estado_anterior_conta_como_concluido(status):
    """Inclusive os que a versao errada tratava como fim: eles nao existem aqui,
    entao uma tarefa com esse status e dado estranho e nao entrega feita."""
    r = R.montar([tarefa("t1", "A", status=status)], [], "Soteria", INI, FIM)
    assert not r.concluidas


def test_aguardando_deploy_ainda_nao_esta_entregue():
    """Release construida e nao publicada nao e entrega para o cliente."""
    r = R.montar([tarefa("t1", "A", status="aguardando deploy")], [], "Soteria", INI, FIM)
    assert not r.concluidas


def test_entrada_de_tarefa_fora_da_lista_soma_nas_horas_mas_nao_inventa_linha():
    r = R.montar([tarefa("t1", "A")], [entrada("t1", 2), entrada("t9", 5)],
                 "Soteria", INI, FIM)
    assert len(r.linhas) == 1
    assert r.horas_totais == 7.0, "as horas do periodo continuam sendo as do periodo"
    assert r.linhas[0].horas == 2.0


def test_o_reporte_carrega_o_nivel_2_no_proprio_artefato():
    """Nivel 3, enviar direto ao cliente, foi recusado em 24/06."""
    r = R.montar([], [], "Soteria", INI, FIM)
    assert "nivel 2" in r.destino
    assert "Max valida e envia" in R.markdown(r)


def test_markdown_ordena_por_horas_decrescentes():
    r = R.montar([tarefa("t1", "Pouco"), tarefa("t2", "Muito")],
                 [entrada("t1", 1), entrada("t2", 9)], "Soteria", INI, FIM)
    texto = R.markdown(r)
    assert texto.index("Muito") < texto.index("Pouco")


def test_tarefa_sem_responsavel_nao_quebra():
    r = R.montar([{"id": "t1", "name": "A", "status": "ideia", "assignees": []}],
                 [], "Soteria", INI, FIM)
    assert r.linhas[0].responsavel == "sem responsavel"


def test_gerar_sobrevive_a_falha_de_leitura():
    class Quebrado:
        def tarefas_da_lista(self, *_a, **_k):
            raise RuntimeError("api fora")

        def entradas(self, *_a, **_k):
            return []

    assert R.gerar(Quebrado(), "1", "Soteria", INI, FIM) == ""


# ── os dois feedbacks do primeiro ano e reporte executivo consolidado ───────
#
# Regra definida pelo Max em 08/09/2026: primeiro feedback aos 45 dias de
# contrato, segundo aos 90, com 5 dias de antecedencia. Substitui o ciclo
# bimestral de 60 dias contado do ultimo feedback, que era o que estes testes
# assertavam antes e que nunca correspondeu ao contrato real.


def test_primeiro_feedback_dispara_com_5_dias_de_antecedencia():
    # Contrato comecou ha 42 dias: os 45 caem em 3 dias, dentro da antecedencia
    p = rh.Pessoa("Carlos", inicio_contrato=HOJE - rh.timedelta(days=42))
    eventos = [e for e in rh.eventos([p], HOJE) if e.tipo == "primeiro feedback"]
    assert len(eventos) == 1
    assert eventos[0].dias == 3
    assert "45 dias de contrato" in eventos[0].detalhe


def test_segundo_feedback_sai_dos_90_dias():
    p = rh.Pessoa("Carlos", inicio_contrato=HOJE - rh.timedelta(days=88))
    eventos = [e for e in rh.eventos([p], HOJE) if e.tipo == "segundo feedback"]
    assert len(eventos) == 1
    assert eventos[0].dias == 2


def test_feedback_atrasado_ainda_aparece():
    p = rh.Pessoa("Carlos", inicio_contrato=HOJE - rh.timedelta(days=55))
    eventos = [e for e in rh.eventos([p], HOJE) if e.tipo == "primeiro feedback"]
    assert len(eventos) == 1
    assert eventos[0].dias == -10


def test_feedback_nao_depende_de_alguem_preencher_ultimo_feedback():
    """A regra antiga nao disparava nada sem `ultimo_feedback` preenchido."""
    p = rh.Pessoa("Carlos", inicio_contrato=HOJE - rh.timedelta(days=42))
    assert p.ultimo_feedback is None
    assert [e for e in rh.eventos([p], HOJE) if "feedback" in e.tipo]


def test_11_dias_antes_do_feedback_ainda_nao_avisa():
    """A antecedencia caiu de 15 para 5 dias."""
    p = rh.Pessoa("Carlos", inicio_contrato=HOJE - rh.timedelta(days=34))
    assert [e for e in rh.eventos([p], HOJE) if "feedback" in e.tipo] == []


def test_reporte_executivo_cliente_consolida_implantacao_e_sustentacao():
    rep_imp = R.montar(
        [tarefa("t1", "Setup Inicial", status="publicado/finalizado")],
        [entrada("t1", 20.0)],
        "Projeto Angelus Core",
        INI,
        FIM,
    )
    rep_sust = R.montar(
        [tarefa("t2", "Ajuste de Permissoes", status="desenvolvimento")],
        [entrada("t2", 5.0)],
        "Chamados Angelus",
        INI,
        FIM,
    )
    cliente_rep = R.ReporteCliente(
        cliente="Grupo Angelus",
        inicio=INI,
        fim=FIM,
        implantacao=[rep_imp],
        sustentacao=[rep_sust],
    )
    assert cliente_rep.total_horas == 25.0
    assert cliente_rep.total_faturavel == 25.0
    md = R.markdown_consolidado(cliente_rep)
    assert "# Reporte Executivo: Grupo Angelus" in md
    assert "## Projetos de Implantacao" in md
    assert "## Chamados e Sustentacao" in md
    assert "Setup Inicial" in md
    assert "Ajuste de Permissoes" in md
    assert "Max valida e envia (nivel 2)" in md



# ── pre-analise do reporte, autorizada pelo Max em 08/09/2026 ────────────────


def test_a_leitura_entra_por_cima_e_marcada_como_leitura():
    saida = R.com_pre_analise("# Soteria\ncorpo com numeros", "O projeto avancou.")
    assert saida.index("Leitura do periodo") < saida.index("corpo com numeros")
    assert "nao um fato apurado" in saida


def test_sem_leitura_o_reporte_continua_inteiro():
    """Falha na etapa de escrita nao pode tirar do ar o item inteiro."""
    corpo = "# Soteria\ncorpo com numeros"
    assert R.com_pre_analise(corpo, "") == corpo
    assert R.com_pre_analise(corpo, "   ") == corpo


def test_o_reporte_le_as_horas_do_time_e_nao_so_as_de_quem_roda():
    """Primeira execucao real: o reporte de um cliente saiu 0,0h numa semana
    com trabalho, porque entradas() sem assignee devolve so as do usuario
    autenticado, que num relatorio de cliente e a pessoa errada por definicao."""
    pedidos = []

    class Falso:
        def tarefas_da_lista(self, list_id, *a, **k):
            return [{"id": "t1", "name": "Tarefa", "status": {"status": "desenvolvimento"},
                     "assignees": [{"username": "Ana"}], "due_date": None}]

        def membros(self):
            return [{"id": "1"}, {"id": "2"}]

        def entradas(self, ini, fim, assignee=None):
            pedidos.append(assignee)
            return [{"id": "e1", "duration": 7_200_000, "billable": True,
                     "task": {"id": "t1"},
                     "task_location": {"list_id": "L1"}}]

    saida = R.gerar(Falso(), "L1", "Cliente", date(2026, 9, 1), date(2026, 9, 7))
    assert pedidos == [("1", "2")]
    assert "2.0h" in saida


def test_o_reporte_nao_soma_horas_de_outro_cliente():
    """A janela devolve o workspace inteiro; sem filtro, as horas de todos os
    clientes entravam no relatorio de um."""
    class Falso:
        def tarefas_da_lista(self, list_id, *a, **k):
            return [{"id": "t1", "name": "Tarefa", "status": {"status": "desenvolvimento"},
                     "assignees": [], "due_date": None}]

        def membros(self):
            return [{"id": "1"}]

        def entradas(self, ini, fim, assignee=None):
            return [{"id": "e1", "duration": 3_600_000, "billable": True,
                     "task": {"id": "t1"}, "task_location": {"list_id": "L1"}},
                    {"id": "e2", "duration": 36_000_000, "billable": True,
                     "task": {"id": "t99"}, "task_location": {"list_id": "OUTRA"}}]

    saida = R.gerar(Falso(), "L1", "Cliente", date(2026, 9, 1), date(2026, 9, 7))
    assert "Horas no periodo: 1.0h" in saida


def test_lista_de_sustentacao_nao_despeja_o_backlog_inteiro():
    """Medido em 08/09: o relatorio de um cliente listava 370 tarefas abertas
    sem horas, e o que aconteceu na semana sumia no meio."""
    linhas = [R.Linha(task_id=f"t{i}", nome=f"Chamado {i}", status="ideia",
                      responsavel="Ana", horas=0.0, concluida=False, vence_em=None)
              for i in range(40)]
    rep = R.Reporte(projeto="Cliente", inicio=date(2026, 9, 1), fim=date(2026, 9, 7),
                    linhas=linhas)
    saida = R.markdown(rep)
    assert "e mais 25 tarefas abertas sem horas" in saida
    assert saida.count("- Chamado") == R.TETO_DE_PARADAS
