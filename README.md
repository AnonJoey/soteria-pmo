# Agentes PMO

Os sete itens de gestao pedidos pelo Max, construidos como modulos que produzem
texto para uma pessoa ler. Escopo fechado em 31/08/2026, marco de entrega 08/09.

Este repo saiu do `delegation-core` em 08/09/2026, onde o pacote nasceu por
conveniencia: o vault, o coletor de evidencia e o modelo local ja estavam la.
A separacao custou pouco porque o acoplamento tinha sido medido antes: o pacote
nao importa nada do `delegation_core`, so stdlib mais `httpx`. O historico dos
commits veio junto, e e onde estao os porques de cada constante.

## Instalar

```
python3 -m venv .venv
.venv/bin/pip install httpx pytest
.venv/bin/pip install --no-deps -e .
```

O `--no-deps` no ultimo passo e por habito herdado da base de origem, onde um
`pip install -e .` direto puxava a pilha de embeddings inteira. Aqui a unica
dependencia de runtime e `httpx`, entao instalar sem ele tambem funciona.

Depois, para deixar as skills e o agente visiveis em toda sessao do Claude Code:

```
.venv/bin/soteria-pmo-instalar
```

Ele copia `skills/pmo-*` para `~/.claude/skills` e `agents/pmo-horas.md` para
`~/.claude/agents`, **sem nunca sobrescrever** o que voce ja tem com aquele
nome: o que ja existe e mantido e reportado como mantido.

## Configurar

O workspace vive em `~/.soteria-pmo/pmo.json`, e nenhum comando roda sem ele.
Sao as coisas que codigo nenhum deve trazer embutidas: qual lista e qual
projeto, se cada um e projeto de implantacao ou fila de chamado, quantas horas
cada bolsao tem, e quem esta no time. Rodar qualquer subcomando sem o arquivo
imprime o exemplo completo com os campos esperados, em vez de um traceback.

O caminho antigo, `~/.delegation_core/pmo.json`, deixou de ser lido em
02/10/2026. Era o ultimo ponto em que o pacote apontava para outro projeto.

### Independente de qualquer outro projeto

O pacote nao importa nada alem da biblioteca padrao e do `httpx`, e nao traz
escrito caminho, porta ou pasta de outro projeto. Dado de fora e bem-vindo,
mas entra **pelo config**, nunca pelo codigo:

| Chave | O que e | Sem ela |
|---|---|---|
| `evidencia.dailies` | pasta com as transcricoes de daily e de reuniao | `~/.soteria-pmo/dailies` |
| `modelo.url` | endpoint compativel com OpenAI que interpreta as dailies | as dailies nao sao interpretadas |
| `evidencia.antigravity` | `history.jsonl` do Antigravity CLI | fonte ausente |
| `evidencia.agenda` | arquivo JSON de eventos, ou comando que imprime esse JSON (`{de}` e `{ate}` trocados pelas datas) | fonte ausente |
| `evidencia.vault` | pasta de notas em markdown, lidas pelo horario de escrita | fonte ausente |

A agenda e o exemplo da regra: o modulo `agenda` existe e imprime exatamente
esse JSON com `--json`, mas este pacote nao o importa. Chama um comando e le a
saida, e qualquer outro produtor do mesmo formato serve.

`tests/test_independencia.py` e a guarda: falha se um modulo importar algo de
fora ou trouxer escrito o caminho, a porta ou a pasta de outro projeto.

## O que e obrigatorio, e o que e so aproveitado

```
soteria-pmo checar
```

**Obrigatorio: o ClickUp**, token e team. Seis dos sete itens leem campo e fazem
conta, e funcionam com isso e mais nada.

**Opcional: tudo que vem da maquina.** Repositorios git, sessoes de IA em disco
(Claude Code e Antigravity), historico do navegador, agenda, a pasta das
dailies e um modelo para interpreta-las. Nenhuma delas e requisito: sem elas o
motor de horas continua rodando e simplesmente **pergunta mais**.

Duas fontes nunca viram hora sozinhas. **A agenda** diz o que estava marcado,
nao o que aconteceu: evento que coincide com outra evidencia so da nome a
proposta, e evento isolado vira pergunta ("aconteceu?"). **O agente rodando
sozinho** tambem: cada mensagem digitada abre 45 min de atencao, e o que o
agente faz fora disso vira pergunta com o horario ("entra no lancamento?"). Faltar fonte nao e erro, e menos
evidencia, e menos evidencia sai declarada como pergunta em vez de virar numero.

