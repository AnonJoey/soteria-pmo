"""O painel da carteira: um HTML por dia, no modelo que o Max mandou em 21/10/2026.

O modelo e uma pagina so: tabela de clientes (consumo contra o teto do mes,
projecao, 12 semanas, dias sem hora, prazos vencidos, situacao), o detalhe de um
cliente (acumulado do mes, horas por semana, quadrado por dia, listas, pessoas,
prazos) e a carga lancada por pessoa. Ela se desenha sozinha a partir de um
objeto `D` embutido; este modulo so monta esse objeto, com dado de agora, e o
poe no lugar do marcador do modelo. Nada aqui escreve no ClickUp.

O modelo que vai no pacote (`painel_modelo.html`) esta sem dado nenhum, sem a
fonte da marca e sem o logotipo: nome de cliente e hora por pessoa nunca entram
no repositorio, que e publico. Quem quiser a aparencia completa aponta
`painel_modelo` no config para o arquivo do Max.

Sustentacao e implantacao seguem a mesma regra do reporte consolidado
(`reporte._e_sustentacao`): o nome da lista e da pasta, e `listas_sustentacao` e
`listas_projeto` do config, que mandam sobre o nome.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import bolsao
from .clickup import ClickUpError, status_normalizado
from .periodo import campo_objeto, de_ms, dias_uteis, janela
from .reporte import _e_sustentacao

logger = logging.getLogger("pmo.painel")

#: O que o modelo espera no lugar do objeto de dados.
MARCADOR = "__DADOS_DO_PAINEL__"

#: O modelo desenha 12 semanas, a corrente incluida.
SEMANAS = 12

#: Tarefa aberta que espera algo de fora do desenvolvimento: o modelo a marca "em espera".
ESPERA = frozenset({
    "homologação", "homologacao", "aguardando deploy", "bloqueado",
    "falta de informação", "falta de informacao",
})

#: Tarefas que o modelo lista por cliente; o resto vira "mais N".
LIMITE_PRAZOS = 60

#: Tipos de status que o ClickUp usa para trabalho acabado.
_FINALIZADOS = frozenset({"closed", "done"})

CAMINHO_MODELO = Path(__file__).with_name("painel_modelo.html")


def _segunda(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _fim_do_mes(d: date) -> date:
    if d.month == 12:
        return d.replace(day=31)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)


def _h(x: float) -> float:
    return round(float(x), 2)


def _horas(entrada: dict) -> float:
    return int(entrada.get("duration") or 0) / 3_600_000


def _dia(entrada: dict) -> date | None:
    d = de_ms(entrada.get("start"))
    return d.date() if d else None


def _pessoa(entrada: dict) -> str:
    u = campo_objeto(entrada, "user")
    return str(u.get("username") or u.get("email") or "sem nome")


def _nomes_das_listas(cliente: Any, space_id: str) -> dict[str, tuple[str, str]]:
    """list_id -> (nome da lista, nome da pasta), lidos do espaco do cliente.

    A entrada de tempo so carrega o id da lista; o nome e o que separa
    sustentacao de implantacao. Falha de leitura devolve o que deu: o painel sai
    com listas sem nome em vez de nao sair.
    """
    nomes: dict[str, tuple[str, str]] = {}
    try:
        for pasta in cliente._get(f"/space/{space_id}/folder").get("folders", []):
            for lista in pasta.get("lists", []):
                nomes[str(lista["id"])] = (lista.get("name") or "", pasta.get("name") or "")
        for lista in cliente._get(f"/space/{space_id}/list").get("lists", []):
            nomes.setdefault(str(lista["id"]), (lista.get("name") or "", ""))
    except ClickUpError as e:
        logger.warning("nao foi possivel ler as listas do espaco %s: %s", space_id, e)
    return nomes


def _finalizada(tarefa: dict) -> bool:
    status = tarefa.get("status")
    return isinstance(status, dict) and str(status.get("type") or "").lower() in _FINALIZADOS


def _prazos(tarefas: list[dict], hoje: date) -> dict:
    """Vencidas e a vencer em 7 dias, no formato do modelo."""
    vencidas, a_vencer = [], []
    vistas: set[str] = set()
    for t in tarefas:
        tid = str(t.get("id") or "")
        if not tid or tid in vistas or _finalizada(t):
            continue
        vistas.add(tid)
        vence = de_ms(t.get("due_date"))
        if not vence:
            continue
        vence = vence.date()
        status = (t.get("status") or {}).get("status") if isinstance(t.get("status"), dict) else t.get("status")
        espera = status_normalizado(status) in ESPERA
        resp = (t.get("assignees") or [{}])[0].get("username") if t.get("assignees") else "sem responsável"
        item = {
            "tarefa": t.get("name") or "(sem nome)",
            "lista": (campo_objeto(t, "list").get("name") or ""),
            "resp": resp or "sem responsável",
            "status": status or "?",
            "espera": bool(espera),
            "vence": vence.isoformat(),
        }
        if vence < hoje:
            vencidas.append(item)
        elif vence <= hoje + timedelta(days=7):
            a_vencer.append(item)
    vencidas.sort(key=lambda i: (i["espera"], i["vence"]))
    a_vencer.sort(key=lambda i: i["vence"])
    return {
        "vencidas": len(vencidas),
        "vencidas_espera": sum(1 for i in vencidas if i["espera"]),
        "a_vencer_7d": len(a_vencer),
        "lista_vencidas": vencidas[:LIMITE_PRAZOS],
        "lista_a_vencer": a_vencer[:LIMITE_PRAZOS],
    }


def _sem_tarefas() -> dict:
    return {"vencidas": 0, "vencidas_espera": 0, "a_vencer_7d": 0, "lista_vencidas": [], "lista_a_vencer": []}


def _cliente(cliente: Any, projeto: dict, entradas: list[dict], hoje: date, inicio: date,
             feriados: frozenset[date]) -> dict:
    nome = projeto.get("nome") or projeto.get("projeto") or "?"
    space = str(projeto.get("space_id") or "")
    lista_cfg = str(projeto.get("list_id") or "")
    proprias = []
    for e in entradas:
        loc = campo_objeto(e, "task_location")
        if space and str(loc.get("space_id") or "") == space:
            proprias.append(e)
        elif not space and lista_cfg and str(loc.get("list_id") or "") == lista_cfg:
            proprias.append(e)

    bolsoes, _ = bolsao.carregar_bolsoes([projeto])
    teto = _h(bolsoes[0].horas_contratadas) if bolsoes else 0.0
    totais = bolsao.carregar_totais([projeto])
    total_projeto = None
    if totais:
        total_projeto = totais[0].horas_previstas or bolsao.total_de_projeto(nome)
    elif not teto:
        total_projeto = bolsao.total_de_projeto(nome)
    motivo = ""
    if not teto and not total_projeto:
        motivo = bolsao.teto_a_confirmar(nome) or "sem teto configurado"

    listas_sust = frozenset(str(x) for x in (projeto.get("listas_sustentacao") or ()))
    listas_proj = frozenset(str(x) for x in (projeto.get("listas_projeto") or ()))
    base_fixa = "sust" if listas_sust else ""
    nomes = _nomes_das_listas(cliente, space) if space else {}

    semanas: dict[date, dict[str, float]] = {}
    for k in range(SEMANAS):
        s = inicio + timedelta(days=7 * k)
        semanas[s] = {"sust": 0.0, "impl": 0.0, "fat": 0.0, "sust_fat": 0.0, "impl_fat": 0.0}
    diario: dict[str, float] = defaultdict(float)
    diario_sust: dict[str, float] = defaultdict(float)
    mes = {
        "total": 0.0, "sust": 0.0, "impl": 0.0, "fat": 0.0, "naofat": 0.0,
        "sust_fat": 0.0, "sust_naofat": 0.0, "impl_fat": 0.0, "impl_naofat": 0.0,
    }
    pessoas: dict[str, dict[str, float]] = defaultdict(lambda: {
        "sust": 0.0, "impl": 0.0, "fat": 0.0, "sust_fat": 0.0, "impl_fat": 0.0
    })
    listas: dict[str, dict] = {}
    sp_ini = _segunda(hoje) - timedelta(days=7)
    sp_fim = sp_ini + timedelta(days=6)
    tarefas_sp: dict[str, dict] = {}
    ultima: date | None = None
    inicio_mes = hoje.replace(day=1)

    for e in proprias:
        d = _dia(e)
        if d is None or d > hoje:
            continue
        h = _horas(e)
        if h <= 0:
            continue
        loc = campo_objeto(e, "task_location")
        lid = str(loc.get("list_id") or "")
        lista, pasta = nomes.get(lid, ("(lista sem nome)" if lid else "(sem lista)", ""))
        if listas_sust:
            # Declarado no config, manda: so as listas nomeadas sao sustentacao. Sem isto, uma
            # lista de projeto caia como sustentacao so porque o cliente e do tipo "chamado"
            # (medido em 21/10/2026: o Angelus aparecia com 362 h contra 129 h do vigia).
            sust = lid in listas_sust and lid not in listas_proj
        else:
            sust = _e_sustentacao(lista, pasta, projeto.get("tipo", ""), lid, listas_sust, listas_proj)
        chave = "sust" if sust else "impl"
        fat = bool(e.get("billable"))
        semana = semanas.get(_segunda(d))
        if semana is not None:
            semana[chave] += h
            if fat:
                semana["fat"] += h
                semana[f"{chave}_fat"] += h
        diario[d.isoformat()] += h
        if sust:
            diario_sust[d.isoformat()] += h
        if ultima is None or d > ultima:
            ultima = d
        if d >= inicio_mes:
            mes[chave] += h
            mes["total"] += h
            mes["fat" if fat else "naofat"] += h
            mes[f"{chave}_{'fat' if fat else 'naofat'}"] += h
            p_dict = pessoas[_pessoa(e)]
            p_dict[chave] += h
            if fat:
                p_dict["fat"] += h
                p_dict[f"{chave}_fat"] += h
            item = listas.setdefault(lid or "-", {"lista": lista, "pasta": pasta, "h": 0.0, "fat": 0.0, "nat": chave})
            item["h"] += h
            if fat:
                item["fat"] += h
        if sp_ini <= d <= sp_fim:
            task = campo_objeto(e, "task")
            tid = str(task.get("id") or e.get("id") or "")
            status = task.get("status")
            status = status.get("status") if isinstance(status, dict) else status
            t = tarefas_sp.setdefault(tid, {
                "tarefa": task.get("name") or "(sem tarefa)", "lista": lista, "nat": chave,
                "pessoas": set(), "status": status or "", "h": 0.0})
            t["pessoas"].add(_pessoa(e))
            t["h"] += h

    sem_hora = None
    if ultima is not None:
        sem_hora = dias_uteis(ultima + timedelta(days=1), hoje - timedelta(days=1), feriados)

    try:
        tarefas = cliente.tarefas_do_espaco(
            space, desde_ms=int((datetime.combine(hoje, datetime.min.time()) - timedelta(days=90)).timestamp() * 1000)
        ) if space else []
    except Exception as ex:  # um espaco que nao le nao derruba a carteira
        logger.warning("tarefas de %s indisponiveis: %s", nome, ex)
        tarefas = []

    return {
        "nome": nome,
        "teto": teto,
        "base_fixa": base_fixa,
        "base_origem": "listas_sustentacao no config do projeto" if base_fixa else "",
        "total_projeto": _h(total_projeto) if total_projeto else None,
        "motivo_sem_teto": motivo,
        "tipo_config": projeto.get("tipo") or "",
        "semanas": [{"semana": s.isoformat(), "sust": _h(v["sust"]), "impl": _h(v["impl"]),
                     "fat": _h(v["fat"]), "sust_fat": _h(v.get("sust_fat", 0.0)), "impl_fat": _h(v.get("impl_fat", 0.0))}
                    for s, v in sorted(semanas.items())],
        "diario": {k: _h(v) for k, v in sorted(diario.items())},
        "diario_sust": {k: _h(v) for k, v in sorted(diario_sust.items())},
        "mes": {k: _h(v) for k, v in mes.items()},
        "pessoas": sorted(({"nome": n, "sust": _h(v["sust"]), "impl": _h(v["impl"]),
                            "fat": _h(v.get("fat", 0.0)), "sust_fat": _h(v.get("sust_fat", 0.0)), "impl_fat": _h(v.get("impl_fat", 0.0))}
                           for n, v in pessoas.items()),
                          key=lambda p: -(p["sust"] + p["impl"])),
        "listas": sorted(({"lista": v["lista"], "pasta": v["pasta"], "h": _h(v["h"]), "fat": _h(v["fat"]), "nat": v["nat"]}
                          for v in listas.values()), key=lambda l: -l["h"]),
        "semana_passada": sorted(({"tarefa": v["tarefa"], "lista": v["lista"], "nat": v["nat"],
                                   "pessoas": sorted(v["pessoas"]), "status": v["status"], "h": _h(v["h"])}
                                  for v in tarefas_sp.values()), key=lambda t: -t["h"]),
        "tarefas": _prazos(tarefas, hoje) if tarefas else _sem_tarefas(),
        "dias_uteis_sem_hora": sem_hora,
        "ultima_hora": ultima.isoformat() if ultima else None,
    }


def montar_dados(cliente: Any, projetos: list[dict], hoje: date,
                 feriados: frozenset[date] = frozenset(), agora: datetime | None = None,
                 fat_padrao: bool = False) -> dict:
    """O objeto `D` do modelo, com o ClickUp lido agora. So leitura.

    `fat_padrao` abre o painel ja filtrado em horas faturaveis; o botao continua valendo e a
    escolha que a pessoa fez no navegador vence o padrao."""
    agora = agora or datetime.now()
    inicio = _segunda(hoje) - timedelta(weeks=SEMANAS - 1)
    try:
        equipe = tuple(str(m["id"]) for m in cliente.membros() if m.get("id"))
    except Exception as e:
        logger.warning("nao foi possivel listar a equipe: %s", e)
        equipe = None
    entradas = cliente.entradas(*janela(inicio, hoje), assignee=equipe)

    ativos = [p for p in projetos if not bolsao.encerrado(p.get("nome") or p.get("projeto") or "")]
    clientes = [_cliente(cliente, p, entradas, hoje, inicio, feriados) for p in ativos]

    por_pessoa: dict[str, dict[str, float]] = defaultdict(dict)
    for c in clientes:
        for p in c["pessoas"]:
            por_pessoa[p["nome"]][c["nome"]] = _h(p["sust"] + p["impl"])
    pessoas = sorted(({"nome": n, "total": _h(sum(v.values())), "clientes": v} for n, v in por_pessoa.items()),
                     key=lambda p: -p["total"])

    inicio_mes = hoje.replace(day=1)
    sp_ini = _segunda(hoje) - timedelta(days=7)
    return {
        "gerado_em": agora.strftime("%Y-%m-%dT%H:%M"),
        "filtro_fat_padrao": bool(fat_padrao),
        "hoje": hoje.isoformat(),
        "inicio": inicio.isoformat(),
        "mes": {"inicio": inicio_mes.isoformat(), "fim": _fim_do_mes(hoje).isoformat(),
                "dias_uteis_passados": dias_uteis(inicio_mes, hoje, feriados),
                "dias_uteis_mes": dias_uteis(inicio_mes, _fim_do_mes(hoje), feriados)},
        "semana_passada": {"inicio": sp_ini.isoformat(), "fim": (sp_ini + timedelta(days=6)).isoformat()},
        "equipe_consultada": len(equipe or ()),
        "entradas_lidas": len(entradas),
        "clientes": clientes,
        "pessoas": pessoas,
    }


def carregar_modelo(modelo: str | Path | None = None) -> str:
    """O modelo do painel: o arquivo do config se existir e tiver o marcador, senao o do pacote."""
    candidato = Path(modelo).expanduser() if modelo else None
    if candidato is not None:
        try:
            texto = candidato.read_text(encoding="utf-8")
            if MARCADOR in texto or "const D = " in texto:
                return texto
            logger.warning("modelo %s sem o marcador %s; usando o do pacote", candidato, MARCADOR)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("modelo %s ilegivel (%s); usando o do pacote", candidato, e)
    return CAMINHO_MODELO.read_text(encoding="utf-8")


def renderizar(dados: dict, modelo: str | Path | None = None) -> str:
    """Poe os dados no lugar do marcador. Aceita tambem o modelo do Max com `const D = {...}`."""
    texto = carregar_modelo(modelo)
    # `</` dentro de um script fecharia a tag: nome de tarefa com HTML nao pode quebrar a pagina.
    bloco = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    if MARCADOR in texto:
        return texto.replace(MARCADOR, bloco)
    i = texto.index("const D = ") + len("const D = ")
    _, fim = json.JSONDecoder().raw_decode(texto[i:])
    return texto[:i] + bloco + texto[i + fim:]


def gerar(cliente: Any, projetos: list[dict], hoje: date, feriados: frozenset[date] = frozenset(),
          modelo: str | Path | None = None, fat_padrao: bool = False) -> str:
    return renderizar(montar_dados(cliente, projetos, hoje, feriados, fat_padrao=fat_padrao), modelo)


def caminho_padrao(hoje: date) -> Path:
    return Path.home() / ".soteria-pmo" / "reportes" / f"painel-{hoje:%Y-%m-%d}.html"


def diretorios_do_briefing(cfg: dict) -> list[Path]:
    """Onde o briefing do dia e gravado alem de ~/.soteria-pmo/reportes/.

    `diretorio_relatorios` do config, ou ~/.soteria-pmo/relatorios quando ausente, e
    o `relatorios/` do diretorio atual se ele existir (a rotina.sh do Max roda la).
    """
    dirs = [Path(cfg.get("diretorio_relatorios") or Path.home() / ".soteria-pmo" / "relatorios").expanduser()]
    local = Path("relatorios")
    if local.is_dir() and local.resolve() not in {d.resolve() for d in dirs}:
        dirs.append(local)
    return dirs


def gravar_briefing(html: str, hoje: date, cfg: dict, destino: Path | None = None) -> list[Path]:
    """Grava o painel como briefing do dia: este e o formato do briefing, nunca o .md convertido.

    Devolve os arquivos escritos. O primeiro e o canonico. `AAAA-MM-DD.html` e o nome que
    a rotina do Max abre; as duas variantes com `painel` ficam por compatibilidade.
    Falha de copia em relatorios/ e registrada e nao derruba o painel.
    """
    destino = destino or caminho_padrao(hoje)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    escritos = [destino]
    for pasta in diretorios_do_briefing(cfg):
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            for nome in (f"{hoje:%Y-%m-%d}.html", f"{hoje:%Y-%m-%d}-painel.html",
                         f"painel-{hoje:%Y-%m-%d}.html"):
                (pasta / nome).write_text(html, encoding="utf-8")
                escritos.append(pasta / nome)
        except OSError as e:
            logger.warning("copia do briefing para %s falhou: %s", pasta, e)
    return escritos
