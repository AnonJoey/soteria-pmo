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

### Regras de contrato ditas em 06/10/2026

Vieram da reuniao de 06/10 e foram registradas aqui sem mudar nenhum numero do
codigo. Os nomes saíram da transcricao automatica; os que estao marcados abaixo
precisam de confirmacao antes de virar regra de verdade.

| Regra dita | Onde esta hoje |
|---|---|
| Bolsao de horas na Yoshi, no Grupo Dimas (30h) e no Grupo Angelus | Os tres estao em `TETOS_DE_REFERENCIA` e no config com `horas_contratadas` (Yoshi 160h, Dimas 30h, Angelus 160h) |
| Diferenciar chamado de projeto de implantacao | `tipo` do projeto (`chamado` ou `projeto`) e `listas_sustentacao`, que separa a sustentacao das listas de projeto dentro do mesmo espaco. Hoje so o Angelus tem `listas_sustentacao` |
| A IoX e o unico cliente de escopo fechado | **Nao esta no codigo como escopo fechado.** `iox` tem 160h mensais em `TETOS_DE_REFERENCIA`, que e a regua de bolsao, e a IoX nao esta no config, entao o vigia nem a le. Escopo fechado se mede contra o total do escopo, como `TOTAIS_DE_PROJETO`, e esse total nao foi informado |

**Pendente de confirmacao, nada alterado:**

1. **IoX.** O nome pode estar errado na transcricao. Se o Max confirmar que e escopo fechado, o teto mensal de 160h sai de `TETOS_DE_REFERENCIA`, entra o total do escopo em `TOTAIS_DE_PROJETO` e a IoX entra no config.
2. **Grupo Dimas.** Medido em 08/10: as horas do mes estao todas na lista de chamados (os sprints mensais de "Controle de Acionamentos" nao tem hora no mes). Nao e projeto contado como sustentacao, como foi no Angelus; o estouro contra 30h e real, a menos que parte dessas horas seja projeto. Essa fronteira e do Max.

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
