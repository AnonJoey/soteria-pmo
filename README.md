# Agentes PMO

Os sete itens de gestao pedidos pelo Max, construidos como modulos que produzem
texto para uma pessoa ler. Escopo fechado em 31/08/2026, marco de entrega 08/09.

## A regra que organiza tudo

**O que ja chega estruturado nao passa pelo modelo.** Coleta com script,
interpretacao com o modelo, confirmacao com a pessoa.

Cinco dos sete itens nao tocam num LLM em momento nenhum: reporte, bolsao, RH,
guardiao das datas e cronograma leem campos e fazem contas. O modelo aparece em
dois lugares, ambos lendo texto que so um humano escreveu: o motor de horas
interpretando transcricao de daily, e o auditor comparando o que foi dito com o
que foi lancado. Nos dois casos ele entra por um `Protocol`, entao teste e dry
run nunca precisam de GPU.

O criterio nao e estetico. O ClickUp AI foi descartado na casa por custo, 9,1k
creditos, o que ja torna custo por execucao um criterio de decisao aqui. Um
script barato rodando diariamente sobre 8 ou 9 projetos por um ano da uma conta
muito diferente de um agente caro fazendo a mesma coisa.

## Os sete itens

| # | Modulo | O que faz | Cadencia |
|---|---|---|---|
| 1 | `reporte.py` | Relatorio do periodo, preenchendo template com dado estruturado | semanal + disparo manual |
| 2 | `cronograma.py` | Log de divergencias entre ritmo esperado e observado | continua |
| 3 | `auditor.py` | Confere o que foi lancado contra a evidencia, nos dois sentidos | mensal, no fechamento |
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

## O que nada aqui faz

- **Nao lanca hora sem aprovacao.** `dry_run` e o padrao do cliente, `Aprovacao`
  e obrigatoria em toda escrita, e `rotina.py` nao tem caminho de escrita.
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

Pela mesma razao a cadencia e por pessoa. Com regua unica, quem junta a semana
na sexta e marcado como parado na quarta. Quem ainda nao tem calibragem recebe a
regua padrao **com o alerta marcado como nao calibrado**, nunca um default
silencioso. A calibragem real segue em aberto com o Abner.

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
`PUT` e `DELETE` em `/v2/team/{team}/time_entries/{id}`, e o PUT aceita
`description`, `billable` e `tags` no formato `{name, tag_fg, tag_bg}`.

Por isso `corrigir()` e `remover()` existem. Aprovacao humana continua
obrigatoria, pela razao que se sustenta: horas viram cobranca e a pessoa e a
unica fonte para a parte delas que a maquina nao ve. Nao porque o erro seria
permanente, que era o argumento antigo e cai na primeira consulta a
documentacao.

O contrato acima e documentacao oficial, nao medicao: nada foi chamado contra o
workspace real. Antes de usar em producao, testar `PUT` numa entrada
descartavel.

## Testes

```
python -m pytest tests/pmo/ -q
```

252 testes, nenhum toca a rede: `httpx.MockTransport` responde por todas as
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

`docs/agentes-pmo/fumaca_dado_real.py` roda os modulos sobre as doze tarefas
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
| `TAGS_DA_CASA` | `clickup.py` | `Reference/2026-07-30-Formato de lancamento`, lancamentos do Marcos Claudio |
| `NAO_FATURAVEL`, `FATURAVEL`, `ATIVIDADE_NAO_FATURAVEL` | `clickup.py` | mesma nota, convencao de faturamento |
| `WORKFLOW`, `CONCLUIDOS`, `BLOQUEADOS` | `clickup.py` | mesma nota, workflow da pasta AI - Claude |
| `CADENCIAS` | `rotina.py` | mapa de cadencias de 30/08, com o bolsao fora do tempo real por 31/08 |
| `_MARCA_ONTEM` | `periodo.py` | regra de datacao apurada em 07/08 |
| `API`, `BRT` | `clickup.py`, `periodo.py` | API do ClickUp e fuso do time |

**Ao mexer em qualquer uma destas, abrir a fonte.** Nao vale confiar na memoria,
que foi exatamente o que falhou duas vezes.

### Escolhas de desenho: sem verdade externa, ajustar a vontade

Errar aqui produz alerta cedo demais ou tarde demais, nao um numero errado.

| Constante | Onde | O que decide |
|---|---|---|
| `FAIXAS` | `bolsao.py` | 75/90/100% para atencao, critico, estourado |
| `NIVEIS` | `cronograma.py` | dias de silencio para lembrete, cobranca, escalar |
| `HORIZONTE` | `datas.py` | quantos dias antes um prazo comeca a aparecer |
| `TOLERANCIA` | `auditor.py` | quanto a hora lancada pode divergir da evidencia |
| `CONFIANCA_MINIMA`, `PESO_FONTE` | `horas.py` | o que e proposta duvidosa, e quanto vale cada fonte |
| `ANTECEDENCIA` | `rh.py` | antecedencia de cada tipo de data |
| `DIA_DO_SEMANAL` | `rotina.py` | segunda, para a semana comecar com o reporte da anterior |

`CADENCIA_PADRAO_DIAS` em `cronograma.py` e um caso a parte: parece escolha mas
e um **placeholder de um fato que ainda nao foi levantado**, a calibragem de
ritmo por pessoa, em aberto com o Abner. Por isso todo alerta pontuado contra
ele sai marcado como nao calibrado, em vez de aplicar a regua em silencio.
