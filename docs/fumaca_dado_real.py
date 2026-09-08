#!/usr/bin/env python3
"""Run the modules against the real card, not fixtures.

Every test in tests/pmo builds its own payloads, which proves the logic and
proves nothing about the shapes ClickUp actually sends. This feeds the twelve
tasks of the Agentes PMO list, read from the API at 00:09 on 02/09/2026 with
their real fields, straight into the modules that will consume them.

Read-only and offline: the payloads are frozen here on purpose, so this stays
runnable and reviewable without a token and without touching the workspace.
"""

from datetime import date

from soteria_pmo import cronograma as C
from soteria_pmo import datas as D

HOJE = date(2026, 9, 2)

# Lidas da API em 02/09/2026 00:09. Datas em ms como o ClickUp devolve:
# 1788246000000 = 01/09 04:00, 1788418800000 = 03/09 04:00,
# 1788850800000 = 08/09 04:00. Todas as doze em "ideia", prioridade low,
# description vazia e time_estimate null, como estao de verdade.
JORDAN = [{"id": 101190987, "username": "Jordan Bernardes"}]
ABNER = [{"id": 89265271, "username": "Abner Ben de Morais"}]

TAREFAS_REAIS = [
    {"id": "86e30yrtp", "name": "Atividades de Agentes PMO", "status": {"status": "ideia"},
     "assignees": JORDAN, "due_date": "1788850800000", "date_updated": "1788186090183",
     "description": "", "time_estimate": None},
    {"id": "86e30ykc3", "name": "1. Levantamento de Workflow", "status": {"status": "ideia"},
     "assignees": ABNER, "due_date": "1788246000000", "date_updated": "1787944574717",
     "description": "", "time_estimate": None},
    {"id": "86e30ykjx", "name": "2. Validacao e definicao dos agentes",
     "status": {"status": "ideia"}, "assignees": JORDAN, "due_date": "1788246000000",
     "date_updated": "1787944574717", "description": "", "time_estimate": None},
    {"id": "86e30ym08", "name": "3. Desenvolvimento dos Agentes", "status": {"status": "ideia"},
     "assignees": JORDAN, "due_date": "1788418800000", "date_updated": "1788186090183",
     "description": "", "time_estimate": None},
    {"id": "86e3127bd", "name": "3.1 Report ao cliente (Skill)", "status": {"status": "ideia"},
     "assignees": JORDAN, "due_date": "1788418800000", "date_updated": "1788185241117",
     "description": "", "time_estimate": None},
    {"id": "86e3127cr", "name": "3.2 Acompanhamento de cronograma (Agente)",
     "status": {"status": "ideia"}, "assignees": JORDAN, "due_date": "1788418800000",
     "date_updated": "1788185239403", "description": "", "time_estimate": None},
    {"id": "86e3127em", "name": "3.2.1 Guardiao das datas do time (Skill Interna)",
     "status": {"status": "ideia"}, "assignees": JORDAN, "due_date": "1788418800000",
     "date_updated": "1788185239403", "description": "", "time_estimate": None},
    {"id": "86e3127fr", "name": "3.3 Auditor de apontamentos (workflow)",
     "status": {"status": "ideia"}, "assignees": JORDAN, "due_date": "1788418800000",
     "date_updated": "1788185231639", "description": "", "time_estimate": None},
    {"id": "86e31gx8v", "name": "3.4 Lancamento de horas", "status": {"status": "ideia"},
     "assignees": JORDAN, "due_date": "1788418800000", "date_updated": "1788187364221",
     "description": "", "time_estimate": None},
    {"id": "86e31dz55", "name": "3.5 Vigia de bolsao em tempo real",
     "status": {"status": "ideia"}, "assignees": JORDAN, "due_date": "1788418800000",
     "date_updated": "1788185221379", "description": "", "time_estimate": None},
    {"id": "86e31dzaa", "name": "3.6 RH e datas", "status": {"status": "ideia"},
     "assignees": JORDAN, "due_date": "1788418800000", "date_updated": "1788185236989",
     "description": "", "time_estimate": None},
    {"id": "86e30yn31", "name": "4. Testes e Ajustes Finais", "status": {"status": "ideia"},
     "assignees": JORDAN, "due_date": "1788850800000", "date_updated": "1788186090183",
     "description": "", "time_estimate": None},
]


def main() -> int:
    print("=" * 72)
    print("GUARDIAO DAS DATAS sobre as 12 tarefas reais")
    print("=" * 72)
    prazos = D.ler(TAREFAS_REAIS)
    print(D.digest(prazos, HOJE) or "(nada a dizer)")

    print()
    print("=" * 72)
    print("ACOMPANHAMENTO DE CRONOGRAMA sobre as mesmas 12")
    print("=" * 72)
    divergencias = C.avaliar(TAREFAS_REAIS, {}, HOJE)
    print(C.log_de_divergencias(divergencias, HOJE) or "(nada a dizer)")

    print()
    print("=" * 72)
    print("CONFERENCIA: o que os modulos concluiram bate com a leitura manual?")
    print("=" * 72)
    vencidas = [p for p in prazos if p.situacao(HOJE) == "vencido"]
    sem_desc = [p for p in prazos if not p.tem_descricao]
    sem_est = [p for p in prazos if not p.tem_estimativa]
    checagens = [
        ("12 tarefas lidas", len(prazos) == 12),
        ("2 vencidas (passos 1 e 2, ambas de 01/09)", len(vencidas) == 2),
        ("as 12 sem descricao", len(sem_desc) == 12),
        ("as 12 sem estimativa", len(sem_est) == 12),
        ("nenhuma tarefa sem data", all(p.vence_em for p in prazos)),
        ("o 3.5 ainda se chama 'em tempo real'",
         any("tempo real" in p.nome for p in prazos)),
        ("existe o 3.2.1, logo sao 7 itens de dev e nao 6",
         any("3.2.1" in p.nome for p in prazos)),
    ]
    falhou = False
    for descricao, ok in checagens:
        print(f"  [{'ok' if ok else 'FALHOU'}] {descricao}")
        falhou |= not ok
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
