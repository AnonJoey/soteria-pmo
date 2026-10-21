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
| China Gate | 100h |
| Grupo BM2 | 100h, gatilho sem contrato |
| APET | 60h |
| Gazin | 40h |
| Grupo Dimas | 30h |

O BM2 nao tem bolsao contratado. Os 100h sao o numero base que o Max pediu para
usar como gatilho. O Abner confirmou em 14/10/2026 que e uma media, nao um limite
contratado, e que e bom ser alertado ao passar de 100h; se os avisos antes disso,
em 75h e 90h, ficam ou saem e decisao do Max, e hoje eles ficam. O Abner tambem
confirmou em 14/10 os numeros do Angelus, China Gate, A.Yoshii, APET e Dimas. O Dimas tem 30h de sustentacao mais projetos em paralelo, e a
media real fica em torno de 100h: as duas coisas precisam ser controladas, e cada
cliente tem lista de sustentacao separada das listas de projeto.

### O que nao e teto mensal: o total do projeto

Reviver e Unimed nao tem teto mensal (Abner, 14/10/2026). O acompanhamento e pelo
**total de horas do projeto**, que nao reseta na virada do mes. Compara-lo com
consumo mensal daria um alerta que nunca dispara ou que dispara sempre, entao o
codigo guarda os dois em tabelas separadas.

Como funciona, com a chave `listas_total` no projeto do config:

- `listas_total` e a lista de IDs das listas do ClickUp que formam o projeto. Nao
  use o espaco inteiro: ele mistura frentes.
- O **previsto** vem, nesta ordem, de `horas_totais` do config (opcional), da soma
  das estimativas das tarefas e das subtarefas dessas listas, e por ultimo da tabela
  de referencia do codigo. O resumo diz qual das tres esta em uso. O **lancado** e a
  soma do tempo lancado nas tarefas.
- As faixas sao as mesmas, 75, 90 e 100% do total. **O vigia do total nao projeta
  data de estouro**: com milhares de horas, a um ritmo mensal, a data sairia anos
  adiante e escrita como dia e mes se leria como prazo. Ele so diz a porcentagem
  e a faixa.
- So o resumo interno traz o total. O reporte ao cliente nao recebe total de projeto.

`TOTAIS_DE_PROJETO` guarda **Unimed Londrina, 390h**, mas e o **ultimo recurso**:
so vale se as tarefas da lista nao tiverem estimativa nem houver `horas_totais`.
O previsto de verdade mora no ClickUp, e o vigia o le antes da tabela. Se o numero
da tabela e o do ClickUp divergirem, diga os dois e qual esta em uso.

Sem `listas_total`, a Reviver e a Unimed saem como "sem teto configurado", em voz
alta, em vez de calar. `TETOS_A_CONFIRMAR` guarda **Concessionaria Reviver** por
esse motivo.

`NAO_MAIS_CLIENTE` guarda **Conta Azul**, que saiu.

### Regras de contrato ditas em 06/10/2026

Vieram da reuniao de 06/10 e foram registradas aqui sem mudar nenhum numero do
codigo. Os nomes saíram da transcricao automatica; os que estao marcados abaixo
precisam de confirmacao antes de virar regra de verdade.

| Regra dita | Onde esta hoje |
|---|---|
| Bolsao de horas na Yoshi, no Grupo Dimas (30h) e no Grupo Angelus | Os tres estao em `TETOS_DE_REFERENCIA` e no config com `horas_contratadas` (Yoshi 160h, Dimas 30h, Angelus 160h) |
| Diferenciar chamado de projeto de implantacao | `tipo` do projeto (`chamado` ou `projeto`) e `listas_sustentacao`, que separa a sustentacao das listas de projeto dentro do mesmo espaco. Hoje so o Angelus tem `listas_sustentacao` |
| A IoX e o unico cliente de escopo fechado | **Nao existe.** O Max confirmou em 21/10/2026 que nao ha cliente IoX (o nome saiu errado na transcricao de 06/10); nao ha cliente de escopo fechado, e `iox` saiu de `TETOS_DE_REFERENCIA`. |

**Pendente de confirmacao, nada alterado:**

1. **Grupo Dimas.** Medido em 08/10: as horas do mes estao todas na lista de chamados (os sprints mensais de "Controle de Acionamentos" nao tem hora no mes). Nao e projeto contado como sustentacao, como foi no Angelus; o estouro contra 30h e real, a menos que parte dessas horas seja projeto. O Max respondeu em 21/10/2026: separar por lista, como no Angelus (`listas_sustentacao`), com a observacao de que o bolsao tambem pode ser usado em projeto quando nao ha atividade de sustentacao especifica.

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

`src/soteria_pmo/bolsao.py`, testes em `tests/test_periodo_bolsao_datas.py` e, para
o total de projeto, `tests/test_bolsao_total.py`. Os parametros do config estao em
`docs/PARAMETROS.md`.
