# Agentes PMO da Sotéria: mapa para o assistente

Este arquivo é lido em toda sessão. Ele existe porque as skills carregam sob
demanda: sem este mapa você vê uma skill de cada vez e nunca o sistema inteiro,
e o que o sistema **não** faz fica invisível, que é o jeito mais fácil de
prometer o que não existe.

## O que é

Sete itens de gestão de projeto e horas sobre o ClickUp, feitos para o Max
Vasconcelos (sócio, área de projetos) pelo Jordan Bernardes. Em homologação
desde 22/09/2026. Não é entrega fechada.

**As skills são instruções, não são o programa.** Quem lê o ClickUp, calcula e
gera o texto é o executável `soteria-pmo`, instalado à parte. Se ele não
responde, nenhuma skill funciona, e o diagnóstico é `soteria-pmo checar`.

## Os sete itens

| Item | Skill ou agente | O que faz | Cadência |
|---|---|---|---|
| 1 | `pmo-reporte` | relatório por cliente, implantação separada de sustentação | semanal |
| 2 | `pmo-cronograma` | alerta de projeto parado, 4 dias úteis em projeto e 2 em chamado | semanal |
| 2.1 | `pmo-datas` | o que vence, o que venceu, higiene do card | diária |
| 3 | `pmo-auditor` | horas: sem descrição, duplicada, sobreposta, tarefa grande | diária |
| 4 | `pmo-horas` (agente) | propõe lançamento a partir de evidência e da daily; lança depois de aprovado | sob demanda |
| 5 | `pmo-bolsao` | consumo contra o teto do cliente | contínua |
| 6 | `pmo-rh` | aniversário, contrato, interrupção, feedbacks de 45 e 90 dias | diária |

Seis não usam modelo nenhum: são conta sobre dado estruturado. O único que lê
texto escrito por pessoa é o agente de horas, que interpreta a transcrição da
daily.

## Comandos

```bash
soteria-pmo checar                    # o que está configurado e o que falta
soteria-pmo rodar                     # o que é devido hoje
soteria-pmo rodar --forcar reporte    # um item fora da cadência
soteria-pmo cadencias                 # o que roda hoje e o que não
soteria-pmo horas --de AAAA-MM-DD --ate AAAA-MM-DD   # só propõe, não grava
soteria-pmo reporte --formato html --saida reporte.html   # reporte em HTML com semáforo
soteria-pmo lancar --arquivo proposta.json --aprovado-por NOME          # simula
soteria-pmo lancar --arquivo proposta.json --aprovado-por NOME --real   # grava no ClickUp
```

O `lancar` só grava com `--real` e com o nome de quem aprovou a proposta. Ele
recusa entrada que se sobrepõe a outra, pula a que já existe e para na primeira
que não conseguir conferir depois de gravar. Nunca lance sem a pessoa ter lido e
aprovado a proposta, e nunca invente o nome de quem aprovou.

O reporte separa **implantação** e **sustentação** (RF-01 da Fase 2). A ordem da
decisão: as listas declaradas no config (`listas_sustentacao`, `listas_projeto`),
depois a marca no nome da lista ou da pasta (chamado, suporte, sustentação,
atendimento, SLA...), e por fim o `tipo` do cliente. É heurística: na dúvida
conta como implantação. Se uma lista cair do lado errado, a correção é declarar
o ID dela no config, não reinterpretar o número.

Config em `~/.soteria-pmo/pmo.json`. O token do ClickUp é o único item
obrigatório e é pessoal: o sistema enxerga exatamente os espaços que o Max
enxerga.

## Os clientes configurados

Sotéria, China Gate, A.Yoshii, Grupo Dimas, Grupo Angelus, Grupo BM2, APET,
Gazin, Concessionária Reviver, Unimed Londrina.

Conta Azul **não é mais cliente** desde 08/09/2026. Se aparecer num extrato
antigo, é registro encerrado, não cliente ativo.

Tetos mensais de sustentação, fechados com o Max e o André em 08/09: Angelus
160h, IoX 160h, China Gate 100h, BM2 100h (gatilho, sem contrato), APET 60h,
Gazin 40h, Dimas 30h. Unimed Londrina tem 390h, mas é **total de projeto**, não
teto mensal. Reviver está sem teto até o Max mandar o cronograma.

## Três regras que não se negociam

**Nada vai para o cliente pelo sistema.** O relatório é gerado para o Max
validar e enviar. Foi decisão do Jordan em 24/06: *"não confio na IA ao ponto de
só enviar direto"*. Se pedirem para mandar direto ao cliente, diga que é o nível
3 e está fora do escopo acordado.

**O sistema não acusa ninguém.** Card parado vira pergunta, não afirmação: pode
ser trabalho que não andou ou trabalho que andou e não foi apontado, e o sistema
não separa os dois. Todo alerta declara essa ambiguidade. Não converta um alerta
em acusação a uma pessoa ao resumir.

**Não monitora máquina de dev.** Descartado pelo André em 08/09 por ser invasivo
em máquina pessoal. A evidência de máquina só existe para quem roda o agente de
horas na própria máquina, sobre o próprio trabalho.

## O que o sistema NÃO faz, e você não deve dizer que faz

Esta seção é a razão principal deste arquivo existir.

**Item 2, acompanhamento de cronograma.** O Max nomeou cinco pontos de atenção
em 24/06. Existe **um**: a régua de projeto parado. Não existem, e não adianta
procurar na skill:

- caminho crítico;
- tarefa abandonada por tarefa (a régua é por projeto, não por tarefa);
- recurso sobrecarregado, a pessoa com N atividades em paralelo;
- camada de portfólio com alocação de pessoas entre projetos.

E ele é **reativo**, não preventivo: avisa depois de 4 dias úteis de silêncio. O
Max pediu aviso antes da situação crítica. Isso é detecção precoce, e chamar de
preventivo seria vender o que não tem.

**Item 1, reporte.** Sai em texto ou em HTML (`--formato html`), com semáforo de
quatro cores: verde, amarelo, vermelho e roxo para teto estourado. As cores
ficam em variáveis no topo do HTML para o design ajustar, mas **ainda não são a
identidade visual oficial** da Sotéria. Não sai em Word nem em slide, que era o
formato pedido. Não aplica tom de voz da marca. Não traz contagem por status do
tipo "3 em rascunho, 6 em análise", nem estado de cronograma dentro do relatório.

**Item 6, RH.** Informa os 20 dias de interrupção acumulados por ano de
contrato. Não sabe quantos dias a pessoa já tirou, porque não há registro de
consumo. Não há saldo. E sem o `rh.csv` preenchido o item declara que não roda.

**Não existe ainda:** camada de rotina e orquestração (as coisas rodam quando
alguém pede), canal de notificação (o resultado só aparece aqui, não vai para
e-mail, Teams ou WhatsApp), e estrutura de parâmetros (os tetos estão dentro do
código, e trocar um exige o Jordan).

Quando perguntarem por qualquer coisa desta seção, diga que não existe e desde
quando está pendente. Não improvise a funcionalidade com outra skill, e não
suavize a ausência.

## Como se portar na homologação

O Max está testando para dizer se **a saída bate com a operação que ele
conhece**. Não é teste de execução. O que ajuda: mostrar a saída crua, apontar
onde o número veio, e registrar quando ele disser que algo está errado. O que
atrapalha: reescrever a saída para parecer melhor, preencher lacuna com
estimativa, ou tratar silêncio do sistema como boa notícia.

Se algo falhar, o erro em si é a informação útil. Reporte o erro, não o contorne.
