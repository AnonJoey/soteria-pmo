"""Quem lancou horas: o quadro do Max no lugar da planilha.

O risco central e a omissao: quem nunca lancou nao aparece num quadro de
"esperados" montado a partir de quem lancou. Estes testes travam isso, o fuso
(a data de uma entrada e a de Brasilia) e o calculo dos dias.
"""
from datetime import date, datetime, timezone

from soteria_pmo import lancamentos as L

SEG, TER, SEX = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 2)


def entrada(quem, inicio_utc: datetime, horas: float):
    return {"user": {"username": quem}, "start": str(int(inicio_utc.timestamp() * 1000)),
            "duration": str(int(horas * 3_600_000))}


def utc(dia: date, h: int = 15, m: int = 0):
    return datetime(dia.year, dia.month, dia.day, h, m, tzinfo=timezone.utc)


# -- dias ------------------------------------------------------------------------------

def test_segunda_olha_para_a_sexta_e_nao_para_o_domingo():
    assert L.dia_util_anterior(date(2026, 10, 5)) == date(2026, 10, 2)


def test_feriado_na_sexta_empurra_ontem_para_a_quinta():
    assert L.dia_util_anterior(date(2026, 10, 5), frozenset({date(2026, 10, 2)})) == date(2026, 10, 1)


def test_semana_passada_sao_cinco_dias_uteis_menos_feriado():
    hoje = date(2026, 10, 7)  # quarta
    dias = L.dias_da_semana_passada(hoje)
    assert dias == [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)]
    assert date(2026, 9, 30) not in L.dias_da_semana_passada(hoje, frozenset({date(2026, 9, 30)}))


# -- soma e fuso ------------------------------------------------------------------------

def test_a_data_da_entrada_e_a_de_brasilia():
    # 01:30 UTC de 06/10 sao 22:30 BRT de 05/10
    e = entrada("Ana", datetime(2026, 10, 6, 1, 30, tzinfo=timezone.utc), 1.0)
    assert L.horas_por_pessoa_e_dia([e]) == {"Ana": {date(2026, 10, 5): 1.0}}


def test_soma_as_entradas_do_mesmo_dia():
    es = [entrada("Ana", utc(SEG, 12), 2.0), entrada("Ana", utc(SEG, 18), 1.5)]
    assert L.horas_por_pessoa_e_dia(es)["Ana"][SEG] == 3.5


def test_entrada_sem_usuario_ou_sem_inicio_e_ignorada():
    assert L.horas_por_pessoa_e_dia([{"duration": "3600000", "start": "1"}, {"user": {"username": "A"}}]) == {}


# -- o quadro ---------------------------------------------------------------------------

def test_quem_lancou_no_historico_e_nao_lancou_ontem_aparece_como_sem_lancamento():
    hist = [entrada("Ana", utc(date(2026, 9, 20)), 4), entrada("Beto", utc(date(2026, 9, 21)), 4)]
    ontem = [entrada("Ana", utc(SEG), 6)]
    q = L.apurar(ontem, [SEG], historico=hist + ontem)
    assert q.lancaram(SEG) == ["Ana"] and q.sem_lancamento(SEG) == ["Beto"]


def test_quem_nunca_lancou_nao_aparece_e_o_quadro_diz_isso():
    q = L.apurar([entrada("Ana", utc(SEG), 6)], [SEG], historico=[entrada("Ana", utc(SEG), 6)])
    assert [l.pessoa for l in q.linhas] == ["Ana"]
    assert "NAO aparece" in q.origem_dos_esperados


def test_a_lista_do_config_vence_e_traz_quem_nunca_lancou():
    q = L.apurar([entrada("Ana", utc(SEG), 6)], [SEG], esperados=["Ana", "Carla"],
                 historico=[entrada("Ana", utc(SEG), 6)])
    assert q.sem_lancamento(SEG) == ["Carla"]
    assert "equipe_lancamento" in q.origem_dos_esperados


def test_quem_fora_da_lista_do_config_e_ignorado():
    q = L.apurar([entrada("Ana", utc(SEG), 6), entrada("Intruso", utc(SEG), 8)], [SEG], esperados=["Ana"])
    assert [l.pessoa for l in q.linhas] == ["Ana"]


def test_hora_fora_dos_dias_pedidos_nao_entra_no_quadro():
    q = L.apurar([entrada("Ana", utc(SEG), 6), entrada("Ana", utc(TER), 5)], [SEG], esperados=["Ana"])
    assert q.linhas[0].por_dia == {SEG: 6.0} and q.linhas[0].total == 6.0


def test_fim_de_semana_nao_e_dia_pedido_mas_nao_quebra():
    sab = date(2026, 10, 3)
    q = L.apurar([entrada("Ana", utc(sab), 3)], [SEX], esperados=["Ana"])
    assert q.sem_lancamento(SEX) == ["Ana"]


# -- o texto ----------------------------------------------------------------------------

def _textos(com_falta: bool):
    es = [entrada("Ana", utc(SEG), 6)] + ([] if com_falta else [entrada("Beto", utc(SEG), 2)])
    hist = es + [entrada("Beto", utc(date(2026, 9, 25)), 1)]
    return L.formatar(L.apurar(es, [SEG], historico=hist), L.apurar(es, [SEG], historico=hist))


def test_o_texto_nomeia_quem_nao_lancou_e_conta_os_esperados():
    t = _textos(com_falta=True)
    assert "1 de 2 lancaram" in t and "Sem lancamento: Beto." in t


def test_o_texto_diz_quando_todos_lancaram():
    assert "Todos os esperados lancaram." in _textos(com_falta=False)


def test_o_texto_sempre_diz_o_limite_de_quem_ve():
    t = _textos(com_falta=False)
    assert "NAO aparece" in t and "nao ter lancado o suficiente" in t
