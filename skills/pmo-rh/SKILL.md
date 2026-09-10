---
name: pmo-rh
description: Avisa das datas da equipe da Soteria: aniversario, tempo de casa, inicio e fim de contrato, interrupcao temporaria e os dois feedbacks do primeiro ano. Use quando perguntarem quem faz aniversario, quem esta perto de fechar contrato, quem esta com feedback vencendo, ou pedirem os lembretes de RH da semana. Item 6 dos Agentes PMO da Soteria.
---

# RH e datas da equipe

Item 6 dos sete. Nao usa modelo: e aritmetica de calendario. Passar isso por um
LLM gasta credito para receber uma subtracao de datas.

## Quando roda

Diariamente.

```bash
soteria-pmo rodar --forcar rh
```

## As regras, definidas pelo Max em 08/09/2026

Os termos importam, e o Max pediu explicitamente que mudassem. O contrato da
Soteria nao e CLT, e a versao anterior desta skill usava vocabulario que nao
corresponde a nada no contrato real.

| Evento | Regra | Aviso |
|---|---|---|
| Aniversario | data de nascimento | 7 dias antes **e de novo no dia** |
| Tempo de casa | marcos anuais do inicio de contrato | 7 dias |
| Primeiro feedback | **45 dias** de contrato | 5 dias |
| Segundo feedback | **90 dias** de contrato | 5 dias |
| Interrupcao temporaria | data de inicio negociada | 20 dias |
| Fim de contrato | data de encerramento | 30 dias |

**Nao existe admissao**: o termo e *data de inicio de contrato*.

**Nao existe fim de experiencia**: o contrato nao preve periodo de experiencia.

**Nao existe ferias**: existe *interrupcao temporaria*, negociada, sem prejuizo
do pagamento, com saldo de **20 dias por ano completo de contrato**. O saldo
acumulado aparece junto do evento de tempo de casa.

O aviso de aniversario sai duas vezes por pedido do Max: com 7 dias ele consegue
programar o day off da pessoa, e no dia ele lembra.

### O que mudou e por que

Ate 08/09 a regra era um ciclo bimestral de 60 dias contado a partir do *ultimo
feedback registrado*, com aviso de 15 dias. Isso tinha um defeito estrutural
alem do numero errado: dependia de alguem preencher a data a cada rodada, e sem
ela nao disparava nada. Os dois feedbacks do primeiro ano derivam do inicio do
contrato, que e uma data que ja existe no cadastro.

## A base

Um roster em CSV ou JSON apontado por `roster_rh` no config, com as mesmas
colunas nos dois formatos. O carregador e resiliente de proposito: linha sem nome
e ignorada, data ilegivel vira vazio e nao derruba a pessoa inteira do relatorio.

Colunas aceitas: `nome`, `nascimento`, `inicio_contrato`, `fim_contrato`,
`interrupcao_inicio`, `ultimo_feedback`. Os nomes antigos `admissao` e
`ferias_inicio` continuam sendo lidos, porque recusar uma planilha valida por
causa do cabecalho transformaria dado bom em silencio.

`contrib/rh-modelo.csv` e a planilha vazia para copiar e preencher, com as
colunas na ordem certa. Um teste le esse arquivo pelo proprio carregador, entao
ele nao pode divergir do codigo em silencio.

Pendente com o Max desde 04/09, reafirmado em 08/09: se as datas ficam como campo
no ClickUp ou seguem na planilha. O aniversario **ja existe** no ClickUp e e lido
de la; os demais campos o Abner nao tem, e ele ficou de confirmar com o Max e o
Marcos se sao sequer desejados. Enquanto nao decidirem, a planilha e a fonte.

## Quem usa

Qualquer pessoa da Soteria com acesso ao roster. A skill nao assume um operador
especifico: quem roda ve as datas de toda a equipe do arquivo apontado no config.
Na pratica o destinatario dos avisos e quem faz gestao de pessoas, hoje o Max.

## Codigo

`src/soteria_pmo/rh.py`, testes em `tests/test_rh_reporte.py`.
