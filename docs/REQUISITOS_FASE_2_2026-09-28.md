# Especificação de Requisitos: Agentes PMO / CX (Fase 2)

**Fonte:** Reunião de Alinhamento sobre Agentes CX (28/09/2026)  
**Participantes:** Max Vasconcelos (PMO/Gestão), André Aguiar (Arquitetura/Direção), Jordan Bernardes (Engenharia)  
**Data da Especificação:** 29/09/2026  
**Status:** Aprovado para detalhamento e execução  
**Ciclo de Amadurecimento:** 10 a 15 dias de uso interno antes de expandir para clientes externos  

---

## 1. Visão Geral e Objetivos da Fase 2

A Fase 1 consolidou as skills determinísticas (`pmo-reporte`, `pmo-bolsao`, `pmo-cronograma`, `pmo-auditor`, `pmo-rh`, `pmo-datas`) e o empacotamento autônomo com wheel no Mac do Max. 

A Fase 2 tem como objetivo transformar esses componentes locais em uma **operação contínua e desacoplada em nuvem**, com **arquivamento histórico no SharePoint**, **notificações no Teams**, **segregação precisa entre Projeto e Sustentação**, e **refinamento visual semafórico dos relatórios HTML**.

---

## 2. Matriz de Requisitos

### RF-01: Segregação Estrita de Horas entre "Projeto" e "Sustentação"
* **Tipo:** Requisito Funcional (Crítico)
* **Descrição:** O sistema deve categorizar na raiz os apontamentos e listas do ClickUp, separando claramente o que são horas de **Projeto** (escopo fechado, cronograma de implantação) e o que são horas de **Sustentação** (banco de horas / bolsão mensal recorrente).
* **Critérios de Aceite:**
  1. A configuração (`pmo.json`) e/ou mapeamento de listas no ClickUp deve permitir identificar explicitamente o tipo de cada lista/pasta (`projeto` ou `sustentacao`).
  2. O cálculo de consumo de bolsão em `bolsao.py` deve considerar **apenas** horas classificadas como sustentação para dedução do teto contratual (ex.: Grupo Angelus: teto de 160h de sustentação, com horas de projetos faturadas ou acompanhadas em separado).
  3. O módulo `reporte.py` deve exibir seções ou colunas segregadas para cada modalidade, evitando distorções no faturamento e no acompanhamento de desvios.

---

### RF-02: Template HTML Parametrizado com Sinalização Semafórica de Status
* **Tipo:** Requisito Funcional / UX
* **Descrição:** O relatório diário/semanal gerado deve ser um documento HTML autônomo e visualmente inteligível, substituindo o formato puramente tracejado/monocromático por cores semafóricas claras, alinhadas à identidade visual da Soteria.
* **Critérios de Aceite:**
  1. **Código de Cores de Status:**
     * **Verde (Normal/Meta):** Bolsão abaixo de 80% do teto, apontamentos em dia, entregas no prazo.
     * **Amarelo (Atenção/Gatilho):** Bolsão entre 80% e 100%, ou tarefas de sustentação/chamado sem apontamento há 2 dias úteis.
     * **Vermelho (Crítico/Estouro):** Bolsão acima de 100% (estourado), projetos parados há 4+ dias úteis, ou desvios contratuais graves.
  2. As cores devem respeitar as diretrizes de sobriedade e identidade visual da Soteria (paleta aprovada por André/Max).
  3. **Modularidade do Template:** A estrutura do HTML/CSS deve ser desacoplada da extração de dados (ex.: template Jinja2/HTML), permitindo que o Max ou a equipe de design atualizem estilos e gráficos sem alterar a lógica de negócios em Python.

---

