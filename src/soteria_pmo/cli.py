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
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from . import auditor, bolsao, coletor, cronograma, daily, datas, horas, periodo, reporte, rh, rotina
from .clickup import ClickUp

logger = logging.getLogger("pmo.cli")

CONFIG_PADRAO = Path.home() / ".delegation_core" / "pmo.json"

# How many days back the daily audit looks. Long enough that an entry logged on
# Friday is still checked on Monday, short enough that the same exception is not
# repeated for weeks after everyone has decided to leave it alone.
JANELA_DA_AUDITORIA = 7

EXEMPLO = {
    "token": "pk_...",
    "team_id": "9007...",
    "pessoa": "Jordan Bernardes",
    "evidencia": {
        "repos": ["~/Projects/delegation-core"],
        "autor_git": "",
        "sessoes_ia": "~/.claude/projects",
        "vault": "~/Documents/Projects_Archive/Claude Vault",
        "historico_navegador": "~/.config/google-chrome/Default/History",
    },
    "task_horas": "86e31gx8v",
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
    return json.loads(caminho.read_text(encoding="utf-8"))


def _feriados(cfg: dict) -> frozenset[date]:
    return frozenset(date.fromisoformat(d) for d in cfg.get("feriados", []))


def _cadencias(cfg: dict) -> dict[str, cronograma.Cadencia]:
    return {nome: cronograma.Cadencia(nome, int(dias))
            for nome, dias in (cfg.get("cadencias") or {}).items()}


def fontes_de_evidencia(cfg: dict) -> "coletor.Fontes":
    """The evidence sources as the config describes them, in one place.

    Both `pmo horas` and the daily audit need the same wiring, and having it
    written twice is how the audit ended up running against an empty evidence
    list while the hours engine collected properly.
    """
    ev = cfg.get("evidencia") or {}
    return coletor.Fontes(
        repos=tuple(ev.get("repos", ())),
        autor_git=ev.get("autor_git", ""),
        sessoes_ia=ev.get("sessoes_ia", ""),
        vault=ev.get("vault", ""),
        historico_navegador=ev.get("historico_navegador", ""),
    )


def evidencia_do_periodo(cfg: dict, inicio: date, fim: date) -> list:
    """Machine evidence for the audit, or nothing at all if it cannot be had.

    A collector that fails must not take the audit down with it: the entries
    are still worth checking against each other, and an audit with no evidence
    reports every entry as having no trail, which is true and says so.
    """
    if not (cfg.get("evidencia") or {}):
        return []
    try:
        evidencias, _falhas = coletor.coletar(fontes_de_evidencia(cfg), inicio, fim)
    except Exception:
        logger.exception("coleta de evidencia falhou; auditoria segue sem lastro")
        return []
    uteis, _pessoais = coletor.separar_pessoal(evidencias)
    return uteis


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
    # The audit runs daily since 04/09, so its window is the stretch a dev can
    # still correct, not the month that already closed. The closing view is the
    # same module over another window: `--forcar auditor --dia` on day one.
    inicio_aud = hoje - timedelta(days=JANELA_DA_AUDITORIA)
    fim_aud = hoje - timedelta(days=1)

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
            cliente.entradas(*periodo.janela(inicio_aud, fim_aud)),
            evidencia_do_periodo(cfg, inicio_aud, fim_aud),
            inicio_aud, fim_aud))
        tarefas["fechamento"] = lambda: auditor.relatorio(auditor.auditar(
            cliente.entradas(*periodo.janela(inicio_mes, fim_mes)),
            evidencia_do_periodo(cfg, inicio_mes, fim_mes),
            inicio_mes, fim_mes))

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


def cmd_horas(args) -> int:
    """Apurar um periodo: coletar evidencia, ler as dailies, propor e perguntar.

    Nunca escreve. Sai com 2 quando restam lacunas, porque uma apuracao com
    pergunta aberta nao esta pronta para lancar e um agendador precisa notar a
    diferenca entre "apurado" e "apurado e completo".
    """
    try:
        cfg = carregar_config(Path(args.config).expanduser())
    except ConfigAusente as e:
        print(f"Sem configuracao do PMO em {e}.\n\nCrie o arquivo com esta forma:\n",
              file=sys.stderr)
        print(json.dumps(EXEMPLO, indent=2, ensure_ascii=False), file=sys.stderr)
        return 2

    inicio = date.fromisoformat(args.de)
    fim = date.fromisoformat(args.ate)
    ev_cfg = cfg.get("evidencia") or {}
    pessoa = args.pessoa or cfg.get("pessoa", "")

    evidencias, falhas = coletor.coletar(fontes_de_evidencia(cfg), inicio, fim)
    print(coletor.resumo(evidencias, falhas))
    print()
    # Personal evidence is dropped from the apuracao, not from the report: the
    # resumo above says how much was separated so a wrong split is visible.
    evidencias, _pessoais = coletor.separar_pessoal(evidencias)

    falas = []
    if pessoa and ev_cfg.get("vault"):
        pasta = Path(ev_cfg["vault"]).expanduser() / "Sessions"
        if args.sem_modelo:
            print("Modo sem modelo: as dailies nao serao interpretadas, entao o "
                  "que a pessoa disse que fez nao entra na apuracao.\n")
        else:
            falas = daily.falas_da_pessoa(pasta, pessoa, inicio, fim)
            print(f"Dailies: {len(falas)} atividade(s) declarada(s) por {pessoa}.\n")

    ap = horas.apurar(inicio, fim, evidencias, falas,
                      cfg.get("task_horas", ""),
                      (cfg.get("projetos") or [{}])[0].get("nome", "Cliente"),
                      tuple(args.tags or ("desenvolvimento",)))
    print(horas.relatorio(ap))
    return 0 if ap.pronta_para_lancar else 2


def cmd_cadencias(args) -> int:
    """Print what runs when, which is the question people actually ask."""
    hoje = date.fromisoformat(args.dia) if args.dia else date.today()
    print(f"Cadencias dos itens, para {hoje:%d/%m/%Y} ({hoje:%A}):\n")
    feriados = frozenset()
    caminho = Path(getattr(args, "config", "") or CONFIG_PADRAO).expanduser()
    if caminho.exists():
        feriados = _feriados(json.loads(caminho.read_text(encoding="utf-8")))
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

    p_horas = pmo_sub.add_parser(
        "horas", help="Apura um periodo a partir da evidencia e das dailies (nao escreve)")
    p_horas.add_argument("--de", required=True, help="AAAA-MM-DD")
    p_horas.add_argument("--ate", required=True, help="AAAA-MM-DD")
    p_horas.add_argument("--config", default=str(CONFIG_PADRAO))
    p_horas.add_argument("--pessoa", default=None, help="sobrepoe a pessoa do config")
    p_horas.add_argument("--tags", nargs="*", default=None)
    p_horas.add_argument("--sem-modelo", action="store_true",
                         help="nao interpreta as dailies; so evidencia de maquina")
    p_horas.set_defaults(func=cmd_horas)

    p_cad = pmo_sub.add_parser("cadencias", help="Mostra o que roda hoje e o que nao")
    p_cad.add_argument("--dia", default=None)
    p_cad.add_argument("--config", default=str(CONFIG_PADRAO))
    p_cad.set_defaults(func=cmd_cadencias)
