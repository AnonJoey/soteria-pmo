1. **Automação de Coleta de Transcrições (Vault):** Implementar salvamento automático das transcrições de Dailies no Vault. Por que: Elimina a dependência de hábito humano, que é um ponto crítico de falha para o fluxo de dados (Red-Team, Dados, Simplificar). Custo: Baixo (Engenharia de dados/automação de fluxo). CONVERGENTE.

2. **Motor de Extração de Horas com Score de Confiança:** Desenvolver o lançamento de horas com Score de Confiança, Citações Diretas e Aprovação em Lote. Por que: Resolve o gargalo de 1800+ horas manuais e permite auditoria por exceção em vez de conferência linha a linha (Adoção, Simplificar, Sequência). Custo: Alto (Desenvolvimento de lógica de extração e interface de aprovação). CONVERGENTE.

3. **Segregação Técnica de Créditos (Scripts vs LLM):** Bloquear acesso a chaves de API para itens de processamento estruturado (RH, Bolsão, Filtros), utilizando código puro. Por que: Evita drenagem de créditos e desperdício de tokens em tarefas determinísticas (Custo, Red-Team). Custo: Baixo (Configuração de permissões e refatoração de scripts). CONVERGENTE.

4. **Trava de Validação de Input (Regex/Skill):** Implementar validação rígida de padrão de descrição (progressão + cliente) e vocabulário de 13 tags na entrada dos dados. Por que: Impede a exclusão de dados válidos nos relatórios e garante a integridade da base (Red-Team, Custo, Dados). Custo: Baixo (Regex e validação de front-end/script). CONVERGENTE.

5. **Controles de Segurança de Escrita (Idempotência e Booleano):** Garantir que a gravação no ClickUp seja idempotente e que o campo faturável seja um hardcode booleano. Por que: Evita alucinações de modelo e registros fantasmas (Red-Team, Adoção, Simplificar). Custo: Baixo (Lógica de programação). CONVERGENTE.

6. **Sumário de Integridade e Heartbeat:** Criar logs de origem, métricas de processamento e alertas de sucesso/erro para os scripts. Por que: Garante autonomia para o Abner e evita a "morte silenciosa" das automações (Adoção). Custo: Baixo (Logging e monitoramento simples).

7. **Formalização da Matriz de Calibração:** Exigir a entrega imediata do documento do Abner Moraes para desbloquear o cronograma. Por que: A ausência do documento torna o desenvolvimento do item 2 impossível de validar (Dados, Sequência). Custo: Zero (Dependência externa).

8. **Módulo de Configuração de Perfil e Exceções:** Criar cadastro de cadência por desenvolvedor e botão de justificativa de atraso. Por que: Reduz falsos positivos no cronograma e permite tratar ritmos não lineares (Adoção). Custo: Médio (Interface e banco de dados de perfis).

9. **Template de Reporte via Script:** Substituir síntese por LLM no reporte ao cliente por um script de preenchimento de template baseado em dados estruturados. Por que: Reduz custo e elimina ruído de "redação" desnecessária (Custo, Sequência). Custo: Baixo (Engenharia de dados).

10. **Simplificação do Item 3 (Log de Divergências):** Reduzir a interface do acompanhamento de cronograma para um log simples de divergências. Por que: Reduz complexidade técnica e tempo de entrega sob pressão (Sequência). Custo: Baixo.

11. **Remoção do Acompanhamento de Cronograma (Sprint Atual):** Excluir o item 2 do cronograma imediato devido à dependência externa. Por que: O risco de alertas falsos supera o benefício imediato (Simplificar, Sequência). Custo: Zero (Ajuste de escopo).

12. **Remoção de Automações de Conveniência (Bolsão e RH):** Rebaixar a prioridade ou remover os itens de RH e Vigia de Bolsão do MVP. Por que: São regras triviais que não resolvem o problema de escala de 1800 horas (Simplificar). Custo: Zero (Ajuste de escopo).