O `checar` diz o que esta la, o que falta, e **o que cada ausencia custa**. Uma
checagem que so lista verde e vermelho transfere para quem le o trabalho de
saber o que cada vermelho significa.

## Usar

```
soteria-pmo cadencias              # o que roda hoje e o que nao, e por que
soteria-pmo rodar                  # roda os itens devidos hoje e imprime
soteria-pmo rodar --forcar reporte # roda um item fora da cadencia dele
soteria-pmo horas --de 2026-09-01 --ate 2026-09-05
soteria-pmo lancar --arquivo proposta.json --aprovado-por "Nome"         # simula
soteria-pmo lancar --arquivo proposta.json --aprovado-por "Nome" --real  # grava
```

Os quatro primeiros nao escrevem no ClickUp. `lancar` e o unico que escreve, e
so com `--real` e o nome de quem aprovou: ele grava uma proposta que uma pessoa
ja leu. Recusa a proposta inteira se duas entradas do mesmo dia se cruzarem,
pula o que ja existe, rele cada entrada e para no primeiro resultado que nao
voltar conferido, sem retentar. `rotina.py` continua sem caminho de escrita.

A proposta e uma lista JSON de `{"dia", "ini", "fim", "task", "desc", "fat",
"tag"}`, com `fat` obrigatorio pelo mesmo motivo do controle 2 abaixo.

### A leitura diaria, rodando sozinha

```
systemctl --user enable --now soteria-pmo.timer
```

Segunda a sexta as 08:30, o horario que o Abner acordou em 03/09: de manha,
recolhendo o que aconteceu ate ali. `Persistent=true` faz a maquina que estava
desligada na hora rodar ao ligar, em vez de pular o dia. A saida vai para
`~/.local/share/soteria-pmo/leitura-diaria.log`.

O timer chama `rodar`, que so le. A escrita continua fora dele.

## A regra que organiza tudo

**O que ja chega estruturado nao passa pelo modelo.** Coleta com script,
interpretacao com o modelo, confirmacao com a pessoa.

**Nenhum dos sete modulos chama modelo.** `reporte.py`, `bolsao.py`, `rh.py`,
`datas.py`, `cronograma.py`, `auditor.py` e a parte deterministica de `horas.py`
leem campo e fazem conta. O que existe de modelo no pacote sao dois pontos, os
dois lendo texto que so uma pessoa escreve:

- `daily.InterpreteLocal`, interpretando transcricao de daily para o motor de
  horas. Entra por um `Protocol`, entao teste e dry run nunca precisam de GPU.
- a **leitura do periodo** no reporte, escrita pelo agente atraves da skill
  `pmo-reporte` e montada por `reporte.com_pre_analise`. Autorizada pelo Max em
  08/09, depois da sugestao do Andre em 04/09.

A separacao entre os dois planos e o que sustenta os dois: o corpo do relatorio
continua auditavel numero a numero, e a leitura chega assinada como leitura,
entre um cabecalho e um rodape fixos. Validar o reporte nunca vira reconferir
aritmetica misturada com opiniao.

A contagem ja esteve errada duas vezes nos artefatos, e por motivos opostos. Os
de 03 e 04/09 diziam cinco de sete e dois pontos de chamada, contando o
`auditor.py`, que nunca chamou modelo nenhum: ele consome a evidencia que o
`daily.py` produziu, o que e outra coisa. Corrigido em 04/09 para seis de sete e
um ponto. Com a leitura do periodo sao dois pontos de novo, e nenhum deles
dentro de modulo.

O criterio nao e estetico. O ClickUp AI foi descartado na casa por custo, 9,1k
creditos, o que ja torna custo por execucao um criterio de decisao aqui. Um
script barato rodando diariamente sobre 8 ou 9 projetos por um ano da uma conta
muito diferente de um agente caro fazendo a mesma coisa.

## Os sete itens

