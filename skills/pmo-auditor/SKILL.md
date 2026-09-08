---
name: pmo-auditor
description: Audita apontamentos de horas do ClickUp contra a evidencia de maquina e contra as outras entradas do mesmo dia. Use quando alguem perguntar se os lancamentos do time estao certos, pedir conferencia de horas antes do faturamento, apontar suspeita de hora duplicada ou sobreposta, ou quiser saber se ha trabalho feito que ninguem lancou. Item 3 dos Agentes PMO da Soteria.
---

# Auditor de apontamentos

Item 3 dos sete. Nao usa modelo: e leitura de campo e aritmetica de relogio.

## Quando roda

**Diariamente**, sobre os ultimos 7 dias, e essa e a entrega principal. A cadencia
mudou em 04/09 por decisao do Andre: uma divergencia achada durante o fechamento
nao da mais para o dev corrigir, entao vai faturada assim mesmo. Achada na manha
seguinte, e correcao de dois minutos.

**Mensalmente**, sobre o mes fechado, com o item `fechamento`. Essa e a leitura do
Andre no faturamento, sobre o que sobrou depois de um mes de correcao diaria.

## Como rodar

```bash
soteria-pmo rodar                      # roda o que e devido hoje
soteria-pmo rodar --forcar auditor     # so o auditor, fora da cadencia
soteria-pmo rodar --forcar fechamento  # o mes fechado, visao do Andre
soteria-pmo cadencias                  # o que roda hoje e o que nao
```

Nao escreve no ClickUp. Produz texto para uma pessoa ler.

## O que ele procura

Contra a evidencia de maquina (commits, sessoes de IA, dailies, notas):

- **corroborada**: as horas batem com o rastro do dia, dentro de 25%.
- **divergente**: batem fora dessa faixa.
- **sem lastro**: nenhum rastro de maquina naquele dia.
- **fora do formato**: descricao vazia ou fora do padrao da casa, que some do
  relatorio de horas faturaveis.
- **horas orfas**: dia com evidencia e nenhum lancamento, o lado da auditoria que
  recupera dinheiro em vez de questionar.

Contra as outras entradas do mesmo dia, tudo aritmetica de relogio:

- **duplicidade**: mesmo inicio e mesma duracao, o bloco lancado duas vezes.
- **contencao**: uma entrada inteira dentro da outra.
- **sobreposicao**: as duas ocupam o mesmo trecho do dia. Conta so o trecho
  disputado, nunca a soma das duas.
- **concentracao**: 8h ou mais numa tarefa so num dia, ou 35h ou mais numa tarefa
  ao longo da janela. Os dois cortes sao exemplos do Andre, nao medicoes, e vivem
  em `CONCENTRACAO_H` e `TAREFA_GRANDE_H`.
- **possivel data trocada**: entrada sem lastro do mesmo tamanho de um dia orfao
  vizinho. Sai como nota, nunca como veredito.

## Como ler o relatorio

Auditoria por excecao: o que corrobora limpo e contado e nao listado. Se voce
sentir falta das entradas corretas, elas estao no contador do topo.

**Nunca apresente um achado como erro ou fraude.** Sem lastro quer dizer que esta
auditoria nao viu evidencia de maquina, e ela nao ve planejamento, ligacao nem
conversa, que foi onde estavam 60% das horas do piloto. Sobreposicao e duplicidade
sao aritmetica: qual das duas entradas esta errada e pergunta para quem lancou.

Quando o relatorio disser que a checagem de horario nao rodou num dia, e porque
os lancamentos daquele dia partem todos do mesmo instante. O ClickUp carimba o
inicio quando a pessoa clica, entao lancamento manual empilha. Nesse dia o relogio
nao diz nada, e o auditor prefere calar a acusar cada par.

## O contexto que ele nao tem

O rigor varia com a relacao com o cliente, e isso nao esta no dado. Projeto no
prazo e cliente satisfeito, uma tarefa generica de 35h passa. Cliente em crise, o
controle aperta. Nunca trate a severidade do achado como absoluta: quem pondera e
o Andre.

## Corrigir depois de auditar

O ClickUp aceita `PUT` e `DELETE` em entrada de tempo, achado confirmado em 03/09.
O Andre autorizou em 04/09 que o auditor **proponha** a correcao de escrita com
confirmacao a cada alteracao. `clickup.corrigir` exige `Aprovacao` explicita e
`dry_run` e o padrao. Nunca escreva sem mostrar antes o que vai mudar e ouvir sim.

## Codigo

`src/soteria_pmo/auditor.py`, testes em `tests/test_auditor_cronograma.py`.
