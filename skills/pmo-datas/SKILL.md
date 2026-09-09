---
name: pmo-datas
description: Guardiao dos prazos das tarefas do ClickUp, com auditoria de higiene do card e deteccao de inversao de datas entre tarefa mae e subtarefa. Use quando perguntarem o que vence essa semana, o que ja venceu, quais cards estao sem descricao ou sem estimativa, ou quando houver suspeita de data invertida na hierarquia. Item 7 dos Agentes PMO da Soteria, subtarefa 3.2.1 do cronograma.
---

# Guardiao das datas

Item 7 dos sete, registrado no ClickUp como subtarefa 3.2.1 do acompanhamento de
cronograma. Nao usa modelo.

## Quando roda

Cadencia continua, todo dia util.

```bash
soteria-pmo rodar --forcar datas
```

## O que vigia

- **Prazos**: o que vence em ate 3 dias e o que ja venceu.
- **Higiene do card**: tarefa sem descricao e tarefa sem estimativa. Sao as duas
  faltas que quebram todo o resto do pacote, porque sem estimativa nao da para
  julgar tamanho e sem descricao a entrada some do relatorio de horas faturaveis.
- **Inversao de hierarquia**: tarefa mae vencendo antes das filhas, e dependencia
  invertida. E defeito estrutural do card, nao atraso de ninguem, e a mensagem
  precisa deixar isso claro.

## Quem usa

Qualquer pessoa da Soteria. A skill le os prazos do workspace inteiro, e nao a
agenda de ninguem em particular: quem roda ve o que vence para o time.

## Codigo

`src/soteria_pmo/datas.py`, testes em `tests/test_periodo_bolsao_datas.py`.
