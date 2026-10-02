"""O coletor do navegador, lendo um historico do Chrome montado em SQLite."""

import sqlite3
from datetime import date, datetime

from soteria_pmo import coletor as C
from soteria_pmo.periodo import BRT

DIA = date(2026, 9, 22)
LINK, RELOAD = 0, 8  # tipo de transicao do Chrome, nos 8 bits de baixo


def _wk(h, m, s=0):
    dt = datetime(2026, 9, 22, h, m, s, tzinfo=BRT)
    return int((dt.timestamp() + C.EPOCA_WEBKIT) * 1_000_000)


def _historico(tmp_path, visitas):
    caminho = tmp_path / "History"
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
    con.execute("CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, "
                "visit_time INTEGER, transition INTEGER, from_visit INTEGER)")
    for i, (quando, url, transicao) in enumerate(visitas, start=1):
        con.execute("INSERT INTO urls VALUES (?, ?, ?)", (i, url, url))
        con.execute("INSERT INTO visits VALUES (?, ?, ?, ?, 0)", (i, i, quando, transicao))
    con.commit()
    con.close()
    return caminho


def test_restauracao_de_abas_nao_vira_janela_de_trabalho(tmp_path):
    """Medido em 22/09/2026 as 10:16: o Chrome reabriu as abas da sessao
    anterior (Azure, Outlook, Teams, ClickUp, Claude) todas no mesmo segundo,
    com transicao RELOAD. O coletor leu isso como uma janela de trabalho de
    cliente, quando so prova que o navegador foi aberto."""
    h = _historico(tmp_path, [
        (_wk(10, 16, 31), "https://portal.azure.com/", RELOAD),
        (_wk(10, 16, 31), "https://teams.cloud.microsoft/", RELOAD),
        (_wk(10, 16, 31), "https://outlook.cloud.microsoft/mail/", RELOAD),
        # O que a restauracao puxa sozinha: o login automatico do Azure, que
        # chega como LINK e nao como RELOAD. Era isso que mantinha a janela
        # das 10:16 viva depois do primeiro filtro, que so olhava o RELOAD.
        (_wk(10, 16, 32), "https://login.microsoftonline.com/oauth", LINK),
        (_wk(10, 16, 35), "https://portal.azure.com/?bundlingKind=x", LINK),
        (_wk(10, 16, 36), "https://app.clickup.com/y", RELOAD),
    ])
    assert C.navegador(h, DIA, DIA) == []


def test_recarga_isolada_nao_derruba_o_que_vem_depois(tmp_path):
    """Uma recarga manual nao e restauracao: so a rajada de abas e."""
    h = _historico(tmp_path, [
        (_wk(10, 0), "https://app.clickup.com/x", RELOAD),
        (_wk(10, 0, 5), "https://app.clickup.com/tarefa", LINK),
        (_wk(10, 20), "https://app.clickup.com/outra", LINK),
    ])
    evs = C.navegador(h, DIA, DIA)
    assert len(evs) == 1
    assert evs[0].inicio == datetime(2026, 9, 22, 10, 0, 5, tzinfo=BRT)


def test_navegacao_de_verdade_continua_contando(tmp_path):
    h = _historico(tmp_path, [
        (_wk(10, 16, 31), "https://app.clickup.com/x", RELOAD),
        (_wk(10, 30), "https://app.clickup.com/tarefa", LINK),
        (_wk(10, 50), "https://app.clickup.com/outra", LINK),
    ])
    evs = C.navegador(h, DIA, DIA)
    assert len(evs) == 1
    assert evs[0].inicio == datetime(2026, 9, 22, 10, 30, tzinfo=BRT)
