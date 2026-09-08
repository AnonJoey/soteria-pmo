# Briefing: a demanda dos Agentes PMO (Soteria)

Fonte: vault do delegation-core, processo `proc_ab64e9`, notas de 24/06 a 01/09/2026.
Este arquivo e a entrada de contexto do modelo local. Tudo aqui e dado registrado,
nao suposicao. Onde algo e incerto, esta marcado como ABERTO.

## Quem

- **Jordan**: quem constroi. Responsavel por 7 das 8 tarefas do card.
- **Max Vasconcelos**: lideranca. Definiu os seis itens e a ordem deles. Fecha escopo.
- **Abner Moraes**: PMO, power user de horas. Dono dos workflows e do levantamento.
- **Andre Aguiar**: validacao tecnica. Faz auditoria de horas hoje pelo cloud.
  Faltou na apresentacao de 31/08. DECISAO DE 01/09: nao esperar aprovacao dele,
  entregar solucao pronta para ele mudar depois.

## O problema de negocio

8 a 9 projetos simultaneos, 1800+ horas, 15 a 16 desenvolvedores, gestao toda manual.
Max redirecionou o Jordan em 25/08: pausa em tudo, foco total nos agentes de gestao.

## Os seis entregaveis, na ordem que o Max definiu

1. Reporte ao cliente (Abner) - semanal + disparo manual
2. Acompanhamento de cronograma - continuo, alerta escalonado
3. Auditor de horas e apontamentos (Andre) - mensal, no fechamento
4. Lancamento de horas (Jordan ja testa) - diario ou semanal, aprovacao humana sempre
5. Vigia de bolsao - era tempo real, virou diario ou a cada dois dias em 31/08
6. RH e datas - regra de calendario, trivial

## Prazos

- Desenvolvimento comecou 01/09 (ganhou um dia: o levantamento do Abner deixou de
  ser predecessora, Max textual: "a gente tirou a predecessora do Jordan, pode mandar bala")
- Marco de entrega: 08/09, significando primeira versao rodando em producao
- Dreamforce 11 a 20/09: Jordan, Max, Andre, Saad e Mauricio nos EUA. Tem que estar
  avancado antes.

## Arquitetura decidida

**Criterio**: se o fluxo pode ser escrito como passo a passo, resolve com skill.
Se exige decidir o que dizer a cada caso, precisa de agente. Skills sao muitas,
agentes sao um ou dois.

**Regra das tres camadas**: o que ja vem estruturado NAO passa pelo modelo.
Coleta com script, interpretacao com o modelo, confirmacao com a pessoa.

**Argumento de custo** (o que a lideranca compra): o ClickUp AI foi descartado por
custo, 9,1k creditos. Logo custo por execucao ja e criterio de decisao na casa.
Skill barata em frequencia alta contra agente caro na mesma frequencia da contas
muito diferentes ao longo de um ano sobre 8-9 projetos.

**Fora de escopo, explicitamente**: lancar horas sem confirmacao; enviar relatorio
direto ao cliente (entrega fica no nivel 2, Max valida e envia); inferir trabalho de
atividade de navegador ou processo; julgamento de mercado sobre volume de horas.

## O que ja existe e sustenta o prazo

- Piloto de lancamento de horas: 97 entradas, 218h37 em 24 dias, 208h37 faturaveis,
  25 subtarefas no padrao da casa. Periodo 15/07 a 07/08, conferido ao vivo.
- Acervo de 41 reunioes processadas (24/06 a 28/08) e base de busca semantica.
- 33 dailies transcritas no vault.

## Medicoes reais de cobertura (nao extrapolar)

Reconstruir o que UMA PESSOA fez a partir de evidencia de maquina captura pouco:
- ciclo 1 (15-30/07): 39,1h apuradas de 130,1h reais
- ciclo 2 (29/07-06/08): 54h apuradas de 89,5h reais

Isso vale para lancamento e auditoria de horas. NAO vale para reporte, cronograma,
bolsao e RH, que leem o que o sistema registra e sao automatizaveis direto.
Usar esses numeros esticados era a vulnerabilidade mais seria da proposta.

O que fechou a lacuna no ciclo 2 foram sete prints de transcricao da daily do Teams,
nao artefato de maquina. Dias 04 e 05/08 apareciam como ZERO e eram dias normais.

## Os quatro controles de seguranca da escrita no ClickUp

Nasceram de um incidente: retentar sem conferir gerou 4 fantasmas e 16h indevidas.

1. Conferencia obrigatoria depois de escrever: chamada que falha grava a entrada mesmo assim
2. Faturavel sempre explicito: omitir o campo marca como nao faturavel
3. Escrita sempre precedida de aprovacao: a API nao edita nem exclui entrada de tempo
4. Tags em etapa separada: o formato aceito difere do que o conector envia

## Padrao da casa para lancamento (extraido dos lancamentos do Marcos Claudio)

- Vocabulario fechado de 13 tags
- Daily e lancamento de horas NAO sao faturaveis
- Descricao com progressao explicita e cliente entre parenteses
- A descricao da ENTRADA DE TEMPO e o rotulo da linha no Relatorio de horas faturaveis.
  Entradas sem descricao somem do relatorio do Abner.

## Achado que destrava a captura diaria

A API de transcripts do Stream devolve a transcricao inteira em JSON com falante e
startOffset, autenticada pelo cookie da sessao:
`/_api/v2.1/drives/{drive}/items/{item}/media/transcripts/{id}/streamContent?format=json`
Se a transcricao pode ser vista, pode ser lida por ali, sem download e sem mudanca
de politica. Regra de download que faltava: recorrente autorizada uma vez libera todas
as ocorrencias; avulsa exige autorizacao de quem INICIOU a gravacao.

Salvar a transcricao da daily no vault todo dia foi apontado desde 30/07 como o achado
de maior alavancagem: e mudanca de processo, nao de codigo, e deve vir antes da automacao.

## Restricoes de desenho

- A cadencia de trabalho NAO e uniforme entre os devs. Com regua unica, o agente de
  cronograma marca como abandonada uma tarefa que so segue outro ritmo. Calibrar por
  pessoa e por projeto. ABERTO: confirmar com o Abner.
- Nenhum item da primeira versao exige infraestrutura dedicada, depois que o bolsao
  saiu do tempo real. O requisito de servidor proprio, aberto desde junho, foi
  resolvido trocando a cadencia em vez da maquina.
- Qualidade do dado no ClickUp avaliada como boa pelo operador.

## Pendencias registradas e nao executadas (em 01/09)

- Descricoes vazias nos seis itens 3.x e nos quatro passos macro do card
- Nenhuma das oito decisoes da pauta tem representacao no ClickUp
- Max e Andre nao sao assignee de nada, embora tenham dono nomeado em 7 das 8 decisoes
- Tags em todas as 97 entradas do piloto (MCP nao grava, a API exige objeto com name)
- Calibragem de cadencia por dev, a perguntar ao Abner

# TESE VALIDADA NA F1

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