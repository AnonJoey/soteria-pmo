# O que o ClickUp diz de verdade, lido em 02/09/2026 00:09

Lista `Agentes PMO` (901716443542), pasta `AI - Claude`, 12 tarefas.
Tudo abaixo e leitura direta da API, nao interpretacao. Nada foi escrito.

## As 12 tarefas

| Tarefa | Id | Status | Responsavel | Vence |
|---|---|---|---|---|
| Atividades de Agentes PMO (pai) | 86e30yrtp | ideia | Jordan | 08/09 |
| 1. Levantamento de Workflow | 86e30ykc3 | ideia | **Abner** | **01/09, vencida** |
| 2. Validacao e definicao dos agentes | 86e30ykjx | ideia | Jordan | **01/09, vencida** |
| 3. Desenvolvimento dos Agentes | 86e30ym08 | ideia | Jordan | 03/09 |
| 3.1 Report ao cliente (Skill) | 86e3127bd | ideia | Jordan | 03/09 |
| 3.2 Acompanhamento de cronograma (Agente) | 86e3127cr | ideia | Jordan | 03/09 |
| 3.2.1 Guardiao das datas do time (Skill Interna) | 86e3127em | ideia | Jordan | 03/09 |
| 3.3 Auditor de apontamentos (workflow) | 86e3127fr | ideia | Jordan | 03/09 |
| 3.4 Lancamento de horas | 86e31gx8v | ideia | Jordan | 03/09 |
| 3.5 Vigia de bolsao **em tempo real** | 86e31dz55 | ideia | Jordan | 03/09 |
| 3.6 RH e datas | 86e31dzaa | ideia | Jordan | 03/09 |
| 4. Testes e Ajustes Finais | 86e30yn31 | ideia | Jordan | 08/09 |

## Sete descompassos entre o card e o que foi decidido

1. **As datas do desenvolvimento nao acompanharam a reuniao de 31/08.** Os sete
   itens 3.x comecam 02/09 e vencem 03/09. Mas em 31/08 o Max tirou a predecessora
   do Abner ("pode mandar bala") e o desenvolvimento passou a comecar 01/09. O card
   ainda descreve o cronograma anterior aquela decisao. Lido agora, ele diz que os
   sete entregaveis nascem hoje e vencem amanha.

2. **Os passos 1 e 2 estao vencidos e intocados.** Levantamento (Abner) e Validacao
   venceram 01/09 e seguem em `ideia`. O levantamento deixou de ser bloqueante para
   o desenvolvimento, mas continua sendo a entrada declarada do passo 2.

3. **O 3.5 ainda se chama "em tempo real".** A reuniao de 31/08 tirou o bolsao do
   tempo real e definiu cadencia diaria ou a cada dois dias, e foi essa troca que
   dispensou o servidor proprio. O titulo no card contradiz a decisao que resolveu
   o unico requisito de infraestrutura do projeto.

4. **Tudo esta com prioridade `low`.** Em 25/08 o Max declarou este o trabalho de
   prioridade maxima e mandou pausar Paperclip, design e delegation-core. As 12
   tarefas estao em `low`.

5. **Nenhuma tarefa tem descricao.** As 12, incluindo os sete 3.x. O criterio de
   entrega por escrito foi definido pelo proprio Abner em 28/08 (passo a passo mais
   dois ou tres exemplos em texto).

6. **Nenhuma tarefa tem estimativa de tempo.** `time_estimate: null` nas 12. Nao ha
   base de capacidade para dizer se sete entregaveis cabem na janela.

7. **Max e Andre nao sao responsaveis por nada.** Onze tarefas com o Jordan, uma com
   o Abner. Em 31/08 a validacao tecnica com o Andre foi nomeada pelo Max como o
   unico risco alto do projeto, e ela nao existe como tarefa.

## O que isso muda no planejamento

Sao **sete** itens de desenvolvimento, nao seis: o 3.2.1 (Guardiao das datas) existe
como subtarefa do 3.2. Bate com a decisao de 28/08 de que o guardiao e uma skill
dentro do auditor, mas quem le a lista do Max conta seis.

A janela real de desenvolvimento no card e de dois dias para sete itens, contra um
marco de 08/09 que so aparece no passo 4 (Testes) e no pai. Ou o desenvolvimento
escorre para dentro da janela de testes, ou as datas dos 3.x estao erradas. As duas
leituras levam ao mesmo lugar: o card nao representa um plano executavel hoje.

Nada disso foi escrito no ClickUp. A decisao de escrita e do Jordan.
