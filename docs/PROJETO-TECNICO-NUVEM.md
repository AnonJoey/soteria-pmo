# Projeto tecnico: a rotina dos Agentes PMO na nuvem

Rascunho para aprovacao do tech lead (item 3.2.1.3 do backlog). Cobre o RNF-01 (execucao sem
laptop), o RF-03 (arquivo diario no SharePoint) e o RF-04 (aviso no Teams) da Fase 2. Os requisitos
estao em `REQUISITOS_FASE_2_2026-09-28.md`.

**O que este documento afirma e o que nao.** As secoes 1 e 2 vem do codigo do pacote (versao 1.4.1) e
do que foi lido, so para leitura, no portal Azure em 15/10/2026. Tudo o que depende de acesso que
ainda nao existe esta marcado **A CONFIRMAR** e listado na secao 9. Nada foi criado na nuvem.

## 1. O que roda hoje e o que precisa mudar

| Hoje | Na nuvem |
|---|---|
| `soteria-pmo rodar` num laptop, por agendador local | Disparo agendado 08:30, segunda a sexta, sem maquina ligada |
| Configuracao e token em `~/.soteria-pmo/pmo.json` | Token fora do codigo, no cofre de segredos |
| Relatorio HTML em disco (`reporte --saida-html`) | Arquivo no SharePoint, com nome padronizado |
| Resumo impresso no terminal | Mensagem no Teams com o resumo e o link do arquivo |
| Codigo de saida diferente de zero quando um item falha | Falha vira alerta, nao silencio |

Fatos do pacote que moldam o projeto:

- **Uma dependencia de execucao**: `httpx`. Python 3.11 ou mais novo. Nao precisa de GPU, de banco nem
  de servidor de modelo.
- **O calculo e deterministico.** Extracao do ClickUp, bolsao, cronograma, datas e o HTML saem de
  codigo, sem modelo. O modelo, quando entra, so escreve a leitura curta do periodo.
- **Duas saidas, dois comandos.** `rodar` roda os itens devidos no dia segundo a cadencia (diaria,
  semanal na segunda, mensal no primeiro dia util; fim de semana e feriado do config nao rodam) e
  devolve um resumo em texto. `reporte` gera o HTML do periodo. A Function chama os dois.
- **As rotinas de leitura nao escrevem no ClickUp.** `rodar` e `reporte` abrem o cliente em modo
  simulado (`dry_run=True`). Por isso uma segunda execucao no mesmo dia e segura.
- **A configuracao e um JSON** (`token`, `team_id`, projetos, feriados, tetos) lido de um caminho
  passado por `--config`. Hoje o token vem desse arquivo; ler do ambiente e uma mudanca pequena de
  codigo (secao 7).

## 2. O que existe no Azure da Soteria (lido em 15/10/2026, somente leitura)

- Uma assinatura ativa; quem desenvolve tem papel de Contributor nela. Conceder papeis a uma
  identidade gerenciada exige um Owner.
- Logic Apps ja existem, no plano **Consumo**, com gatilho HTTP, **sem nenhum agendado** e sem
  recorrencia.
- Conexoes de API existentes: SharePoint (num grupo de homologacao, por conta nominal), Office 365,
  OneDrive e outras. **Nao ha conexao de Teams.**
- Nao ha Key Vault, Function nem Foundry. Os provedores `Microsoft.KeyVault` e `Microsoft.App`
  (Container Apps) **nao estao registrados**; `Microsoft.Web` (Functions) esta.
- Nao apareceu trava (lock) na assinatura nem politica que impeca criar recursos.
- **A CONFIRMAR**: tipo do contrato (o plano e "Azure Plan"; se for CSP, o Claude no Foundry nao e
  suportado, ver secao 6).

## 3. Arquitetura proposta

```
Logic App (Recorrencia 08:30 seg a sex, fuso de Sao Paulo)
   |  1. HTTP POST  ---------->  Function "pmo-rotina"  --> ClickUp (so leitura)
   |                                  (Python 3.11, soteria-pmo)
   |  <-- 2. corpo: { html, resumo, dia, itens_com_erro }
   |
   |  3. SharePoint "Criar arquivo"  (Relatorios-Diarios/AAAA-MM/AAAA-MM-DD_Relatorio_PMO_Soteria.html,
   |                                  substituir se existir)
   |  4. Teams "Postar mensagem"      (resumo + link do arquivo)
   |  5. Em caso de falha em 1 a 4:   Teams "Postar mensagem" no canal de operacao com o erro
```

