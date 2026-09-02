"""The door to the seven items: `delegation-core pmo`.

Kept in the package rather than in the repo's cli.py so the whole PMO surface
sits in one directory and can be lifted out or handed over as a unit.

The command reads a config file describing this workspace, because the seven
items need things no code should hardcode: which list is which project, how
many hours each budget holds, the team roster, and each person's cadence. A
missing config produces an explicit error naming the file, not an empty run
that looks like a quiet day.

Nothing here writes to ClickUp. `pmo rodar` prints; approving and launching
hours is a separate, deliberate act.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from . import auditor, bolsao, cronograma, datas, periodo, reporte, rh, rotina
from .clickup import ClickUp

CONFIG_PADRAO = Path.home() / ".delegation_core" / "pmo.json"

EXEMPLO = {
    "token": "pk_...",
    "team_id": "9007...",
    "projetos": [
        {"nome": "Soteria", "list_id": "901716443542", "horas_contratadas": 1800}
    ],
    "roster_rh": "~/.delegation_core/rh.csv",
    "cadencias": {"Jordan Bernardes": 2, "Abner Ben de Morais": 5},
    "feriados": ["2026-09-07"],
}


class ConfigAusente(RuntimeError):
    """No workspace config. Named as its own error so the CLI can print the
    example instead of a traceback."""


def carregar_config(caminho: Path) -> dict:
    if not caminho.exists():
        raise ConfigAusente(str(caminho))
    return json.loads(caminho.read_text())


def _feriados(cfg: dict) -> frozenset[date]:
    return frozenset(date.fromisoformat(d) for d in cfg.get("feriados", []))


def _cadencias(cfg: dict) -> dict[str, cronograma.Cadencia]:
    return {nome: cronograma.Cadencia(nome, int(dias))
            for nome, dias in (cfg.get("cadencias") or {}).items()}


def montar_tarefas(cfg: dict, cliente: ClickUp, hoje: date) -> dict:
    """Wire each item to its data. Kept out of rotina.py so that module stays
    free of any client and can be tested without a network."""
    projetos = cfg.get("projetos") or []
    feriados = _feriados(cfg)
    bolsoes = [bolsao.Bolsao(p["nome"], p["list_id"], float(p["horas_contratadas"]))
               for p in projetos]
    primeiro = projetos[0] if projetos else None

    inicio_semana = hoje - timedelta(days=hoje.weekday() + 7)
    fim_semana = inicio_semana + timedelta(days=6)
    inicio_mes = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
    fim_mes = hoje.replace(day=1) - timedelta(days=1)

    tarefas: dict[str, callable] = {
        "bolsao": lambda: bolsao.digest(
            bolsao.vigiar(cliente, bolsoes, hoje - timedelta(days=30), hoje, feriados)),
        "datas": lambda: datas.vigiar(cliente, primeiro["list_id"], hoje) if primeiro else "",
        "cronograma": lambda: cronograma.acompanhar(
            cliente, primeiro["list_id"], _cadencias(cfg), hoje, feriados) if primeiro else "",
    }

    if cfg.get("roster_rh"):
        caminho = Path(cfg["roster_rh"]).expanduser()
        tarefas["rh"] = lambda: rh.rodar(caminho, hoje)

    if primeiro:
        tarefas["reporte"] = lambda: reporte.gerar(
            cliente, primeiro["list_id"], primeiro["nome"], inicio_semana, fim_semana)
        tarefas["auditor"] = lambda: auditor.relatorio(auditor.auditar(
            cliente.entradas(*periodo.janela(inicio_mes, fim_mes)),
            # Sem evidencia de maquina por enquanto: o auditor reporta as
            # entradas como sem lastro, que e verdade e nao acusacao. Ligar o
            # coletor aqui e o passo seguinte.
            [], inicio_mes, fim_mes))

    # Item 4 is absent on purpose. Hours need evidence this command does not
    # collect and an approval it must not fabricate, so it has its own path.
    return tarefas


def cmd_rodar(args) -> int:
    hoje = date.fromisoformat(args.dia) if args.dia else date.today()
    try:
        cfg = carregar_config(Path(args.config).expanduser())
    except ConfigAusente as e:
        print(f"Sem configuracao do PMO em {e}.\n\nCrie o arquivo com esta forma:\n",
              file=sys.stderr)
        print(json.dumps(EXEMPLO, indent=2, ensure_ascii=False), file=sys.stderr)
        return 2

    with ClickUp(cfg["token"], cfg["team_id"], dry_run=True) as cliente:
        digest = rotina.rodar(hoje, montar_tarefas(cfg, cliente, hoje),
                              forcar=frozenset(args.forcar or ()),
                              feriados=_feriados(cfg))
    print(digest.texto())
    # Non-zero when an item failed, so a scheduler notices. A quiet day is
    # success; a broken item is not.
    return 1 if digest.erros else 0


def cmd_cadencias(args) -> int:
    """Print what runs when, which is the question people actually ask."""
    hoje = date.fromisoformat(args.dia) if args.dia else date.today()
    print(f"Cadencias dos itens, para {hoje:%d/%m/%Y} ({hoje:%A}):\n")
    feriados = frozenset()
    caminho = Path(getattr(args, "config", "") or CONFIG_PADRAO).expanduser()
    if caminho.exists():
        feriados = _feriados(json.loads(caminho.read_text()))
    if hoje in feriados:
        print("  (feriado: nada roda hoje)\n")
    for item, cadencia in sorted(rotina.CADENCIAS.items()):
        marca = "roda hoje" if rotina.devido(item, hoje, feriados=feriados) else "nao hoje"
        print(f"  {item:12} {cadencia:10} {marca}")
    return 0


def registrar(sub) -> None:
    """Hang `pmo` off the main CLI's subparsers."""
    p = sub.add_parser("pmo", help="Agentes PMO: rodar os itens de gestao do dia")
    pmo_sub = p.add_subparsers(dest="pmo_command", metavar="pmo-command")

    p_rodar = pmo_sub.add_parser("rodar", help="Roda os itens devidos hoje e imprime")
    p_rodar.add_argument("--config", default=str(CONFIG_PADRAO))
    p_rodar.add_argument("--dia", default=None, help="AAAA-MM-DD, para testar outro dia")
    p_rodar.add_argument("--forcar", nargs="*", default=None,
                         help="itens a rodar fora da cadencia (ex: reporte)")
    p_rodar.set_defaults(func=cmd_rodar)

    p_cad = pmo_sub.add_parser("cadencias", help="Mostra o que roda hoje e o que nao")
    p_cad.add_argument("--dia", default=None)
    p_cad.add_argument("--config", default=str(CONFIG_PADRAO))
    p_cad.set_defaults(func=cmd_cadencias)
