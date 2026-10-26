"""Quem lancou horas ontem e na semana passada, e quem nao lancou.

Pedido do Max em 06/10/2026: uma visao simples no lugar da planilha. Esta e a
cobranca mais direta do pacote, entao a parte que importa e dizer o que ela NAO
enxerga:

- **Quem nunca lancou nao aparece.** O quadro lista os esperados, e sem uma lista
  informada em `equipe_lancamento` no config os esperados sao quem lancou ao menos
  uma vez nos ultimos 30 dias. Quem nao lanca ha mais tempo que isso, ou nunca
  lancou, some do quadro, e sumir daqui e indistinguivel de estar em dia. Por isso
  a origem da lista sai impressa em todo quadro.
- **"Lancou" e ter alguma entrada no dia**, nao ter lancado "o suficiente". Julgar
  quantas horas um dia deveria ter e papel do auditor, e ele nao acusa ninguem.
- Ferias, feriado local e meio periodo nao existem aqui: um dia util sem entrada
  aparece como sem lancamento. A pessoa e o Max sabem o motivo; o quadro nao.

Nada aqui escreve no ClickUp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .periodo import BRT, campo_objeto, de_ms

JANELA_DE_ESPERADOS = 30
NOMES_DOS_DIAS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")


def dia_util_anterior(hoje: date, feriados: frozenset[date] = frozenset()) -> date:
    """O ultimo dia util antes de `hoje`: segunda olha para a sexta, nao para o domingo."""
    d = hoje - timedelta(days=1)
    while d.weekday() >= 5 or d in feriados:
        d -= timedelta(days=1)
    return d


def ultimos_dias_uteis(hoje: date, n: int = 5, feriados: frozenset[date] = frozenset()) -> list[date]:
    """Os `n` dias uteis que terminam no dia util anterior a `hoje`, do mais antigo ao mais novo.

    E a janela do resumo diario: a semana passada so cobre segunda a sexta de uma
    semana calendario, e na quarta ela ja nao diz nada sobre ontem."""
    dias: list[date] = []
    d = dia_util_anterior(hoje, feriados)
    while len(dias) < n:
        dias.append(d)
        d = dia_util_anterior(d, feriados)
    return sorted(dias)


def dias_da_semana_passada(hoje: date, feriados: frozenset[date] = frozenset()) -> list[date]:
    """Os dias uteis da semana calendario anterior a de `hoje` (segunda a sexta, sem feriado)."""
    segunda = hoje - timedelta(days=hoje.weekday() + 7)
    return [segunda + timedelta(days=i) for i in range(5) if (segunda + timedelta(days=i)) not in feriados]


@dataclass
class Linha:
    pessoa: str
    por_dia: dict[date, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return round(sum(self.por_dia.values()), 2)


@dataclass
class Quadro:
    dias: list[date]
    linhas: list[Linha]
    origem_dos_esperados: str

    def sem_lancamento(self, dia: date) -> list[str]:
        return [l.pessoa for l in self.linhas if l.por_dia.get(dia, 0.0) <= 0.0]

    def lancaram(self, dia: date) -> list[str]:
        return [l.pessoa for l in self.linhas if l.por_dia.get(dia, 0.0) > 0.0]


def _quem(entrada: dict) -> str:
    usuario = campo_objeto(entrada, "user")
    return str(usuario.get("username") or usuario.get("email") or "")


def _dia_da(entrada: dict) -> date | None:
    comeco = de_ms(entrada.get("start"))
    return comeco.astimezone(BRT).date() if comeco else None


def horas_por_pessoa_e_dia(entradas: list[dict]) -> dict[str, dict[date, float]]:
    """Soma a duracao das entradas por pessoa e por dia da data de INICIO, no fuso de Brasilia."""
    saida: dict[str, dict[date, float]] = {}
    for e in entradas:
        quem, dia = _quem(e), _dia_da(e)
        if not quem or dia is None:
            continue
        horas = int(e.get("duration") or 0) / 3_600_000
        saida.setdefault(quem, {})
        saida[quem][dia] = round(saida[quem].get(dia, 0.0) + horas, 2)
    return saida


def esperados_do_historico(entradas_do_historico: list[dict]) -> list[str]:
    """Quem lancou ao menos uma vez na janela de historico. Ordem alfabetica."""
    return sorted({q for q in (_quem(e) for e in entradas_do_historico) if q}, key=str.lower)


def apurar(entradas: list[dict], dias: list[date], esperados: list[str] | None = None,
           historico: list[dict] | None = None) -> Quadro:
    """O quadro de `dias`, com uma linha por pessoa esperada.

    `esperados` vence quando vem do config. Sem ele valem os autores do `historico`
    (que deve cobrir os 30 dias anteriores); sem os dois, valem os autores das
    proprias `entradas`, que e o caso mais fraco e e dito como tal.
    """
    por_pessoa = horas_por_pessoa_e_dia(entradas)
    if esperados:
        nomes, origem = sorted(set(esperados), key=str.lower), "lista informada em equipe_lancamento"
    elif historico is not None:
        nomes = esperados_do_historico(historico)
        origem = (f"quem lancou ao menos uma vez nos ultimos {JANELA_DE_ESPERADOS} dias; "
                  "quem nao lanca ha mais tempo, ou nunca lancou, NAO aparece aqui")
    else:
        nomes = sorted(por_pessoa, key=str.lower)
        origem = "so quem lancou algo no periodo; quem ficou a janela inteira sem lancar NAO aparece aqui"
    linhas = [Linha(p, {d: h for d, h in por_pessoa.get(p, {}).items() if d in dias}) for p in nomes]
    return Quadro(dias=list(dias), linhas=linhas, origem_dos_esperados=origem)


def _rotulo(d: date) -> str:
    return f"{NOMES_DOS_DIAS[d.weekday()]} {d:%d/%m}"


def _hm(h: float) -> str:
    return f"{h:.1f}".replace(".", ",") if h > 0 else "-"


def formatar(ontem: Quadro, semana: Quadro) -> str:
    dia = ontem.dias[0]
    lancaram, faltam = ontem.lancaram(dia), ontem.sem_lancamento(dia)
    total = len(ontem.linhas)
    linhas = ["# Quem lancou horas", "",
              f"## Ontem ({_rotulo(dia)}): {len(lancaram)} de {total} lancaram", ""]
    if faltam:
        linhas.append("Sem lancamento: " + ", ".join(faltam) + ".")
    else:
        linhas.append("Todos os esperados lancaram.")
    linhas += ["", f"## Semana passada ({_rotulo(semana.dias[0])} a {_rotulo(semana.dias[-1])})", "",
               "| Pessoa | " + " | ".join(_rotulo(d) for d in semana.dias) + " | Total |",
               "|---|" + "---:|" * (len(semana.dias) + 1)]
    for l in semana.linhas:
        celulas = " | ".join(_hm(l.por_dia.get(d, 0.0)) for d in semana.dias)
        linhas.append(f"| {l.pessoa} | {celulas} | {_hm(l.total)} |")
    linhas += ["", "Dias sem lancamento por pessoa na semana:"]
    por_pessoa = {l.pessoa: [d for d in semana.dias if l.por_dia.get(d, 0.0) <= 0.0] for l in semana.linhas}
    pendentes = {p: ds for p, ds in por_pessoa.items() if ds}
    if pendentes:
        for p, ds in sorted(pendentes.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
            linhas.append(f"- {p}: {len(ds)} de {len(semana.dias)} ({', '.join(_rotulo(d) for d in ds)})")
    else:
        linhas.append("- Nenhum.")
    linhas += ["", f"Esperados: {ontem.origem_dos_esperados}.",
               "\"Lancou\" quer dizer ter alguma entrada no dia, nao ter lancado o suficiente. "
               "Ferias, feriado local e meio periodo nao aparecem: um dia util sem entrada e "
               "listado como sem lancamento."]
    return "\n".join(linhas)


def formatar_resumo(ontem: Quadro, recentes: Quadro) -> str:
    """O quadro curto do resumo diario: quem nao lancou no dia util anterior e quem
    acumula dias sem lancar nos ultimos dias uteis. E o que o Max pediu de uma
    auditoria de apontamentos (26/10/2026); a tabela inteira segue em
    `soteria-pmo lancamentos`."""
    dia = ontem.dias[0]
    lancaram, faltam = ontem.lancaram(dia), ontem.sem_lancamento(dia)
    linhas = ["Lancamentos da equipe",
              f"Dia util anterior ({_rotulo(dia)}): {len(lancaram)} de {len(ontem.linhas)} lancaram.",
              ("Sem lancamento: " + ", ".join(faltam) + ".") if faltam else "Todos os esperados lancaram."]
    por_pessoa = {l.pessoa: [d for d in recentes.dias if l.por_dia.get(d, 0.0) <= 0.0] for l in recentes.linhas}
    pendentes = {p: ds for p, ds in por_pessoa.items() if ds}
    linhas += ["", f"Dias sem lancamento, {_rotulo(recentes.dias[0])} a {_rotulo(recentes.dias[-1])}:"]
    if pendentes:
        for p, ds in sorted(pendentes.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
            linhas.append(f"- {p}: {len(ds)} de {len(recentes.dias)} ({', '.join(_rotulo(d) for d in ds)})")
    else:
        linhas.append("- Nenhum.")
    linhas += ["", f"Esperados: {ontem.origem_dos_esperados}.",
               "\"Lancou\" quer dizer ter alguma entrada no dia, nao ter lancado o suficiente. "
               "Ferias, feriado local e meio periodo nao aparecem: um dia util sem entrada e "
               "listado como sem lancamento."]
    return "\n".join(linhas)


def faturaveis_de_quem_nao_fatura(entradas: list[dict], nao_faturam: list[str],
                                  dias: list[date]) -> dict[str, float]:
    """Horas FATURAVEIS lancadas, nos `dias`, por quem so lanca hora nao faturavel.

    Regra confirmada em 14/10/2026: todos devem lancar horas, e algumas pessoas lancam
    so hora nao faturavel, por enquanto. Quem esta em `nao_faturam` continua sendo
    cobrado de lancar (e `equipe_lancamento` que decide quem e esperado), mas uma entrada
    faturavel dessa pessoa e um sinal de que a etiqueta saiu errada, e e isso que esta
    funcao devolve. Os nomes ficam no config local, nunca no repositorio. Nao julga: so soma. A regra vale "por
    enquanto" e por isso mora no config, nao no codigo.
    """
    alvo = {_sem_acento(n) for n in nao_faturam if n}
    achado: dict[str, float] = {}
    for e in entradas:
        quem, dia = _quem(e), _dia_da(e)
        if not quem or dia is None or dia not in dias or _sem_acento(quem) not in alvo:
            continue
        if e.get("billable"):
            achado[quem] = round(achado.get(quem, 0.0) + int(e.get("duration") or 0) / 3_600_000, 2)
    return achado


def formatar_faturaveis_indevidos(achado: dict[str, float], nao_faturam: list[str]) -> str:
    cabecalho = f"## Faturavel de quem lanca so nao faturavel ({len(nao_faturam)} pessoa(s) em nao_faturam)"
    if not achado:
        return f"{cabecalho}\n\nNenhuma entrada faturavel no periodo."
    linhas = [cabecalho, ""]
    for pessoa, horas in sorted(achado.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        linhas.append(f"- {pessoa}: {_hm(horas)} h faturaveis (a regra diz que as horas dessa pessoa sao sempre nao faturaveis)")
    return "\n".join(linhas)


# Hora que nao tem cliente por natureza: reuniao do time, daily, folga. Medido em
# 13/10/2026 sobre o time inteiro, isso explica so 53,7 h + 70 h das 964 h sem
# tarefa; o resto e hora que alguem lancou sem escolher a tarefa.
ETIQUETAS_SEM_CLIENTE = frozenset({"daily", "reuniao interna", "reuniao com o cliente"})
DESCRICOES_SEM_CLIENTE = ("ferias", "feriado", "dayoff", "day off")


def _sem_acento(texto: str) -> str:
    import unicodedata
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in base if not unicodedata.combining(c)).lower().strip()


def _esperada_sem_tarefa(entrada: dict) -> bool:
    etiquetas = {_sem_acento(t.get("name", "")) for t in (entrada.get("tags") or [])
                 if isinstance(t, dict)}
    if etiquetas & ETIQUETAS_SEM_CLIENTE:
        return True
    return _sem_acento(entrada.get("description") or "").startswith(DESCRICOES_SEM_CLIENTE)


@dataclass
class SemTarefa:
    """Horas lancadas sem tarefa: o time inteiro, numa janela."""

    horas: float
    faturaveis: float
    entradas: int
    horas_sem_descricao: float
    por_pessoa: dict[str, float]
    #: Parte de `horas` que e daily, reuniao, ferias ou feriado: nao tem cliente por natureza.
    horas_esperadas: float = 0.0


def _sem_tarefa(entrada: dict) -> bool:
    """Entrada de tempo solta: sem espaco na localizacao da tarefa.

    E o que o vigia de bolsao e o reporte usam para dizer de que cliente e uma
    hora. Sem espaco, a hora nao pertence a cliente nenhum.
    """
    onde = campo_objeto(entrada, "task_location")
    return not str(onde.get("space_id") or "").strip()


def apurar_sem_tarefa(entradas: list[dict]) -> SemTarefa:
    soltas = [e for e in entradas if _sem_tarefa(e)]
    a_explicar = [e for e in soltas if not _esperada_sem_tarefa(e)]
    h = lambda L: round(sum(int(e.get("duration") or 0) for e in L) / 3_600_000, 1)
    por_pessoa: dict[str, float] = {}
    for e in a_explicar:
        quem = _quem(e) or "(sem usuario)"
        por_pessoa[quem] = por_pessoa.get(quem, 0.0) + int(e.get("duration") or 0) / 3_600_000
    return SemTarefa(
        horas=h(soltas),
        faturaveis=h([e for e in soltas if e.get("billable")]),
        entradas=len(soltas),
        horas_sem_descricao=h([e for e in soltas if not (e.get("description") or "").strip()]),
        por_pessoa={k: round(v, 1) for k, v in sorted(por_pessoa.items(), key=lambda kv: -kv[1])},
        horas_esperadas=h([e for e in soltas if _esperada_sem_tarefa(e)]),
    )


def formatar_sem_tarefa(st: SemTarefa, dias: int) -> str:
    if not st.entradas:
        return ""
    sobram = round(st.horas - st.horas_esperadas, 1)
    linhas = ["", f"## Horas sem tarefa (ultimos {dias} dias)", "",
              f"{st.horas:.1f}h em {st.entradas} entradas, {st.faturaveis:.1f}h marcadas como faturaveis; "
              f"{st.horas_sem_descricao:.1f}h sem tarefa E sem descricao.",
              f"Daily, reuniao, ferias e feriado explicam {st.horas_esperadas:.1f}h, que nao tem cliente "
              f"por natureza. Sobram {sobram:.1f}h que alguem lancou sem escolher a tarefa.",
              "Hora sem tarefa nao entra no bolsao de cliente nenhum nem no reporte: ela nao "
              "tem como ser atribuida. Quem mais tem, entre as que sobram:"]
    for quem, h in list(st.por_pessoa.items())[:8]:
        linhas.append(f"- {quem}: {h:.1f}h")
    return "\n".join(linhas)
