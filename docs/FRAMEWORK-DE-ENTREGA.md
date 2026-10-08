# Framework de entrega (rascunho para validar com o André e o Max)

Fluxo descrito pelo Max em 06/10/2026 para entregar um agente ou ferramenta ao time, escrito aqui como uma lista de artefatos e portas, para valer para os Agentes PMO e para o que vier depois. **É um rascunho:** as regras marcadas como pergunta ainda precisam de resposta.

## O fluxo, em seis etapas

| # | Etapa | Artefato que prova que ela terminou | Quem aprova |
|---|---|---|---|
| 1 | **Planejamento e requisitos** | Descrição da demanda, quem pediu e para quem, e o que não está no escopo | Max |
| 2 | **Projeto técnico** | Documento curto: problema, desenho, dependências, riscos, o que roda onde, o que lê e o que escreve | André |
| 3 | **MVP** | A menor versão que dá para homologar, com testes e sem escrita não autorizada | André (revisão técnica) |
| 4 | **Homologação com critério de aceite** | Documento de critérios de aceite, escrito antes da homologação, com a medição contra cada critério | Max |
| 5 | **Teste com um dev** | Instalação feita junto, na máquina de um dev, e o relato dele | O dev e o Jordan |
| 6 | **Produção** | Pacote versionado, roteiro de atualização e quem avisa quem | Max |

Correspondência com os status da lista Agentes PMO no ClickUp: ideia, proposta de solução, aprovação com cliente (etapas 1 e 2), planejamento técnico (2), backlog, desenvolvimento (3), homologação (4 e 5), aguardando deploy e publicado ou finalizado (6). Bloqueado vale para qualquer etapa.

## Modelos dos artefatos

**Projeto técnico (etapa 2)**
1. Problema, em duas frases, e para quem.
2. O que entra e o que não entra.
3. Desenho: o que lê, o que escreve, o que roda onde, o que depende de modelo.
4. Segurança: o que a ferramenta pode quebrar e como o dano é contido (simulação por padrão, aprovação nominal, releitura depois de escrever).
5. Riscos e o que ainda não se sabe.
6. Como será medido.

**Critério de aceite (etapa 4)**
Uma tabela com: critério, como se mede, valor esperado, valor medido, atende ou não. **Os critérios vêm do pedido do Max, não da implementação**: a medição dos Agentes PMO contra os critérios do Max de 22/09 achou itens que atendiam, itens que ultrapassavam o pedido e um que estava longe do pedido, e foi isso que orientou o replanejamento.

**Teste com um dev (etapa 5)**
- A instalação é feita **junto**, em tempo real, com a pessoa ao lado.
- Lista de passos que o dev executa sem ajuda e lista dos que precisou de ajuda.
- Tudo o que foi pedido para ele colar ou rodar fica anotado: é o roteiro de atualização do próximo.
- O dev relata o que estranhou. Sem relato, o teste não conta.

## Perguntas em aberto

1. **Quanto dura o teste com um dev?** Na transcrição da reunião saiu "23 dias", que é quase certamente "2 ou 3 dias". Confirmar com o Max.
2. **Quem é o dev do teste dos Agentes PMO?** Foi sugerido alguém com máquina da Sotéria, por ser um ambiente representativo.
3. **O que bloqueia a produção?** Só o aceite do Max, ou também o relato do dev?
4. **O fluxo vale para o que já está em homologação** (cards 3.x e 5.x), ou só para o que começar daqui em diante?

## O que isto muda no que já existe

- Os critérios de aceite dos Agentes PMO existem em forma de medição, não de documento: falta escrevê-los como a tabela acima.
- O roteiro de atualização (`ATUALIZAR.md`) já cumpre o papel do artefato da etapa 6.
- A etapa 5 ainda não aconteceu para nenhum dos sete itens.
