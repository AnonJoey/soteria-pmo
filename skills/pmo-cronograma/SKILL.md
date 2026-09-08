---
name: pmo-cronograma
description: Acompanha o ritmo dos projetos no ClickUp e levanta divergencia entre o esperado e o observado antes de virar incendio. Use quando perguntarem se o cronograma esta em dia, se algum projeto travou, quais tarefas estao paradas, ou quando pedirem pontos de atencao do time. Item 2 dos Agentes PMO da Soteria.
---

# Acompanhamento de cronograma

Item 2 dos sete. Nao usa modelo: compara ritmo esperado com observado.

## Quando roda

Cadencia continua, todo dia util.

```bash
soteria-pmo rodar --forcar cronograma
```

## A regua, acertada com o Abner em 03/09

- **4 dias uteis** sem apontamento para projeto de implantacao.
- **2 dias uteis** para chamado e sustentacao.
- O alerta e **por projeto**, nao por dev. Cobrar pessoa foi descartado de
  proposito: e o jeito mais rapido de o sistema inteiro ser desligado.
- **Calibragem por pessoa foi descartada nessa mesma conversa.** Perguntado
  quantos dias cada dev costuma passar sem tocar numa tarefa, o Abner respondeu
  que nao consegue precisar isso e que individualizar daria problema. O modulo
  ainda carrega o caminho antigo, por pessoa, e e ele que a rotina chama hoje:
  `avaliar_projeto` implementa a regua acima e ainda nao foi ligada no lugar de
  `acompanhar`. Ate isso mudar, o log fala em ritmo nao calibrado e pede ao
  Abner uma calibragem que ele ja respondeu que nao existe. Nao repita esse
  pedido para quem perguntar.

## A ambiguidade que todo alerta declara

Silencio no ClickUp e identico para trabalho que nao andou e para trabalho que
andou e nao foi apontado. **Todo alerta tem que declarar que nao consegue separar
as duas hipoteses.** Nunca escreva que uma tarefa foi abandonada, nunca escolha a
leitura acusatoria. A palavra abandonada nao aparece no log e ha teste que falha
se ela voltar.

Tarefa concluida sai do radar. Tarefa bloqueada tambem, porque parada e o
esperado dela. Tarefa sem estimativa gera alerta com a nota de que nao da para
julgar o tamanho.

## Codigo

`src/soteria_pmo/cronograma.py`, testes em `tests/test_auditor_cronograma.py`.
