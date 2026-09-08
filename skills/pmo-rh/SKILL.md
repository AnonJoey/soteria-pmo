---
name: pmo-rh
description: Avisa das datas da equipe: aniversario, tempo de casa, fim de experiencia, fim de contrato, ferias e o ciclo bimestral de feedback. Use quando perguntarem quem faz aniversario, quem esta perto de fechar contrato ou experiencia, quem esta atrasado no feedback, ou pedirem os lembretes de RH da semana. Item 6 dos Agentes PMO da Soteria.
---

# RH e datas da equipe

Item 6 dos sete. Nao usa modelo: e aritmetica de calendario. Passar isso por um
LLM gasta credito para receber uma subtracao de datas.

## Quando roda

Diariamente.

```bash
delegation-core pmo rodar --forcar rh
```

## Antecedencias

- **Aniversario**: 7 dias.
- **Fim de experiencia e fim de contrato**: 30 dias.
- **Ciclo de feedback**: bimestral, 60 dias, com alerta 15 dias antes de vencer.
- **Tempo de casa**: marcos anuais.

## A base

Um roster em CSV ou JSON apontado por `roster_rh` no config, com as mesmas colunas
nos dois formatos. O carregador e resiliente de proposito: linha sem nome e
ignorada, data ilegivel vira vazio e nao derruba a pessoa inteira do relatorio.

Pendente com o Max desde 04/09: se inicio de contrato e ultimo feedback ficam como
campo no ClickUp ou seguem na planilha. Enquanto nao decidirem, a planilha e a
fonte.

## Codigo

`src/delegation_core/pmo/rh.py`, testes em `tests/pmo/test_rh_reporte.py`.
