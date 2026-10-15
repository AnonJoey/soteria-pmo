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
| `listas_total` | Para projeto **sem teto mensal**: as listas do ClickUp que formam o projeto. O vigia soma o `time_estimate` (previsto) e o `time_spent` (lançado) das tarefas e das subtarefas e vigia a porcentagem do total, nas mesmas faixas do teto mensal (75, 90 e 100%) | Abner (pediu em 14/10/2026 para Reviver e Unimed) | O projeto sai do digest como "sem teto configurado", com o motivo. Não use o espaço inteiro: ele mistura frentes |
| `horas_totais` | Opcional, só com `listas_total`: o previsto, quando as tarefas não têm estimativa ou se quer fixar outro número | Abner ou Max | O previsto é a soma das estimativas das tarefas; sem estimativa, vale a tabela de referência do código; sem nenhuma das três, o digest diz que o projeto está sem previsto |

**Duas unidades que não se misturam:** teto **mensal** (sustentação, reseta na virada do mês) e total de **projeto** (implantação, não reseta). O código guarda os dois em tabelas separadas, porque comparar um total de projeto com o consumo mensal daria um alerta que nunca dispara ou que dispara sempre. Escopo fechado (cliente medido contra o total do escopo) entra na segunda categoria, e é o que `listas_total` faz. O vigia do total **não projeta data de estouro**: um previsto de milhares de horas, a um ritmo mensal, daria uma data de anos adiante, e uma data escrita como dia e mês se lê como prazo. Ele só diz a porcentagem e a faixa. Conferido em 15/10/2026 contra o ClickUp: para o Reviver, a soma das estimativas e a soma do tempo lançado da lista do projeto bateram, ao minuto, com os números que o Abner leu na tela.

**Confirmado pelo Abner em 14/10/2026:** Angelus (160) e China Gate (100) de sustentação, e A.Yoshii, Apet e Dimas como estão no código. BM2: 100 h é uma média e não um limite contratado, e é bom ser alertado ao passar de 100 h. Reviver e Unimed: sem teto mensal, o acompanhamento é pelo total do projeto (`listas_total`).

**Pendente com o Max e o Abner:** o Gazin (o Abner não conhece o número; a informação de 40 h veio do Max ou do André), e se cada cliente com lista de projeto no mesmo espaço precisa de `listas_sustentacao`.

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

**O nascimento já está no ClickUp (confirmado em 14/10/2026):** a lista de cadastro de pessoas tem o campo "Data de nascimento". `soteria-pmo rh-importar --lista ID` lê só o nome da tarefa (cada tarefa é uma pessoa) e esse campo, mescla no roster (o nascimento do ClickUp vence; as outras datas de quem já estava ficam) e grava com permissão 600; sem `--real` só simula e nunca imprime datas. A mesma lista guarda contato de emergência, e-mail e telefone pessoais, endereço e respostas sobre saúde: nada disso é lido nem gravado. Início e fim de contrato e último feedback não estão no ClickUp e seguem dependendo de quem cuida dos contratos. `rh_lista` no config guarda o ID para não precisar repetir.

## Quem lança horas

Regra confirmada em 14/10/2026: **todos devem lançar horas**, e algumas pessoas lançam só hora não faturável, por enquanto. Duas chaves do config, com os nomes como aparecem nas entradas de tempo (o `username`, ou o e-mail se a pessoa não tem `username`). Os nomes ficam só no config local, nunca no repositório, que é público.

| Chave | O que é | Se faltar |
|---|---|---|
| `equipe_lancamento` | Quem é esperado no quadro de `soteria-pmo lancamentos`. Inclui quem lança só hora não faturável | Valem os autores dos últimos 30 dias, e o quadro avisa que quem nunca lançou não aparece |
| `nao_faturam` | Quem lança só hora não faturável. Não isenta de lançar: o comando acrescenta ao quadro as horas **faturáveis** que essas pessoas lançaram, que são sinal de etiqueta errada | Nada é checado |

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
