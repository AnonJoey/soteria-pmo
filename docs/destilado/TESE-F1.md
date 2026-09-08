## Qual e o problema de verdade
A gestão manual de 8 a 9 projetos simultâneos, envolvendo mais de 1800 horas e uma equipe de 15 a 16 desenvolvedores, é ineficiente. O objetivo é implementar uma solução de automação híbrida (scripts para dados estruturados e agentes para interpretação) que garanta escala e controle de custos. A solução utiliza o salvamento diário de transcrições no vault como alavancagem principal para mitigar a baixa taxa de recuperação de dados observada em ciclos anteriores (ciclo 1: 39,1h de 130,1h; ciclo 2: 54h de 89,5h). O critério de decisão tecnológica baseia-se no custo por execução, priorizando Skills para frequências altas e Agentes para decisões complexas, conforme o descarte do ClickUp AI.

## O que exatamente foi contratado (os seis itens, o que cada um entrega)
1. Reporte ao cliente: entrega de relatório semanal com disparo manual por Abner. O fluxo de entrega ocorre no nível 2: Max valida e envia ao cliente.
2. Acompanhamento de cronograma: monitoramento contínuo com sistema de alertas escalonados.
3. Auditor de horas e apontamentos: auditoria mensal no fechamento para validação técnica (Andre).
4. Lançamento de horas: registro diário ou semanal com obrigatoriedade de aprovação humana.
5. Vigia de bolsão: monitoramento diário ou a cada dois dias. A mudança da cadência para este intervalo resolveu a necessidade de infraestrutura de servidor próprio.
6. RH e datas: aplicação de regras de calendário (item trivial).

Fora de escopo: lançar horas sem confirmação; enviar relatório direto ao cliente; inferir trabalho de atividade de navegador ou processo; julgamento de mercado sobre volume de horas.

## O que ja esta pronto e o que falta
Pronto:
Piloto de lançamento de horas com 97 entradas, 218h37 totais (sendo 208h37 faturáveis).
Acervo de 41 reuniões processadas com base de busca semântica.
33 dailies transcritas no vault.
Identificação do endpoint de transcripts do Stream para captura de dados em JSON sem download.
Arquitetura de três camadas decidida (coleta por script, interpretação por modelo, confirmação humana).
Definição dos quatro controles de segurança para escrita no ClickUp: conferência obrigatória pós escrita, faturável sempre explícito, escrita precedida de aprovação e tags em etapa separada.
Requisito de processo: salvamento diário de transcrições das dailies no vault.

Falta:
Descrições nos seis itens 3.x e nos quatro passos macro do card.
Representação das oito decisões da pauta no ClickUp.
Atribuição de Max e Andre como assignees nos itens correspondentes.
Aplicação de tags em todas as 97 entradas do piloto, seguindo o vocabulário fechado de 13 tags.
Calibragem da lógica de cadência por desenvolvedor e por projeto (ABERTO: confirmar com o Abner).
Aplicação do padrão da casa (descrições com progressão e cliente entre parênteses; marcação de itens não faturáveis). A ausência de descrição impede a exibição no relatório do Abner.

## Riscos que podem furar o prazo de 08/09
Prazo de entrega extremamente curto (primeira versão em produção em 7 dias).
Necessidade de avanço significativo antes da Dreamforce (11 a 20/09).
Bloqueio por mudança de processo: a automação exige que a equipe adote o salvamento diário das transcrições no vault antes da execução do código.
Risco de bloqueio de desenvolvimento: a falta de calibração da cadência por pessoa e projeto pode impedir a correta marcação de tarefas (ABERTO: confirmar com o Abner).
Risco de conformidade: a não aplicação do padrão da casa (descrições obrigatórias) causará a exclusão de entradas do relatório de horas faturáveis.
Viabilidade financeira: a solução deve manter baixo custo por execução, seguindo o critério de descarte do ClickUp AI.

## ABERTO
ABERTO: Confirmar com o Abner a calibração da cadência por pessoa e por projeto.
ABERTO: Preencher as descrições vazias nos seis itens 3.x e nos quatro passos macro do card.