| # | Modulo | O que faz | Cadencia |
|---|---|---|---|
| 1 | `reporte.py` | Relatorio do periodo com dado estruturado, mais a leitura escrita pelo agente | semanal + disparo manual |
| 2 | `cronograma.py` | Log de projetos sem horas apontadas, na regua por tipo de trabalho | continua |
| 3 | `auditor.py` | Confere o que foi lancado contra a evidencia e as entradas entre si | diaria, mais o mes fechado |
| 4 | `horas.py` | Propoe lancamentos a partir de evidencia, e pergunta pelo resto | diaria |
| 5 | `bolsao.py` | Consumo do bolsao e projecao de estouro | diaria |
| 6 | `rh.py` | Datas de aniversario, tempo de casa, experiencia, contrato e ferias | diaria |
| 7 | `datas.py` | Guardiao dos prazos das tarefas, mais higiene do card | continua |

Apoio: `clickup.py` (cliente com os controles de escrita), `periodo.py`
(janelas e datacao), `rotina.py` (o que roda quando).

`rotina.py` existe porque os sete tem quatro frequencias diferentes, e tratar
tudo como uma entrega so escondeu, ate 30/08, que so um item exigia
infraestrutura dedicada. Quando o bolsao saiu do tempo real em 31/08, nenhum
passou a exigir.

## Onde os itens viram skill e agente

A fronteira validada com o Andre em 04/09, empacotada:

| Item | Entrega | Arquivo |
|---|---|---|
| 1 reporte | skill `pmo-reporte` | `skills/pmo-reporte/SKILL.md` |
| 2 cronograma | skill `pmo-cronograma` | `skills/pmo-cronograma/SKILL.md` |
| 3 auditor | skill `pmo-auditor` | `skills/pmo-auditor/SKILL.md` |
| 4 horas | agente `pmo-horas` | `agents/pmo-horas.md` |
| 5 bolsao | skill `pmo-bolsao` | `skills/pmo-bolsao/SKILL.md` |
| 6 RH | skill `pmo-rh` | `skills/pmo-rh/SKILL.md` |
| 7 datas | skill `pmo-datas` | `skills/pmo-datas/SKILL.md` |

Um agente so, com varias capacidades, que e como o Andre desmontou a contagem de
sete: sete e numero de funcionalidade, nao de processo. `soteria-pmo-instalar`
copia as skills para `~/.claude/skills` e os agentes para `~/.claude/agents`,
sem nunca sobrescrever o que a pessoa ja tem com aquele nome.

## O que nada aqui faz

- **Nao lanca hora sem aprovacao.** `dry_run` e o padrao do cliente, `Aprovacao`
  e obrigatoria em toda escrita, `lancar` simula sem `--real`, e `rotina.py`
  nao tem caminho de escrita.
- **Nao fatura o que nao sabe o que foi.** Janela de evidencia sem atividade
  identificada sai nao faturavel e vira pergunta.
- **Nao manda relatorio ao cliente.** Entrega no nivel 2: produz, o Max valida e
  envia. O nivel 3 foi recusado em 24/06 e isso viaja como campo no artefato.
- **Nao infere trabalho de aba de navegador ou processo aberto.** Navegador pesa
  pouco na confianca justamente porque prova que uma pagina estava aberta, nao
  que houve trabalho.
- **Nao julga volume de horas.** O auditor diz o que a evidencia mostra e o que
  ela nao alcanca. Nenhum veredito acusa erro.

## As tres coisas que este pacote se recusa a fazer, e por que

**1. Dia sem evidencia nao vira zero, vira pergunta.**

Reconstruir o que uma pessoa fez a partir de evidencia de maquina capturou 39,1h
de 130,1h no primeiro ciclo e 54h de 89,5h no segundo. Os dias 04 e 05/08
voltaram sem commit, sem sessao e sem nota, e eram dias normais de planejamento
e pesquisa. Zero e pergunta tem a mesma forma no dado e sentido oposto, e o que
fechou aquela lacuna foram sete prints de transcricao da daily, nao artefato de
maquina.

Por isso `Apuracao.cobertura` compara o proposto com o esperado do periodo e
nunca consigo mesmo. Dividir o achado pelo achado da 100% sempre, e e esse
numero confortavel que esconde a lacuna.

**2. Card parado nao vira "abandonado".**

Silencio no ClickUp e igual para trabalho que nao andou e para trabalho que
andou e nao foi apontado. `cronograma.py` declara essa ambiguidade em todo
alerta em vez de escolher a leitura acusatoria, porque cobrar quem estava
trabalhando e o jeito mais rapido de o sistema inteiro ser desligado.

