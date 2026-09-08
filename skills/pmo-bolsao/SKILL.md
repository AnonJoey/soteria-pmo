---
name: pmo-bolsao
description: Vigia o consumo do bolsao de horas contratadas por cliente e projeta estouro em dias uteis. Use quando perguntarem quanto resta do contrato de um cliente, se o bolsao vai estourar, quantas horas foram queimadas no mes, ou pedirem alerta preventivo de teto de horas. Item 5 dos Agentes PMO da Soteria.
---

# Vigia de bolsao

Item 5 dos sete. Nao usa modelo: soma consumo contra teto e projeta.

## Quando roda

Diariamente. Era tempo real ate 31/08, e sair do tempo real foi o que tirou a
exigencia de servidor dedicado do pacote inteiro: nenhum item precisa mais de
infraestrutura propria.

```bash
soteria-pmo rodar --forcar bolsao
```

## As faixas

- **75%**: atencao.
- **90%**: critico.
- **100%**: estourado.

A projecao conta **dias uteis**, nao dias de calendario. Contar calendario le o
projeto queimando horas no fim de semana e antecipa o alerta em dois dias por
semana.

## Os tetos

Valores de referencia levantados na reuniao de 03/09 com o Abner, em
`TETOS_DE_REFERENCIA`: China Gate 100h, Yoshii 160h, Grupo Dimas 30h, Grupo Anjos
cerca de 100h por mes. **Sao referencia, nao confirmacao.** Estao pendentes de
validacao do Max. Se o config do workspace trouxer `horas_contratadas` para o
projeto, esse valor ganha do default. Sempre diga qual dos dois esta em uso.

## Codigo

`src/soteria_pmo/bolsao.py`, testes em `tests/test_periodo_bolsao_datas.py`.
