# Captura da daily

A apuracao de horas precisa da transcricao da daily do dia. No teste de 02/09/2026 a
mesma evidencia de maquina deu **68% de cobertura sem a daily e 98% com ela**, e a
atividade passou de "nao identificada" a nomeada com as palavras ditas na reuniao. Sem
a transcricao, toda hora volta como pergunta.

## Ver o que falta

```bash
soteria-pmo dailies                  # ultimos 14 dias, ate ontem
soteria-pmo dailies --dias 30
soteria-pmo dailies --ate 2026-10-16
```

So le. Lista cada dia util como `ok`, `FALTA` ou `feriado` (feriados vem de `feriados`
no config) e sai com **2** enquanto faltar algum dia, para um agendador ou uma rotina
de sessao notar a diferenca entre "em dia" e "tem dia faltando".

Conta como transcricao uma nota na pasta `evidencia.dailies` que tenha falas no formato
`[m:ss] Nome: fala` e cujo titulo ou nome cite "daily". Uma nota que so **resume** a
reuniao, sem as falas, nao conta: o dia segue faltando. A data que vale e a ultima
data do nome do arquivo (a da reuniao, nao a do dia em que a nota foi escrita).

## Capturar um dia que falta

O texto sai da API de transcricoes do Stream, autenticada pela sessao do Teams que ja
esta aberta num Chrome. **Precisa de um agente com o Chrome conectado** (por exemplo o
Claude Code com a extensao do Chrome). Nao ha como rodar isto sozinho, sem o navegador
logado.

1. No Teams, abra o chat da reuniao e a aba **Recap**. Escolha a data no seletor. Se a
   data nao tem gravacao, o Recap nao mostra video e nao ha o que capturar (feriado,
   reuniao que nao aconteceu).
2. Descubra onde a gravacao esta. O botao `[data-tid="recap-open-in-stream-button"]`
   abre uma aba nova que sai do controle do agente. Intercepte o `window.open` e
   clique nele para ler so o caminho:

   ```js
   window.__cap = [];
   const orig = window.open;
   window.open = (u) => { window.__cap.push(String(u)); return {closed:false, focus(){}, close(){}}; };
   document.querySelector('[data-tid="recap-open-in-stream-button"]').click();
   await new Promise(r => setTimeout(r, 2500));
   window.open = orig;
   decodeURIComponent(new URL(window.__cap[0]).pathname)
   ```

   O caminho tem o dono da gravacao e o nome `Daily - Equipe Dev-AAAAMMDD_HHMMSSUTC-Meeting Recording.mp4`.
   O horario do nome esta em UTC (menos 3 h em Brasilia), o que confirma a hora de inicio.
3. Navegue na mesma aba para `https://<site do dono>/<caminho>?web=1`. O `javascript_tool`
   roda no contexto da pagina de topo, entao o `fetch` so sai autenticado de dentro do SharePoint.
4. Resolva o item pelo caminho e busque a transcricao em JSON:

   ```js
   const base = '/personal/<dono da gravacao>';
   const it = await (await fetch(base + '/_api/v2.0/drive/root:' + encodeURI('<caminho dentro do drive>'), {headers:{accept:'application/json'}})).json();
   const drive = it.parentReference.driveId, id = it.id;
   const lista = await (await fetch(`${base}/_api/v2.1/drives/${drive}/items/${id}/media/transcripts`, {headers:{accept:'application/json'}})).json();
   const bruto = await (await fetch(`${base}/_api/v2.1/drives/${drive}/items/${id}/media/transcripts/${lista.value[0].id}/streamContent?format=json`, {headers:{accept:'application/json'}})).text();
   ```

   Cada entrada tem `text`, `speakerDisplayName`, `startOffset` (nao `startTime`) e `confidence`.
5. Formate como `[m:ss] Nome: fala`, juntando falas seguidas do mesmo falante, e tire o texto do
   navegador: o `javascript_tool` trunca o retorno perto de 900 caracteres, entao injete o texto na
   pagina (`<pre>` no `body`) e leia com `get_page_text`.
6. Grave a nota em `evidencia.dailies` com o titulo `Daily Equipe Dev AAAA-MM-DD transcricao`,
   o inicio e a duracao da reuniao e o que a pessoa declarou. Confira com `soteria-pmo dailies`.

### O que nao funciona

- **Mandar o texto da pagina para um servico local** (um `fetch` para `127.0.0.1`) e uma
  ideia que poupa o passo 5, mas o classificador de permissoes do Claude Code nega: expor um
  servico local a uma pagina da web. Nao contorne; o texto passa pelo agente.
- O botao de download da transcricao pode estar bloqueado pelo organizador. A API de
  transcricoes alcanca o que a sessao ja consegue ver, nada alem disso.
- Listar a pasta das gravacoes da 403. Cada gravacao e endereçada pelo nome, vindo do Teams.

## Validar por uma semana

O criterio do item e "a transcricao da daily entra no vault todo dia util". Rode
`soteria-pmo dailies` toda manha. A semana vale quando cinco dias uteis seguidos aparecem
como `ok` (feriado nao conta contra). Se aparecer `FALTA`, capture o dia pela lista acima e
anote por que ficou para tras.
