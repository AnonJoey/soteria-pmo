#!/usr/bin/env python3
"""audit_pipeline_pmo.py — Pipeline de Auditoria Multi-Passagem Especializada para soteria-pmo.

Executa auditoria estática profunda no codebase de Agentes PMO via GPU local (Qwen-14B).
Passagens com vieses técnicos:
- Passagem 1: Integridade de Cálculo, Aritmética de Horas, Datas e Concorrência
- Passagem 2: Integração ClickUp API, Rate Limiting, Sanitização e Segurança de Tokens
- Passagem 3: Resiliência em Rede, Timeouts, Retentativas e Tratamento de Exceções
- Passagem 4: Regras de Negócio PMO, Invariantes (Reviver/Unimed) e Contratos de Saída
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, List, Dict

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("audit_pipeline_pmo")

DEFAULT_API_URL = "http://10.42.0.73:8181/v1/chat/completions"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "audit_soteria_pmo.db"
DEFAULT_SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "soteria_pmo"

PASS_1_PROMPT = """Você é um Engenheiro Sênior Especialista em Cálculos Financeiros, Aritmética de Datas e Concorrência.
Sua missão é auditar o módulo Python de PMO com viés estrito de:
1. Precisão Aritmética e Cálculos: Arredondamento indevido de horas/minutos, overflow/underflow, divisão por zero em taxas e bolsões.
2. Manipulação de Datas: Zonas de tempo (UTC vs America/Sao_Paulo), virada de mês/ano, dias úteis, formatos ISO vs strings despadronizadas.
3. Concorrência e Arquivos: Sobrescrita de arquivos JSON/relatórios sem atomicidade, falta de lock em leitura/gravação simultânea.

Ignore estilo e formatação. Foque exclusivamente em erros de cálculo e integridade temporal.
Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "pass_id": 1,
  "category": "calculo_datas_e_concorrencia",
  "findings": [
    {
      "severity": "ALTA" | "MEDIA" | "BAIXA",
      "line_hint": <numero_aproximado_da_linha>,
      "description": "<descricao factual e concisa do problema>",
      "code_snippet": "<trecho do codigo relevante>",
      "risk": "<distorcao de horas ou corrupcao de dados>"
    }
  ]
}
"""

PASS_2_PROMPT = """Você é um Engenheiro Sênior de Segurança Ofensiva e Integrações de API.
Sua missão é auditar o módulo Python de PMO com viés estrito de:
1. Autenticação e Segredos: Vazamento do token do ClickUp em logs, tracebacks ou arquivos temporários.
2. Sanitização de Entradas: Falta de sanitização em nomes de tarefas, IDs de listas, comentários e campos personalizados.
3. Rate Limiting e Quotas: Ausência de tratamento para HTTP 429 (Too Many Requests), estouro de limite de requisições por minuto da API do ClickUp.

Ignore estilo e formatação. Aponte apenas vulnerabilidades e abusos de API.
Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "pass_id": 2,
  "category": "api_clickup_e_seguranca",
  "findings": [
    {
      "severity": "ALTA" | "MEDIA" | "BAIXA",
      "line_hint": <numero_aproximado_da_linha>,
      "description": "<descricao factual da falha de seguranca ou API>",
      "code_snippet": "<trecho do codigo relevante>",
      "risk": "<bloqueio de API, vazamento de credenciais ou injecao>"
    }
  ]
}
"""

PASS_3_PROMPT = """Você é um Engenheiro Sênior de Resiliência e Confiabilidade (SRE).
Sua missão é auditar o módulo Python de PMO com viés estrito de:
1. Timeouts de Rede: Chamadas HTTP (httpx, requests, urllib) sem timeout explícito que possam travar a rotina indefinidamente.
2. Retentativas com Backoff: Falha ao lidar com HTTP 500, 502, 503 transitórios do ClickUp ou da rede local sem recuo exponencial.
3. Degradação Graciosa: Falhas parciais em um projeto que derrubam a execução inteira do relatório diário em vez de isolar o erro.
4. Exceções Silenciosas: Blocos except Exception vazios que ocultam erros de parsing.

