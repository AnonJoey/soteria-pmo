#!/usr/bin/env python3
"""generate_audit_report_pmo.py — Consolidador de Relatório de Auditoria do soteria-pmo.

Lê o banco audit_soteria_pmo.db e gera o documento docs/AUDITORIA_CONSOLIDADA_PMO.md.
"""

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path("/home/joey/Projects/soteria-pmo")
DB_PATH = REPO_ROOT / "audit_soteria_pmo.db"
OUTPUT_PATH = REPO_ROOT / "docs" / "AUDITORIA_CONSOLIDADA_PMO.md"


def main():
    if not DB_PATH.exists():
        print(f"Erro: Banco {DB_PATH} não encontrado.")
        sys.exit(1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_findings = cur.execute("SELECT count(*) FROM audit_findings").fetchone()[0]
    total_fp = cur.execute("SELECT count(*) FROM audit_findings WHERE is_false_positive = 1").fetchone()[0]
    total_genuine = cur.execute("SELECT count(*) FROM audit_findings WHERE is_false_positive = 0").fetchone()[0]
    total_modules = cur.execute("SELECT count(*) FROM audit_progress").fetchone()[0]

    passes_stats = []
    for p in [1, 2, 3, 4]:
        done = cur.execute(f"SELECT count(*) FROM audit_progress WHERE pass_{p}_status = 'done'").fetchone()[0]
        cnt = cur.execute(f"SELECT count(*) FROM audit_findings WHERE pass_id = {p}").fetchone()[0]
        passes_stats.append((p, done, cnt))

    sev_cat = cur.execute("""
        SELECT category, severity, count(*) as cnt
        FROM audit_findings
        WHERE is_false_positive = 0
        GROUP BY category, severity
        ORDER BY category, cnt DESC
    """).fetchall()

    top_modules = cur.execute("""
        SELECT rel_path, count(*) as cnt,
               SUM(CASE WHEN severity = 'ALTA' THEN 1 ELSE 0 END) as alta,
               SUM(CASE WHEN severity = 'MEDIA' THEN 1 ELSE 0 END) as media,
               SUM(CASE WHEN severity = 'BAIXA' THEN 1 ELSE 0 END) as baixa
        FROM audit_findings
        WHERE is_false_positive = 0
        GROUP BY rel_path
        ORDER BY cnt DESC
    """).fetchall()

    genuine_findings = cur.execute("""
        SELECT rel_path, pass_id, category, severity, line_hint, description, code_snippet, risk
        FROM audit_findings
        WHERE is_false_positive = 0
        ORDER BY rel_path, severity, line_hint
    """).fetchall()

    fps = cur.execute("""
        SELECT rel_path, line_hint, description, test_verification
        FROM audit_findings
        WHERE is_false_positive = 1
        ORDER BY rel_path, line_hint
        LIMIT 30
    """).fetchall()

    lines = []
    lines.append("# Relatório Consolidado de Auditoria Especializada: Agentes PMO (`soteria-pmo`)")
    lines.append("")
    lines.append("- **Data da Conclusão**: 2026-10-23")
    lines.append("- **Motor de Inferência**: Qwen2.5-Coder-14B-Instruct-Q4_K_M (Execução Local via GPU RTX 4070, 16.384 tokens de contexto)")
    lines.append("- **Escopo**: 21 módulos do pipeline de automação PMO em `src/soteria_pmo` (6.425 linhas de código)")
    lines.append("- **Passagens Executadas**: 4 passagens técnicas especializadas + Passagem 5 (Validação Cruzada contra Testes)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Resumo Executivo e Métricas Globais")
    lines.append("")
    lines.append(f"A esteira automatizada executou uma varredura completa dos **{total_modules} módulos** do soteria-pmo, gerando um total de **{total_findings:,} apontamentos** do modelo.")
    lines.append(f"A Passagem 5 realizou o cruzamento com a suíte de testes unitários (`tests/`), isolando **{total_fp:,} falsos positivos** (cenários já cobertos e garantidos, e 31 achados de severidade ALTA refutados na revisão manual) e restando **{total_genuine:,} apontamentos que ela não descartou**. Isso não os torna defeitos: veja a revisão manual abaixo.")
    lines.append("")
    lines.append("| Métrica | Valor Absoluto | Proporção |")
    lines.append("| :--- | :---: | :---: |")
    lines.append(f"| **Módulos Auditados** | {total_modules} | 100.0% |")
    lines.append(f"| **Apontamentos Totais da LLM** | {total_findings:,} | 100.0% |")
    lines.append(f"| **Falsos Positivos Filtrados (Passagem 5)** | {total_fp:,} | {(total_fp/total_findings)*100:.1f}% |" if total_findings else "| **Falsos Positivos** | 0 | 0.0% |")
    lines.append(f"| **Apontamentos não descartados (não confirmados)** | {total_genuine:,} | {(total_genuine/total_findings)*100:.1f}% |" if total_findings else "| **Apontamentos não descartados** | 0 | 0.0% |")
    lines.append("")
    triados = cur.execute("SELECT is_false_positive, count(*) FROM audit_findings "
                          "WHERE test_verification LIKE 'Triagem manual%' GROUP BY 1").fetchall()
    if triados:
        t = dict(triados)
        lines.append("### Revisão manual de 23/10/2026 (severidade ALTA)")
        lines.append("")
        lines.append(f"Os 33 apontamentos de severidade ALTA foram lidos contra o código e os mais plausíveis foram reproduzidos. "
                     f"**{t.get(1, 0)} eram falsos** e **{t.get(0, 0)} eram reais, mas só de exibição** (rebaixados para BAIXA). "
                     "Nenhum é defeito de cálculo, segurança ou resiliência.")
        lines.append("")
        lines.append("- 16 aplicam regras inventadas (tetos do Reviver e da Unimed, exclusão do IoX) a funções que não calculam teto.")
        lines.append("- Divisão por zero: as linhas citadas não têm divisão, e `Bolsao` recusa `horas_contratadas <= 0` (testado com 0 e -5).")
        lines.append("- Fim antes do início: `sobreposicoes` já recusa (testado com 15:00-14:00).")
        lines.append("- Chamada HTTP sem timeout: `daily.py` usa `timeout=300` e o `coletor.py` não faz HTTP.")
        lines.append("- Vazamento do token: o token só vai no cabeçalho e nenhum log o imprime.")
        lines.append("")
        lines.append("**Consequência:** a taxa de acerto da amostra ALTA foi 0 de 33 para defeito que altere resultado. Trate os demais "
                     "apontamentos como hipóteses do modelo, não como lista de trabalho. O motivo de cada veredito está em "
                     "`test_verification` no banco e foi gravado por `scripts/triagem_manual_pmo.py`.")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Estatísticas das 4 Passagens Especializadas")
    lines.append("")
    lines.append("| Passagem | Viés Técnico Especializado | Módulos Concluídos | Apontamentos Totais |")
    lines.append("| :--- | :--- | :---: | :---: |")
    pass_names = {
        1: "Integridade de Cálculo, Aritmética de Horas, Datas e Concorrência",
        2: "Integração ClickUp API, Rate Limiting, Sanitização e Segurança de Tokens",
        3: "Resiliência em Rede, Timeouts, Retentativas e Tratamento de Exceções",
        4: "Regras de Negócio PMO, Invariantes (Reviver/Unimed) e Contratos de Saída"
    }
    for p, done, cnt in passes_stats:
        lines.append(f"| **Passagem {p}** | {pass_names[p]} | {done} / {total_modules} | {cnt:,} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Distribuição dos Apontamentos Não Descartados")
    lines.append("")
    lines.append("### A. Por Categoria e Severidade")
    lines.append("")
    lines.append("| Categoria da Auditoria | Severidade | Quantidade |")
    lines.append("| :--- | :---: | :---: |")
    for r in sev_cat:
        lines.append(f"| `{r['category']}` | **{r['severity']}** | {r['cnt']} |")
    lines.append("")
    lines.append("### B. Módulos por Densidade de Débito Técnico")
    lines.append("")
    lines.append("| Módulo | Total Genuínos | Alta | Média | Baixa |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    for m in top_modules:
        lines.append(f"| `{m['rel_path']}` | **{m['cnt']}** | {m['alta']} | {m['media']} | {m['baixa']} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Amostra Representativa de Falsos Positivos Descartados (Passagem 5)")
    lines.append("")
    lines.append(f"Foram identificados **{total_fp:,} apontamentos** cujos cenários já estavam cobertos e protegidos pela suíte de testes unitários:")
    lines.append("")
    lines.append("| Módulo | Linha | Alerta da LLM | Cobertura Comprovada em Testes |")
    lines.append("| :--- | :---: | :--- | :--- |")
    for fp in fps:
        desc_clean = fp['description'].replace("|", "-").replace("\n", " ")[:80]
        test_clean = fp['test_verification'].replace("|", "-").replace("\n", " ")[:90]
        lines.append(f"| `{fp['rel_path']}` | {fp['line_hint']} | {desc_clean}... | {test_clean} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Catálogo dos Apontamentos Não Descartados (Por Módulo e Severidade)")
    lines.append("")
    current_mod = None
    for g in genuine_findings:
        if g['rel_path'] != current_mod:
            current_mod = g['rel_path']
            lines.append(f"### Módulo: `{current_mod}`")
            lines.append("")
        snippet = g['code_snippet'].strip() if g['code_snippet'] else "N/A"
        lines.append(f"- **[{g['severity']}]** `{g['category']}` (Linha ~{g['line_hint']})")
        lines.append(f"  - **Descrição**: {g['description']}")
        lines.append(f"  - **Risco**: {g['risk']}")
        if snippet and snippet != "N/A":
            lines.append(f"  - **Trecho**: `{snippet[:120]}`")
        lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatório consolidado gerado com sucesso em: {OUTPUT_PATH} ({len(lines)} linhas)")


if __name__ == "__main__":
    main()
