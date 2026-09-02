"""The audit and the schedule follow-up.

Both modules are mostly about what they refuse to claim. The audit must not
call a missing trail an error, because it cannot see planning or a phone call,
and that is where 60% of the pilot's hours lived. The schedule agent must not
call silence abandonment, because silence in ClickUp is also what work looks
like when nobody logs it.
"""

from datetime import date, datetime, timedelta

import pytest

from delegation_core.pmo import auditor as A
from delegation_core.pmo import cronograma as C
from delegation_core.pmo.horas import Evidencia
from delegation_core.pmo.periodo import BRT, ms

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


def test_descricao_sem_cliente_entre_parenteses_e_apontada():
    aud = A.auditar([entrada(DIA, 8, desc="Desenvolvimento do coletor")],
                    [ev("commit", DIA, 9, 17)], INI, FIM)
    assert aud.achados[0].veredito == "fora do formato"


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
    """
    outro = date(2026, 9, 3)
    entradas = [entrada(DIA, 8, desc=f"Desenvolvimento passo {i} (Soteria)", eid=f"te_{i}")
                for i in range(20)]
    entradas.append(entrada(outro, 8, desc="Excecao sem lastro (Soteria)", eid="te_x"))
    texto = A.relatorio(A.auditar(entradas, [ev("commit", DIA, 9, 17)], INI, FIM))

    assert "20 de 21" in texto
    assert "## Excecoes" in texto, "o bloco tem que existir para o teste valer"
    assert "Excecao sem lastro" in texto
    for i in range(20):
        assert f"Desenvolvimento passo {i} (Soteria)" not in texto


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


# ── cronograma ───────────────────────────────────────────────────────────────


HOJE = date(2026, 9, 2)


def tarefa(nome="3.4 Lancamento", quem="Jordan", status="ideia",
           tocado_ha=0, due=None, est=None):
    d = HOJE - timedelta(days=tocado_ha)
    return {"id": "t1", "name": nome, "status": {"status": status},
            "assignees": [{"username": quem}] if quem else [],
            "date_updated": ms(datetime.combine(d, datetime.min.time(), tzinfo=BRT)),
            "due_date": due, "time_estimate": est}


def test_tarefa_recem_tocada_nao_gera_divergencia():
    assert C.avaliar([tarefa(tocado_ha=0)], {}, HOJE) == []


def test_silencio_longo_escala():
    (d,) = C.avaliar([tarefa(tocado_ha=20)], {}, HOJE)
    assert d.nivel == "escalar"


def test_ritmo_proprio_evita_cobrar_quem_so_trabalha_em_lote():
    """A restricao central: com regua unica, quem junta a semana na sexta e
    marcado como abandonado na quarta."""
    lote = {"Bia": C.Cadencia("Bia", dias_entre_toques=7)}
    t = tarefa(quem="Bia", tocado_ha=5)
    assert C.avaliar([t], lote, HOJE) == []
    assert C.avaliar([t], {}, HOJE) != [], "na regua padrao, 5 dias ja alertaria"


def test_pessoa_sem_calibragem_e_marcada_como_tal():
    (d,) = C.avaliar([tarefa(tocado_ha=20)], {}, HOJE)
    assert not d.cadencia.calibrada
    assert "nao calibrado" in d.linha()
    assert any("Abner" in n for n in d.notas)


def test_todo_alerta_declara_a_ambiguidade_que_nao_consegue_resolver():
    (d,) = C.avaliar([tarefa(tocado_ha=20)], {}, HOJE)
    assert "nao foi apontado" in d.ambiguidade
    assert "nao consegue separar" in d.ambiguidade


def test_o_log_nunca_usa_a_palavra_abandonada():
    log = C.log_de_divergencias(C.avaliar([tarefa(tocado_ha=20)], {}, HOJE), HOJE)
    for palavra in ("abandonada", "abandonado", "parou de trabalhar"):
        assert palavra not in log.lower()
    assert "pode ser trabalho que nao andou ou trabalho que andou e nao foi apontado" in log


def test_tarefa_concluida_sai_do_radar():
    assert C.avaliar([tarefa(tocado_ha=30, status="complete")], {}, HOJE) == []


def test_sem_estimativa_o_alerta_diz_que_nao_da_para_julgar_o_tamanho():
    (d,) = C.avaliar([tarefa(tocado_ha=20, est=None)], {}, HOJE)
    assert any("sem estimativa" in n for n in d.notas)


def test_com_estimativa_essa_nota_some():
    (d,) = C.avaliar([tarefa(tocado_ha=20, est=3600000)], {}, HOJE)
    assert not any("sem estimativa" in n for n in d.notas)


def test_ordena_escalar_antes_de_lembrete():
    tarefas = [tarefa(nome="novo", tocado_ha=4), tarefa(nome="velho", tocado_ha=25)]
    niveis = [d.nome for d in C.avaliar(tarefas, {}, HOJE)]
    assert niveis[0] == "velho"


def test_tarefa_sem_responsavel_nao_quebra():
    (d,) = C.avaliar([tarefa(quem=None, tocado_ha=20)], {}, HOJE)
    assert d.pessoa == "sem responsavel"


def test_tarefa_sem_data_de_toque_e_pulada():
    assert C.avaliar([{"id": "t", "name": "x", "status": "ideia",
                       "assignees": [], "date_updated": None,
                       "date_created": None}], {}, HOJE) == []


def test_log_vazio_quando_nada_divergiu():
    assert C.log_de_divergencias([], HOJE) == ""


def test_log_lista_quem_esta_sem_calibragem():
    log = C.log_de_divergencias(C.avaliar([tarefa(quem="Ana", tocado_ha=20)], {}, HOJE), HOJE)
    assert "Sem ritmo calibrado: Ana" in log


def test_acompanhar_sobrevive_a_falha_de_leitura():
    class Quebrado:
        def tarefas_da_lista(self, *_a, **_k):
            raise RuntimeError("api fora")

    assert C.acompanhar(Quebrado(), "1", {}, HOJE) == ""