Ignore estilo e formatação. Aponte apenas falhas de resiliência e estabilidade.
Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "pass_id": 3,
  "category": "resiliencia_e_timeouts",
  "findings": [
    {
      "severity": "ALTA" | "MEDIA" | "BAIXA",
      "line_hint": <numero_aproximado_da_linha>,
      "description": "<descricao factual do risco de estabilidade>",
      "code_snippet": "<trecho do codigo relevante>",
      "risk": "<travamento em producao ou perda de reporte>"
    }
  ]
}
"""

PASS_4_PROMPT = """Você é um Auditor Principal de Governança de PMO e Contratos Corporativos.
Sua missão é auditar o módulo Python com viés estrito de:
1. Invariantes de Negócio: Respeito estrito aos tetos de horas acordados (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
2. Validação de Regras de Lançamento: Verificação de apontamentos fora de vigência de contrato, horas atribuídas a pessoas sem cadastro.
3. Consistência do Painel HTML/Reporte: Geração de HTML sem tags truncadas, precisão nos status de entrega (no prazo, em risco, atrasado).

Ignore estilo e formatação. Aponte apenas quebras de contratos de negócio e regras de governança.
Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "pass_id": 4,
  "category": "regras_de_negocio_e_pmo",
  "findings": [
    {
      "severity": "ALTA" | "MEDIA" | "BAIXA",
      "line_hint": <numero_aproximado_da_linha>,
      "description": "<descricao factual da quebra de regra de negocio>",
      "code_snippet": "<trecho do codigo relevante>",
      "risk": "<erro em auditoria executiva ou divergencia contratual>"
    }
  ]
}
"""

PASS_PROMPTS = {
    1: PASS_1_PROMPT,
    2: PASS_2_PROMPT,
    3: PASS_3_PROMPT,
    4: PASS_4_PROMPT,
}

CHUNK_THRESHOLD_LINES = 550
CHUNK_SIZE_LINES = 500
CHUNK_OVERLAP_LINES = 50


def get_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=60000;")
    return conn


def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_progress (
        rel_path TEXT PRIMARY KEY,
        sha256 TEXT NOT NULL,
        lines_count INTEGER NOT NULL,
        pass_1_status TEXT DEFAULT 'pending',
        pass_2_status TEXT DEFAULT 'pending',
        pass_3_status TEXT DEFAULT 'pending',
        pass_4_status TEXT DEFAULT 'pending',
        updated_at REAL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rel_path TEXT NOT NULL,
        pass_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        line_hint INTEGER,
        description TEXT NOT NULL,
        code_snippet TEXT,
        risk TEXT,
        created_at REAL,
        is_false_positive INTEGER DEFAULT 0,
        test_verification TEXT DEFAULT '',
        FOREIGN KEY(rel_path) REFERENCES audit_progress(rel_path)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_findings_path ON audit_findings(rel_path);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_findings_pass ON audit_findings(pass_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_findings_severity ON audit_findings(severity);")
    conn.commit()
    conn.close()


def collect_modules(src_dir: Path) -> List[Path]:
    return sorted(
        [
            p
            for p in src_dir.rglob("*.py")
            if "__pycache__" not in p.parts and not p.name.startswith(".#")
        ],
        key=lambda p: len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    )


def calculate_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def call_llm_audit(api_url: str, system_prompt: str, filename: str, code_content: str, line_offset: int = 1, timeout: int = 180) -> Dict[str, Any]:
    lines = code_content.splitlines()
    numbered_lines = [f"{line_offset + i:4d} | {line}" for i, line in enumerate(lines)]
    annotated_code = "\n".join(numbered_lines)

    user_prompt = f"Analise o seguinte arquivo de código de PMO:\nNome do arquivo: {filename}\nLinhas ({line_offset} a {line_offset + len(lines) - 1}):\n\n{annotated_code}\n"

    payload = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        raw_msg = data["choices"][0]["message"]["content"]
        return json.loads(raw_msg)


def split_into_chunks(lines: List[str]) -> List[tuple[int, str]]:
    if len(lines) <= CHUNK_THRESHOLD_LINES:
        return [(1, "\n".join(lines))]
    chunks = []
    start = 0
    while start < len(lines):
        end = min(start + CHUNK_SIZE_LINES, len(lines))
        chunk_str = "\n".join(lines[start:end])
        chunks.append((start + 1, chunk_str))
        if end >= len(lines):
            break
        start += (CHUNK_SIZE_LINES - CHUNK_OVERLAP_LINES)
    return chunks


def process_module_pass(db_path: Path, api_url: str, file_path: Path, src_dir: Path, pass_id: int):
    rel_path = str(file_path.relative_to(src_dir.parent.parent))
    content = file_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    sha = calculate_sha256(content)
    now = time.time()

    status_col = f"pass_{pass_id}_status"

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_progress (rel_path, sha256, lines_count, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(rel_path) DO UPDATE SET lines_count=excluded.lines_count, updated_at=excluded.updated_at;
    """, (rel_path, sha, len(lines), now))
    conn.commit()
    conn.close()

    chunks = split_into_chunks(lines)
    all_findings = []
    category = "general"
    system_prompt = PASS_PROMPTS[pass_id]

    try:
        for offset, chunk_text in chunks:
            res = call_llm_audit(api_url, system_prompt, file_path.name, chunk_text, line_offset=offset)
            category = res.get("category", category)
            for f in res.get("findings", []):
                all_findings.append(f)

        conn = get_db(db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM audit_findings WHERE rel_path = ? AND pass_id = ?", (rel_path, pass_id))

        for f in all_findings:
            if isinstance(f, str):
                f = {"description": f, "severity": "MEDIA", "line_hint": 0, "code_snippet": "", "risk": ""}
            elif not isinstance(f, dict):
                continue

            cur.execute("""
                INSERT INTO audit_findings (rel_path, pass_id, category, severity, line_hint, description, code_snippet, risk, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rel_path,
                pass_id,
                category,
                str(f.get("severity", "MEDIA")).upper(),
                int(f.get("line_hint", 0) or 0),
                str(f.get("description", "")),
                str(f.get("code_snippet", "")),
                str(f.get("risk", "")),
                time.time()
            ))

        cur.execute(f"UPDATE audit_progress SET {status_col} = 'done', updated_at = ? WHERE rel_path = ?", (time.time(), rel_path))
        conn.commit()
        conn.close()
        logger.info(f"[PASS {pass_id}] OK: {rel_path} ({len(lines)} linhas, {len(chunks)} chunks) -> {len(all_findings)} achados")
    except Exception as e:
        conn = get_db(db_path)
        cur = conn.cursor()
        cur.execute(f"UPDATE audit_progress SET {status_col} = 'error', updated_at = ? WHERE rel_path = ?", (time.time(), rel_path))
        conn.commit()
        conn.close()
        logger.error(f"[PASS {pass_id}] ERRO em {rel_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Auditoria Multi-Passagem Especializada - soteria-pmo")
    parser.add_argument("--src-dir", type=Path, default=DEFAULT_SRC_DIR)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--api-url", type=str, default=DEFAULT_API_URL)
    parser.add_argument("--pass-id", type=int, choices=[1, 2, 3, 4], help="Executar apenas uma passagem específica")
    args = parser.parse_args()

    init_db(args.db_path)
    modules = collect_modules(args.src_dir)

    logger.info(f"Iniciando auditoria especializada em {len(modules)} módulos de soteria-pmo.")
    logger.info(f"Banco de dados SQLite WAL: {args.db_path}")
    logger.info(f"Endpoint LLM local: {args.api_url}")

    passes_to_run = [args.pass_id] if args.pass_id else [1, 2, 3, 4]

    for p_id in passes_to_run:
        logger.info(f"==================== INICIANDO PASSAGEM {p_id} ====================")
        status_col = f"pass_{p_id}_status"
        
        conn = get_db(args.db_path)
        cur = conn.cursor()
        processed = set(
            r[0] for r in cur.execute(f"SELECT rel_path FROM audit_progress WHERE {status_col} = 'done'").fetchall()
        )
        conn.close()

        pending = [m for m in modules if str(m.relative_to(args.src_dir.parent.parent)) not in processed]
        logger.info(f"Passagem {p_id}: {len(processed)} já concluídos, {len(pending)} pendentes.")

        for idx, mod in enumerate(pending, start=1):
            logger.info(f"[{idx}/{len(pending)}] Processando Passagem {p_id} para {mod.name}...")
            process_module_pass(args.db_path, args.api_url, mod, args.src_dir, p_id)
            time.sleep(0.5)

    logger.info("Auditoria de soteria-pmo concluída!")


if __name__ == "__main__":
    main()
