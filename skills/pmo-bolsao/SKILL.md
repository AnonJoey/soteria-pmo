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

Confirmados pelo Max na reuniao de homologacao de 08/09/2026, em
`TETOS_DE_REFERENCIA`. Sao **mensais e de sustentacao**:

| Cliente | Teto mensal |
|---|---|
| Grupo Angelus | 160h |
| IoX | 160h |
| China Gate | 100h |
| Grupo BM2 | 100h, gatilho sem contrato |
| APET | 60h |
| Gazin | 40h |
| Grupo Dimas | 30h |

O BM2 nao tem bolsao contratado. Os 100h sao o numero base que o Max pediu para
usar como gatilho. O Dimas tem 30h de sustentacao mais projetos em paralelo, e a
media real fica em torno de 100h: as duas coisas precisam ser controladas, e cada
cliente tem lista de sustentacao separada das listas de projeto.

### O que nao e teto mensal

`TOTAIS_DE_PROJETO` guarda **Unimed Londrina, 390h**, que e o total de um projeto
de implantacao. Fica separado de proposito: um total de projeto nao reseta na
virada do mes, e compara-lo com consumo mensal daria um alerta que nunca dispara
ou que dispara sempre.

`TETOS_A_CONFIRMAR` guarda **Concessionaria Reviver**, que e projeto sem media de
bolsao. O Max ficou de mandar o cronograma com a previsao mensal. Ate la o vigia
diz que nao ha teto, em voz alta, em vez de calar.

`NAO_MAIS_CLIENTE` guarda **Conta Azul**, que saiu.

### Duas armadilhas ja pagas

O codigo carregou ate 08/09 um teto de 100h para **"Grupo Anjos"**, que nao
existe: a transcricao automatica moeu "Angelus", e o valor era um meio-termo
entre 75 e 150 que ninguem disse. Um teto errado nao levanta erro, so move a
faixa de alerta e faz a projecao sair confiante sobre um numero inventado.

A busca do teto e por **palavra inteira**, nao por substring. Com substring, a
chave curta de um cliente casaria dentro do nome de outro: existe **APET** no
workspace e nao existe "PET", e uma busca frouxa daria a um o teto do outro.

Se o config do workspace trouxer `horas_contratadas` para o projeto, esse valor
ganha do default. Sempre diga qual dos dois esta em uso.

## Quem usa

Qualquer pessoa da Soteria com acesso ao workspace. A skill soma entradas de
tempo **da equipe toda** contra o teto do cliente, entao nao ha operador cujo
consumo pese mais: o bolsao e do projeto, nao de quem roda o comando.

Quem recebe o alerta e quem responde pelo contrato, hoje o Max e o Abner.

## Codigo

`src/soteria_pmo/bolsao.py`, testes em `tests/test_periodo_bolsao_datas.py`.
