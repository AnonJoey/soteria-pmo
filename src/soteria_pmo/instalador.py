"""Copiar as skills e o agente para onde o Claude Code os enxerga.

As duas funcoes vieram do instalador do delegation-core, onde nasceram
genericas: elas nao sabem de qual repo os arquivos vieram, so que ha uma pasta
`skills/` e uma `agents/` na raiz. Foi por isso que a extracao de 08/09/2026
nao precisou reescreve-las.

A regra que as duas dividem: **nunca sobrescrever o que a pessoa ja tem com
aquele nome.** Uma skill ou um subagente que alguem ajustou para o proprio
trabalho e dessa pessoa, e uma instalacao que passa por cima e uma perda
silenciosa. O que ja existe e mantido e reportado como mantido.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def install_skills(root: Path) -> dict:
    """Copia as skills empacotadas para ~/.claude/skills, sem sobrescrever.

    Skills pessoais ali ficam disponiveis em toda sessao do Claude Code na
    maquina, independente de configuracao de plugin.
    """
    origem = root / "skills"
    resultado: dict = {"installed": [], "kept_yours": [], "available": bool(origem.is_dir())}
    if not origem.is_dir():
        return resultado

    destino_raiz = Path.home() / ".claude" / "skills"
    destino_raiz.mkdir(parents=True, exist_ok=True)
    for pasta in sorted(p for p in origem.iterdir() if p.is_dir()):
        destino = destino_raiz / pasta.name
        if destino.exists():
            resultado["kept_yours"].append(pasta.name)
            continue
        try:
            shutil.copytree(pasta, destino)
            resultado["installed"].append(pasta.name)
        except OSError as e:
            resultado.setdefault("errors", []).append({"skill": pasta.name, "error": str(e)})
    return resultado


def install_agents(root: Path) -> dict:
    """Copia os agentes empacotados para ~/.claude/agents, sem sobrescrever.

    Mesmo contrato de `install_skills`, um diretorio adiante: agente e um
    arquivo markdown solto, nao uma pasta.
    """
    origem = root / "agents"
    resultado: dict = {"installed": [], "kept_yours": [], "available": bool(origem.is_dir())}
    if not origem.is_dir():
        return resultado

    destino_raiz = Path.home() / ".claude" / "agents"
    destino_raiz.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted(origem.glob("*.md")):
        destino = destino_raiz / arquivo.name
        if destino.exists():
            resultado["kept_yours"].append(arquivo.stem)
            continue
        try:
            shutil.copy2(arquivo, destino)
            resultado["installed"].append(arquivo.stem)
        except OSError as e:
            resultado.setdefault("errors", []).append({"agent": arquivo.stem, "error": str(e)})
    return resultado


def instalar(root: Path | None = None) -> dict:
    """As duas de uma vez, para o comando de instalacao chamar."""
    raiz = root or Path(__file__).resolve().parents[2]
    return {"skills": install_skills(raiz), "agents": install_agents(raiz)}


def main(argv: list[str] | None = None) -> int:
    """`soteria-pmo-instalar`: copia skills e agente e diz o que fez."""
    r = instalar()
    for tipo in ("skills", "agents"):
        parte = r[tipo]
        if not parte["available"]:
            print(f"{tipo}: nada empacotado neste repo")
            continue
        print(f"{tipo}: {len(parte['installed'])} instalada(s), "
              f"{len(parte['kept_yours'])} mantida(s) como estavam")
        for nome in parte["installed"]:
            print(f"  + {nome}")
        for nome in parte["kept_yours"]:
            print(f"  = {nome} (ja existia, nao foi tocada)")
        for erro in parte.get("errors", ()):
            print(f"  ! {erro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
