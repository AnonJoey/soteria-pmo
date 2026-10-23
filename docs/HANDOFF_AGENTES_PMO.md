# Handoff Técnico e Operacional: Agentes PMO (`soteria-pmo`)

**Data de Emissão**: 23 de outubro de 2026  
**Repositório**: `/home/joey/Projects/soteria-pmo` (`git@github.com:AnonJoey/soteria-pmo.git`)  
**Branch Ativo**: `main`  
**Última Tag**: `v1.5.0` (commit `9af910c`)  
**Último Commit**: `4585e2c` (`feat(pmo): filtro de horas faturaveis, retentativas clickup e espelhamento relatorios`)  
**Status da Suíte**: 544 testes unitários automatizados passando (100% de sucesso, 0 chamadas externas de rede).

---

## 1. Resumo Executivo e Finalidade

O sistema de **Agentes PMO** (`soteria-pmo`) automatiza a apuração de horas, controle orçamentário de contratos ("bolsões de sustentação"), acompanhamento de cadência diária, detecção de desvios em cronogramas de projetos e alertas de gestão de pessoas (RH/aniversários/contratos) integrando a API do ClickUp.

O pacote foi originalmente extraído do `delegation-core` em 08/09/2026 e opera como uma biblioteca Python e utilitário CLI independente, com empacotamento para Claude Code / Gemini CLI em formato de *skills* e agente especializado.

---

## 2. Arquitetura do Sistema e Componentes

### 2.1 Módulos Centrais (`src/soteria_pmo/`)

| Módulo | Arquivo | Responsabilidade |
|---|---|---|
| **ClickUp Client** | `clickup.py` | Interface HTTP via `httpx` com retentativas automáticas (backoff exponencial) para timeouts, rate limit (`429`) e erros transitórios de rede (`/team`, `/task`, `/time_entries`). |
| **Bolsão Orçamentário** | `bolsao.py` | Apuração de horas consumidas vs. tetos contratados de clientes. Suporta filtro de horas faturáveis (`somente_faturaveis`), limites nominais e totais oficiais de projeto. |
| **Cronograma & Cadência** | `cronograma.py` | Avaliação de tarefas estagnadas (régua padrão: 4 dias úteis para projeto, 2 dias úteis para chamados/sustentação). |
| **Gestão de Pessoas (RH)** | `rh.py` | Validação de roster confidencial (`rh.csv`), aniversários, vencimentos de experiência e contratos. |
| **Painel da Carteira** | `painel.py` | Geração de relatório consolidado diário em HTML com controle semafórico (verde/amarelo/vermelho), separação entre faturáveis/não-faturáveis e persistência de visualização em `localStorage`. |
| **Interface CLI** | `cli.py` | Entrypoints de linha de comando (`soteria-pmo`, `soteria-pmo-instalar`). Suporta execução diária agendada via subcomando `rodar`. |

### 2.2 Skills e Agente para LLM (`src/soteria_pmo/skills/` e `agents/`)

- `pmo-bolsao`: Verificação orçamentária e consumo contratual.
- `pmo-horas`: Apuração de lançamentos diários e semanais da equipe.
- `pmo-cronograma`: Diagnóstico de bloqueios e desvios de datas em tarefas.
- `pmo-cadencias`: Checagem matinal de presença e alinhamento de equipe.
- `pmo-rh`: Monitoramento de aniversários e datas de colaboradores.
- `pmo-relatorio`: Montagem de minutas de status report para clientes.
- `agentes/pmo.md`: Agente integrador de alto nível.

---

## 3. Estado das Configurações e Dados Locais

### 3.1 Arquivo de Configuração Principal
- Localização: `~/.soteria-pmo/pmo.json` (fallback de compatibilidade: `~/.delegation_core/pmo.json`).
- Parâmetros vigentes alinhados com o time de gestão (Max e Abner):
  - **Reviver**: 2.950 h (total oficial definido pelo Max, sobrepondo somas parciais de estimativas do ClickUp).
  - **Unimed Londrina**: 390 h (total oficial definido pelo Max).
  - **IoX**: Descontinuado do cálculo de bolsão de sustentação (classificado como projeto avulso).
  - **`nao_faturam`**: `["Abner", "Luan"]` (membros internos cuja apuração não consome orçamento faturável de clientes).
  - **`bolsao_somente_faturaveis`**: `true` por padrão no config diário.

### 3.2 Roster de Pessoal (`rh.csv`)
- Localização: `~/.soteria-pmo/rh.csv`
- Permissões no filesystem: estritamente `0600` (`-rw-------`).
- Conteúdo: 17 colaboradores mapeados entre o ClickUp e o registro de pessoal.

---

## 4. Histórico Recente de Correções Críticas (23/10/2026)

Em decorrência dos relatos operacionais e capturas de tela compartilhados pelo Max Vasconcelos, foram identificadas e resolvidas três fragilidades de produção:

1. **Timeout e Desconexão na API do ClickUp (`/team`)**:
   - *Causa*: O endpoint `/team` do ClickUp apresentava latência superior a 10s sob tráfego concorrente, disparando exceção `httpx.TimeoutException` e `Server disconnected without sending a response`. A falha impedia a obtenção de membros da equipe, forçando fallback para o usuário autenticado e truncando a visualização geral do painel.
   - *Remediação*: Implementada política de retentativas automáticas (`_request_com_retry`) em `src/soteria_pmo/clickup.py` com backoff exponencial (`0.5s`, `1.0s`, `2.0s`) cobrindo `TimeoutException`, `NetworkError`, status HTTP `429` e erros de servidor `5xx`.
