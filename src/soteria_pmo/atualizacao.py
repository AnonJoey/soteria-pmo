"""Atualizar o pacote pelo GitHub: `soteria-pmo atualizar`.

Quem instala clonando o repositorio atualiza com um comando: baixa o ramo
acompanhado (`git pull --ff-only`), reinstala o pacote e copia as skills e o
agente novos com a regra do `soteria-pmo-instalar --atualizar`, que so troca o
que e versao nossa e deixa a versao nova ao lado, como `.novo`, do que a pessoa
alterou. O `~/.soteria-pmo/pmo.json` nunca e lido nem escrito aqui: e dali que
vem o token, e ele nao viaja por git.

Duas recusas, as duas para nao perder trabalho de ninguem:

- alteracao local em arquivo rastreado: um `pull` ali poderia conflitar ou
  esconder o que a pessoa fez;
- historia que nao avanca em linha reta (`--ff-only` falha): quem decide como
  juntar e a pessoa, nao este comando.

Nao ha rede de seguranca por restaurar copia antiga: se um passo falha, o
comando para, diz qual foi e deixa o checkout como esta.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from . import instalador


def raiz_do_checkout(a_partir_de: Path | None = None) -> Path | None:
    """A pasta do checkout git deste pacote, ou None se ele nao veio de um.

    `parents[2]` do modulo so e a raiz num checkout instalado em modo editavel.
    Instalado por wheel cai em `site-packages`, onde nao ha `.git`: nesse caso
    nao ha o que puxar, e o comando diz como migrar em vez de adivinhar.
    """
    raiz = a_partir_de or Path(__file__).resolve().parents[2]
    if (raiz / ".git").exists() and (raiz / "pyproject.toml").is_file():
        return raiz
    return None


def versao_em(raiz: Path) -> str | None:
    try:
        dados = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
        return dados["project"]["version"]
    except (OSError, KeyError, ValueError):
        return None


def _git(raiz: Path, *args: str, rodar=subprocess.run) -> subprocess.CompletedProcess:
    return rodar(["git", "-C", str(raiz), *args], capture_output=True, text=True)


def estado(raiz: Path, rodar=subprocess.run) -> dict:
    """Ramo, commit, quantos commits faltam e quais arquivos rastreados mudaram.

    Faz `fetch` antes de contar: sem isso `behind` compara com o que a maquina
    sabia da ultima vez e diz "em dia" para quem esta atras.
    """
    busca = _git(raiz, "fetch", "--quiet", "origin", rodar=rodar)
    ramo = _git(raiz, "rev-parse", "--abbrev-ref", "HEAD", rodar=rodar).stdout.strip()
    commit = _git(raiz, "rev-parse", "--short", "HEAD", rodar=rodar).stdout.strip()
    up = _git(raiz, "rev-parse", "--abbrev-ref", "@{u}", rodar=rodar)
    upstream = up.stdout.strip() if up.returncode == 0 else None
    atras = None
    if upstream:
        n = _git(raiz, "rev-list", "--count", "HEAD..@{u}", rodar=rodar)
        atras = int(n.stdout.strip()) if n.returncode == 0 and n.stdout.strip().isdigit() else None
    sujos = [
        linha[3:] for linha in
        _git(raiz, "status", "--porcelain", "--untracked-files=no", rodar=rodar).stdout.splitlines()
    ]
    return {"ramo": ramo, "commit": commit, "upstream": upstream, "atras": atras,
            "sujos": sujos, "fetch_ok": busca.returncode == 0,
            "fetch_erro": busca.stderr.strip() if busca.returncode else ""}


def atualizar(raiz: Path | None = None, so_verificar: bool = False,
              rodar=subprocess.run, instalar=instalador.instalar) -> dict:
    """Devolve um dicionario com `status` e, quando houve trabalho, os passos.

    `status`: `sem_checkout`, `sem_rede`, `sem_ramo_acompanhado`, `alteracao_local`,
    `verificado` (so_verificar), `em_dia`, `atualizado` ou `falhou`.
    """
    raiz = raiz or raiz_do_checkout()
    if raiz is None:
        return {"status": "sem_checkout",
                "detalhe": "Este pacote nao foi instalado de um clone do GitHub, entao nao ha de onde atualizar."}
    antes = versao_em(raiz)
    e = estado(raiz, rodar=rodar)
    base = {"raiz": str(raiz), "versao_antes": antes, **e, "passos": []}
    if not e["fetch_ok"]:
        return {**base, "status": "sem_rede", "detalhe": e["fetch_erro"] or "git fetch falhou"}
    if e["upstream"] is None:
        return {**base, "status": "sem_ramo_acompanhado",
                "detalhe": f"O ramo {e['ramo']} nao acompanha nenhum ramo remoto."}
    if e["sujos"]:
        return {**base, "status": "alteracao_local",
                "detalhe": "Ha alteracao em arquivo rastreado: " + ", ".join(e["sujos"])}
    if so_verificar:
        return {**base, "status": "verificado"}

    passos = base["passos"]
    if e["atras"]:
        pull = _git(raiz, "pull", "--ff-only", "--quiet", rodar=rodar)
        passos.append({"passo": "git pull --ff-only", "ok": pull.returncode == 0})
        if pull.returncode:
            return {**base, "status": "falhou", "detalhe": (pull.stderr or pull.stdout).strip()}
        pip = rodar([sys.executable, "-m", "pip", "install", "--quiet", "-e", str(raiz)],
                    capture_output=True, text=True)
        passos.append({"passo": "pip install -e", "ok": pip.returncode == 0})
        if pip.returncode:
            return {**base, "status": "falhou", "detalhe": (pip.stderr or pip.stdout).strip()}
    copiado = instalar(raiz, atualizar=True)
    passos.append({"passo": "skills e agente", "ok": True})
    return {**base, "status": "atualizado" if e["atras"] else "em_dia",
            "versao_depois": versao_em(raiz), "copiado": copiado}