### RF-03: Arquivamento Diário Automático no SharePoint
* **Tipo:** Requisito Funcional / Armazenamento
* **Descrição:** Todo relatório HTML gerado pela rotina diária deve ser arquivado automaticamente no SharePoint corporativo da Soteria, construindo uma trilha de auditoria diária.
* **Critérios de Aceite:**
  1. O relatório deve ser salvo automaticamente na pasta designada do SharePoint (ex.: `/Documentos Compartilhados/PMO/Relatorios-Diarios/YYYY-MM/`).
  2. Nomenclatura padronizada: `YYYY-MM-DD_Relatorio_PMO_Soteria.html`.
  3. O Max e a gestão devem conseguir acessar o histórico de relatórios de dias anteriores com um clique, sem necessidade de regerar dados retroativos.

---

### RF-04: Notificação Proativa no Microsoft Teams / WhatsApp
* **Tipo:** Requisito Funcional / Comunicação
* **Descrição:** A conclusão da rotina matinal deve disparar uma notificação proativa para a liderança, eliminando a necessidade de login proativo no Claude ou CLI para checagem.
* **Critérios de Aceite:**
  1. Integração nativa com o **Microsoft Teams**:
     * Mensagem enviada nominalmente para o Max (chat 1:1) ou em canal dedicado de Operações/PMO.
     * Conteúdo da notificação: Resumo executivo (alertas críticos do dia, bolsões em risco, total de horas faturadas) + link direto para o arquivo HTML no SharePoint.
  2. Suporte futuro/secundário para gatilho de WhatsApp via webhook.

---

### RF-05: Tratamento de Inconsistências de Contexto em Listas (Ex.: Caso Yoshi)
* **Tipo:** Requisito Funcional / Regra de Negócio
* **Descrição:** Corrigir a lógica de interpretação de listas especiais no ClickUp onde a listagem representa horas específicas de um recurso/mês (caso Yoshi), evitando soma incorreta ou omissão de horas.
* **Critérios de Aceite:**
  1. Max validará a regra empírica no Claude Desktop e repassará a especificação exata do mapeamento.
  2. O cliente de extração e normalização do `soteria-pmo` deve acomodar a regra identificada sem quebrar as listas dos outros 9 clientes.

---

### RNF-01: Execução Serverless / Nuvem sem Dependência de Máquina Local
* **Tipo:** Requisito Não Funcional / Arquitetura
* **Descrição:** Toda a cadeia de execução dos agentes (extração de dados ClickUp, cálculo determinístico, montagem do HTML, gravação no SharePoint e envio de Teams) deve ser transferida para a nuvem.
* **Critérios de Aceite:**
  1. Zero dependência de o laptop do Max ou do Jordan estar ligado no momento do disparo.
  2. **Orquestrador Oficial:** Azure Logic Apps (ou Azure Functions integrado).
  3. Agendamento matinal configurado (segunda a sexta-feira, 08:30 BRT).
  4. Execução idempotente com logs de auditoria na nuvem.

---

## 3. Requisitos Postergados (Roadmap Fase 3: 10–15 dias)

### RF-P01: Visão Externa e Compartilhamento com Clientes (Single-Tenant)
* **Situação Atual:** O relatório atual é consolidado internamente (apresenta todos os clientes da Soteria em uma única tela).
* **Risco Identificado:** O compartilhamento do HTML atual geraria vazamento de dados confidenciais entre clientes concorrentes/distintos.
* **Diretriz de André/Jordan:** Congelado por 10 a 15 dias para validação e maturidade dos dados internos.
* **Requisitos Futuros para Fase 3:**
  1. Mecanismo de exportação filtrado por `cliente_id` (cada cliente só recebe seu próprio extrato).
  2. Definição do formato de entrega externa: PDF assinado via e-mail ou link web autenticado / temporário.

---

## 4. Próxima Frente Estratégica no Backlog

Assim que o ciclo da Fase 2 (Logic Apps + SharePoint + Teams + Segregação Projeto/Sustentação) for concluído e aceito pelo Max:
1. **Opção A:** Projeto KMS (Knowledge Management System corporativo).
2. **Opção B:** Agente de Lançamento de Horas com Entrada por Áudio / Microfone (assistente interativo na barra de tarefas, confrontado com a agenda do Outlook e daily, sem monitoramento de máquina invasivo).
