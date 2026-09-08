#!/usr/bin/env python3
"""Fold the angle documents into one prioritised list of changes.

Eighteen documents at roughly 3.2k characters each is about 16k tokens, which
is the whole context window with nothing left for an answer. So this folds in
two stages: the three passes of one angle collapse into that angle's verdict,
then the six verdicts collapse into one list. Each stage stays well inside the
window, and no stage ever sees text it cannot fit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from driver import SYSTEM, ask, trim, wait_for_llama, log

ANGLE_NAMES = ["red-team", "custo", "adocao", "sequencia", "dados", "simplificar"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--angles-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.angles_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if not wait_for_llama(out):
        log(out, "ABORTADO: llama fora do ar")
        return 1

    verdicts: list[str] = []
    for name in ANGLE_NAMES:
        parts = sorted(src.glob(f"{name}-v*.md"))
        if not parts:
            continue
        joined = "\n\n---\n\n".join(p.read_text() for p in parts)
        user = (
            f"# TRES ANALISES DO MESMO ANGULO ({name})\n\n{trim(joined, 20000)}\n\n"
            "# TAREFA\n\nAs tres analises acima olham o mesmo plano pelo mesmo angulo. "
            "Consolide num veredito unico de no maximo 400 palavras: o que as tres "
            "concordam, o que so uma viu e vale a pena, e o que e ruido. Termine com "
            "os 3 pontos de acao mais importantes deste angulo, em ordem de impacto."
        )
        text, source, secs = ask(SYSTEM, user, 1600, out, temperature=0.3)
        if not text:
            log(out, f"{name}: veredito vazio")
            continue
        (out / f"veredito-{name}.md").write_text(text)
        verdicts.append(f"## Angulo: {name}\n\n{text}")
        log(out, f"veredito {name}: {len(text)} chars em {secs:.0f}s [{source}]")

    if not verdicts:
        log(out, "nenhum veredito produzido")
        return 1

    user = (
        f"# VEREDITOS DE SEIS ANGULOS SOBRE O MESMO PLANO\n\n"
        f"{trim(chr(10).join(verdicts), 22000)}\n\n"
        "# TAREFA\n\nProduza UMA lista priorizada de mudancas no plano, no maximo 12 "
        "itens, ordenada por impacto. Para cada item: o que muda, por que (citando o "
        "angulo que levantou), e o custo de fazer. Junte itens que dizem a mesma coisa "
        "por caminhos diferentes e marque esses como CONVERGENTE, porque um ponto que "
        "aparece em varios angulos e mais forte que um que aparece em um so."
    )
    text, source, secs = ask(SYSTEM, user, 2500, out, temperature=0.3)
    if not text:
        log(out, "consolidacao final vazia")
        return 1
    (out / "MUDANCAS.md").write_text(text)
    log(out, f"MUDANCAS.md: {len(text)} chars em {secs:.0f}s [{source}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
