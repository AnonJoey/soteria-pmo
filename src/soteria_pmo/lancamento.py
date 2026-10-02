"""Lancar uma proposta de horas ja aprovada, dia a dia, com conferencia.

Ate 02/10/2026 isto nao existia no pacote: o motor de horas propoe e nunca
escreve, e quem lancou setembro inteiro (78 entradas, 208,83h) fez isso por um
script solto em volta de `ClickUp.lancar`. O script acertou porque carregava
tres cuidados que o pacote nao tinha em lugar nenhum, e eles estao aqui agora:

1. **Recusar sobreposicao antes de escrever.** Duas entradas do mesmo dia que
   se cruzam sao hora contada duas vezes, e isso se ve antes de qualquer chamada.
2. **Pular o que ja existe.** Rodar de novo depois de uma falha nao pode criar
   uma segunda copia: a mesma tarefa com inicio a menos de um minuto e a mesma
   entrada. Foi o retentar sem conferir que criou os quatro fantasmas de agosto.
3. **Parar no primeiro resultado nao conferido.** Nada e retentado sozinho; o
   resto do lote espera uma pessoa olhar.

A proposta e um JSON com uma lista de entradas:
`{"dia": "AAAA-MM-DD", "ini": "HH:MM", "fim": "HH:MM", "task": "<id>",
"desc": "...", "fat": true, "tags": ["desenvolvimento"]}`. `tag` sozinha
tambem e aceita.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .clickup import Aprovacao, ClickUp, Lancamento, Resultado
from .periodo import BRT, campo_objeto

#: Mesma tarefa com inicio a menos disto e a mesma entrada.
TOLERANCIA_DUPLICATA_MS = 60_000


@dataclass(frozen=True)
class Item:
    dia: str
    ini: str
    fim: str
    task: str
    desc: str
    fat: bool
    tags: tuple[str, ...]

    def _ms(self, hm: str) -> int:
        h, m = map(int, hm.split(":"))
        y, mo, d = map(int, self.dia.split("-"))
        return int(datetime(y, mo, d, h, m, tzinfo=BRT).timestamp() * 1000)

    @property
    def inicio_ms(self) -> int:
        return self._ms(self.ini)

    @property
    def fim_ms(self) -> int:
        return self._ms(self.fim)

    def lancamento(self) -> Lancamento:
        return Lancamento(task_id=self.task, inicio_ms=self.inicio_ms,
                          duracao_ms=self.fim_ms - self.inicio_ms,
                          descricao=self.desc, faturavel=self.fat, tags=self.tags)


@dataclass
class RelatorioDia:
    dia: str
    escritos: list[Resultado] = field(default_factory=list)
    pulados: list[tuple[Item, str]] = field(default_factory=list)
    parado_em: Resultado | None = None


def ler_proposta(caminho: str | Path) -> list[Item]:
    dados: list[dict[str, Any]] = json.loads(Path(caminho).read_text(encoding="utf-8"))
    itens = []
    for d in dados:
        tags = d.get("tags") or ([d["tag"]] if d.get("tag") else [])
        if "fat" not in d:
            # Faturavel omitido e gravado como nao faturavel pela API, em
            # silencio. Na proposta ele e obrigatorio pelo mesmo motivo.
            raise ValueError(f"entrada sem 'fat' em {d.get('dia')} {d.get('ini')}")
        itens.append(Item(dia=d["dia"], ini=d["ini"], fim=d["fim"], task=d["task"],
                          desc=d["desc"], fat=bool(d["fat"]), tags=tuple(tags)))
    return itens


def sobreposicoes(itens: list[Item]) -> list[str]:
    """Pares do mesmo dia que se cruzam, ditos antes de qualquer escrita."""
    problemas = []
    por_dia: dict[str, list[Item]] = {}
    for i in itens:
        por_dia.setdefault(i.dia, []).append(i)
    for dia, lista in sorted(por_dia.items()):
        lista.sort(key=lambda i: i.inicio_ms)
        for a, b in zip(lista, lista[1:]):
            if b.inicio_ms < a.fim_ms:
                problemas.append(f"{dia}: {a.ini}-{a.fim} cruza com {b.ini}-{b.fim}")
    for i in itens:
        if i.fim_ms <= i.inicio_ms:
            problemas.append(f"{i.dia}: {i.ini}-{i.fim} termina antes de comecar")
    return problemas


def lancar(cliente: ClickUp, itens: list[Item], aprovacao: Aprovacao,
           tags_permitidas: set[str] | frozenset[str] | None = None) -> list[RelatorioDia]:
    """Escreve a proposta dia a dia. Para no primeiro resultado nao conferido."""
    problemas = sobreposicoes(itens)
    if problemas:
        raise ValueError("proposta com sobreposicao, nada foi escrito:\n  "
                         + "\n  ".join(problemas))

    relatorios: list[RelatorioDia] = []
    por_dia: dict[str, list[Item]] = {}
    for i in itens:
        por_dia.setdefault(i.dia, []).append(i)

    for dia in sorted(por_dia):
        rel = RelatorioDia(dia)
        relatorios.append(rel)
        lista = sorted(por_dia[dia], key=lambda i: i.inicio_ms)
        ini_dia = lista[0]._ms("00:00")
        existentes = cliente.entradas(ini_dia, ini_dia + 86_400_000)
        for item in lista:
            dup = next((e for e in existentes
                        if campo_objeto(e, "task").get("id") == item.task
                        and abs(int(e.get("start", 0)) - item.inicio_ms) < TOLERANCIA_DUPLICATA_MS),
                       None)
            if dup is not None:
                rel.pulados.append((item, str(dup.get("id"))))
                continue
            r = cliente.lancar(item.lancamento(), aprovacao, tags_permitidas)
            rel.escritos.append(r)
            if not cliente.dry_run and not r.conferido:
                rel.parado_em = r
                return relatorios
    return relatorios


def resumo(relatorios: list[RelatorioDia], dry_run: bool) -> str:
    linhas = []
    for rel in relatorios:
        linhas.append(f"{rel.dia}: {len(rel.escritos)} "
                      f"{'simulada(s)' if dry_run else 'escrita(s)'}, "
                      f"{len(rel.pulados)} ja existia(m)")
        for r in rel.escritos:
            linhas.append(f"   {r.entry_id or '-'} {r.detalhe} {r.divergencias or ''}".rstrip())
        if rel.parado_em is not None:
            linhas.append(f"PARADO em {rel.dia}: {rel.parado_em.detalhe} "
                          f"{rel.parado_em.divergencias}. Nada foi retentado.")
    return "\n".join(linhas)
