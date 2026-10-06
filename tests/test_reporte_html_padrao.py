"""O reporte sai em HTML por padrao (06/10/2026), e o `rodar` o grava em arquivo.

Dois fatos medidos que motivam os testes:
- `rodar --saida-html` quebrava com AttributeError: lia `digest.resultados`, que
  o Digest nunca teve.
- Com HTML como padrao, o resumo do dia (e o log do timer das 08:30) viraria a
  pagina inteira. O HTML vai para um arquivo e o resumo diz onde ele esta.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from soteria_pmo import cli
from soteria_pmo import reporte as R

INI, FIM = date(2026, 8, 31), date(2026, 9, 6)


class ClienteMinimo:
    """So o que o reporte de um cliente com lista pede."""

    def tarefas_da_lista(self, *_a, **_k):
        return [{"id": "t1", "name": "Fazer coisa", "status": {"status": "em andamento"},
                 "assignees": [], "time_spent": 0, "date_updated": "1788000000000"}]

    def membros(self):
        return []

    def entradas(self, *_a, **_k):
        return []


PROJETOS = [{"nome": "Cliente A", "list_id": "9"}]


def test_gerar_todos_devolve_html_sem_pedir():
    assert R.gerar_todos(ClienteMinimo(), PROJETOS, INI, FIM).lstrip().startswith("<!DOCTYPE html>")


def test_markdown_continua_disponivel():
    texto = R.gerar_todos(ClienteMinimo(), PROJETOS, INI, FIM, formato="markdown")
    assert not texto.lstrip().startswith("<")


def test_o_padrao_do_comando_rodar_e_html():
    assert cli.FORMATO_PADRAO == "html"


def _tarefa_reporte(tmp_path, monkeypatch, **atributos):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    cliente = ClienteMinimo()
    for k, v in atributos.items():
        setattr(cliente, k, v)
    cfg = {"projetos": PROJETOS}
    return cli.montar_tarefas(cfg, cliente, date(2026, 9, 8))["reporte"]


def test_rodar_grava_o_html_e_o_resumo_so_diz_onde(tmp_path, monkeypatch):
    texto = _tarefa_reporte(tmp_path, monkeypatch)()
    arquivos = list((tmp_path / ".soteria-pmo" / "reportes").glob("reporte-*.html"))
    assert len(arquivos) == 1
    assert arquivos[0].read_text(encoding="utf-8").lstrip().startswith("<!DOCTYPE html>")
    assert "<" not in texto and str(arquivos[0]) in texto
    assert "validar e enviar" in texto, "o reporte nunca sai direto ao cliente"


def test_saida_html_explicita_vence_o_caminho_padrao(tmp_path, monkeypatch):
    destino = tmp_path / "meu" / "r.html"
    texto = _tarefa_reporte(tmp_path, monkeypatch, _saida_reporte=destino)()
    assert destino.is_file() and str(destino) in texto
    assert not (tmp_path / ".soteria-pmo" / "reportes").exists()


def test_formato_markdown_no_rodar_nao_grava_arquivo(tmp_path, monkeypatch):
    texto = _tarefa_reporte(tmp_path, monkeypatch, _formato_reporte="markdown")()
    assert not (tmp_path / ".soteria-pmo").exists()
    assert not texto.lstrip().startswith("<")