Pela mesma razao a unidade e o **projeto**, e nao a tarefa. Um dev que larga uma
tarefa e vai para a proxima do mesmo projeto nao e projeto parado, e a regua e
por tipo de trabalho: quatro dias uteis sem hora apontada para projeto de
implantacao, dois para chamado e sustentacao.

Isso substituiu uma tentativa anterior de calibrar o ritmo **por pessoa**.
Perguntado em 03/09 quantos dias cada dev costuma passar sem tocar numa tarefa,
o Abner respondeu que nao consegue precisar isso e que individualizar daria
problema. O caminho por pessoa foi apagado em 08/09, e nao deixado ao lado do
novo: nos quatro dias em que os dois conviveram, era o antigo que rodava, e
toda execucao real pedia uma calibragem que ja tinha sido recusada.

O furo que o proprio Abner apontou continua declarado em cada alerta: nem todo
mundo lanca hora todo dia, entao ausencia de lancamento nao separa "nao andou"
de "andou e nao foi apontado". O alerta diz isso em vez de escolher.

**3. Entrada sem rastro nao vira erro.**

O auditor nao ve planejamento, ligacao nem conversa, e foi exatamente ali que
estavam 60% das horas do piloto. "Sem lastro" quer dizer que esta auditoria nao
encontrou evidencia de maquina, e o relatorio diz isso a quem le.

## Os quatro controles de escrita

Nasceram de um incidente: retentar uma chamada que falhara na etapa de tags
criou quatro entradas fantasma e 16 horas cobradas indevidamente. Em
`clickup.py` eles sao a forma do tipo, nao comentario.

1. **Conferencia obrigatoria depois de escrever.** Uma chamada que falha grava
   mesmo assim, entao status de resposta nao decide nada: a releitura decide.
2. **Faturavel sempre explicito.** `Lancamento.faturavel` nao tem default,
   porque omitir o campo na API grava como nao faturavel em silencio.
3. **Escrita precedida de aprovacao.** `Aprovacao` registra quem e o escopo.
4. **Tags em etapa separada.** O formato que o create aceita e o que as tags
   exigem nao sao o mesmo.

### Uma premissa antiga que estava errada

O projeto carregava desde 07/08 que "nao existe edicao nem exclusao de entrada
de tempo". Isso descrevia o conector MCP, nao o ClickUp: existem
`PUT` e `DELETE` em `/v2/team/{team}/time_entries/{id}`.

Por isso `corrigir()` e `remover()` existem. Aprovacao humana continua
obrigatoria, pela razao que se sustenta: horas viram cobranca e a pessoa e a
unica fonte para a parte delas que a maquina nao ve. Nao porque o erro seria
permanente, que era o argumento antigo e cai na primeira consulta a
documentacao.

O que foi medido contra o workspace real, e nao lido na documentacao:

- **08/09/2026:** o `PUT` aceita `description` e `billable`, mas **ignora
  `tags`**, e com tags sozinhas responde 400 TIMEENTRY_060. Etiqueta de entrada
  entra por `POST /team/{id}/time_entries/tags`. A documentacao dizia o
  contrario, e foi a conferencia pos-escrita que pegou.
- **02/10/2026:** o `PUT` aceita `start`, `end` e `duration` e move a entrada.
  `corrigir()` passou a mudar horario por ai.
- **02/10/2026:** em `GET /time_entries`, **`start_date` e `end_date` sao
  exclusivos**. Uma entrada que comeca exatamente no inicio da janela nao vem.
  `entradas()` pede 1ms antes do inicio; sem isso, toda entrada da meia-noite
  sumia da conta do proprio dia, no auditor e no bolsao inclusive.

## Testes

```
python -m pytest -q
```

269 testes, nenhum toca a rede: `httpx.MockTransport` responde por todas as
chamadas e o interprete do modelo entra por `Protocol`.

Os comportamentos criticos foram conferidos por mutacao, e um deles expos um
teste fraco: o de "corroboradas nao sao listadas" passava pelo motivo errado,
porque com tudo corroborado o bloco de excecoes nem renderiza. Vale repetir a
mutacao ao mexer nestes pontos:

