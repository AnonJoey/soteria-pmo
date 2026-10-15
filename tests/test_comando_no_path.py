"""O `soteria-pmo` que o PATH resolve tem de ser o desta instalacao.

Medido em 15/10/2026 num ensaio a frio de 1.0.0 (`uv tool`) para 1.4.0 (clone do GitHub):
depois do `soteria-pmo-instalar --atualizar` as skills e o agente eram os novos, mas o
comando do PATH continuava o da 1.0.0, que so conhece `rodar`, `horas`, `cadencias` e
`checar`. As skills chamam o comando pelo NOME, entao uma skill nova chamando `lancar`
ou `lancamentos` morria com `invalid choice`, e nada dizia por que.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from soteria_pmo import instalador as I

pytestmark = pytest.mark.skipif(os.name == "nt", reason="links simbolicos e PATH de POSIX")


def _executavel(caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/bin/sh\n", encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR)
    return caminho


@pytest.fixture
def venv_novo(tmp_path, monkeypatch) -> Path:
    """Um venv com o comando desta instalacao; `sys.executable` aponta para ele."""
    bin_ = tmp_path / "clone" / ".venv" / "bin"
    _executavel(bin_ / "python")
    _executavel(bin_ / "soteria-pmo")
    _executavel(bin_ / "soteria-pmo-instalar")
    monkeypatch.setattr(I.sys, "executable", str(bin_ / "python"))
    return bin_


def test_path_apontando_para_esta_instalacao_nao_avisa(venv_novo, tmp_path, monkeypatch):
    local = tmp_path / "home" / ".local" / "bin"
    local.mkdir(parents=True)
    (local / "soteria-pmo").symlink_to(venv_novo / "soteria-pmo")
    monkeypatch.setenv("PATH", str(local))
    assert I.aviso_do_comando_no_path() is None


def test_path_com_o_comando_de_outra_instalacao_avisa_e_diz_o_remedio(venv_novo, tmp_path, monkeypatch):
    velho = _executavel(tmp_path / "home" / ".local" / "bin" / "soteria-pmo")
    monkeypatch.setenv("PATH", str(velho.parent))
    aviso = I.aviso_do_comando_no_path()
    assert aviso is not None
    assert str(velho) in aviso and str(venv_novo / "soteria-pmo") in aviso
    assert "ln -sf" in aviso
    assert "soteria-pmo-instalar" in aviso
    assert "invalid choice" in aviso


def test_o_comando_do_clone_antes_do_velho_no_path_nao_avisa(venv_novo, tmp_path, monkeypatch):
    velho = _executavel(tmp_path / "home" / ".local" / "bin" / "soteria-pmo")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_novo), str(velho.parent)]))
    assert I.aviso_do_comando_no_path() is None


def test_comando_fora_do_path_avisa(venv_novo, tmp_path, monkeypatch):
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    aviso = I.aviso_do_comando_no_path()
    assert aviso is not None and "nao esta no PATH" in aviso
    assert str(venv_novo / "soteria-pmo") in aviso


def test_sem_o_executavel_ao_lado_do_interprete_nao_da_para_julgar_e_nao_avisa(tmp_path, monkeypatch):
    bin_ = tmp_path / "x" / "bin"
    _executavel(bin_ / "python")
    monkeypatch.setattr(I.sys, "executable", str(bin_ / "python"))
    monkeypatch.setenv("PATH", str(tmp_path))
    assert I.aviso_do_comando_no_path() is None


def test_o_instalador_imprime_o_aviso(venv_novo, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(I, "aviso_do_comando_no_path", lambda nome="soteria-pmo": "ATENCAO: teste do aviso")
    entrega = tmp_path / "entrega"
    (entrega / "skills" / "pmo-x").mkdir(parents=True)
    (entrega / "skills" / "pmo-x" / "SKILL.md").write_text("# s\n", encoding="utf-8")
    assert I.main([str(entrega)]) == 0
    assert "ATENCAO: teste do aviso" in capsys.readouterr().out


def test_o_instalador_nao_imprime_aviso_quando_esta_certo(venv_novo, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(I, "aviso_do_comando_no_path", lambda nome="soteria-pmo": None)
    entrega = tmp_path / "entrega"
    (entrega / "skills" / "pmo-x").mkdir(parents=True)
    (entrega / "skills" / "pmo-x" / "SKILL.md").write_text("# s\n", encoding="utf-8")
    assert I.main([str(entrega)]) == 0
    assert "ATENCAO" not in capsys.readouterr().out
