"""The door to the seven items: `soteria-pmo`.

Kept in the package rather than in a top-level script so the whole PMO surface
sits in one directory. That is what made lifting it out of delegation-core, in
08/09/2026, a move of two directories instead of an excavation; `registrar` is
still here so a host CLI can hang the same three subcommands off its own
subparsers.

The command reads a config file describing this workspace, because the seven
items need things no code should hardcode: which list is which project, how
many hours each budget holds, the team roster, and each person's cadence. A
missing config produces an explicit error naming the file, not an empty run
that looks like a quiet day.

Only one subcommand writes to ClickUp, `lancar`, and only with `--real` and a
named approver: it launches a proposal a person already read and approved.
`rodar` and `horas` print. Approving and launching hours stays a separate,
deliberate act.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from . import (auditor, bolsao, checagem, coletor, cronograma, daily, datas, horas,
               lancamento, periodo, reporte, rh, rotina)
from .clickup import Aprovacao, ClickUp

logger = logging.getLogger("pmo.cli")

CONFIG_HOME = Path.home() / ".soteria-pmo"
CONFIG_PADRAO = CONFIG_HOME / "pmo.json"

#: Onde as transcricoes de daily ficam quando o config nao diz outra pasta. E
#: do proprio pacote: o caminho antigo era a pasta Sessions do vault do
#: delegation-core, e um pacote independente nao pode nascer apontando para o
#: disco de outro projeto. Quem guarda as dailies em outro lugar aponta
#: `evidencia.dailies` para la.
DAILIES_PADRAO = CONFIG_HOME / "dailies"

# How many days back the daily audit looks. Long enough that an entry logged on
# Friday is still checked on Monday, short enough that the same exception is not
# repeated for weeks after everyone has decided to leave it alone.
JANELA_DA_AUDITORIA = 7

# O exemplo que a CLI imprime quando nao ha config. Tudo aqui e placeholder de
# proposito: e a primeira coisa que uma pessoa nova da Soteria ve, e um valor
# real de outra pessoa copiado daqui vira apuracao no nome errado, evidencia
# lida da maquina errada e hora lancada na tarefa errada.
#
# "pessoa" e por operador: cada um aponta para o proprio nome como aparece nas
# transcricoes e no ClickUp. O pacote nao assume um dono unico.
EXEMPLO = {
    "token": "pk_...",
    "team_id": "9007...",
    "pessoa": "Nome Sobrenome, como aparece na daily e no ClickUp",
    "evidencia": {
        "repos": ["~/Projects/algum-repo"],
        "autor_git": "",
        "sessoes_ia": "~/.claude/projects",
        # Transcricoes de daily, uma por arquivo. Ausente, vale ~/.soteria-pmo/dailies.
        "dailies": "~/.soteria-pmo/dailies",
        # Notas em markdown que viram evidencia pelo horario de escrita. Opcional.
        "vault": "~/caminho/para/notas",
        "historico_navegador": "~/.config/google-chrome/Default/History",
        # Historico de pedidos do Antigravity CLI. Opcional.
        "antigravity": "~/.gemini/antigravity-cli/history.jsonl",
        # Agenda: um arquivo JSON de eventos ou um comando que imprime esse JSON,
        # com {de} e {ate} trocados pelas datas. Opcional.
        "agenda": "agenda eventos --de {de} --ate {ate} --json",
        # Projetos pessoais desta maquina, por caminho ou por nome. O que cair
        # aqui sai da apuracao em vez de virar hora de cliente.
        "pessoais": ["~/Projects/algum-projeto-pessoal"],
    },
    # Endpoint compativel com OpenAI que interpreta as dailies. Sem ele as
    # dailies nao sao lidas, e a apuracao segue so com a evidencia de maquina.
    "modelo": {"url": "http://127.0.0.1:8080"},
    "task_horas": "id da tarefa guarda-chuva de horas desta pessoa",
    "projetos": [
        # "space_id" e a unidade do bolsao: o trabalho de um cliente se espalha
        # por dezenas de listas do espaco dele, entao medir consumo por uma
        # lista mede uma fatia. "list_id" segue sendo o que o item 2 e o
        # guardiao das datas leem, porque esses olham tarefa.
        # "tipo" escolhe a regua do item 2: "projeto" da 4 dias uteis sem hora
        # apontada, "chamado" da 2. Ausente vale "projeto".
        {"nome": "Soteria", "list_id": "901716443542", "space_id": "90070084485",
         "horas_contratadas": 1800, "tipo": "projeto"},
        {"nome": "China Gate", "space_id": "90070091337",
         "horas_contratadas": 100, "tipo": "chamado"}
    ],
    "roster_rh": "~/.soteria-pmo/rh.csv",
    "feriados": ["2026-09-07"],
}


class ConfigAusente(RuntimeError):
    """No workspace config. Named as its own error so the CLI can print the
    example instead of a traceback."""


def carregar_config(caminho: Path) -> dict:
    # O config antigo em ~/.delegation_core deixou de ser lido em 02/10/2026:
    # era o ultimo caminho do pacote que apontava para outro projeto.
    if not caminho.exists():
        raise ConfigAusente(str(caminho))
    return json.loads(caminho.read_text(encoding="utf-8"))


def pasta_dailies(cfg: dict) -> Path:
    """Onde estao as transcricoes de daily: o config, ou a pasta do pacote."""
    ev = cfg.get("evidencia") or {}
    return Path(ev.get("dailies") or DAILIES_PADRAO).expanduser()


def modelo_url(cfg: dict) -> str:
    """O modelo que interpreta as dailies, se houver. Sem padrao de proposito:
    o 127.0.0.1:8181 que ficava escrito no codigo era o modelo do delegation-core."""
    return str((cfg.get("modelo") or {}).get("url") or "").rstrip("/")


def _feriados(cfg: dict) -> frozenset[date]:
    return frozenset(date.fromisoformat(d) for d in cfg.get("feriados", []))


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
        pessoais=tuple(ev.get("pessoais", ())),
        dailies=str(pasta_dailies(cfg)),
        antigravity=ev.get("antigravity", ""),
        agenda=ev.get("agenda", ""),
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
        fontes = fontes_de_evidencia(cfg)
        evidencias, _falhas = coletor.coletar(fontes, inicio, fim)
    except Exception:
        logger.exception("coleta de evidencia falhou; auditoria segue sem lastro")
        return []
    uteis, _pessoais = coletor.separar_pessoal(evidencias, fontes.pessoais)
    return uteis


def montar_tarefas(cfg: dict, cliente: ClickUp, hoje: date) -> dict:
    """Wire each item to its data. Kept out of rotina.py so that module stays
    free of any client and can be tested without a network."""
    projetos = cfg.get("projetos") or []
    feriados = _feriados(cfg)
    # Passa pelo carregador em vez de construir aqui: e ele que sabe cair no
    # teto de referencia quando o config nao traz horas, e que devolve os
    # projetos sem teto nenhum para o digest dizer que ficaram de fora.
    bolsoes, bolsoes_sem_teto = bolsao.carregar_bolsoes(projetos)
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
        # A janela do bolsao e o MES CORRENTE, nao trinta dias corridos: o teto
        # e mensal e reseta na virada. Com a janela movel, dois clientes
        # apareceram estourados em 08/09 sem estarem.
        "bolsao": lambda: bolsao.digest(
            bolsao.vigiar(cliente, bolsoes, hoje.replace(day=1), hoje,
                          feriados, sem_teto=bolsoes_sem_teto,
                          fim_do_ciclo=periodo.fim_do_mes(hoje))),
        "datas": lambda: datas.vigiar(cliente, primeiro["list_id"], hoje) if primeiro else "",
        # Item 2 le TODOS os projetos, nao so o primeiro: a regua de 03/09 e
        # por projeto, e avaliar um de uma lista de nove nao e acompanhar
        # cronograma nenhum.
        "cronograma": lambda: cronograma.acompanhar_projetos(
            cliente, projetos, hoje, feriados),
    }

    if cfg.get("roster_rh"):
        caminho = Path(cfg["roster_rh"]).expanduser()
        tarefas["rh"] = lambda: rh.rodar(caminho, hoje)

    # Item 1 sobre TODOS os clientes, consolidado por espaco e separando
    # implantacao de sustentacao, que e o que o Max especificou em 24/06. Ate
    # 10/09/2026 isto lia um `list_id` unico, o do primeiro projeto do config,
    # que nesta maquina e a lista interna dos proprios Agentes PMO: o reporte ao
    # cliente nao passava por cliente nenhum.
    if projetos:
        tarefas["reporte"] = lambda: reporte.gerar_todos(
            cliente, projetos, inicio_semana, fim_semana)

    if primeiro:
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

    fontes = fontes_de_evidencia(cfg)
    evidencias, falhas = coletor.coletar(fontes, inicio, fim)
    print(coletor.resumo(evidencias, falhas, fontes.pessoais))
    print()
    # Personal evidence is dropped from the apuracao, not from the report: the
    # resumo above says how much was separated so a wrong split is visible.
    evidencias, _pessoais = coletor.separar_pessoal(evidencias, fontes.pessoais)

    falas = []
    url = modelo_url(cfg)
    if pessoa:
        pasta = pasta_dailies(cfg)
        if args.sem_modelo or not url:
            motivo = "modo sem modelo" if args.sem_modelo else "nenhum modelo em modelo.url"
            print(f"Dailies nao interpretadas ({motivo}): o que a pessoa disse que "
                  "fez nao entra na apuracao.\n")
        else:
            falas = daily.falas_da_pessoa(pasta, pessoa, inicio, fim,
                                          daily.InterpreteLocal(pessoa, url=url))
            print(f"Dailies: {len(falas)} atividade(s) declarada(s) por {pessoa}.\n")

    ap = horas.apurar(inicio, fim, evidencias, falas,
                      cfg.get("task_horas", ""),
                      (cfg.get("projetos") or [{}])[0].get("nome", "Cliente"),
                      tuple(args.tags or ("desenvolvimento",)),
                      feriados=_feriados(cfg))
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


def _subcomandos(pmo_sub) -> None:
    """Os tres subcomandos, pendurados no objeto de subparsers que vier.

    Existe separado de `registrar` para que a mesma arvore sirva ao comando
    proprio e a um CLI hospedeiro, sem a definicao ser escrita duas vezes.
    """
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

    p_lan = pmo_sub.add_parser(
        "lancar", help="Lanca uma proposta de horas ja aprovada (simula sem --real)")
    p_lan.add_argument("--arquivo", required=True, help="JSON com a proposta aprovada")
    p_lan.add_argument("--aprovado-por", required=True,
                       help="quem leu e aprovou esta proposta, pelo nome")
    p_lan.add_argument("--real", action="store_true",
                       help="escreve de verdade; sem isto, so simula")
    p_lan.add_argument("--config", default=str(CONFIG_PADRAO))
    p_lan.set_defaults(func=cmd_lancar)

    p_cad = pmo_sub.add_parser("cadencias", help="Mostra o que roda hoje e o que nao")
    p_cad.add_argument("--dia", default=None)
    p_cad.add_argument("--config", default=str(CONFIG_PADRAO))
    p_cad.set_defaults(func=cmd_cadencias)

    p_chk = pmo_sub.add_parser(
        "checar", help="O que e obrigatorio, o que e opcional, e o que falta agora")
    p_chk.add_argument("--config", default=str(CONFIG_PADRAO))
    p_chk.set_defaults(func=cmd_checar)


def cmd_lancar(args) -> int:
    """Lanca uma proposta aprovada, dia a dia, conferindo cada entrada.

    Sai com 1 se a proposta tiver sobreposicao (nada e escrito) ou se alguma
    entrada nao voltar conferida (o lote para ali e nada e retentado).
    """
    cfg = carregar_config(Path(args.config).expanduser())
    itens = lancamento.ler_proposta(args.arquivo)
    aprovacao = Aprovacao.de(args.aprovado_por, f"proposta {Path(args.arquivo).name}")
    with ClickUp(cfg["token"], cfg["team_id"], dry_run=not args.real) as cliente:
        try:
            rels = lancamento.lancar(cliente, itens, aprovacao)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
    print(lancamento.resumo(rels, dry_run=not args.real))
    if not args.real:
        print("\nSimulacao: nada foi escrito. Rode com --real para lancar.")
    return 1 if any(r.parado_em for r in rels) else 0


def cmd_checar(args) -> int:
    """Diz o que este pacote precisa, o que ele so aproveita, e o que falta.

    Sai com 0 mesmo faltando fonte opcional: ausencia de fonte nao e falha do
    ambiente, e menos evidencia. So o obrigatorio ausente sai com 1.
    """
    try:
        cfg = carregar_config(Path(args.config).expanduser())
    except ConfigAusente as e:
        print(f"Sem configuracao do PMO em {e}.\n\nCrie o arquivo com esta forma:\n",
              file=sys.stderr)
        print(json.dumps(EXEMPLO, indent=2, ensure_ascii=False), file=sys.stderr)
        return 2
    c = checagem.checar(cfg, modelo=modelo_url(cfg), dailies=pasta_dailies(cfg))
    print(checagem.relatorio(c))
    return 0 if c.pronto else 1


def registrar(sub) -> None:
    """Hang `pmo` off a host CLI's subparsers, as delegation-core did."""
    p = sub.add_parser("pmo", help="Agentes PMO: rodar os itens de gestao do dia")
    _subcomandos(p.add_subparsers(dest="pmo_command", metavar="pmo-command"))


def main(argv: list[str] | None = None) -> int:
    """O comando `soteria-pmo`."""
    parser = argparse.ArgumentParser(
        prog="soteria-pmo",
        description="Agentes PMO: os sete itens de gestao, rodando sobre o ClickUp.")
    sub = parser.add_subparsers(dest="command", metavar="command")
    _subcomandos(sub)
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except ConfigAusente as e:
        # Rede para o subcomando que nao trata por conta propria. Mesma frase
        # dos outros dois, porque duas mensagens para a mesma falta so fazem
        # quem le procurar diferenca onde nao ha.
        print(f"Sem configuracao do PMO em {e}.\n\nCrie o arquivo com esta forma:\n",
              file=sys.stderr)
        print(json.dumps(EXEMPLO, indent=2, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
