#!/usr/bin/env python3
"""Have the local model review each module, one at a time.

Not a second opinion for its own sake. The modules were written and tested by
the same head, so the failure mode they share is a blind spot, and a reader with
no memory of the intent is the cheapest way to find one. A 12B model will also
produce noise, so this asks for concrete claims tied to line-level behaviour and
the orchestrator throws away whatever does not survive a look at the code.

One module per call: at roughly 3.5 chars per token, the larger modules alone
are 3k tokens, and sending two would push the answer out of the window.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from driver import ask, log, trim, wait_for_llama

SISTEMA = (
    "Voce e um revisor de codigo Python severo e concreto. Escreve em portugues do "
    "Brasil. NUNCA use travessao. Nao elogie, nao resuma o que o codigo faz, nao "
    "sugira renomear coisas. So aponte defeito que voce consegue ancorar num trecho "
    "especifico: bug, caso de borda nao tratado, comportamento que contradiz o que o "
    "docstring promete, ou teste que passaria mesmo com o codigo errado. Se nao achar "
    "nada de verdade, escreva exatamente NADA A APONTAR."
)

TAREFA = (
    "Revise o modulo abaixo. Para cada defeito, escreva:\n"
    "DEFEITO: uma frase\n"
    "ONDE: nome da funcao ou trecho\n"
    "COMO QUEBRA: a entrada concreta que produz o erro\n"
    "Maximo 5 defeitos, do mais grave para o menos. Se o modulo estiver correto, "
    "responda so NADA A APONTAR."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pacote", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not wait_for_llama(out):
        log(out, "ABORTADO: llama fora do ar")
        return 1

    modulos = sorted(p for p in Path(args.pacote).glob("*.py")
                     if p.name != "__init__.py")
    achados = 0
    for m in modulos:
        codigo = trim(m.read_text(), 20000)
        user = f"# MODULO {m.name}\n\n```python\n{codigo}\n```\n\n# TAREFA\n\n{TAREFA}"
        texto, fonte, secs = ask(SISTEMA, user, 1800, out, temperature=0.2)
        if not texto:
            log(out, f"{m.name}: revisao vazia em {secs:.0f}s")
            continue
        (out / f"revisao-{m.stem}.md").write_text(texto)
        limpo = texto.strip().upper()
        nada = limpo.startswith("NADA A APONTAR") or "NADA A APONTAR" in limpo[:200]
        if not nada:
            achados += 1
        log(out, f"{m.name}: {len(texto)} chars em {secs:.0f}s "
                 f"[{'apontou' if not nada else 'limpo'}]")
    log(out, f"=== revisao encerrada, {achados} modulos com apontamento ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
