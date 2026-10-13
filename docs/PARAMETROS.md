# Parâmetros: onde cada número vive

Este documento responde, para cada parâmetro que o Max e o Abner precisam informar, **onde ele mora hoje**, **quem o fornece** e **o que acontece quando falta**. Nada aqui é novo no código: é o mapa do que já existe, para a estrutura de parâmetros do backlog (item B4) não virar uma segunda fonte de verdade.

## Onde está o config

`~/.soteria-pmo/pmo.json`, um arquivo por pessoa que opera o pacote. Só `token`, `team_id` e `projetos` são obrigatórios (`soteria-pmo checar` diz o que falta e o preço de cada ausência).

## Projetos, tetos e horas contratadas

Lista `projetos`, uma entrada por cliente ou projeto:

| Chave | O que é | Quem informa | Se faltar |
|---|---|---|---|
| `nome` | Nome do cliente ou projeto, como aparece no ClickUp | Max | O projeto não é lido |
| `space_id` | Espaço do cliente. É a **unidade do bolsão**: o trabalho de um cliente se espalha por dezenas de listas | Max, ou lido da hierarquia do ClickUp | O bolsão usa só a lista (mede uma fatia) |
| `list_id` | Lista lida pelo cronograma e pelo guardião das datas | Max | O item de cronograma não lê esse projeto |
| `tipo` | `projeto` (régua de 4 dias úteis sem hora apontada) ou `chamado` (2 dias úteis) | Acordado com o Abner em 03/09 | Vale `projeto` |
| `horas_contratadas` | Teto mensal de sustentação, ou total de um projeto | Max e Abner | Vale o teto de referência do código, se houver. Sem nenhum, o vigia diz "sem teto", em voz alta, e não projeta estouro |
| `listas_sustentacao` | Listas que contam para o teto. Separa a sustentação de projetos dentro do mesmo espaço | Max | Tudo no espaço conta como sustentação |
| `listas_projeto` | Listas que **não** contam para o teto | Max | Idem |

**Duas unidades que não se misturam:** teto **mensal** (sustentação, reseta na virada do mês) e total de **projeto** (implantação, não reseta). O código guarda os dois em tabelas separadas, porque comparar um total de projeto com o consumo mensal daria um alerta que nunca dispara ou que dispara sempre. Escopo fechado (cliente medido contra o total do escopo) entra na segunda categoria e hoje não tem nenhum cliente configurado.

**Pendente com o Max e o Abner:** os tetos dos clientes que ainda estão "sem teto", e se cada cliente com lista de projeto no mesmo espaço precisa de `listas_sustentacao`.

## Datas do time

Arquivo `roster_rh` (padrão `~/.soteria-pmo/rh.csv`), uma linha por pessoa. Só `nome` é obrigatório; todo o resto é opcional e a ausência de um campo apenas desliga o lembrete correspondente:

| Coluna | Alias aceito | Para que serve |
|---|---|---|
| `nome` | | Identifica a pessoa |
| `nascimento` | | Aniversário (7 dias antes e no dia) |
| `inicio_contrato` | `admissao` | Tempo de contrato e os dois feedbacks do primeiro ano, aos 45 e aos 90 dias do início do contrato |
| `fim_contrato` | | Aviso de fim de contrato |
| `interrupcao_inicio` | `ferias_inicio` | Interrupção temporária negociada (não é férias) |
| `ultimo_feedback` | `data_ultimo_feedback` | Mantido para planilhas antigas; os dois feedbacks do primeiro ano não dependem dele |

Sem o arquivo, o item de RH diz que não há roster, em vez de devolver uma lista vazia, porque os dois casos são indistinguíveis. **Quem fornece os dados é o Abner, o Max e o Marcos**, e é a pendência B16.

## Outros parâmetros

| Chave | O que é | Padrão |
|---|---|---|
| `task_horas` | ID da tarefa guarda-chuva onde as horas são lançadas quando nenhuma outra é indicada | Nenhum (a proposta aponta tudo para uma tarefa só) |
| `pessoa` | Nome de quem opera, como aparece na daily e no ClickUp | Nenhum |
| `feriados` | Lista de datas `AAAA-MM-DD` que não contam como dia útil | Vazia |
| `evidencia` | Fontes de evidência da máquina (repositórios, sessões de IA, daily, agenda) e a lista `pessoais` de projetos que **não** são do trabalho | Vazia: sem fontes, o motor só pergunta mais |
| `modelo` | Endereço de um servidor compatível com OpenAI para ler as dailies | Nenhum: sem ele as dailies não são lidas |

## Regra para quem for estender

Um parâmetro novo entra aqui antes de entrar no código, com três respostas: quem o fornece, qual o padrão quando falta e o que o pacote diz quando falta. Um valor que "falta" e é substituído por um palpite silencioso foi a origem do teto de "Grupo Anjos" que nunca existiu.
