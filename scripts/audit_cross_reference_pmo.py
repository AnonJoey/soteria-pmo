#!/usr/bin/env python3
"""audit_cross_reference_pmo.py — Passagem 5: Validação Cruzada de Testes do soteria-pmo.

Cruza todos os achados em audit_soteria_pmo.db contra os 541 testes unitários em tests/
e isola falsos positivos dos achados genuínos.
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("audit_cross_reference_pmo")

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "audit_soteria_pmo.db"
DEFAULT_TESTS_DIR = Path(__file__).resolve().parents[1] / "tests"


def load_test_suite_index(tests_dir: Path) -> Dict[str, str]:
    test_files = {}
    for p in sorted(tests_dir.rglob("test_*.py")):
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            test_files[p.name] = content
        except Exception as e:
            logger.warning(f"Erro ao ler teste {p}: {e}")
    return test_files


def verify_finding_against_tests(
    finding_id: int,
    rel_path: str,
    category: str,
    description: str,
    code_snippet: str,
    risk: str,
    test_index: Dict[str, str],
) -> Tuple[bool, str]:
    stem = Path(rel_path).stem
    mod_name = stem.replace(".py", "")

    candidate_tests = []
    for test_name, content in test_index.items():
        if mod_name in test_name or f"test_{mod_name}" in test_name:
            candidate_tests.append((test_name, content))

    search_terms = set()
    if code_snippet:
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", code_snippet)
        search_terms.update(words[:6])

    desc_words = re.findall(r"\b(reviver|unimed|iox|timeout|overflow|arredondamento|timezone|utc|clickup|rate limit|429|retry)\b", description.lower())
    search_terms.update(desc_words)

    evidences = []

    for test_name, content in candidate_tests:
        matches = [term for term in search_terms if term.lower() in content.lower()]
        if len(matches) >= 2 or any(term in desc_words for term in matches):
            evidences.append(f"{test_name} (termos: {', '.join(matches[:4])})")

    if not evidences and candidate_tests:
        for test_name, content in candidate_tests:
            if "assert " in content and len(candidate_tests) <= 2:
                for term in search_terms:
                    if term.lower() in content.lower():
                        evidences.append(f"{test_name} (termo: {term})")
                        break

    if evidences:
        return True, "Cenário já coberto em: " + "; ".join(evidences[:3])
    return False, "Sem evidência de teste cobrindo este caso de borda."


def main():
    parser = argparse.ArgumentParser(description="Passagem 5: Validação Cruzada de Testes de soteria-pmo")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--tests-dir", type=Path, default=DEFAULT_TESTS_DIR)
    args = parser.parse_args()

    if not args.db_path.exists():
        logger.error(f"Banco {args.db_path} não encontrado.")
        sys.exit(1)

    logger.info(f"Carregando índice da suíte de testes em {args.tests_dir}...")
    test_index = load_test_suite_index(args.tests_dir)
    logger.info(f"Total de arquivos de teste carregados: {len(test_index)}")

    conn = sqlite3.connect(args.db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, rel_path, category, description, code_snippet, risk FROM audit_findings")
    findings = cur.fetchall()
    logger.info(f"Analisando {len(findings)} achados para validação cruzada...")

    fp_count = 0
    genuine_count = 0

    for fid, rel_path, category, desc, snippet, risk in findings:
        is_fp, reason = verify_finding_against_tests(fid, rel_path, category, desc, snippet, risk, test_index)
        cur.execute(
            "UPDATE audit_findings SET is_false_positive = ?, test_verification = ? WHERE id = ?",
            (1 if is_fp else 0, reason, fid),
        )
        if is_fp:
            fp_count += 1
        else:
            genuine_count += 1

    conn.commit()
    conn.close()

    logger.info("==================== VALIDAÇÃO CONCLUÍDA ====================")
    logger.info(f"Total de achados analisados: {len(findings)}")
    logger.info(f"Falsos positivos (já cobertos por testes): {fp_count}")
    logger.info(f"Achados genuínos (débitos / vulnerabilidades em aberto): {genuine_count}")


if __name__ == "__main__":
    main()
