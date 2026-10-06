---
name: pmo-reporte
description: Gera o relatorio executivo semanal por cliente a partir das tarefas e horas do ClickUp, separando implantacao de sustentacao, e escreve por cima dele uma leitura curta do periodo. Use quando pedirem o reporte da semana, um relatorio de status para cliente, ou o resumo do que foi entregue no periodo. Item 1 dos Agentes PMO da Soteria. O relatorio nunca sai direto ao cliente: o Max valida e envia.
---

# Reporte ao cliente

Item 1 dos sete. O corpo do relatorio nao usa modelo: preenche template com dado
estruturado. **Voce escreve a leitura que vai por cima dele**, e so ela.

## Quando roda

Semanalmente, na segunda-feira, sobre a semana que fechou, mais disparo manual
quando alguem pedir.

```bash
soteria-pmo rodar --forcar reporte
```

O reporte sai em **HTML**, com semaforo, e o `rodar` grava a pagina em
`~/.soteria-pmo/reportes/` (ou onde `--saida-html` mandar) e so diz no resumo
onde ela ficou. Para o texto puro, `--formato markdown`.

## A regra que nao se negocia

**Entrega no nivel 2.** O agente gera, o Max valida, o Max envia. O nivel 3, em
que a maquina fala com o cliente, foi recusado em 24/06 e a recusa viaja como
campo no artefato. Nunca ofereca enviar, nunca redija como se fosse sair assim.

## O que o relatorio traz

Um reporte por cliente configurado, e nao um do workspace inteiro. A unidade de
um cliente e o **espaco** do ClickUp, nao uma lista: o trabalho dele se espalha
por dezenas de listas dentro do espaco, e medir por uma lista mede uma fatia.

- Bloco de **projetos de implantacao** separado do bloco de **chamados e
  sustentacao**. Sao conversas diferentes e misturar as duas foi o defeito da
  primeira versao. A separacao sai do nome da lista e da pasta, e o `tipo` do
  cliente no config decide quando o nome nao entrega.
- Tarefas concluidas, em andamento, e as que passaram o periodo sem apontamento.
- Horas faturaveis e nao faturaveis consolidadas, sempre separadas.
- Lista sem hora e sem tarefa concluida no periodo nao aparece: o documento e
  executivo, e listar o backlog inteiro do cliente foi como o que aconteceu na
  semana sumiu no meio do que so existe.

Um cliente cujo espaco nao puder ser lido aparece dizendo isso, e nao some: os
outros dez continuam saindo, pela mesma razao que um item quebrado nao pode
virar semana quieta.

## A leitura do periodo, e como escrever

O Andre sugeriu a pre-analise em 04/09 e **o Max aprovou em 08/09**. Ela e a sua
parte do item 1, e a unica parte dele que passa por um modelo.

Fluxo: leia o conteudo com `soteria-pmo reporte --formato markdown`, escreva a
leitura, e gere o reporte final em HTML com
`soteria-pmo reporte --pre-analise "<a leitura>" --saida reporte.html`. Quem monta
em markdown usa `reporte.com_pre_analise(corpo, analise)`. Nos dois formatos o
bloco sai sempre entre o titulo "Leitura do periodo" e um rodape que diz que e
proposta de interpretacao, porque a fronteira entre o que foi contado e o que foi
interpretado nao pode depender da redacao daquele dia.

**Cinco regras, e nenhuma e de estilo.**

1. **So o que esta no relatorio.** Nada de contexto de outra fonte, nada de
   memoria de conversa. Se voce precisa de um fato que o relatorio nao tem, o
   certo e dizer que ele falta.
2. **Fale do projeto, nunca da pessoa.** "A frente de integracao ficou sem
   apontamento nesta semana" e leitura; "fulano nao trabalhou" e acusacao, e a
   evidencia nao sustenta a segunda.
3. **Declare o que voce nao consegue separar.** Tarefa sem hora lancada pode ser
   trabalho que nao andou ou trabalho que andou e nao foi apontado. Toda vez que
   a leitura tocar nisso, diga que sao duas hipoteses.
4. **Curta.** Tres a cinco frases. O que passa disso vira relatorio concorrente
   e o Max passa a validar dois textos.
5. **Sem recomendacao ao cliente.** A entrega e nivel 2: o Max valida e envia.
   Uma leitura que ja propoe acao ao cliente esta escrevendo por ele.

Se o corpo do relatorio sair vazio, nao escreva leitura nenhuma: nao ha o que
ler, e uma leitura sobre nada e a forma mais rapida de inventar.

## Quem usa

Qualquer pessoa da Soteria que precise do status de um cliente. A skill nao
assume um operador especifico: ela le o ClickUp do workspace, nao a maquina de
ninguem.

O destinatario do relatorio, esse sim e nomeado: **o Max valida e envia**. Nada
sai daqui direto para o cliente. Confirmado de novo em 08/09, quando ficou em
aberto com ele se o agente entrega ao cliente ou gera o conteudo para ele mandar.

## Codigo

`src/soteria_pmo/reporte.py`, testes em `tests/test_rh_reporte.py`.
`gerar_todos` percorre os clientes do config, `gerar_consolidado` faz um, e
`gerar` continua servindo o caso de uma lista so.
