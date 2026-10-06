"""Copiar as skills e o agente para onde o Claude Code os enxerga.

As duas funcoes vieram do instalador do delegation-core, onde nasceram
genericas: elas nao sabem de qual repo os arquivos vieram, so que ha uma pasta
`skills/` e uma `agents/` na raiz. Foi por isso que a extracao de 08/09/2026
nao precisou reescreve-las.

A regra que as duas dividem: **nunca sobrescrever o que a pessoa ja tem com
aquele nome.** Uma skill ou um subagente que alguem ajustou para o proprio
trabalho e dessa pessoa, e uma instalacao que passa por cima e uma perda
silenciosa. O que ja existe e mantido e reportado como mantido.

`--atualizar` (desde 06/10/2026) troca o arquivo SO quando ele e identico a
alguma versao que nos entregamos (`versoes_entregues.json`, os hashes dos
pacotes de 08/09, 10/09 e 22/09 e do repo). Arquivo editado pela pessoa nao
casa com nenhum hash: fica como esta, e a versao nova vai ao lado como `.novo`
para ela comparar. Sem isso, atualizar era impossivel: a regra acima mantinha
para sempre a skill de 22/09.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

_VERSOES = Path(__file__).with_name("versoes_entregues.json")


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def versoes_entregues() -> dict[str, set[str]]:
    try:
        return {k: set(v) for k, v in json.loads(_VERSOES.read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        return {}


def _atualizar_arquivo(novo: Path, destino: Path, chave: str, resultado: dict, nome: str) -> None:
    """Troca `destino` por `novo` se `destino` for uma versao nossa, intocada."""
    if destino.exists() and _hash(destino) == _hash(novo):
        resultado["already_current"].append(nome)
        return
    if _hash(destino) in versoes_entregues().get(chave, set()):
        shutil.copy2(novo, destino)
        resultado["updated"].append(nome)
        return
    shutil.copy2(novo, destino.with_name(destino.name + ".novo"))
    resultado["kept_yours"].append(nome)


def install_skills(root: Path, atualizar: bool = False) -> dict:
    """Copia as skills empacotadas para ~/.claude/skills, sem sobrescrever.

    Skills pessoais ali ficam disponiveis em toda sessao do Claude Code na
    maquina, independente de configuracao de plugin.
    """
    origem = root / "skills"
    resultado: dict = {"installed": [], "kept_yours": [], "updated": [], "already_current": [],
                       "available": bool(origem.is_dir())}
    if not origem.is_dir():
        return resultado

    destino_raiz = Path.home() / ".claude" / "skills"
    destino_raiz.mkdir(parents=True, exist_ok=True)
    for pasta in sorted(p for p in origem.iterdir() if p.is_dir()):
        destino = destino_raiz / pasta.name
        if destino.exists():
            novo, alvo = pasta / "SKILL.md", destino / "SKILL.md"
            if atualizar and novo.is_file() and alvo.is_file():
                try:
                    _atualizar_arquivo(novo, alvo, f"skills/{pasta.name}/SKILL.md", resultado, pasta.name)
                except OSError as e:
                    resultado.setdefault("errors", []).append({"skill": pasta.name, "error": str(e)})
            else:
                resultado["kept_yours"].append(pasta.name)
            continue
        try:
            shutil.copytree(pasta, destino)
            resultado["installed"].append(pasta.name)
        except OSError as e:
            resultado.setdefault("errors", []).append({"skill": pasta.name, "error": str(e)})
    return resultado


def install_agents(root: Path, atualizar: bool = False) -> dict:
    """Copia os agentes empacotados para ~/.claude/agents, sem sobrescrever.

    Mesmo contrato de `install_skills`, um diretorio adiante: agente e um
    arquivo markdown solto, nao uma pasta.
    """
    origem = root / "agents"
    resultado: dict = {"installed": [], "kept_yours": [], "updated": [], "already_current": [],
                       "available": bool(origem.is_dir())}
    if not origem.is_dir():
        return resultado

    destino_raiz = Path.home() / ".claude" / "agents"
    destino_raiz.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted(origem.glob("*.md")):
        destino = destino_raiz / arquivo.name
        if destino.exists():
            if atualizar:
                try:
                    _atualizar_arquivo(arquivo, destino, f"agents/{arquivo.name}", resultado, arquivo.stem)
                except OSError as e:
                    resultado.setdefault("errors", []).append({"agent": arquivo.stem, "error": str(e)})
            else:
                resultado["kept_yours"].append(arquivo.stem)
            continue
        try:
            shutil.copy2(arquivo, destino)
            resultado["installed"].append(arquivo.stem)
        except OSError as e:
            resultado.setdefault("errors", []).append({"agent": arquivo.stem, "error": str(e)})
    return resultado


def _candidatas() -> tuple[Path, ...]:
    """As raizes a tentar, da intencao mais explicita para a menos.

    O diretorio atual vem primeiro de proposito. Quem esta dentro da pasta de
    entrega e roda o comando esta dizendo qual material quer instalar, e essa
    afirmacao vale mais que o lugar onde o pacote por acaso foi instalado. A
    ordem inversa faz um checkout do repo sequestrar a instalacao de uma pasta
    de entrega aberta ao lado, que e silencioso e dificil de enxergar.

    `parents[2]` fica como segunda opcao porque so acerta em checkout: numa
    instalacao por wheel ele cai dentro de `site-packages`, onde nao existe
    `skills/` nem `agents/`.
    """
    return (Path.cwd(), Path(__file__).resolve().parents[2])


def raiz_provavel(root: Path | None = None) -> Path:
    """Onde procurar as pastas `skills/` e `agents/`.

    O caminho explicito vence sempre. Sem ele, vale a primeira candidata que
    de fato tenha uma das duas pastas. Se nenhuma tiver, devolve a primeira,
    e quem chama reporta ausencia em vez de copiar o que encontrar pela frente.
    """
    if root is not None:
        return root
    candidatas = _candidatas()
    for candidata in candidatas:
        if (candidata / "skills").is_dir() or (candidata / "agents").is_dir():
            return candidata
    return candidatas[0]


def instalar(root: Path | None = None, atualizar: bool = False) -> dict:
    """As duas de uma vez, para o comando de instalacao chamar."""
    raiz = raiz_provavel(root)
    return {"skills": install_skills(raiz, atualizar), "agents": install_agents(raiz, atualizar)}


def main(argv: list[str] | None = None) -> int:
    """`soteria-pmo-instalar [pasta]`: copia skills e agente e diz o que fez.

    O argumento posicional existe para quem instalou o pacote por wheel e
    guarda a pasta de entrega em outro lugar: aponte para ela e a busca
    automatica sai do caminho.
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    atualizar = "--atualizar" in args
    args = [a for a in args if a != "--atualizar"]
    alvo = Path(args[0]).expanduser().resolve() if args else None
    if alvo is not None and not alvo.is_dir():
        print(f"pasta nao encontrada: {alvo}")
        return 1
    r = instalar(alvo, atualizar)
    print(f"lendo de: {raiz_provavel(alvo)}")
    for tipo in ("skills", "agents"):
        parte = r[tipo]
        if not parte["available"]:
            print(f"{tipo}: nenhuma pasta `{tipo}/` na raiz lida acima. "
                  f"Rode dentro da pasta de entrega, ou passe o caminho dela.")
            continue
        print(f"{tipo}: {len(parte['installed'])} instalada(s), {len(parte['updated'])} atualizada(s), "
              f"{len(parte['already_current'])} ja na versao nova, {len(parte['kept_yours'])} mantida(s) como estavam")
        for nome in parte["installed"]:
            print(f"  + {nome}")
        for nome in parte["updated"]:
            print(f"  ^ {nome} (era uma versao nossa, intocada: trocada pela nova)")
        for nome in parte["already_current"]:
            print(f"  . {nome} (ja estava na versao nova)")
        for nome in parte["kept_yours"]:
            if atualizar:
                print(f"  = {nome} (voce alterou: mantida; a versao nova ficou ao lado como .novo)")
            else:
                print(f"  = {nome} (ja existia, nao foi tocada; use --atualizar para trocar as versoes nossas)")
        for erro in parte.get("errors", ()):
            print(f"  ! {erro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
