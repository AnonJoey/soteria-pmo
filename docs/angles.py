#!/usr/bin/env python3
"""Attack one frozen plan from several fixed angles, one document per angle.

The refine loop in driver.py converges: measured over 23 refinements, the
similarity between one round and the next rose from 0.64 to 0.86 and then sat
there. Past that point another round of "critique and rewrite" mostly reshuffles
the same paragraphs, so the way to spend the remaining time is to change the
question rather than repeat it.

Each angle runs independently against the frozen plan and writes its own file.
Nothing is merged here on purpose: merging is a judgement call and belongs to
the orchestrator, which can weigh an angle against the vault and against real
ClickUp data that the local model cannot see.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from driver import SYSTEM, ask, healthy, log, trim, wait_for_llama

ANGLES: dict[str, str] = {
    "red-team": (
        "Voce e o cetico da sala. O plano abaixo vai ser entregue em producao em "
        "08/09. Escreva os 5 modos de falha mais provaveis, do mais provavel para o "
        "menos. Para cada um: o que quebra, qual sinal apareceria primeiro, e qual a "
        "mudanca minima no plano que evitaria. Nao repita riscos genericos de prazo: "
        "quero falha tecnica ou de adocao especifica deste desenho."
    ),
    "custo": (
        "Analise o plano abaixo so pelo angulo de custo por execucao ao longo de um "
        "ano, sobre 8 a 9 projetos. Onde o desenho gasta chamada de modelo onde "
        "bastava script deterministico? Liste cada ponto, o que ele custa hoje no "
        "desenho, e o que passaria a custar se virasse script. Termine com a ordem "
        "de grandeza da economia anual."
    ),
    "adocao": (
        "O Abner e o Andre precisam usar isso todo dia sem o Jordan por perto. "
        "Aponte, no plano abaixo, tudo que eles NAO vao usar do jeito que esta: "
        "onde a saida exige interpretacao que so o autor tem, onde o fluxo pede um "
        "passo manual que ninguem vai lembrar, e onde um erro do agente passaria sem "
        "ninguem perceber. Proponha a correcao de cada um."
    ),
    "sequencia": (
        "O prazo e 08/09 e o desenvolvimento comecou 01/09. Reordene os seis itens "
        "do plano abaixo para maximizar o que estara realmente pronto em 08/09, "
        "assumindo que so da tempo de terminar alguns. Justifique cada posicao pelo "
        "custo de construcao contra o valor entregue, e diga explicitamente quais "
        "itens voce sacrificaria e o que se perde com isso."
    ),
    "dados": (
        "Liste toda fonte de dado que o plano abaixo assume existir. Para cada uma: "
        "de onde vem, quem e dono dela, o que acontece se ela faltar num dia, e se o "
        "plano tem plano B para a falta. Marque as que dependem de uma pessoa lembrar "
        "de fazer algo, que sao as mais frageis."
    ),
    "simplificar": (
        "Corte o plano abaixo pela metade sem perder o que importa. Qual e a versao "
        "minima que ainda resolve o problema real do Max (8 a 9 projetos, 1800 horas, "
        "tudo manual)? Diga o que sai, o que fica, e por que o que sai nao faz falta "
        "na primeira versao."
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--briefing", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--passes", type=int, default=2,
                    help="quantas voltas dar na lista de angulos")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = Path(args.plan).read_text()
    briefing = trim(Path(args.briefing).read_text(), 9000)
    deadline = datetime.now() + timedelta(minutes=args.minutes)

    log(out, f"=== angulos iniciados, ate {deadline:%H:%M} ===")
    if not wait_for_llama(out):
        log(out, "ABORTADO: llama.cpp fora do ar")
        return 1

    done = 0
    for volta in range(1, args.passes + 1):
        for name, instruction in ANGLES.items():
            if datetime.now() >= deadline:
                log(out, "prazo alcancado, encerrando")
                log(out, f"=== angulos encerrados, {done} documentos ===")
                return 0
            if not healthy() and not wait_for_llama(out):
                log(out, "llama sumiu e nao voltou")
                break

            # Later passes see the earlier answers on the same angle, so a
            # second visit deepens rather than restates.
            anterior = ""
            previo = out / f"{name}-v{volta - 1}.md"
            if volta > 1 and previo.exists():
                anterior = (f"\n\n# SUA RESPOSTA ANTERIOR NESTE ANGULO\n\n"
                            f"{trim(previo.read_text(), 5000)}\n\n"
                            "Va mais fundo: nao repita o que ja disse, "
                            "acrescente o que ficou de fora.")

            user = (f"# BRIEFING\n\n{briefing}\n\n# PLANO\n\n{trim(plan, 12000)}"
                    f"{anterior}\n\n# TAREFA\n\n{instruction}")
            text, source, secs = ask(SYSTEM, user, 2500, out, temperature=0.5)
            if not text:
                log(out, f"{name} v{volta} voltou vazio em {secs:.0f}s")
                continue
            (out / f"{name}-v{volta}.md").write_text(text)
            done += 1
            log(out, f"{name} v{volta}: {len(text)} chars em {secs:.0f}s [{source}]")

    log(out, f"=== angulos encerrados, {done} documentos ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
