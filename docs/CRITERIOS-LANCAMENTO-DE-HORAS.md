# Critérios do agente de lançamento de horas

Rascunho de 08/10/2026 para validar com o André e o Max numa conversa a três. Cada regra diz de onde vem: **código** (o que o pacote faz hoje), **decisão** (dita pelo Max ou pelo Jordan) ou **proposta** (ainda não decidida).

## 1. O que o agente faz e o que nunca faz

- Reconstrói o que a pessoa fez num período a partir de evidências, propõe os lançamentos e **pergunta pelo que ficou de fora**. (código)
- **Nunca lança sem aprovação.** A proposta é simulada primeiro; só grava no ClickUp com `--real`, depois de a pessoa conferir. (código)
- **Nunca devolve zero em silêncio.** Um dia sem evidência vira pergunta, porque dia sem evidência e dia sem trabalho são idênticos no dado e opostos no sentido. (código)
- Imprime sempre a cobertura do que mediu. Nos dois ciclos medidos, a leitura só por artefato pegou cerca de 40% das horas reais (39,1 h de 130,1 h no primeiro; 54 h de 89,5 h no segundo). (código)
- A leitura de máquina é da própria máquina da pessoa, sob o controle dela. O sniffer que leria a máquina de outras pessoas foi vetado pelo André por serem PJ, e foi trocado por entrada assistida. (decisão)

## 2. As fontes e quanto cada uma pesa

O peso diz quão bem a fonte sustenta uma **duração**, que é o que vira hora lançada. (código)

| Fonte | Peso | O que prova | O que não prova |
|---|---:|---|---|
| Reunião (transcrição) | 0,90 | Duração medida na própria transcrição | O que foi feito fora dela |
| Agenda do Outlook | fora da escala: hoje só nomeia ou gera pergunta (código) | Que havia uma reunião marcada. O Max disse que é fonte 100% boa (decisão) | Que a reunião aconteceu: a "Reunião com o Max" de 23/09 estava na agenda e não aconteceu (código) |
| Sessão do Claude | 0,75 | Muitos carimbos de tempo, agrupados | Só existe para quem usa o Claude; pesa menos porque nem todos pagam (decisão) |
| Commit | 0,60 | Um instante; a janela é inferida dos vizinhos | Quanto tempo levou |
| Declaração na daily | 0,55 | A pessoa disse o que fez | Por quanto tempo |
| Nota do vault | 0,50 | Um instante, pela hora de gravação | Duração |
| Arquivo | 0,45 | Um instante | Duração |
| Navegador | 0,30 | Que uma página estava aberta | Que alguém olhava para ela |
| Salesforce do cliente | não lida | Só entra se o dev liberar acesso (decisão) | |

**Conflito a resolver:** o Max diz que a agenda é fonte 100% boa; o código a trata como não prova, porque um evento marcado já deixou de acontecer. Hoje evento sem outra evidência vira pergunta, e evento que coincide com evidência só dá nome à proposta. Proposta: a agenda passa a valer como janela medida quando a pessoa confirma o evento na proposta, ou quando há transcrição da reunião. (proposta)

## 3. Pessoal contra Sotéria

- O pacote separa evidência pessoal pela lista `evidencia.pessoais` do config de **cada pessoa**, por pasta ou por nome de projeto, mais uma lista fixa de marcas (jogos, streaming). O que cai ali sai da apuração em vez de virar hora de cliente. (código)
- Erra para o lado de perguntar: um falso alerta custa uma pergunta; uma falha custa hora faturada errada. (código)
- **Medido em 08/10:** com as pastas da carreira fora da lista, a auditoria de 30/09 a 06/10 corroborava 12 de 48 entradas; com elas na lista, 23 de 48. A lista precisa ser mantida por quem conhece os próprios projetos. (medição)
- Proposta: o pacote avisar quando uma sessão do Claude roda numa pasta que não é de nenhum projeto configurado nem está na lista de pessoais, para a pessoa classificar. (proposta)

## 4. Faturável ou não

Decisões do Jordan e do Max até 07/10. (decisão)

| Tipo de hora | Faturável? |
|---|---|
| Trabalho de desenvolvimento, inclusive sessões autônomas | Sim |
| Dailies | Não, com a etiqueta `daily`, na tarefa das dailies |
| Lançamento de horas | Não |
| Dreamforce | Não |
| Trabalho pessoal | Fora da apuração |

Pendente: a regra dos dias do Max e de eventos que não são do contrato, quando aparecerem. (proposta)

## 5. Formato do lançamento

- Uma entrada por bloco contíguo de trabalho, com horário real de início e fim. (decisão, a partir de 29/07)
- **Descrição obrigatória, e só isso.** A descrição é o rótulo da linha no Relatório de horas faturáveis; entrada sem descrição existe, é cobrada e fica invisível para quem lê o relatório. O "cliente entre parênteses" no fim NÃO é regra: em agosto, 7,6% das 1.506 entradas de 14 pessoas terminavam assim, e o pacote deixou de cobrar isso em 08/09. (código)
- A descrição cita a evidência que sustenta o bloco; resultado negativo (pesquisa sem solução, troubleshooting que não resolveu) consta explicitamente. (decisão)
- Reuniões ficam no horário verdadeiro. Uma entrada nunca se sobrepõe à daily. (decisão)

## 6. O que faz uma hora virar pergunta e não lançamento

- Dia ou intervalo sem nenhuma evidência.
- Janela inferida (um commit isolado, por exemplo) em vez de medida.
- Declaração da daily que diverge da janela medida em mais de meia hora.
- Evidência que parece pessoal.
- Entrada que se sobrepõe a outra ou que contém outra: a auditoria aponta; no lançamento, o corte contra a daily é feito na proposta. (código para o apontamento; decisão para o corte)

As quatro primeiras são de código.

## 7. O que fica de fora de propósito

- Planejamento, ligação e conversa que não deixam rastro de máquina. O agente não os inventa: pergunta.
- Julgamento de volume comercial. A auditoria aponta, não acusa: nenhum veredito afirma erro, e "sem lastro" quer dizer só que a auditoria não viu evidência de máquina.

## 8. Perguntas para a conversa a três

1. Os pesos da seção 2 estão certos? E a agenda do Outlook: vale como janela medida sozinha, ou continua a exigir confirmação?
2. A tabela de faturável da seção 4 cobre os casos reais do time, ou há mais exceções?
3. Quem mantém a lista de projetos pessoais de cada pessoa, e o pacote deve avisar quando achar uma pasta nova?
4. Basta exigir descrição não vazia, ou o André e o Max querem um padrão de descrição?
