"""A pagina do reporte e um arquivo que o Max edita, e a logica nao muda por isso.

Pedido do Max (RF-02, 5.5): editar estilo e graficos sem mexer em Python. O
modelo usa `string.Template` da biblioteca padrao, porque o pacote so aceita
biblioteca padrao e httpx (ver test_independencia). O que estes testes travam:
- o padrao continua sendo a pagina de sempre;
- o arquivo do Max vale quando esta inteiro e nao derruba o reporte quando nao esta;
- dado vindo do ClickUp nunca e tratado como marcador.
"""
from __future__ import annotations

import logging
import re
from datetime import date

import pytest

from soteria_pmo import template_html as T

INI, FIM = date(2026, 9, 28), date(2026, 10, 4)


def _pagina(modelo=None, sem_movimento=("Gazin",), pre="") -> str:
    return T.renderizar_relatorio_html(
        reportes=[], sem_movimento=list(sem_movimento), inicio=INI, fim=FIM,
        pre_analise=pre, modelo=modelo)


def _sem_hora(html: str) -> str:
    return re.sub(r"gerado pelo Sotéria PMO em [^<.]*\.", "gerado pelo Sotéria PMO em X.", html)


def test_o_padrao_traz_todos_os_blocos_e_nenhum_marcador_sobrando(tmp_path):
    html = _pagina(modelo=tmp_path / "nao-existe.html")
    assert "Relatório Executivo Consolidado" in html and "Gazin" in html
    assert "28/09/2026 a 04/10/2026" in html
    assert not re.search(r"\$[A-Z_]{3,}", html), "sobrou marcador sem trocar"


def test_o_modelo_exportado_gera_a_mesma_pagina_que_o_padrao(tmp_path):
    destino = T.exportar_modelo(tmp_path / "m.html")
    assert "--color-verde" in destino.read_text(encoding="utf-8")
    assert _sem_hora(_pagina(modelo=destino)) == _sem_hora(_pagina(modelo=tmp_path / "nao.html"))


def test_exportar_nao_sobrescreve_o_que_o_max_editou(tmp_path):
    destino = T.exportar_modelo(tmp_path / "m.html")
    destino.write_text("edicao do Max $CARDS $SEM_MOVIMENTO", encoding="utf-8")
    with pytest.raises(FileExistsError):
        T.exportar_modelo(destino)
    assert destino.read_text(encoding="utf-8").startswith("edicao do Max")
    T.exportar_modelo(destino, sobrescrever=True)
    assert "<!DOCTYPE html>" in destino.read_text(encoding="utf-8")


def test_o_arquivo_do_max_vale(tmp_path):
    m = tmp_path / "m.html"
    m.write_text("<h1>$TITULO</h1><p>total $HORAS_TOTAIS</p>$CARDS<footer>$SEM_MOVIMENTO</footer>",
                 encoding="utf-8")
    html = _pagina(modelo=m)
    assert html.startswith("<h1>Sotéria PMO - Relatório Executivo (28/09 a 04/10)</h1>")
    assert "total 0.0h" in html and "Gazin" in html


def test_cifrao_literal_do_max_nao_quebra(tmp_path):
    m = tmp_path / "m.html"
    m.write_text("<p>Custo R$ 100 e $$ e $</p>$CARDS$SEM_MOVIMENTO", encoding="utf-8")
    html = _pagina(modelo=m)
    assert "Custo R$ 100" in html


def test_modelo_sem_marcador_obrigatorio_volta_ao_padrao_e_avisa(tmp_path, caplog):
    m = tmp_path / "m.html"
    m.write_text("<p>so o titulo: $TITULO</p>", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        html = _pagina(modelo=m)
    assert "Gazin" in html and "so o titulo" not in html
    assert "$CARDS" in caplog.text and "$SEM_MOVIMENTO" in caplog.text


def test_modelo_ilegivel_volta_ao_padrao_e_avisa(tmp_path, caplog):
    m = tmp_path / "m.html"
    m.write_bytes(b"\xff\xfe\x00 nao e utf-8 \x80\x81")
    with caplog.at_level(logging.WARNING):
        html = _pagina(modelo=m)
    assert "Gazin" in html
    assert "ilegivel" in caplog.text


def test_dado_do_clickup_com_marcador_nao_e_trocado(tmp_path):
    html = _pagina(modelo=tmp_path / "nao.html", sem_movimento=["Cliente $HORAS_TOTAIS $CARDS"])
    assert "Cliente $HORAS_TOTAIS $CARDS" in html
    html2 = _pagina(modelo=tmp_path / "nao.html", pre="leitura com $TITULO dentro")
    assert "leitura com $TITULO dentro" in html2


def test_o_arquivo_do_max_e_lido_do_caminho_padrao_quando_existe(tmp_path, monkeypatch):
    m = tmp_path / "padrao.html"
    m.write_text("MAX $CARDS $SEM_MOVIMENTO", encoding="utf-8")
    monkeypatch.setattr(T, "CAMINHO_MODELO", m)
    assert _pagina().startswith("MAX ")
