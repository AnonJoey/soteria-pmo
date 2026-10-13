# Como editar a página do reporte (guia curto)

A página do reporte é um arquivo HTML. Você muda a aparência nele, sem tocar em Python, e o reporte passa a usar a sua versão.

## Passo a passo

1. Gere o arquivo para editar:

   ```
   soteria-pmo reporte --exportar-modelo
   ```

   Ele grava `~/.soteria-pmo/modelo-reporte.html`. Esse é o seu arquivo.
2. Abra no editor de texto, mude o que quiser e salve.
3. Gere o reporte de novo (`soteria-pmo reporte` ou `soteria-pmo rodar`). Ele já sai com a sua página.

## O que dá para mudar

- **Cores e fonte:** logo no início do arquivo, dentro de `:root { ... }`, ficam os valores `--color-verde`, `--color-amarelo`, `--color-vermelho`, `--color-roxo` e as demais cores. Trocar o valor troca a cor em toda a página.
- **Textos fixos:** títulos, rótulos dos quatro quadros do topo e o rodapé.
- **Ordem e posição dos blocos:** mova os marcadores de lugar.
- **Gráficos e blocos seus:** escreva o HTML, o SVG ou o script direto no arquivo, no lugar que quiser.

## Os marcadores

Um marcador é uma palavra com `$` na frente. O reporte troca cada um pelo valor do período.

| Marcador | O que entra |
|---|---|
| `$TITULO` | Título da página (aba do navegador) |
| `$PERIODO` | Período, por exemplo `28/09/2026 a 04/10/2026` |
| `$HORAS_TOTAIS`, `$HORAS_FATURAVEIS`, `$HORAS_NAO_FATURAVEIS` | Horas do período, por exemplo `18.1h` |
| `$PCT_FATURAVEIS`, `$PCT_NAO_FATURAVEIS` | Percentuais, por exemplo `83%` |
| `$CLIENTES_ATIVOS`, `$SEM_MOVIMENTO_QTD` | Quantidades de clientes |
| `$LEITURA` | Bloco "Leitura do Período", vazio quando não há |
| **`$CARDS`** | Os cartões de cada cliente, com semáforo e tabelas. **Obrigatório** |
| **`$SEM_MOVIMENTO`** | Bloco dos clientes sem movimento. **Obrigatório** |
| `$GERADO_EM` | Data e hora da geração |
| `$CSS` | O estilo padrão. O arquivo exportado já traz o estilo escrito por extenso e não usa este |

Para escrever um cifrão de verdade no texto, use `$$`. Um `$` solto, como em "R$ 100", é mantido.

## O que o reporte garante

- **Os dois marcadores obrigatórios.** Sem `$CARDS` ou `$SEM_MOVIMENTO` o arquivo esconderia clientes do relatório. Nesse caso o reporte usa a página padrão e avisa no log o que faltou. O reporte nunca deixa de sair por causa de um arquivo editado.
- **Arquivo ilegível** (não é texto UTF-8, por exemplo): mesma coisa, página padrão e aviso.
- **Os dados não são marcadores.** Um nome de cliente com `$` dentro aparece como está.
- **Atualizar o pacote não apaga o seu arquivo.** Ele fica em `~/.soteria-pmo/`, fora da pasta instalada.

## Voltar ao padrão

Apague `~/.soteria-pmo/modelo-reporte.html`, ou rode `soteria-pmo reporte --exportar-modelo --forcar` para recomeçar do padrão (isso sobrescreve a sua edição).

## O que este guia não cobre

Os marcadores trazem valores já formatados do período. Um gráfico que precise de dados novos, como horas por cliente ao longo das semanas, exige que o código passe esses dados à página, e isso é uma mudança em Python. Combine com o Jordan quais gráficos você quer.
