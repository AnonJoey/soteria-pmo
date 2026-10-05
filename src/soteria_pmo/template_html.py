"""Item 1 (Fase 2 - RF-02): Template HTML desacoplado com semaforo visual.

Renderiza o relatorio consolidado dos clientes em HTML executivo, padronizado
e responsivo, com sinalizacao semaforica nas 4 cores alinhadas com design:
  - Verde: Normal / Saudavel (< 80% bolsao, tarefas em dia)
  - Amarelo: Atencao (80% a 100% bolsao, chamados sem apontamento ha 2d)
  - Vermelho: Critico (projeto parado ha 4+ dias uteis, horas sem descricao)
  - Roxo: Estourado (> 100% do teto contratado)

A estrutura CSS/HTML e desacoplada da extracao de dados (declarada em tokens no
:root), permitindo que a equipe de design e o Saad ajustem cores e estilos
sem alterar a logica de negocio em Python.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .reporte import Linha, Reporte, ReporteCliente


CSS_PADRAO = """
:root {
  /* ==========================================================================
     SOTERIA DESIGN TOKENS - PALETA CORPORATIVA E SEMAFORO
     Ajuste estes valores para alinhar com a identidade visual oficial.
     ========================================================================== */
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-surface-subtle: #f1f5f9;
  --color-border: #e2e8f0;
  --color-border-strong: #cbd5e1;
  --color-text-main: #0f172a;
  --color-text-muted: #64748b;
  --color-brand: #0f172a;
  --color-brand-accent: #2563eb;

  /* Semaforo Visual (Escala aprovada em 05/10/2026 com Design/Saad) */
  --color-verde: #10b981;
  --color-verde-bg: #ecfdf5;
  --color-verde-border: #a7f3d0;
  --color-verde-text: #065f46;

  --color-amarelo: #f59e0b;
  --color-amarelo-bg: #fffbeb;
  --color-amarelo-border: #fde68a;
  --color-amarelo-text: #92400e;

  --color-critico: #ef4444;
  --color-critico-bg: #fef2f2;
  --color-critico-border: #fecaca;
  --color-critico-text: #991b1b;

  --color-estourado: #8b5cf6;
  --color-estourado-bg: #f5f3ff;
  --color-estourado-border: #ddd6fe;
  --color-estourado-text: #5b21b6;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-family);
  background-color: var(--color-bg);
  color: var(--color-text-main);
  line-height: 1.5;
  padding: 24px 16px;
}

.container {
  max-width: 1100px;
  margin: 0 auto;
}

/* Header Executivo */
.header-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 24px 32px;
  margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 16px;
}

.brand-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-brand);
  letter-spacing: -0.02em;
}

.brand-subtitle {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-top: 4px;
}

.period-pill {
  background: var(--color-surface-subtle);
  border: 1px solid var(--color-border);
  border-radius: 9999px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
}

/* KPIs Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.kpi-card {
  background: var(--color-surface-subtle);
  border-radius: 8px;
  padding: 14px 18px;
  border-left: 4px solid var(--color-brand-accent);
}

.kpi-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  font-weight: 600;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-main);
  margin-top: 4px;
}

.kpi-subtext {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

/* Pre-Analise (Leitura Executiva) */
.pre-analise-card {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-left: 6px solid #0284c7;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.pre-analise-title {
  font-size: 15px;
  font-weight: 700;
  color: #0369a1;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pre-analise-body {
  font-size: 14px;
  color: #0c4a6e;
  white-space: pre-line;
}

.pre-analise-footer {
  font-size: 12px;
  color: #0284c7;
  margin-top: 12px;
  font-style: italic;
}

/* Card de Cliente */
.client-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  margin-bottom: 24px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.client-header {
  padding: 18px 24px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.client-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-main);
}

.client-badges {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Badges do Semaforo */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 9999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.badge-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.badge-verde {
  background: var(--color-verde-bg);
  color: var(--color-verde-text);
  border: 1px solid var(--color-verde-border);
}
.badge-verde .badge-dot { background: var(--color-verde); }

.badge-amarelo {
  background: var(--color-amarelo-bg);
  color: var(--color-amarelo-text);
  border: 1px solid var(--color-amarelo-border);
}
.badge-amarelo .badge-dot { background: var(--color-amarelo); }

.badge-critico {
  background: var(--color-critico-bg);
  color: var(--color-critico-text);
  border: 1px solid var(--color-critico-border);
}
.badge-critico .badge-dot { background: var(--color-critico); }

.badge-estourado {
  background: var(--color-estourado-bg);
  color: var(--color-estourado-text);
  border: 1px solid var(--color-estourado-border);
}
.badge-estourado .badge-dot { background: var(--color-estourado); }

/* Bolsao Progress Bar */
.bolsao-block {
  padding: 16px 24px;
  background: var(--color-surface-subtle);
  border-bottom: 1px solid var(--color-border);
}

.bolsao-info {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--color-text-main);
  margin-bottom: 6px;
  font-weight: 500;
}