2. **Distorção no Orçamento do Bolsão por Horas Não Faturáveis**:
   - *Causa*: Horas internas de gestão (ex.: apontamentos internos de Abner no Grupo Angelus) estavam sendo somadas indistintamente às horas de sustentação, indicando consumo de 136 h / 160 h de teto contratual faturável.
   - *Remediação*: Parametrização de `somente_faturaveis=True` em `src/soteria_pmo/bolsao.py`. Exposição da flag via CLI (`--faturaveis`) e controles interativos no painel HTML (`src/soteria_pmo/painel_modelo.html`) permitindo alternar entre horas totais e apenas faturáveis sem perda de rastreabilidade.
3. **Caminho e Espelhamento dos Relatórios Gerados**:
   - *Causa*: O comando `rodar` gravava o relatório consolidado na raiz de execução (`AAAA-MM-DD-painel.html`), gerando desencontro com a pasta esperada `relatorios/`.
   - *Remediação*: Atualizado `src/soteria_pmo/cli.py` para espelhar automaticamente o arquivo gerado em `relatorios/AAAA-MM-DD-painel.html` e `relatorios/painel-AAAA-MM-DD.html`.

---

## 5. Auditoria Especializada em 5 Passagens (Servidor GPU)

Uma auditoria exaustiva do repositório foi executada no servidor local de GPU (`10.42.0.73:8181`, Qwen2.5-Coder-14B) em 23/10/2026:

- **Passagem 1 (Sintaxe, AST & Invariantes)**: 122 achados.
- **Passagem 2 (Fluxo de Dados & Concorrência)**: 198 achados.
- **Passagem 3 (Segurança, I/O & Permissões)**: 165 achados.
- **Passagem 4 (Métricas de Limite, SLA & Tipagem)**: 196 achados.
- **Passagem 5 (Validação Cruzada contra a Suíte de Testes)**:
  - 576 achados foram comprovados como **falsos positivos** (84,6% de cobertura direta pelos 544 testes unitários existentes).
  - **105 achados genuínos** foram confirmados e catalogados no banco SQLite `audit_soteria_pmo.db` e documentados em `docs/AUDITORIA_CONSOLIDADA_PMO.md`.
  - Principais itens para backlog técnico: sanitização de paths no salvamento de relatórios em OS legados, tolerância a retornos nulos de `custom_fields` no ClickUp e locks locais em escrita simultânea de caches.

---

## 6. Framework de Entrega e Status das Etapas (Decisões de 21/10)

Conforme estabelecido em `docs/FRAMEWORK-DE-ENTREGA.md`:

| Etapa | Descrição | Status Atual | Evidência / Requisito |
|---|---|---|---|
| **1. Requisitos** | Demanda e escopo delimitado | Concluída | Briefing e regras validadas com Max e Abner. |
| **2. Projeto Técnico** | Desenho técnico, segurança, I/O | Pendente de Aprovação | Documentado em `docs/PROJETO-TECNICO-NUVEM.md`; aguarda aprovação formal do André. |
| **3. MVP & Testes** | Versão funcional com testes | Concluída | Repositório `soteria-pmo` v1.5.0, 544 testes unitários passando. |
| **4. Homologação** | Critérios de aceite formais | Parcial | Cards 3.x e 5.x em homologação no ClickUp aguardando aceite formal do Max. |
| **5. Teste com Dev** | Teste assistido em máquina de dev (mínimo 15 dias) | Não iniciada | O dev designado é o Gildo (condicionado à entrega da máquina corporativa Sotéria). |
| **6. Produção** | Pacote final e automação na nuvem | Bloqueada | Condicionada ao aceite do Max (Etapa 4), relato do Gildo (Etapa 5) e aprovação do André (Etapa 2). |

---

## 7. Infraestrutura de Execução Local vs. Nuvem

### 7.1 Execução Atual (Máquina Local)
- Agendamento diário via `systemd` user service / timer às `08:32`:
  - Executa: `soteria-pmo rodar`
  - Realiza apuração de cadências, bolsões, alertas e gera o painel HTML em `relatorios/`.

### 7.2 Migração para Nuvem (Azure)
- Arquitetura desenhada em `docs/PROJETO-TECNICO-NUVEM.md`:
  - Execução serverless agendada via Azure Container App ou Function isolada.
  - Publicação do painel gerado em Azure Blob Storage / SharePoint da organização.
  - Dependência externa: credenciais do tenant Azure e aprovação do André.

---

## 8. Matriz de Pendências por Responsável

### Max Vasconcelos
- [ ] Formalizar aceite dos 7 cards atualmente em homologação no ClickUp (cards 2, 3.1, 3.2.1, 3.3, 3.4, 5.1 e 5.5).
- [ ] Validar a régua semafórica definitiva do bolsão (se 75%/90% ou 80%/100%).
- [ ] Fornecer as datas contratuais pendentes para o roster de RH (início/fim de contratos e ciclo de feedbacks formais).

### André
- [ ] Revisão e aprovação formal do projeto técnico de nuvem (`docs/PROJETO-TECNICO-NUVEM.md`).
- [ ] Provisionamento dos acessos ao Azure, SharePoint e canal dedicado no Microsoft Teams.

### Gildo / Jordan
- [ ] Instalação acompanhada do pacote na máquina de trabalho do Gildo para início do ciclo de testes assistidos de 15 dias (Etapa 5).
- [ ] Coleta e registro diário dos apontamentos e feedbacks do desenvolvedor.

### Jordan
- [ ] Manter acompanhamento dos apontamentos diários e verificação dos espelhos gerados em `relatorios/`.
- [ ] Programar a triagem e remediação modular dos 105 achados genuínos catalogados na auditoria técnica.