**Por que o Logic App continua sendo o orquestrador.** E a decisao registrada com o tech lead
(29/09): agenda, SharePoint e Teams ficam nos conectores nativos, e o codigo Python fica como uma
chamada. O Logic App sozinho nao executa o pacote Python (**A CONFIRMAR** com TI; os conectores nao
rodam codigo arbitrario alem de JavaScript embutido), por isso o passo 1 e uma Function.

### Onde roda o Python: tres opcoes

| Opcao | Vantagem | Custo |
|---|---|---|
| **A. Azure Function HTTP (recomendada)** | Provedor ja registrado; deploy do pacote como pacote de funcao; plano de consumo | Limite de tempo da chamada (hoje alguns minutos), a medir com dados reais |
| B. Container Apps Job | Sem limite de tempo; imagem propria | Exige registrar `Microsoft.App`, registro de imagens e mais pecas |
| C. Logic App Standard com codigo em linha | Uma peca so | Python parece nao ser suportado no codigo em linha (**A CONFIRMAR** na documentacao da Microsoft) |

A opcao A pede **medir a duracao**: a rotina le o ClickUp de todas as listas configuradas, e o tempo
total ainda nao foi medido num ambiente de nuvem. Se passar do limite, a B e a saida e o restante do
desenho nao muda (o contrato do passo 1 e o mesmo).

## 4. Contrato da Function

`POST /api/rotina` com `{ "dia": "AAAA-MM-DD" }` (opcional; padrao: hoje em America/Sao_Paulo).

Resposta `200`:

```json
{
  "dia": "2026-10-16",
  "html": "<!doctype html>...",
  "resumo": {
    "alertas_criticos": ["..."],
    "bolsoes_em_risco": ["..."],
    "horas_faturadas": 123.5
  },
  "itens_com_erro": []
}
```

Resposta `500` quando `soteria-pmo rodar` terminaria com codigo diferente de zero (hoje: algum item
falhou), com a lista em `itens_com_erro`. O Logic App trata isso como falha (secao 8).

**Mudanca de codigo necessaria.** O `rodar` imprime o resumo como texto para o terminal e o `reporte`
grava o HTML em arquivo; a Function precisa dos dois estruturados e em memoria. A proposta e um modo
`--json` em `rodar` e em `reporte`, sem mudar o comportamento atual. Esse e o unico trecho novo de
logica de negocio do projeto todo.

## 5. SharePoint e Teams

- **Arquivo (RF-03).** Pasta `/Documentos Compartilhados/PMO/Relatorios-Diarios/AAAA-MM/`, arquivo
  `AAAA-MM-DD_Relatorio_PMO_Soteria.html`. A acao "Criar arquivo" com a opcao de substituir deixa a
  reexecucao do dia idempotente: o mesmo nome, o mesmo lugar.
- **Historico com um clique.** A biblioteca ordenada por data ja serve; uma pagina ou visao de
  biblioteca com os ultimos dias e o item 3.3.3 e nao depende de codigo.
- **Mensagem (RF-04).** Cartao com o resumo executivo e o link do arquivo, no chat do responsavel ou
  em canal de operacao. **A CONFIRMAR**: qual dos dois (decisao do PMO) e quem posta.
- **Conta das conexoes.** Hoje a conexao de SharePoint e nominal e nao ha conexao de Teams. As
  conexoes de um Logic App usam uma conta; o recomendado e uma **conta de servico**, para a rotina nao
  parar quando uma pessoa sair ou trocar a senha. Alguem precisa autorizar as conexoes. **A CONFIRMAR**
  com TI.

## 6. O modelo de linguagem na rotina

O calculo nao precisa dele; so a leitura curta do periodo. Duas saidas:

1. **Sem modelo na rotina da nuvem (recomendada para o MVP).** O resumo do passo 4 sai todo do codigo
   deterministico. Nao ha chave de API a guardar nem a pergunta do contrato.