- zerar um dia cego em vez de perguntar
- cobertura dividida por si mesma
- lancar com lacuna aberta
- faturavel uniforme
- cronograma com regua unica ou sem distincao de projeto vs chamado
- alerta afirmando abandono
- inversao de datas entre tarefa-mae e subtarefas
- ciclo bimestral de feedback de RH

`docs/fumaca_dado_real.py` roda os modulos sobre as doze tarefas
reais da lista, congeladas como a API as devolveu, porque teste com payload
proprio prova a logica e nao prova as formas que chegam de verdade.

## Duas classes de constante, e so uma pode estar errada em silencio

Escrevi duas constantes de cabeca nesta base e as duas estavam erradas: o
vocabulario de 13 tags e os status de conclusao. Nenhuma das duas levanta erro
quando errada. Uma tag fora do vocabulario e aceita pelo ClickUp e so faz a
entrada nao casar com o que o relatorio agrupa; um status inexistente faz toda
tarefa entregue ser reportada como aberta. Foram encontradas conferindo o vault,
nao testando, porque os testes afirmavam os mesmos valores inventados.

A defesa e separar as duas classes e tratar cada uma como ela merece.

### Fatos do workspace: tem fonte, e mudar exige conferir a fonte

Descrevem algo que existe fora deste codigo. Errar e falha silenciosa.

| Constante | Onde | Fonte |
|---|---|---|
| `TAGS_DA_CASA` | `clickup.py` | lido da API em 08/09/2026, `GET /team/{id}/time_entries/tags` |
| `NAO_FATURAVEL`, `FATURAVEL`, `ATIVIDADE_NAO_FATURAVEL` | `clickup.py` | mesma nota, convencao de faturamento |
| `WORKFLOW`, `CONCLUIDOS`, `BLOQUEADOS` | `clickup.py` | mesma nota, workflow da pasta AI - Claude |
| `CADENCIAS` | `rotina.py` | mapa de cadencias de 30/08, com o bolsao fora do tempo real por 31/08 |
| `REGUA_PROJETO_DIAS`, `REGUA_CHAMADO_DIAS` | `cronograma.py` | regua acordada com o Abner em 03/09 |
| `TETOS_DE_REFERENCIA` | `bolsao.py` | tetos ditos com firmeza pelo Abner em 03/09; o texto escrito segue pendente |
| `_MARCA_ONTEM` | `periodo.py` | regra de datacao apurada em 07/08 |
| `API`, `BRT` | `clickup.py`, `periodo.py` | API do ClickUp e fuso do time |

**Ao mexer em qualquer uma destas, abrir a fonte.** Nao vale confiar na memoria,
que foi exatamente o que falhou duas vezes.

### Escolhas de desenho: sem verdade externa, ajustar a vontade

Errar aqui produz alerta cedo demais ou tarde demais, nao um numero errado.

| Constante | Onde | O que decide |
|---|---|---|
| `FAIXAS` | `bolsao.py` | 75/90/100% para atencao, critico, estourado |
| `MULTIPLOS` | `cronograma.py` | quantas reguas de silencio viram lembrete, cobranca, escalar |
| `HORIZONTE` | `datas.py` | quantos dias antes um prazo comeca a aparecer |
| `TOLERANCIA` | `auditor.py` | quanto a hora lancada pode divergir da evidencia |
| `CONFIANCA_MINIMA`, `PESO_FONTE` | `horas.py` | o que e proposta duvidosa, e quanto vale cada fonte |
| `ANTECEDENCIA` | `rh.py` | antecedencia de cada tipo de data |
| `DIA_DO_SEMANAL` | `rotina.py` | segunda, para a semana comecar com o reporte da anterior |

### Uma constante que existiu e nao existe mais

`CADENCIA_PADRAO_DIAS` era o placeholder da calibragem de ritmo por pessoa,
apresentada aqui como pergunta em aberto com o Abner. Ela foi respondida em
03/09 e respondida ao contrario: ele nao consegue precisar o ritmo de cada dev
e disse que individualizar daria problema. A regua por tipo de trabalho tomou o
lugar, e o caminho por pessoa foi apagado em 08/09 em vez de ficar ao lado do
novo. Ficar ao lado ja tinha custado quatro dias de execucoes reais pedindo uma
calibragem que ninguem ia dar.
