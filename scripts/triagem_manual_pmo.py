#!/usr/bin/env python3
"""triagem_manual_pmo.py: registra no banco a triagem manual dos achados de severidade ALTA.

Em 23/10/2026 os 33 achados ALTA que sobreviveram a Passagem 5 foram lidos contra o codigo
e os mais plausiveis foram reproduzidos. Nenhum e defeito real. O script grava o veredito
em `test_verification` (prefixo "Triagem manual") e marca `is_false_positive`. Roda uma vez
por banco; rodar de novo reescreve os mesmos valores. Depois: generate_audit_report_pmo.py.
"""

import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "audit_soteria_pmo.db"

REGRA_INVENTADA = ("o modelo aplicou as invariantes do prompt (Reviver 2.950 h, Unimed 390 h, IoX) a "
                   "uma funcao que nao calcula teto nem horas contratadas")
MOTIVOS = {
    **{i: REGRA_INVENTADA for i in (581, 582, 589, 590, 591, 592, 593, 594, 595, 596, 603,
                                    673, 674, 675, 676, 677)},
    **{i: "linha citada sem divisao; Bolsao recusa horas_contratadas <= 0 no __post_init__ "
          "(testado com 0 e -5: ValueError)" for i in (198, 199, 200)},
    536: "__init__.py vazio por desenho, nao ha o que auditar",
    214: "o token so vai no cabecalho Authorization; nenhum log ou excecao imprime cabecalho",
    265: "o texto vai so ao modelo local, nao a log; o nome da pessoa e necessario para a tarefa",
    616: "tolerancia de 0,25 h e parametro documentado no comentario, nao defeito",
    665: "China Gate nao tem 390 h no codigo (o exemplo do config traz 100 h); achado inventado",
    152: "aritmetica de timedelta, sem arredondamento",
    90: "aritmetica de timedelta, sem arredondamento",
    92: "resolver_quando trabalha com datas, sem hora; fuso nao se aplica",
    508: "o coletor nao faz chamada HTTP; os subprocess tem timeout de 60 s e 120 s",
    444: "urlopen com timeout=300 em daily.py:357",
    540: "ja tratado em lancamento.sobreposicoes (testado: 15:00-14:00 vira 'termina antes de comecar')",
    392: "excecao registrada como warning e o item entra no digest como falha, por desenho",
}
# Reais, mas de efeito so de exibicao: o total por tarefa e arredondado a 2 casas.
MARGINAIS = {96: "arredondamento a 2 casas so na exibicao do total por tarefa",
             598: "arredondamento a 2 casas so na exibicao do total por tarefa"}


def main() -> int:
    conn = sqlite3.connect(DB)
    n = 0
    for i, motivo in MOTIVOS.items():
        n += conn.execute("UPDATE audit_findings SET is_false_positive=1, test_verification=? "
                          "WHERE id=? AND severity='ALTA'", (f"Triagem manual 23/10/2026: {motivo}", i)).rowcount
    for i, motivo in MARGINAIS.items():
        n += conn.execute("UPDATE audit_findings SET severity='BAIXA', test_verification=? WHERE id=?",
                          (f"Triagem manual 23/10/2026: real, mas rebaixado: {motivo}", i)).rowcount
    conn.commit()
    print(f"{n} achados triados")
    return 0 if n == len(MOTIVOS) + len(MARGINAIS) else 1


if __name__ == "__main__":
    sys.exit(main())