2. **Com modelo.** Dois caminhos: a API da Anthropic por HTTP, com a chave no cofre, ou o Claude no
   Foundry. O segundo nao e suportado em assinatura CSP (documentacao da Microsoft) e **nao ha projeto
   Foundry hoje**. So vale decidir se o PMO considerar a leitura indispensavel.

## 7. Segredos, identidade e configuracao

- **Token do ClickUp**: um segredo no Key Vault. Pede registrar `Microsoft.KeyVault` e criar o cofre
  (Contributor consegue registrar o provedor; **A CONFIRMAR** se a politica da organizacao permite).
- **Leitura pela Function**: referencia de Key Vault nas configuracoes da Function, com identidade
  gerenciada da Function. Dar a ela o papel de leitura de segredos no cofre exige um Owner.
- **Mudanca de codigo**: o pacote passa a ler `token` e `team_id` de variaveis de ambiente quando o
  arquivo de configuracao nao os traz, e a configuracao (projetos, tetos, feriados) vai nas
  configuracoes da Function ou num arquivo no pacote implantado. Nada disso pode ser commitado: o
  repositorio e publico.
- **Nunca em codigo ou em fluxo**: o token nao aparece no desenho do Logic App (nem como parametro).

## 8. Idempotencia, erros e auditoria

- **Idempotencia.** A Function nao escreve no ClickUp; o arquivo tem nome deterministico e e
  substituido; a mensagem do Teams carrega o dia, e a reexecucao do mesmo dia so a repete. Uma
  reexecucao automatica por falha transitoria e, portanto, segura.
- **Reexecucao.** Politica de nova tentativa do Logic App no passo 1 (por exemplo 3 tentativas com
  intervalo crescente); falha persistente cai no escopo de erro.
- **Falha visivel.** Um escopo "em caso de falha" posta no canal de operacao: qual passo, o dia e o
  identificador da execucao. Silencio nao pode significar "deu certo".
- **Auditoria (RNF-01.4).** O historico de execucoes do Logic App guarda cada passo; a Function envia
  seus logs ao Application Insights, com a retencao definida pela TI. Os arquivos diarios no
  SharePoint sao a trilha do conteudo.
- **Feriados.** Hoje `feriados` vem do config; o gatilho roda de segunda a sexta e o `rodar` ja nao
  executa nada em feriado nem em fim de semana. Nesse dia a Function devolve `200` com o resumo vazio
  e o Logic App nao grava arquivo nem avisa (a regra a combinar com o PMO: dia sem rotina nao gera
  mensagem).

## 9. O que falta e quem decide

| Pendencia | Quem | Bloqueia |
|---|---|---|
| Aprovar este projeto (Function + Logic App, sem modelo no MVP) | Tech lead | Todo o resto |
| Site e pasta do SharePoint; conta de servico para as conexoes | TI | 3.3.2, 3.2.2.3 |
| Canal ou chat do Teams para o aviso | PMO | 3.4.3 |
| Um Owner para o papel da identidade gerenciada e para registrar provedores | Owner da assinatura | 3.2.2.2 |
| Tipo do contrato (CSP ou nao) | Quem administra a cobranca | So a opcao 2 da secao 6 |
| Duracao real da rotina (decide Function ou Container Apps Job) | Medicao | Opcao A |

## 10. Plano de trabalho e estimativa

Ligacao com os itens do backlog (horas do plano de 13/10; a estimativa fecha depois da medicao de
duracao):

| Item | O que | Horas |
|---|---|---|
| 3.2.2.1 | Empacotar o pacote para a Function (modo `--json`, leitura de ambiente) | 8 |
| 3.2.2.2 | Cofre de segredos e identidade | 2 |
| 3.2.2.3 | Logic App: recorrencia, reexecucao, escopo de erro | 6 |
| 3.2.2.4 | Logs de auditoria | 3 |
| 3.3.2 | Gravar no SharePoint com o nome padrao | 5 |
| 3.4.2, 3.4.3 | Mensagem e envio ao Teams | 6 |
| 3.2.2.5 | Execucao de ponta a ponta no ambiente de homologacao | 4 |

Ordem: homologacao primeiro (um grupo de recursos proprio, sem tocar na producao), depois a mesma
implantacao na producao. A visao externa para clientes (RF-P01) fica fora: este projeto entrega so a
rotina interna.
