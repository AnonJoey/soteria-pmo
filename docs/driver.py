#!/usr/bin/env python3
"""Drive the local model through a timed generate/critique/refine loop.

Runs against llama.cpp on :8181 directly rather than through the MCP local task
queue, because the queue is one call per tool invocation and the point here is
to spend wall-clock time on the local model without spending the orchestrator's
context on it. Every round lands on disk, so the work survives this process.

Two things about this particular server shape the code:

  * The model is a thinking model. It fills `reasoning_content` first and
    `content` only afterwards, so a round that runs out of budget mid-thought
    returns an empty `content` and looks like a failure. `_extract` reads both
    and says which one it got.
  * Context is 16384 tokens shared by prompt and completion. The working
    document grows every round, so it is trimmed to a character budget before
    being sent, keeping the head (which holds the thesis) over the tail.

Usage:
    driver.py --phase F1 --minutes 29 --out DIR --briefing FILE [--seed FILE]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

LLAMA = "http://127.0.0.1:8181/v1/chat/completions"
HEALTH = "http://127.0.0.1:8181/health"

# Characters, not tokens: the server tokenises, this only has to be safe. At
# roughly 3.5 chars/token for Portuguese, 22000 chars is about 6300 tokens,
# which leaves room for the briefing, the instruction and a full completion
# inside the 16384-token window.
DOC_BUDGET = 22000
BRIEF_BUDGET = 12000


def log(out: Path, msg: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    with (out / "driver.log").open("a") as fh:
        fh.write(line + "\n")


def healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=5) as r:
            return json.loads(r.read()).get("status") == "ok"
    except Exception:
        return False


def wait_for_llama(out: Path, minutes: float = 5) -> bool:
    """Give the arbiter time to hand the card back after a vault search."""
    deadline = time.time() + minutes * 60
    warned = False
    while time.time() < deadline:
        if healthy():
            return True
        if not warned:
            log(out, "llama.cpp fora do ar, aguardando o arbitro devolver a placa")
            warned = True
        time.sleep(10)
    return False


def _extract(msg: dict) -> tuple[str, str]:
    """Return (text, source). Falls back to the reasoning when content is empty.

    An empty `content` with a full `reasoning_content` means the budget ran out
    while the model was still thinking. The reasoning is still worth keeping,
    so it is returned and labelled rather than discarded as a failed round.
    """
    content = (msg.get("content") or "").strip()
    if content:
        return content, "content"
    reasoning = (msg.get("reasoning_content") or "").strip()
    if reasoning:
        return reasoning, "reasoning"
    return "", "vazio"


def ask(system: str, user: str, max_tokens: int, out: Path,
        temperature: float = 0.4, thinking: bool = False) -> tuple[str, str, float]:
    body = json.dumps({
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        # Thinking off by default, on measurement rather than taste: with it on,
        # 6 of the first 17 rounds spent the whole budget in reasoning_content
        # and returned an empty content, and one of those empty rounds was
        # accepted as the working document and wiped it. Off, content comes back
        # every time and the same budget buys answer instead of preamble.
        "chat_template_kwargs": {"enable_thinking": bool(thinking)},
    }).encode()
    req = urllib.request.Request(LLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log(out, f"chamada falhou: {e}")
        return "", "erro", time.time() - started
    text, source = _extract(data["choices"][0]["message"])
    return text, source, time.time() - started


def accept_refine(new: str, current: str, out: Path) -> bool:
    """Gate a refined document before it replaces the one that works.

    Round 13 of the first F1 run answered "ABERTO: Qual e a tese a ser
    criticada?" in 38 characters, the driver took it as the new document, and
    the 4019-character thesis from round 11 was gone. Every later round then
    refined the wreckage. A refine is only an improvement if it still looks
    like the document: it keeps the section structure and does not collapse.
    """
    if not current:
        return True
    headers = new.count("\n## ")
    if headers < 3:
        log(out, f"refino recusado: so {headers} secoes")
        return False
    if len(new) < len(current) * 0.6:
        log(out, f"refino recusado: encolheu de {len(current)} para {len(new)} chars")
        return False
    return True


def trim(text: str, budget: int) -> str:
    """Keep the head, drop the middle. The thesis lives at the top."""
    if len(text) <= budget:
        return text
    head = int(budget * 0.75)
    tail = budget - head - 40
    return text[:head] + "\n\n[...trecho omitido...]\n\n" + text[-tail:]


SYSTEM = (
    "Voce e um analista senior de PMO e engenharia de software. Escreve em portugues "
    "do Brasil, direto, sem elogios e sem repetir a pergunta. NUNCA use travessao "
    "(em dash ou en dash): use virgula, dois pontos, parenteses ou ponto final. "
    "Toda afirmacao sua deve ser rastreavel ao briefing; quando algo nao estiver no "
    "briefing, escreva ABERTO: e a pergunta que precisa ser respondida, em vez de supor."
)

PROMPTS = {
    "F1": {
        "seed": (
            "Leia o briefing e escreva uma TESE da demanda, em no maximo 900 palavras, "
            "com esta estrutura exata:\n"
            "## Qual e o problema de verdade\n"
            "## O que exatamente foi contratado (os seis itens, o que cada um entrega)\n"
            "## O que ja esta pronto e o que falta\n"
            "## Riscos que podem furar o prazo de 08/09\n"
            "## ABERTO (o que o briefing nao responde e precisa ser respondido)\n"
        ),
        "critique": (
            "Critique a tese abaixo com severidade. Aponte: afirmacao que nao se "
            "sustenta no briefing, item dos seis que ficou mal caracterizado, risco "
            "que foi subestimado, e qualquer lugar onde a tese confunde o que foi "
            "medido com o que foi suposto. Liste no maximo 6 defeitos, do mais grave "
            "para o menos. Nao reescreva a tese."
        ),
        "refine": (
            "Reescreva a tese inteira corrigindo os defeitos apontados. Mantenha a "
            "mesma estrutura de secoes e o limite de 900 palavras. Nao mencione a "
            "critica nem o processo de revisao: entregue so a tese nova."
        ),
    },
    "F2": {
        "seed": (
            "Com base no briefing e na tese, escreva um PLANO DE SOLUCAO para entregar "
            "os seis itens ate 08/09, em no maximo 1200 palavras:\n"
            "## Arquitetura (o que e skill, o que e agente, e por que)\n"
            "## Ordem de construcao e por que nessa ordem\n"
            "## Para cada um dos seis itens: entrada, processamento, saida, criterio de aceite\n"
            "## O que reaproveita do piloto de horas ja pronto\n"
            "## Plano B se o prazo apertar\n"
            "## ABERTO\n"
        ),
        "critique": (
            "Ataque o plano abaixo por quatro angulos, um paragrafo cada:\n"
            "1. VIABILIDADE: o que nao da para construir no prazo, com que evidencia\n"
            "2. CUSTO: onde o desenho gasta modelo onde bastava script\n"
            "3. CONFIABILIDADE: onde uma saida errada passa sem ninguem perceber\n"
            "4. ADOCAO: o que o Abner e o Andre nao vao usar do jeito que esta\n"
            "Termine com a UNICA mudanca de maior impacto no plano."
        ),
        "refine": (
            "Reescreva o plano inteiro incorporando as criticas. Mantenha a estrutura "
            "de secoes. Entregue so o plano novo."
        ),
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=sorted(PROMPTS))
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--briefing", required=True)
    ap.add_argument("--seed", default="", help="documento de partida (ex: tese da F1)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    briefing = trim(Path(args.briefing).read_text(), BRIEF_BUDGET)
    prompts = PROMPTS[args.phase]

    deadline = datetime.now() + timedelta(minutes=args.minutes)
    log(out, f"=== {args.phase} iniciada, ate {deadline:%H:%M} ===")

    if not wait_for_llama(out):
        log(out, "ABORTADO: llama.cpp nao subiu em 5 minutos")
        return 1

    doc = Path(args.seed).read_text() if args.seed and Path(args.seed).exists() else ""
    rounds = 0

    while datetime.now() < deadline:
        rounds += 1
        remaining = (deadline - datetime.now()).total_seconds()
        # A round is seed/critique/refine. Below ~4 minutes there is not enough
        # time for a critique and its refine, and a critique with no refine
        # leaves the document worse documented than before.
        if remaining < 240 and doc:
            log(out, f"faltam {remaining:.0f}s, encerrando sem abrir nova rodada")
            break

        if not doc:
            kind, instruction, budget = "seed", prompts["seed"], 3000
            user = f"# BRIEFING\n\n{briefing}\n\n# TAREFA\n\n{instruction}"
        elif rounds % 2 == 0:
            kind, instruction, budget = "critique", prompts["critique"], 2000
            user = (f"# BRIEFING\n\n{briefing}\n\n# DOCUMENTO\n\n{trim(doc, DOC_BUDGET)}"
                    f"\n\n# TAREFA\n\n{instruction}")
        else:
            kind, instruction, budget = "refine", prompts["refine"], 3500
            crit = (out / "ultima_critica.md")
            critique = crit.read_text() if crit.exists() else ""
            user = (f"# BRIEFING\n\n{briefing}\n\n# DOCUMENTO\n\n{trim(doc, DOC_BUDGET)}"
                    f"\n\n# CRITICA\n\n{trim(critique, 6000)}\n\n# TAREFA\n\n{instruction}")

        if not healthy() and not wait_for_llama(out):
            log(out, "llama.cpp sumiu e nao voltou, encerrando")
            break

        text, source, secs = ask(SYSTEM, user, budget, out)
        if not text:
            log(out, f"rodada {rounds} ({kind}) voltou vazia em {secs:.0f}s, seguindo")
            continue

        stamp = datetime.now().strftime("%H%M%S")
        (out / f"r{rounds:02d}-{kind}-{stamp}.md").write_text(text)
        log(out, f"rodada {rounds} ({kind}) {len(text)} chars em {secs:.0f}s [{source}]")

        if kind == "critique":
            (out / "ultima_critica.md").write_text(text)
        elif accept_refine(text, doc, out):
            doc = text
            (out / "CORRENTE.md").write_text(text)

    log(out, f"=== {args.phase} encerrada, {rounds} rodadas, doc com {len(doc)} chars ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
