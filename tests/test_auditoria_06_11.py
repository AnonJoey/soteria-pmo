"""Testes que a auditoria de 06/11/2026 achou faltando, e os filtros de evidencia dela.

Duas das oito mutacoes aplicadas passaram pela suite: ignorar `listas_sustentacao` do
config e calcular o dia do lancamento em UTC. As duas funcionavam; faltava o teste que
segura uma regressao. Nenhum dado real: tudo aqui e inventado.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from soteria_pmo import auditor as A
from soteria_pmo import coletor as C
from soteria_pmo import lancamentos as L
from soteria_pmo import painel
from soteria_pmo.coletor import Evidencia
from soteria_pmo.periodo import BRT, ms

from .test_painel import Falso, HOJE, PROJETOS, _entrada


# ---- item 5: as duas regras sem teste ----

def test_lista_do_config_decide_mesmo_quando_o_nome_da_lista_diz_outra_coisa():
    """No dublê, 'L-proj' se chama 'Projeto novo' e 'L-sust' fica numa pasta 'Chamados'.
    O config inverte os dois: se o painel ignorar `listas_sustentacao`, o nome vence e o
    resultado volta ao contrario (era o que a suite nao pegava)."""
    projetos = [dict(PROJETOS[0], listas_sustentacao=["L-proj"])]
    entradas = [_entrada(HOJE, 4, "L-proj"), _entrada(HOJE, 6, "L-sust")]
    c = painel.montar_dados(Falso(entradas), projetos, HOJE)["clientes"][0]
    assert c["mes"]["sust"] == 4.0 and c["mes"]["impl"] == 6.0
    assert c["base_fixa"] == "sust"


def _entrada_as(dia: date, hora: int, minuto: int, quem: str = "ana") -> dict:
    comeco = datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=BRT)
    return {"user": {"username": quem}, "start": str(ms(comeco)), "duration": 3_600_000,
            "task_location": {"space_id": "S1", "list_id": "1"}}


def test_lancamento_depois_das_21h_fica_no_dia_de_brasilia_e_nao_no_dia_seguinte_em_utc():
    """22:30 em Brasilia sao 01:30 do dia seguinte em UTC. O quadro da equipe tem de dizer
    que a pessoa lancou no dia em que trabalhou."""
    terca = date(2026, 10, 20)
    por_dia = L.horas_por_pessoa_e_dia([_entrada_as(terca, 22, 30)])
    assert list(por_dia["ana"]) == [terca]
    por_dia = L.horas_por_pessoa_e_dia([_entrada_as(terca, 23, 59), _entrada_as(terca, 0, 5)])
    assert list(por_dia["ana"]) == [terca] and por_dia["ana"][terca] == 2.0


def test_painel_poe_a_hora_da_noite_no_dia_de_brasilia():
    terca = date(2026, 10, 20)
    e = _entrada(terca, 2, "L-sust")
    e["start"] = str(ms(datetime(2026, 10, 20, 22, 30, tzinfo=BRT)))
    c = painel.montar_dados(Falso([e]), PROJETOS, HOJE)["clientes"][0]
    assert c["diario"] == {"2026-10-20": 2.0}


# ---- item 4: evidencia que inflava o "trabalho sem lancamento" ----

def _nota(pasta, nome, quando: datetime):
    arq = pasta / f"{nome}.md"
    arq.write_text("x", encoding="utf-8")
    t = quando.timestamp()
    os.utime(arq, (t, t))


def test_passada_de_maquina_sobre_centenas_de_notas_nao_vira_trabalho(tmp_path):
    base = datetime(2026, 11, 4, 3, 0, tzinfo=BRT)
    for i in range(60):  # uma reindexacao: 60 notas em 2 minutos
        _nota(tmp_path, f"antiga-{i}", base + timedelta(seconds=2 * i))
    dia = date(2026, 11, 4)
    assert C.notas_vault(tmp_path, dia, dia) == []


def test_poucas_notas_escritas_por_uma_pessoa_continuam_valendo(tmp_path):
    base = datetime(2026, 11, 4, 14, 0, tzinfo=BRT)
    for i in range(5):
        _nota(tmp_path, f"real-{i}", base + timedelta(minutes=3 * i))
    dia = date(2026, 11, 4)
    evs = C.notas_vault(tmp_path, dia, dia)
    assert len(evs) == 1 and "5 evento(s)" in evs[0].descricao


def test_a_rajada_sai_e_a_nota_isolada_do_mesmo_dia_fica(tmp_path):
    for i in range(C.RAJADA_DE_NOTAS):
        _nota(tmp_path, f"lote-{i}", datetime(2026, 11, 4, 3, 0, i, tzinfo=BRT))
    _nota(tmp_path, "minha-nota", datetime(2026, 11, 4, 16, 0, tzinfo=BRT))
    evs = C.notas_vault(tmp_path, date(2026, 11, 4), date(2026, 11, 4))
    assert len(evs) == 1 and "minha-nota" in evs[0].descricao


def _ev(dia: date, h1: int, h2: int) -> Evidencia:
    base = datetime.combine(dia, datetime.min.time(), tzinfo=BRT)
    return Evidencia(tipo="nota_vault", inicio=base.replace(hour=h1), fim=base.replace(hour=h2),
                     descricao="nota: algo")


def test_fim_de_semana_e_feriado_saem_da_conta_do_trabalho_sem_lancamento():
    sabado, domingo, feriado, util = date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)
    evid = [_ev(sabado, 10, 12), _ev(domingo, 10, 11), _ev(feriado, 9, 12), _ev(util, 9, 11)]
    aud = A.auditar([], evid, date(2026, 10, 30), date(2026, 11, 5), feriados=frozenset({feriado}))
    assert [o.dia for o in aud.orfas] == [util] and aud.horas_orfas == 2.0
    assert sorted(o.dia for o in aud.orfas_nao_uteis) == [sabado, domingo, feriado]
    txt = A.relatorio(aud)
    assert "Trabalho com evidencia e sem lancamento: 2.0h em 1 dias" in txt
    assert "dia nao util" in txt and "6.0h em 3 dias" in txt


def test_sem_a_lista_de_feriados_so_o_fim_de_semana_sai():
    feriado = date(2026, 11, 2)
    aud = A.auditar([], [_ev(feriado, 9, 12)], date(2026, 10, 30), date(2026, 11, 5))
    assert [o.dia for o in aud.orfas] == [feriado] and aud.orfas_nao_uteis == []


def test_data_trocada_ainda_enxerga_a_evidencia_do_domingo():
    domingo = date(2026, 11, 1)
    entrada = {"id": "e1", "start": ms(datetime(2026, 11, 2, 9, tzinfo=BRT)), "duration": 3 * 3_600_000,
               "description": "Ajuste no objeto vendedor (Soteria)", "billable": True, "task": {"id": "t1"}}
    aud = A.auditar([entrada], [_ev(domingo, 9, 12)], date(2026, 10, 30), date(2026, 11, 5))
    assert any("possivel data trocada" in o for a in aud.achados for o in a.observacoes)


def test_nota_que_o_proprio_sistema_escreve_nao_e_evidencia_de_trabalho(tmp_path):
    base = datetime(2026, 11, 4, 9, 0, tzinfo=BRT)
    _nota(tmp_path, "2026-11-04-Resumo da sessão - Daily - Equipe Dev", base)
    _nota(tmp_path, "2026-11-04-Sonho de 2026-11-04 - 1 atualizacoes entre notas", base + timedelta(hours=2))
    _nota(tmp_path, "2026-11-04-Boletim de 2026-11-04 - 17 notas mudaram", base + timedelta(hours=4))
    _nota(tmp_path, "2026-11-04-Decisao do ajuste no painel", base + timedelta(hours=6))
    evs = C.notas_vault(tmp_path, date(2026, 11, 4), date(2026, 11, 4))
    assert len(evs) == 1 and "Decisao do ajuste" in evs[0].descricao