.progress-track {
  height: 10px;
  background: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.3s ease;
}

.progress-verde { background: var(--color-verde); }
.progress-amarelo { background: var(--color-amarelo); }
.progress-critico { background: var(--color-critico); }
.progress-estourado { background: var(--color-estourado); }

/* Secoes Internas: Implantacao vs Sustentacao */
.client-content {
  padding: 20px 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px dashed var(--color-border);
}

.project-block {
  margin-bottom: 20px;
  background: #fafafa;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px 18px;
}

.project-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.project-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-main);
}

.project-stats {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 10px;
}

/* Tabelas de Tarefas */
.task-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.task-table th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  color: var(--color-text-muted);
  padding: 6px 8px;
  border-bottom: 1px solid var(--color-border);
}

.task-table td {
  padding: 8px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}

.task-table tr:last-child td {
  border-bottom: none;
}

.task-status-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.tag-concluida { background: #dcfce7; color: #15803d; }
.tag-andamento { background: #e0f2fe; color: #0369a1; }
.tag-parada { background: #f1f5f9; color: #64748b; }

/* Clientes Sem Movimento */
.sem-movimento-card {
  background: var(--color-surface);
  border: 1px dashed var(--color-border-strong);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.sem-movimento-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.sem-movimento-list {
  list-style: disc;
  margin-left: 20px;
  font-size: 13px;
  color: var(--color-text-muted);
}

/* Footer */
.footer-card {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
  padding: 20px;
}

@media (max-width: 768px) {
  .header-top, .client-header, .project-block-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
"""


def _classe_semaforo(nivel: str) -> str:
    """Normaliza o nivel de bolsao ou projeto para uma classe CSS semaforica."""
    n = (nivel or "").lower().strip()
    if n in ("estourado", "estouro"):
        return "estourado"  # Roxo
    if n in ("critico", "cobranca", "escalar"):
        return "critico"    # Vermelho
    if n in ("atencao", "lembrete"):
        return "amarelo"    # Amarelo
    return "verde"          # Verde / Normal


def _rotulo_semaforo(nivel: str) -> str:
    n = (nivel or "").lower().strip()
    if n == "estourado":
        return "Estourado"
    if n in ("critico", "cobranca", "escalar"):
        return "Crítico"
    if n in ("atencao", "lembrete"):
        return "Atenção"
    return "Normal"


def renderizar_cliente_html(rc: ReporteCliente, bolsao_info: Any | None = None) -> str:
    """Renderiza um card executivo completo de um cliente."""
    # Nivel geral do cliente: se tem bolsao, o bolsao dita; senao, padrao verde
    nivel_cliente = "verde"
    bolsao_html = ""

    if bolsao_info is not None:
        # Pode ser objeto Situacao ou dict
        gastas = getattr(bolsao_info, "horas_gastas", None)
        contratadas = getattr(bolsao_info, "horas_contratadas", None)
        if gastas is None and isinstance(bolsao_info, dict):
            gastas = bolsao_info.get("horas_gastas", 0.0)
            contratadas = bolsao_info.get("horas_contratadas", 0.0)
            nivel_bolsao = bolsao_info.get("nivel", "ok")
        else:
            nivel_bolsao = getattr(bolsao_info, "nivel", "ok")

        if contratadas and contratadas > 0:
            pct = (gastas or 0.0) / contratadas
            pct_exibicao = min(int(pct * 100), 100)
            classe = _classe_semaforo(nivel_bolsao)
            nivel_cliente = classe
            saldo = contratadas - (gastas or 0.0)
            saldo_str = f"Saldo: {saldo:.1f}h" if saldo >= 0 else f"Estourado em +{-saldo:.1f}h"

            bolsao_html = f"""
            <div class="bolsao-block">
              <div class="bolsao-info">
                <span><strong>Bolsão de Sustentação:</strong> {gastas:.1f}h consumidas de {contratadas:.0f}h ({pct:.0%})</span>
                <span>{escape(saldo_str)}</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill progress-{classe}" style="width: {pct_exibicao}%;"></div>
              </div>
            </div>
            """

    classe_badge = _classe_semaforo(nivel_cliente)
    rotulo_badge = _rotulo_semaforo(nivel_cliente)

    implantacao_html = ""
    if rc.implantacao:
        blocos = []
        for rep in rc.implantacao:
            linhas_tr = []
            for l in rep.concluidas[:10]:
                v = f", vence {l.vence_em:%d/%m}" if l.vence_em else ""
                linhas_tr.append(f"""
                <tr>
                  <td><span class="task-status-tag tag-concluida">Concluída</span></td>
                  <td><strong>{escape(l.nome)}</strong>{escape(v)}</td>
                  <td>{l.horas:.1f}h</td>
                  <td>{escape(l.responsavel)}</td>
                </tr>
                """)
            for l in rep.em_andamento[:10]:
                v = f", vence {l.vence_em:%d/%m}" if l.vence_em else ""
                linhas_tr.append(f"""
                <tr>
                  <td><span class="task-status-tag tag-andamento">Em Andamento</span></td>
                  <td>{escape(l.nome)}{escape(v)}</td>
                  <td>{l.horas:.1f}h</td>
                  <td>{escape(l.responsavel)}</td>
                </tr>
                """)
            restantes = max(len(rep.concluidas) + len(rep.em_andamento) - 20, 0)
            restante_msg = f"<p style='font-size:12px;color:#64748b;margin-top:6px;'>... e mais {restantes} tarefa(s) não listadas</p>" if restantes else ""

            blocos.append(f"""
            <div class="project-block">
              <div class="project-block-header">
                <span class="project-title">{escape(rep.projeto)}</span>
                <span style="font-weight:600;">{rep.horas_totais:.1f}h</span>
              </div>
              <div class="project-stats">
                {len(rep.concluidas)} concluídas &bull; {len(rep.em_andamento)} em andamento &bull; {len(rep.paradas)} sem horas na semana
              </div>
              <table class="task-table">
                <thead>
                  <tr>
                    <th style="width:110px;">Status</th>
                    <th>Tarefa</th>
                    <th style="width:60px;">Horas</th>
                    <th style="width:130px;">Responsável</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(linhas_tr) if linhas_tr else '<tr><td colspan="4" style="color:#94a3b8;">Nenhuma tarefa movimentada</td></tr>'}
                </tbody>
              </table>
              {restante_msg}
            </div>
            """)
        implantacao_html = f"""
        <div style="margin-bottom: 20px;">
          <h4 class="section-title">Projetos de Implantação</h4>
          {''.join(blocos)}
        </div>
        """

    sustentacao_html = ""
    if rc.sustentacao:
        blocos = []
        for rep in rc.sustentacao:
            linhas_tr = []
            for l in rep.concluidas[:10]:
                linhas_tr.append(f"""
                <tr>
                  <td><span class="task-status-tag tag-concluida">Resolvido</span></td>
                  <td><strong>{escape(l.nome)}</strong></td>
                  <td>{l.horas:.1f}h</td>
                  <td>{escape(l.responsavel)}</td>
                </tr>
                """)
            for l in rep.em_andamento[:10]:
                linhas_tr.append(f"""
                <tr>
                  <td><span class="task-status-tag tag-andamento">Aberto</span></td>
                  <td>{escape(l.nome)}</td>
                  <td>{l.horas:.1f}h</td>
                  <td>{escape(l.responsavel)}</td>
                </tr>
                """)
            restantes = max(len(rep.concluidas) + len(rep.em_andamento) - 20, 0)
            restante_msg = f"<p style='font-size:12px;color:#64748b;margin-top:6px;'>... e mais {restantes} chamado(s) não listados</p>" if restantes else ""

            blocos.append(f"""
            <div class="project-block">
              <div class="project-block-header">
                <span class="project-title">{escape(rep.projeto)}</span>
                <span style="font-weight:600;">{rep.horas_totais:.1f}h</span>
              </div>
              <div class="project-stats">
                {len(rep.concluidas)} resolvidos &bull; {len(rep.em_andamento)} em atendimento &bull; {len(rep.paradas)} sem horas na semana
              </div>
              <table class="task-table">
                <thead>
                  <tr>
                    <th style="width:110px;">Status</th>
                    <th>Chamado</th>
                    <th style="width:60px;">Horas</th>
                    <th style="width:130px;">Responsável</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(linhas_tr) if linhas_tr else '<tr><td colspan="4" style="color:#94a3b8;">Nenhum chamado movimentado</td></tr>'}
                </tbody>
              </table>
              {restante_msg}
            </div>
            """)
        sustentacao_html = f"""
        <div>
          <h4 class="section-title">Chamados e Sustentação</h4>
          {''.join(blocos)}
        </div>
        """

    return f"""
    <div class="client-card">
      <div class="client-header">
        <div>
          <span class="client-name">{escape(rc.cliente)}</span>
          <span style="font-size:13px;color:#64748b;margin-left:12px;">
            {rc.total_horas:.1f}h totais ({rc.total_faturavel:.1f}h faturáveis)
          </span>
        </div>
        <div class="client-badges">
          <span class="badge badge-{classe_badge}">
            <span class="badge-dot"></span>
            {escape(rotulo_badge)}
          </span>
        </div>
      </div>
      {bolsao_html}
      <div class="client-content">
        {implantacao_html}
        {sustentacao_html}
      </div>
    </div>
    """


def renderizar_relatorio_html(
    reportes: list[ReporteCliente],
    sem_movimento: list[str],
    inicio: date,
    fim: date,
    pre_analise: str = "",
    bolsoes: dict[str, Any] | None = None,
) -> str:
    """Monta o documento HTML completo com todos os clientes, metricas e semaforo."""
    bolsoes = bolsoes or {}
    total_horas = sum(r.total_horas for r in reportes)
    total_faturavel = sum(r.total_faturavel for r in reportes)
    total_nao_faturavel = sum(r.total_nao_faturavel for r in reportes)

    # Identificar cliente no bolsoes por proximidade de chave
    def _achar_bolsao(nome_cliente: str):
        c_norm = nome_cliente.lower().strip()
        for k, v in bolsoes.items():
            k_norm = k.lower().strip()
            if k_norm in c_norm or c_norm in k_norm:
                return v
        return None

    cards_html = [renderizar_cliente_html(rc, _achar_bolsao(rc.cliente)) for rc in reportes]

    pre_analise_html = ""
    if pre_analise.strip():
        pre_analise_html = f"""
        <div class="pre-analise-card">
          <div class="pre-analise-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
            Leitura do Período
          </div>
          <div class="pre-analise-body">{escape(pre_analise.strip())}</div>
          <div class="pre-analise-footer">
            Esta leitura foi escrita a partir dos números do período como proposta de interpretação para validação do Max (Nível 2).
          </div>
        </div>
        """

    sem_movimento_html = ""
    if sem_movimento:
        itens_li = "".join(f"<li>{escape(n)}</li>" for n in sem_movimento)
        sem_movimento_html = f"""
        <div class="sem-movimento-card">
          <div class="sem-movimento-title">Clientes sem movimentação no período</div>
          <p style="font-size:13px;color:#64748b;margin-bottom:8px;">
            Nenhuma tarefa tocada e nenhum apontamento registrado entre {inicio:%d/%m/%Y} e {fim:%d/%m/%Y}.
            Listados explicitamente para conferência e auditoria:
          </p>
          <ul class="sem-movimento-list">
            {itens_li}
          </ul>
        </div>
        """

    gerado_em = datetime.now().strftime("%d/%m/%Y às %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sotéria PMO - Relatório Executivo ({inicio:%d/%m} a {fim:%d/%m})</title>
  <style>
{CSS_PADRAO}
  </style>
</head>
<body>
  <div class="container">
    <div class="header-card">
      <div class="header-top">
        <div>
          <div class="brand-title">Sotéria PMO</div>
          <div class="brand-subtitle">Relatório Executivo Consolidado de Clientes</div>
        </div>
        <div class="period-pill">
          Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}
        </div>
      </div>
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Horas Totais</div>
          <div class="kpi-value">{total_horas:.1f}h</div>
          <div class="kpi-subtext">apontadas na janela</div>
        </div>
        <div class="kpi-card" style="border-left-color: var(--color-verde);">
          <div class="kpi-label">Horas Faturáveis</div>
          <div class="kpi-value">{total_faturavel:.1f}h</div>
          <div class="kpi-subtext">{(total_faturavel / total_horas * 100) if total_horas else 0:.0f}% do total</div>
        </div>
        <div class="kpi-card" style="border-left-color: var(--color-amarelo);">
          <div class="kpi-label">Não Faturáveis</div>
          <div class="kpi-value">{total_nao_faturavel:.1f}h</div>
          <div class="kpi-subtext">{(total_nao_faturavel / total_horas * 100) if total_horas else 0:.0f}% do total</div>
        </div>
        <div class="kpi-card" style="border-left-color: var(--color-brand);">
          <div class="kpi-label">Clientes Ativos</div>
          <div class="kpi-value">{len(reportes)}</div>
          <div class="kpi-subtext">{len(sem_movimento)} sem movimento</div>
        </div>
      </div>
    </div>

    {pre_analise_html}

    {''.join(cards_html)}

    {sem_movimento_html}

    <div class="footer-card">
      Max valida e envia (Nível 2) &bull; Documento executivo confidencial gerado pelo Sotéria PMO em {gerado_em}.
    </div>
  </div>
</body>
</html>
"""
