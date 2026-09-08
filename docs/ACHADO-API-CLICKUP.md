# A API do ClickUp edita e exclui entrada de tempo. O vault dizia que nao.

Pesquisado em 02/09/2026 00:50 na documentacao oficial, contra duas restricoes
que estavam registradas em `proc_ab64e9` desde 07/08 e que moldaram o desenho
dos controles de escrita.

## O que estava registrado

> "Tres limitacoes de MCP que a automacao precisa contornar: tags em entrada de
> tempo nao gravam (formato incompativel), **nao existe edicao nem exclusao de
> entrada**, e uma chamada que falha na tag GRAVA a entrada mesmo assim."

E, na nota de arquitetura, o terceiro controle de escrita:

> "Escrita sempre precedida de aprovacao: **a API nao edita nem exclui entrada
> de tempo**."

## O que a documentacao diz

Editar: `PUT /v2/team/{team_id}/time_entries/{timer_id}`
Excluir: `DELETE /v2/team/{team_id}/time_entries/{timer_id}`

O corpo do PUT aceita exatamente os tres campos que faltavam:

```json
{
  "description": "Updated work",
  "billable": true,
  "tags": [{"name": "nome da tag", "tag_fg": "#FFFFFF", "tag_bg": "#BF55EC"}]
}
```

E aceita `tag_action` com `replace`, `add` ou `remove`.

## Por que isso importa

**A limitacao era do conector MCP, nao da API.** As duas coisas foram confundidas,
e a confusao virou premissa de arquitetura.

Tres consequencias praticas:

1. **As tags das 97 entradas do piloto podem ser corrigidas por programa.** A nota
   de 12/08 lista isso como pendencia manual justamente porque "MCP nao grava, a
   API exige objeto com name". A API exige objeto com `name`, e o PUT aceita.
   O que faltava era o endpoint certo, nao um formato impossivel.

2. **Os quatro lancamentos fantasma de 07/08 eram reversiveis por API.** Foram
   apagados na interface. O incidente das 16h indevidas continua sendo um bom
   motivo para conferir depois de escrever, mas deixa de ser irreversivel.

3. **O terceiro controle de escrita perde a justificativa que tinha e ganha outra.**
   Aprovacao humana antes de lancar continua certa, porque horas viram cobrança e
   a pessoa e a unica fonte para as 60% que a evidencia de maquina nao ve. Nao
   porque o erro seria permanente. A justificativa importa: apresentada como
   "a API nao deixa consertar", ela cai na primeira vez que alguem consultar a
   documentacao, e leva junto a credibilidade do resto.

## O que muda no desenho

O item 4 (Lancamento de horas) ganha caminho de correcao: propor, aprovar,
escrever, conferir, e **corrigir ou remover** o que saiu errado, em vez de so
detectar e pedir intervencao manual na interface.

## Nao verificado

Nao testei as chamadas contra o workspace real: a autorizacao desta madrugada e
so de leitura. O contrato acima e a documentacao oficial, nao medicao. Antes de
usar em producao, testar `PUT` numa entrada descartavel e conferir o retorno.
