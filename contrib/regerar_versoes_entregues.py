"""Acrescenta a versao atual de cada skill e agente a `versoes_entregues.json`.

Rode depois de editar uma skill ou o agente, ANTES de gerar a wheel:

    python3 contrib/regerar_versoes_entregues.py

Mantem os hashes antigos: `soteria-pmo-instalar --atualizar` precisa reconhecer
as versoes que ja estao instaladas nas maquinas para poder troca-las. O teste
`test_versoes_entregues_cobrem_o_que_o_repo_entrega_hoje` falha se isto for
esquecido.
"""
import hashlib
import json
from pathlib import Path

raiz = Path(__file__).resolve().parents[1]
alvo = raiz / "src" / "soteria_pmo" / "versoes_entregues.json"
dados = {k: set(v) for k, v in json.loads(alvo.read_text(encoding="utf-8")).items()} if alvo.exists() else {}
for f in sorted(list(raiz.glob("skills/*/SKILL.md")) + list(raiz.glob("agents/*.md"))):
    dados.setdefault(str(f.relative_to(raiz)), set()).add(hashlib.sha256(f.read_bytes()).hexdigest())
alvo.write_text(json.dumps({k: sorted(v) for k, v in sorted(dados.items())}, indent=1) + "\n", encoding="utf-8")
for k, v in sorted(dados.items()):
    print(len(v), k)
