## Arquitetura
A arquitetura segue a regra das três camadas: Coleta (Script), Interpretação (Modelo) e Confirmação (Humana). O critério de decisão é o custo por execução e a complexidade da tomada de decisão. Itens de processo com dados estruturados devem ser processados via scripts puros. O modelo (LLM) é restrito à interpretação de transcrições e à auditoria comparativa.

**Restrição de Custo:** Itens 1, 5 e 6 devem ser executados estritamente via script de formatação ou cruzamento de dados para evitar estouro de créditos. O modelo (LLM) é proibido para consolidar dados já estruturados no ClickUp.

## Os sete itens

**1. Reporte ao Cliente**
*   **Entrada:** Dados estruturados de horas, cronograma e bolsão no ClickUp.
*   **Processamento:** Script de preenchimento de template (substituindo síntese por LLM).
*   **Saída:** Relatório semanal formatado para validação do Max.
*   **Critério de Aceite:** Relatório gerado sem alucinações de texto e com dados 100% fidedignos ao ClickUp.

**2. Acompanhamento de Cronograma**
*   **Entrada:** Matriz de calibração (por pessoa/projeto) e dados de progresso no ClickUp.
*   **Processamento:** Comparativo entre progresso real e cadência esperada (com módulo de configuração de perfil e exceções).
*   **Saída:** Log de divergências e alertas escalonados.
*   **Critério de Aceite:** Alertas disparados apenas para desvios reais, minimizando falsos positivos.

**3. Auditor de Horas e Apontamentos**
*   **Entrada:** Transcrições brutas do Vault e apontamentos no ClickUp.
*   **Processamento:** Agente comparador de texto (LLM) com Score de Confiança.
*   **Saída:** Exibição lado a lado da transcrição bruta e do apontamento para validação técnica do Andre.
*   **Critério de Aceite:** Auditoria mensal concluída com rastreabilidade total da origem do dado.

**4. Lançamento de Horas**
*   **Entrada:** Transcrições de reuniões/dailies e vocabulário de 13 tags.
*   **Processamento:** Motor de extração com Score de Confiança e citações diretas.
*   **Saída:** Proposta de registro com interface de aprovação humana em lote.
*   **Critério de Aceite:** Registro diário/semanal com obrigatoriedade de aprovação e exibição da transcrição bruta.

**5. Vigia de Bolsão**
*   **Entrada:** Dados de horas e limites de projeto no ClickUp.
*   **Processamento:** Script de cruzamento de dados (execução 100% via script).
*   **Saída:** Monitoramento diário ou a cada dois dias com alertas de limite.
*   **Critério de Aceite:** Alerta de estouro de bolsão sem consumo de créditos de modelo.

**6. RH e Datas**
*   **Entrada:** Calendário de regras e dados de equipe.
*   **Processamento:** Script de aplicação de regras de calendário (execução 100% via script).
*   **Saída:** Alertas de datas e prazos de RH.
*   **Critério de Aceite:** Execução automática sem intervenção de LLM.

**7. Guardião das Datas do Time (Skill Interna)**
*   **Entrada:** Datas de entrega e prazos das tarefas no ClickUp.
*   **Processamento:** Skill de monitoramento de datas críticas e alertas de proximidade.
*   **Saída:** Alertas proativos para o time.
*   **Critério de Aceite:** Identificação antecipada de riscos de atraso nas tarefas do projeto.

## Ordem de construção
1.  **Base de Dados:** Automação do salvamento diário de transcrições das dailies no Vault (prioridade máxima para garantir o fluxo de dados).
2.  **Desenvolvimento de Scripts (Baixo Custo):** Itens 1, 5 e 6 (foco em automação determinística).
3.  **Motor de Extração e Auditoria:** Itens 3 e 4 (foco em Score de Confiança e interface de aprovação).
4.  **Monitoramento e Skills:** Itens 2 e 7 (condicionados à calibração de cadência).

## O que reaproveita do piloto de horas
*   **Base de Dados:** As 97 entradas do piloto como dataset de treino e validação.
*   **Vocabulário:** As 13 tags e o padrão de descrição (progressão + cliente) já definidos.
*   **Infraestrutura:** Endpoint de transcripts do Stream validado para JSON.
*   **Segurança:** Os 4 controles de escrita (conferência, faturabilidade, aprovação e tags isoladas) serão a base da API.

## Descompassos do card que precisam de decisão do Jordan
1.  **Datas de Desenvolvimento:** O card indica que os sete itens 3.x vencem em 03/09, mas o desenvolvimento deveria ter iniciado em 01/09. É necessário atualizar as datas no ClickUp.
2.  **Prioridade:** Todas as 12 tarefas estão como `low`, mas o projeto foi declarado como prioridade máxima em 25/08.
3.  **Status de Passos 1 e 2:** O levantamento e a validação estão vencidos e em `ideia`. O levantamento não é mais bloqueante, mas o card não reflete essa mudança.
4.  **Título do Item 3.5:** O card ainda cita "em tempo real", contradizendo a decisão de cadência diária/bi-diária.
5.  **Descrições e Estimativas:** Nenhuma tarefa possui descrição ou `time_estimate`. É necessário preencher para permitir a auditoria do Andre e o cálculo de capacidade.
6.  **Responsáveis:** Max e Andre não constam como responsáveis em nenhuma tarefa, apesar de serem pontos críticos de validação.

## ABERTO
ABERTO: Confirmar com o Abner a calibração da cadência por pessoa e por projeto (necessário para o item 2).
ABERTO: Preencher as descrições vazias nos seis itens 3.x e nos quatro passos macro do card (necessário para auditoria do Andre e visibilidade do fluxo).