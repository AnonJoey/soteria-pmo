---
name: pmo-reporte
description: Gera o relatorio executivo semanal por cliente a partir das tarefas e horas do ClickUp, separando implantacao de sustentacao. Use quando pedirem o reporte da semana, um relatorio de status para cliente, ou o resumo do que foi entregue no periodo. Item 1 dos Agentes PMO da Soteria. O relatorio nunca sai direto ao cliente: o Max valida e envia.
---

# Reporte ao cliente

Item 1 dos sete. Nao usa modelo: preenche template com dado estruturado.

## Quando roda

Semanalmente, na segunda-feira, sobre a semana que fechou, mais disparo manual
quando alguem pedir.

```bash
soteria-pmo rodar --forcar reporte
```

## A regra que nao se negocia

**Entrega no nivel 2.** O agente gera, o Max valida, o Max envia. O nivel 3, em
que a maquina fala com o cliente, foi recusado em 24/06 e a recusa viaja como
campo no artefato. Nunca ofereca enviar, nunca redija como se fosse sair assim.

## O que o relatorio traz

- Bloco de **projetos de implantacao** separado do bloco de **chamados e
  sustentacao**. Sao conversas diferentes e misturar as duas foi o defeito da
  primeira versao.
- Tarefas concluidas, em andamento, e as que passaram o periodo sem apontamento.
- Horas faturaveis e nao faturaveis consolidadas, sempre separadas.

## Pergunta aberta com o Max desde 04/09

O Andre sugeriu que o reporte possa levar uma pre-analise em texto, uma leitura
curta dizendo se o projeto vai bem ou quais situacoes pedem atencao, e no mesmo
minuto se freou: foca no que foi pedido, melhorias depois. Enquanto o Max nao
responder, o reporte continua so preenchendo o template, sem modelo. Se alguem
pedir a pre-analise, diga que ela esta pendente de decisao do Max.

## Codigo

`src/soteria_pmo/reporte.py`, testes em `tests/test_rh_reporte.py`.
