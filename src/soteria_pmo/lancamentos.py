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
