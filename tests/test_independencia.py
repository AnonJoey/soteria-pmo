"""O pacote nao depende de outro projeto, nem por import nem por caminho.

Exigencia de 02/10/2026: o soteria-pmo nasceu dentro do delegation-core e
levou uma extracao inteira para se soltar, e o que o prendia nao era codigo,
era config compartilhado e caminho escrito. Este teste e a guarda: falha se
um modulo importar algo fora da biblioteca padrao e do httpx, ou se trouxer
escrito o caminho, a porta ou a pasta de outro projeto. Dado de outro projeto
continua bem-vindo, desde que entre pelo config.
"""

import ast
import sys
from pathlib import Path

PACOTE = Path(__file__).resolve().parents[1] / "src" / "soteria_pmo"
PERMITIDOS = {"httpx"}
PROIBIDOS_NO_CODIGO = ("127.0.0.1:8181", ".delegation_core", "delegation_core.",
                       "Claude Vault", "Projects_Archive")


def _modulos():
    return sorted(PACOTE.glob("*.py"))


def test_so_importa_biblioteca_padrao_e_httpx():
    estrangeiros = []
    for arquivo in _modulos():
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                nomes = [no.module]
            for nome in nomes:
                raiz = nome.split(".")[0]
                if raiz in PERMITIDOS or raiz in sys.stdlib_module_names or raiz == "__future__":
                    continue
                estrangeiros.append(f"{arquivo.name}: {nome}")
    assert estrangeiros == []


def _docstrings(arvore):
    ids = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corpo = no.body
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(
                    getattr(corpo[0], "value", None), ast.Constant):
                ids.add(id(corpo[0].value))
    return ids


def test_nenhum_caminho_ou_porta_de_outro_projeto_no_codigo():
    """So as strings que o codigo USA. Docstring e comentario contam a
    historia do pacote, e citar de onde ele saiu nao cria dependencia."""
    achados = []
    for arquivo in _modulos():
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docs = _docstrings(arvore)
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docs:
                if any(p in no.value for p in PROIBIDOS_NO_CODIGO):
                    achados.append(f"{arquivo.name}:{no.lineno}: {no.value[:60]!r}")
    assert achados == []


def test_dependencias_declaradas_sao_so_httpx():
    texto = (PACOTE.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    deps = texto.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert [d.strip().strip('"').split(">")[0] for d in deps.split(",") if d.strip()] == ["httpx"]
