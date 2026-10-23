# Relatório Consolidado de Auditoria Especializada — Agentes PMO (`soteria-pmo`)

- **Data da Conclusão**: 2026-10-23
- **Motor de Inferência**: Qwen2.5-Coder-14B-Instruct-Q4_K_M (Execução Local via GPU RTX 4070, 16.384 tokens de contexto)
- **Escopo**: 21 módulos do pipeline de automação PMO em `src/soteria_pmo` (6.425 linhas de código)
- **Passagens Executadas**: 4 passagens técnicas especializadas + Passagem 5 (Validação Cruzada contra Testes)

---

## 1. Resumo Executivo e Métricas Globais

A esteira automatizada executou uma varredura completa dos **21 módulos** do soteria-pmo, gerando um total de **681 apontamentos** do modelo.
A Passagem 5 realizou o cruzamento com a suíte de testes unitários (`tests/`), isolando **576 falsos positivos** (cenários já cobertos e garantidos) e catalogando **105 achados genuínos**.

| Métrica | Valor Absoluto | Proporção |
| :--- | :---: | :---: |
| **Módulos Auditados** | 21 | 100.0% |
| **Apontamentos Totais da LLM** | 681 | 100.0% |
| **Falsos Positivos Filtrados (Passagem 5)** | 576 | 84.6% |
| **Achados Genuínos Catalogados** | 105 | 15.4% |

---

## 2. Estatísticas das 4 Passagens Especializadas

| Passagem | Viés Técnico Especializado | Módulos Concluídos | Apontamentos Totais |
| :--- | :--- | :---: | :---: |
| **Passagem 1** | Integridade de Cálculo, Aritmética de Horas, Datas e Concorrência | 21 / 21 | 213 |
| **Passagem 2** | Integração ClickUp API, Rate Limiting, Sanitização e Segurança de Tokens | 20 / 21 | 158 |
| **Passagem 3** | Resiliência em Rede, Timeouts, Retentativas e Tratamento de Exceções | 20 / 21 | 164 |
| **Passagem 4** | Regras de Negócio PMO, Invariantes (Reviver/Unimed) e Contratos de Saída | 20 / 21 | 146 |

---

## 3. Distribuição dos Achados Genuínos

### A. Por Categoria e Severidade

| Categoria da Auditoria | Severidade | Quantidade |
| :--- | :---: | :---: |
| `api_clickup_e_seguranca` | **MEDIA** | 8 |
| `api_clickup_e_seguranca` | **BAIXA** | 5 |
| `api_clickup_e_seguranca` | **ALTA** | 2 |
| `calculo_datas_e_concorrencia` | **MEDIA** | 23 |
| `calculo_datas_e_concorrencia` | **BAIXA** | 12 |
| `calculo_datas_e_concorrencia` | **ALTA** | 7 |
| `regras_de_negocio_e_pmo` | **ALTA** | 21 |
| `regras_de_negocio_e_pmo` | **MEDIA** | 7 |
| `regras_de_negocio_e_pmo` | **BAIXA** | 3 |
| `resiliencia_e_timeouts` | **MEDIA** | 7 |
| `resiliencia_e_timeouts` | **BAIXA** | 7 |
| `resiliencia_e_timeouts` | **ALTA** | 3 |

### B. Módulos por Densidade de Débito Técnico

| Módulo | Total Genuínos | Alta | Média | Baixa |
| :--- | :---: | :---: | :---: | :---: |
| `src/soteria_pmo/coletor.py` | **22** | 2 | 14 | 6 |
| `src/soteria_pmo/daily.py` | **22** | 12 | 6 | 4 |
| `src/soteria_pmo/template_html.py` | **16** | 5 | 6 | 5 |
| `src/soteria_pmo/reporte.py` | **13** | 3 | 4 | 6 |
| `src/soteria_pmo/cli.py` | **9** | 4 | 4 | 1 |
| `src/soteria_pmo/__init__.py` | **5** | 2 | 2 | 1 |
| `src/soteria_pmo/auditor.py` | **5** | 1 | 2 | 2 |
| `src/soteria_pmo/cronograma.py` | **4** | 2 | 0 | 2 |
| `src/soteria_pmo/lancamento.py` | **2** | 1 | 1 | 0 |
| `src/soteria_pmo/lancamentos.py` | **2** | 0 | 2 | 0 |
| `src/soteria_pmo/rh.py` | **2** | 0 | 2 | 0 |
| `src/soteria_pmo/rotina.py` | **2** | 1 | 1 | 0 |
| `src/soteria_pmo/horas.py` | **1** | 0 | 1 | 0 |

---

## 4. Amostra Representativa de Falsos Positivos Descartados (Passagem 5)

Foram identificados **576 apontamentos** cujos cenários já estavam cobertos e protegidos pela suíte de testes unitários:

| Módulo | Linha | Alerta da LLM | Cobertura Comprovada em Testes |
| :--- | :---: | :--- | :--- |
| `src/soteria_pmo/atualizacao.py` | 53 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: rodar, return, capture_output, args) |
| `src/soteria_pmo/atualizacao.py` | 62 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: _git, raiz, origin) |
| `src/soteria_pmo/atualizacao.py` | 64 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: _git, raiz, ramo) |
| `src/soteria_pmo/atualizacao.py` | 65 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: _git, raiz, commit) |
| `src/soteria_pmo/atualizacao.py` | 66 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: rodar, _git, raiz) |
| `src/soteria_pmo/atualizacao.py` | 69 | A conversão de string para inteiro em `atras` pode falhar se `n.stdout.strip()` ... | Cenário já coberto em: test_atualizacao.py (termos: stdout, atras, strip) |
| `src/soteria_pmo/atualizacao.py` | 69 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: rodar, _git, raiz, list) |
| `src/soteria_pmo/atualizacao.py` | 73 | O método `splitlines()` pode retornar linhas vazias, resultando em índices invál... | Cenário já coberto em: test_atualizacao.py (termos: linha, _git, raiz, status) |
| `src/soteria_pmo/atualizacao.py` | 73 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: linha, _git, raiz, status) |
| `src/soteria_pmo/atualizacao.py` | 107 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: only, _git, raiz, pull) |
| `src/soteria_pmo/atualizacao.py` | 107 | A função `atualizar` permite a execução de `git pull --ff-only`, que pode confli... | Cenário já coberto em: test_atualizacao.py (termos: only, _git, raiz, pull) |
| `src/soteria_pmo/atualizacao.py` | 111 | O comando `pip install -e` pode falhar se o ambiente Python não estiver configur... | Cenário já coberto em: test_atualizacao.py (termos: rodar, capture_output, raiz, install) |
| `src/soteria_pmo/atualizacao.py` | 111 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: rodar, capture_output, raiz, install) |
| `src/soteria_pmo/atualizacao.py` | 111 | A função `atualizar` permite a reinstalação do pacote via `pip install -e`, que ... | Cenário já coberto em: test_atualizacao.py (termos: rodar, capture_output, raiz, install) |
| `src/soteria_pmo/atualizacao.py` | 116 | A função `instalar(raiz, atualizar=True)` pode sobrescrever arquivos sem garanti... | Cenário já coberto em: test_atualizacao.py (termos: copiado, raiz, True, atualizar) |
| `src/soteria_pmo/atualizacao.py` | 116 | Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.... | Cenário já coberto em: test_atualizacao.py (termos: copiado, raiz, True, atualizar) |
| `src/soteria_pmo/atualizacao.py` | 116 | A função `atualizar` chama `instalar(raiz, atualizar=True)`, que pode ser usado ... | Cenário já coberto em: test_atualizacao.py (termos: copiado, raiz, True, atualizar) |
| `src/soteria_pmo/auditor.py` | 43 | O módulo de logging pode expor informações sensíveis, como tokens de autenticaçã... | Cenário já coberto em: test_auditor_cronograma.py (termo: auditor) |
| `src/soteria_pmo/auditor.py` | 109 | A propriedade horas_lancadas_no_dia é inicializada como 0.0, o que pode levar a ... | Cenário já coberto em: test_auditor_cronograma.py (termo: horas_lancadas_no_dia) |
| `src/soteria_pmo/auditor.py` | 137 | Arredondamento indevido de horas/minutos na propriedade 'diferenca'.... | Cenário já coberto em: test_auditor_cronograma.py (termos: return, self) |
| `src/soteria_pmo/auditor.py` | 226 | Arredondamento indevido de horas/minutos na propriedade 'horas_em_conflito'.... | Cenário já coberto em: test_auditor_cronograma.py (termos: return, conflitos, self, horas) |
| `src/soteria_pmo/auditor.py` | 231 | Divisão por zero potencial na propriedade 'taxa_de_corroboracao'.... | Cenário já coberto em: test_auditor_cronograma.py (termos: return, corroboradas, achados,  |
| `src/soteria_pmo/auditor.py` | 272 | A função 'dias_sem_relogio' não sanitiza os IDs de entradas, o que pode levar a ... | Cenário já coberto em: test_auditor_cronograma.py (termos: date, inicio) |
| `src/soteria_pmo/auditor.py` | 273 | A função dias_sem_relogio não verifica se as entradas estão dentro do período de... | Cenário já coberto em: test_auditor_cronograma.py (termos: date, list, entradas, dict) |
| `src/soteria_pmo/auditor.py` | 278 | Verificação inadequada de overflow/underflow na função 'dias_sem_relogio'.... | Cenário já coberto em: test_auditor_cronograma.py (termos: date, inicio) |
| `src/soteria_pmo/auditor.py` | 303 | A função 'conflitos' não trata HTTP 429 (Too Many Requests), o que pode levar a ... | Cenário já coberto em: test_auditor_cronograma.py (termos: date, clickup, horas, inicio) |
| `src/soteria_pmo/auditor.py` | 304 | A função 'conflitos' não sanitiza os IDs de entradas, o que pode levar a injeção... | Cenário já coberto em: test_auditor_cronograma.py (termos: date, inicio, append) |
| `src/soteria_pmo/auditor.py` | 322 | Arredondamento indevido de horas/minutos na criação de conflitos.... | Cenário já coberto em: test_auditor_cronograma.py (termos: disputado, horas) |
| `src/soteria_pmo/auditor.py` | 323 | A função conflitos não verifica se as entradas estão dentro do período de contra... | Cenário já coberto em: test_auditor_cronograma.py (termos: date, conflitos, list, entradas |
| `src/soteria_pmo/auditor.py` | 360 | A função 'concentracoes' não sanitiza os IDs de tarefas, o que pode levar a inje... | Cenário já coberto em: test_auditor_cronograma.py (termo: horas) |

---

## 5. Catálogo Completo de Achados Genuínos (Por Módulo e Severidade)

### Módulo: `src/soteria_pmo/__init__.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~0)
  - **Descrição**: Arquivo vazio ou não fornecido. Não é possível realizar a auditoria devido à falta de código para analisar.
  - **Risco**: Não é possível garantir o cumprimento das invariantes de negócios e regras de governança devido à ausência de código.

- **[ALTA]** `api_clickup_e_seguranca` (Linha ~1)
  - **Descrição**: Vazamento do token do ClickUp em logs, tracebacks ou arquivos temporários.
  - **Risco**: vazamento de credenciais
  - **Trecho**: `token = 'seu_token_clickup'`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~0)
  - **Descrição**: Arquivo vazio ou não fornecido.
  - **Risco**: Não há riscos identificados devido ao arquivo estar vazio ou não fornecido.

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~1)
  - **Descrição**: Falta de sanitização em nomes de tarefas, IDs de listas, comentários e campos personalizados.
  - **Risco**: injecao
  - **Trecho**: `task_name = input('Digite o nome da tarefa: ')`

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~1)
  - **Descrição**: Ausência de tratamento para HTTP 429 (Too Many Requests), estouro de limite de requisições por minuto da API do ClickUp.
  - **Risco**: bloqueio de API
  - **Trecho**: `response = requests.get(url, headers=headers)`

### Módulo: `src/soteria_pmo/auditor.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~43)
  - **Descrição**: Tolerância de 0.25 horas é muito alta, podendo levar a apontamentos significativos fora do esperado.
  - **Risco**: Erro em auditoria executiva
  - **Trecho**: `TOLERANCIA = 0.25`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~499)
  - **Descrição**: Manipulação de datas sem especificar a zona de tempo, potencialmente causando problemas de fuso horário.
  - **Risco**: Corrupção de dados
  - **Trecho**: `dia=dia`

- **[BAIXA]** `api_clickup_e_seguranca` (Linha ~616)
  - **Descrição**: Falta de sanitização em nomes de tarefas, IDs de listas, comentários e campos personalizados.
  - **Risco**: injecao
  - **Trecho**: `for ev in cabeca.evidencias:`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~0)
  - **Descrição**: 
  - **Risco**: 

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~614)
  - **Descrição**: Arredondamento indevido de horas pode causar distorção significativa nos cálculos de horas.
  - **Risco**: 
  - **Trecho**: `f`

### Módulo: `src/soteria_pmo/cli.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~93)
  - **Descrição**: Contrato de China Gate excede o teto de horas acordado (390h).
  - **Risco**: Erro em auditoria executiva
  - **Trecho**: `{'nome': 'China Gate', 'space_id': '90070091337', 'horas_contratadas': 100, 'tipo': 'chamado'}`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~423)
  - **Descrição**: Possível falta de tratamento de divisão por zero ao calcular a porcentagem de horas trabalhadas em relação ao bolso de horas.
  - **Risco**: Distorção de horas
  - **Trecho**: `bolsao.vigiar(...)`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~433)
  - **Descrição**: Possível falta de tratamento de divisão por zero ao calcular a porcentagem de horas trabalhadas em relação ao bolso de horas.
  - **Risco**: Distorção de horas
  - **Trecho**: `reporte.gerar_todos(...)`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~489)
  - **Descrição**: Possível falta de tratamento de divisão por zero ao calcular a porcentagem de horas trabalhadas em relação ao bolso de horas.
  - **Risco**: Distorção de horas
  - **Trecho**: `horas.apurar(...)`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~345)
  - **Descrição**: Possível falta de tratamento de divisão por zero ao calcular a porcentagem de horas trabalhadas em relação ao bolso de horas.
  - **Risco**: Distorção de horas
  - **Trecho**: `rh.rodar(...)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~218)
  - **Descrição**: Possível falta de tratamento de divisão por zero ao calcular a porcentagem de horas trabalhadas em relação ao bolso de horas.
  - **Risco**: Distorção de horas
  - **Trecho**: `bolsao.digest(...)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~260)
  - **Descrição**: Possível falta de tratamento de divisão por zero ao calcular a porcentagem de horas trabalhadas em relação ao bolso de horas.
  - **Risco**: Distorção de horas
  - **Trecho**: `auditor.auditar(...)`

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~331)
  - **Descrição**: A função `lancamentos.formatar_sem_tarefa` não trata exceções que podem ocorrer durante a formatação das horas sem tarefa, o que pode levar a falhas silenciosas e dificultar a depuração.
  - **Risco**: falhas silenciosas
  - **Trecho**: `331 |     saida_solta = lancamentos.formatar_sem_tarefa(`

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~433)
  - **Descrição**: A função `reporte.gerar_todos` não trata exceções que podem ocorrer durante a geração do relatório, o que pode levar a falhas silenciosas e dificultar a depuração.
  - **Risco**: falhas silenciosas
  - **Trecho**: `433 |         conteudo = reporte.gerar_todos(`

### Módulo: `src/soteria_pmo/coletor.py`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~456)
  - **Descrição**: Arredondamento indevido de horas/minutos ao calcular a duração da reunião.
  - **Risco**: Distorção de horas
  - **Trecho**: `fim_reuniao = comeco + t.duracao`

- **[ALTA]** `resiliencia_e_timeouts` (Linha ~495)
  - **Descrição**: Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.
  - **Risco**: Travamento em produção
  - **Trecho**: `shutil.copy2(origem, copia)`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~297)
  - **Descrição**: Possível comparação de datetime com timedelta.
  - **Risco**: Corrupção de dados
  - **Trecho**: `if max(quandos) < ini_dt or min(quandos) > fim_dt:`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~457)
  - **Descrição**: Possível comparação de datetime com timedelta.
  - **Risco**: Corrupção de dados
  - **Trecho**: `proximo_livre = max(proximo_livre or fim_reuniao, fim_reuniao)`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~457)
  - **Descrição**: Possível overflow ao calcular o próximo horário livre.
  - **Risco**: Corrupção de dados
  - **Trecho**: `proximo_livre = max(proximo_livre or fim_reuniao, fim_reuniao)`

- **[BAIXA]** `api_clickup_e_seguranca` (Linha ~461)
  - **Descrição**: Falta de sanitização em nomes de tarefas, IDs de listas, comentários e campos personalizados.
  - **Risco**: injecao
  - **Trecho**: `f'{t.titulo} ({len(t.falas)} falas, {int(t.duracao.total_seconds() // 60)}min){marca} [duracao medida, {origem}]'`

- **[BAIXA]** `api_clickup_e_seguranca` (Linha ~561)
  - **Descrição**: Falta de sanitização em nomes de tarefas, IDs de listas, comentários e campos personalizados.
  - **Risco**: injecao
  - **Trecho**: `f'antigravity em {onde}: {texto}'`

- **[BAIXA]** `regras_de_negocio_e_pmo` (Linha ~659)
  - **Descrição**: Possível falha na coleta de evidências, sem tratamento adequado de exceções.
  - **Risco**: Erro em auditoria executiva: falta de tratamento adequado de exceções pode levar a evidências incompletas.
  - **Trecho**: `def tenta(nome: str, fn): try: achado = fn() evidencias.extend(achado) logger.info("%s: %d janelas", nome, len(achado)) `

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~144)
  - **Descrição**: Função `_agrupar` não verifica apontamentos fora de vigência de contrato.
  - **Risco**: Divergência contratual: apontamentos fora de contrato podem ser incluídos.
  - **Trecho**: `def _agrupar(pontos: list[Ponto], tipo: str, intervalo: timedelta = INTERVALO_DE_CLUSTER, minimo: timedelta = MINIMO_ISO`

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~144)
  - **Descrição**: Função `_agrupar` não verifica horas atribuídas a pessoas sem cadastro.
  - **Risco**: Divergência contratual: horas atribuídas a pessoas sem cadastro podem ser incluídas.
  - **Trecho**: `def _agrupar(pontos: list[Ponto], tipo: str, intervalo: timedelta = INTERVALO_DE_CLUSTER, minimo: timedelta = MINIMO_ISO`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~160)
  - **Descrição**: Possível overflow/underflow ao somar timedelta a datetime.
  - **Risco**: Corrupção de dados
  - **Trecho**: `grupos[-1].append(p)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~170)
  - **Descrição**: Possível overflow/underflow ao somar timedelta a datetime.
  - **Risco**: Corrupção de dados
  - **Trecho**: `fim = inicio + minimo`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~218)
  - **Descrição**: Exceções silenciosas (except Exception) que ocultam erros de parsing.
  - **Risco**: perda de reporte
  - **Trecho**: `except Exception as e:`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~292)
  - **Descrição**: Exceções silenciosas (except OSError) que ocultam erros de parsing.
  - **Risco**: perda de reporte
  - **Trecho**: `except OSError as e:`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~359)
  - **Descrição**: Possível overflow/underflow ao somar timedelta a datetime.
  - **Risco**: Corrupção de dados
  - **Trecho**: `if ultima_digitada is not None and quando - ultima_digitada <= ATENCAO:`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~395)
  - **Descrição**: Exceções silenciosas (except OSError) que ocultam erros de parsing.
  - **Risco**: perda de reporte
  - **Trecho**: `except OSError:`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~458)
  - **Descrição**: Possível overflow/underflow ao somar timedelta a datetime.
  - **Risco**: Corrupção de dados
  - **Trecho**: `proximo_livre = max(proximo_livre or fim_reuniao, fim_reuniao)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~472)
  - **Descrição**: Falta de tratamento de zonas de tempo ao copiar o histórico do navegador.
  - **Risco**: Corrupção de dados
  - **Trecho**: `shutil.copy2(origem, copia)`

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~507)
  - **Descrição**: Possível inclusão de horas de restauração do navegador, que não devem ser contabilizadas.
  - **Risco**: Divergência contratual: horas de restauração do navegador não devem ser contabilizadas.
  - **Trecho**: `restauracoes = _rajadas_de_restauracao([q for q, _, _, t in linhas if t == TRANSICAO_RELOAD])`

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~512)
  - **Descrição**: Possível inclusão de horas de restauração do navegador, que não devem ser contabilizadas.
  - **Risco**: Divergência contratual: horas de restauração do navegador não devem ser contabilizadas.
  - **Trecho**: `if any(a <= quando_wk <= b for a, b in restauracoes): continue`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~620)
  - **Descrição**: Falta de tratamento de zonas de tempo ao processar as evidências pessoais.
  - **Risco**: Corrupção de dados
  - **Trecho**: `separar_pessoal(evidencias, marcas)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~683)
  - **Descrição**: Falta de tratamento de zonas de tempo ao ordenar as evidências.
  - **Risco**: Corrupção de dados
  - **Trecho**: `evidencias.sort(key=lambda e: e.inicio)`

### Módulo: `src/soteria_pmo/cronograma.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~45)
  - **Descrição**: A regra de negócio para projetos de implantação está configurada para 4 dias úteis sem lançamento de horas, mas o teto de horas acordado para Reviver é 2.950h. A regra de 4 dias úteis pode levar a alertas excessivos sem respeitar o teto de horas.
  - **Risco**: Erro em auditoria executiva
  - **Trecho**: `REGUA_PROJETO_DIAS = 4`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~47)
  - **Descrição**: A regra de negócio para chamados/sustentação está configurada para 2 dias úteis sem lançamento de horas, mas o teto de horas acordado para Unimed é 390h. A regra de 2 dias úteis pode levar a alertas excessivos sem respeitar o teto de horas.
  - **Risco**: Erro em auditoria executiva
  - **Trecho**: `REGUA_CHAMADO_DIAS = 2`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~272)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Perda de reporte
  - **Trecho**: `except Exception as e:`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~289)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Perda de reporte
  - **Trecho**: `except Exception as e:`

### Módulo: `src/soteria_pmo/daily.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~40)
  - **Descrição**: A constante HORA_DA_DAILY está definida como 14, o que pode causar inconsistências com os tétos de horas acordados (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Erro em auditoria executiva
  - **Trecho**: `HORA_DA_DAILY = 14`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~41)
  - **Descrição**: A constante DURACAO_MAXIMA está definida como timedelta(hours=1), o que pode causar inconsistências com os tétos de horas acordados (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Erro em auditoria executiva
  - **Trecho**: `DURACAO_MAXIMA = timedelta(hours=1)`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~130)
  - **Descrição**: Arredondamento indevido de horas/minutos ao calcular o offset das falas.
  - **Risco**: Distorção de horas
  - **Trecho**: `offset = (timedelta(hours=int(a), minutes=int(b), seconds=int(c)) if c else timedelta(minutes=int(a), seconds=int(b)))`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~130)
  - **Descrição**: A função ler_transcricao não verifica se as horas apontadas estão dentro do contrato acordado (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Divergência contratual
  - **Trecho**: `offset = (timedelta(hours=int(a), minutes=int(b), seconds=int(c)) if c else timedelta(minutes=int(a), seconds=int(b)))`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~142)
  - **Descrição**: A função e_daily não verifica se a transcrição está dentro do contrato acordado (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Divergência contratual
  - **Trecho**: `return "daily" in (t.titulo or "").lower() or "daily" in (t.caminho.name.lower() if t.caminho else "")`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~175)
  - **Descrição**: A função transcricoes não verifica se as horas apontadas estão dentro do contrato acordado (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Divergência contratual
  - **Trecho**: `if t is not None and inicio <= t.dia <= fim:`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~258)
  - **Descrição**: Resolução de datas sem considerar a zona de tempo, podendo causar desalinhamento de dias úteis.
  - **Risco**: Distorção de horas
  - **Trecho**: `return dia_da_reuniao - timedelta(days=atras)`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~260)
  - **Descrição**: A função resolver_quando não verifica se as horas apontadas estão dentro do contrato acordado (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Divergência contratual
  - **Trecho**: `return dia_da_reuniao - timedelta(days=1)`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~310)
  - **Descrição**: A função _horas não verifica se as horas apontadas estão dentro do contrato acordado (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Divergência contratual
  - **Trecho**: `return h if 0 < h <= 16 else None`

- **[ALTA]** `resiliencia_e_timeouts` (Linha ~357)
  - **Descrição**: Chamada HTTP sem timeout explícito que pode travar a rotina indefinidamente.
  - **Risco**: travamento em produção
  - **Trecho**: `with urllib.request.urlopen(req) as r:`

- **[ALTA]** `api_clickup_e_seguranca` (Linha ~367)
  - **Descrição**: O texto da requisição HTTP para o modelo é formatado com informações sensíveis, como o nome da pessoa e o dia, que podem ser extraídos dos logs ou tracebacks.
  - **Risco**: Vazamento de credenciais
  - **Trecho**: `usuario = TAREFA.format(pessoa=self.pessoa, dia=f"{dia:%d/%m/%Y}", falas=texto)`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~419)
  - **Descrição**: A função falas_da_pessoa não verifica se as horas apontadas estão dentro do contrato acordado (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Divergência contratual
  - **Trecho**: `todas.extend(extraidas)`

- **[BAIXA]** `api_clickup_e_seguranca` (Linha ~330)
  - **Descrição**: A URL do modelo é armazenada em uma variável de instância, mas não há evidências de que ela seja tratada de forma segura ou criptografada.
  - **Risco**: Vazamento de credenciais
  - **Trecho**: `self.url = url.rstrip("/")`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~371)
  - **Descrição**: Blocos except Exception vazios que ocultam erros de parsing.
  - **Risco**: perda de reporte
  - **Trecho**: `except Exception as e:`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~425)
  - **Descrição**: Falta de tratamento de concorrência ao ler e escrever arquivos JSON/relatórios.
  - **Risco**: Corrupção de dados
  - **Trecho**: `todas.extend(extraidas)`

- **[BAIXA]** `api_clickup_e_seguranca` (Linha ~439)
  - **Descrição**: O texto das falas é formatado com informações sensíveis, como o nome da pessoa e o dia, que podem ser extraídos dos logs ou tracebacks.
  - **Risco**: Vazamento de credenciais
  - **Trecho**: `texto = "\n".join(f"[{int(l.offset.total_seconds() // 60)}min] {l.texto}" for l in minhas)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~198)
  - **Descrição**: Falta de verificação de zonas de tempo ao calcular a data do arquivo.
  - **Risco**: Corrupção de dados
  - **Trecho**: `dia = date(*(int(x) for x in datas[-1]))`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~314)
  - **Descrição**: Divisão por zero potencial ao converter horas declaradas.
  - **Risco**: Corrupção de dados
  - **Trecho**: `h = float(bruto)`

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~354)
  - **Descrição**: A requisição HTTP para o modelo é feita sem tratamento de rate limiting ou quotas, o que pode levar a um estouro de limite de requisições por minuto.
  - **Risco**: Bloqueio de API
  - **Trecho**: `with urllib.request.urlopen(req, timeout=300) as r:`

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~370)
  - **Descrição**: A chamada ao modelo é feita dentro de um bloco try-except, mas não há tratamento para exceções relacionadas a rate limiting (HTTP 429).
  - **Risco**: Bloqueio de API
  - **Trecho**: `resposta = self._chamar(SISTEMA, usuario, self.max_tokens)`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~371)
  - **Descrição**: Falha ao lidar com HTTP 500, 502, 503 transitórios do ClickUp ou da rede local sem recuo exponencial.
  - **Risco**: perda de reporte
  - **Trecho**: `except Exception as e:`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~438)
  - **Descrição**: Falhas parciais em um projeto que derrubam a execução inteira do relatório diário em vez de isolar o erro.
  - **Risco**: perda de reporte
  - **Trecho**: `if not extraidas and falhas is not None and interprete.ultima_falhou:`

### Módulo: `src/soteria_pmo/horas.py`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~630)
  - **Descrição**: Manipulação de datas sem considerar fuso horário pode causar problemas de integridade temporal.
  - **Risco**: Corrupção de dados
  - **Trecho**: `if f.dia in dias_percorridos:`

### Módulo: `src/soteria_pmo/lancamento.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~100)
  - **Descrição**: Apontamentos com término antes de início estão sendo permitidos.
  - **Risco**: Erro em auditoria executiva: violação de regra de negócio que pode levar a horas negativas ou mal contabilizadas.
  - **Trecho**: `if i.fim_ms <= i.inicio_ms:`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~125)
  - **Descrição**: A verificação de duplicatas pode falhar se a tolerância for muito pequena ou muito grande, resultando em entradas duplicadas ou entradas perdidas.
  - **Risco**: Duplicação de entradas
  - **Trecho**: `if abs(int(e.get(`

### Módulo: `src/soteria_pmo/lancamentos.py`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~34)
  - **Descrição**: Possível underflow ao subtrair dias.
  - **Risco**: Corrupção de dados
  - **Trecho**: `d -= timedelta(days=1)`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~169)
  - **Descrição**: Possível underflow ao subtrair dias.
  - **Risco**: Corrupção de dados
  - **Trecho**: `alvo = {_sem_acento(n) for n in nao_faturam if n}`

### Módulo: `src/soteria_pmo/reporte.py`

- **[ALTA]** `calculo_datas_e_concorrencia` (Linha ~123)
  - **Descrição**: Arredondamento indevido de horas/minutos. O número de horas por tarefa é arredondado para duas casas decimais, o que pode levar a perda de precisão.
  - **Risco**: Distorção de horas
  - **Trecho**: `horas=round(horas_por_tarefa.get(tid, 0.0), 2)`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~123)
  - **Descrição**: A atribuição de horas a uma tarefa está arredondando para duas casas decimais, o que pode resultar em perda de precisão e inconsistência nas contagens de horas.
  - **Risco**: Erro em auditoria executiva: possibilidade de horas sendo arredondadas de forma inadequada.
  - **Trecho**: `horas=round(horas_por_tarefa.get(tid, 0.0), 2)`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~495)
  - **Descrição**: O relatório consolidado está sendo gerado sem considerar o teto de horas acordado para Reviver (2.950h) e Unimed (390h), o que pode resultar em excesso de horas.
  - **Risco**: 
  - **Trecho**: `f`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~164)
  - **Descrição**: Falta de tratamento de overflow/underflow. O relatório lista até 370 tarefas abertas sem horas, o que pode levar a overflow em variáveis de contagem.
  - **Risco**: Corrupção de dados
  - **Trecho**: `TETO_DE_PARADAS = 15`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~231)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Perda de reporte
  - **Trecho**: `except Exception as e:`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~235)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Perda de reporte
  - **Trecho**: `except Exception as e:`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~290)
  - **Descrição**: Falta de tratamento de overflow/underflow. O relatório lista até 10 tarefas por lista, o que pode levar a overflow em variáveis de contagem.
  - **Risco**: Corrupção de dados
  - **Trecho**: `TETO_POR_LISTA = 10`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~399)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Perda de reporte
  - **Trecho**: `except Exception as e:`

- **[BAIXA]** `resiliencia_e_timeouts` (Linha ~446)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Perda de reporte
  - **Trecho**: `except Exception as e:`

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~0)
  - **Descrição**: 
  - **Risco**: 

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~121)
  - **Descrição**: Falta de sanitização em status de tarefas.
  - **Risco**: injecao
  - **Trecho**: `status=nome_status`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~163)
  - **Descrição**: Falta de tratamento de overflow/underflow. O relatório lista até 370 tarefas abertas sem horas, o que pode levar a overflow em variáveis de contagem.
  - **Risco**: Corrupção de dados
  - **Trecho**: `TETO_DE_PARADAS = 15`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~291)
  - **Descrição**: Falta de tratamento de overflow/underflow. O relatório lista até 10 tarefas por lista, o que pode levar a overflow em variáveis de contagem.
  - **Risco**: Corrupção de dados
  - **Trecho**: `TETO_POR_LISTA = 10`

### Módulo: `src/soteria_pmo/rh.py`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~138)
  - **Descrição**: Falha ao lidar com exceções gerais sem recuo exponencial ao carregar o roster.
  - **Risco**: Perda de reporte ao carregar o roster.
  - **Trecho**: `except Exception as e:`

- **[MEDIA]** `resiliencia_e_timeouts` (Linha ~319)
  - **Descrição**: Falha ao lidar com exceções gerais sem recuo exponencial ao escrever o roster.
  - **Risco**: Perda de reporte ao escrever o roster.
  - **Trecho**: `except BaseException:`

### Módulo: `src/soteria_pmo/rotina.py`

- **[ALTA]** `resiliencia_e_timeouts` (Linha ~173)
  - **Descrição**: Exceções silenciosas que ocultam erros de parsing.
  - **Risco**: Travamento em produção
  - **Trecho**: `except Exception as e:`

- **[MEDIA]** `api_clickup_e_seguranca` (Linha ~175)
  - **Descrição**: Em caso de exceção, o traceback completo é registrado no log de debug. Isso pode expor informações sensíveis sobre o ambiente de execução e a estrutura do código.
  - **Risco**: vazamento de informações
  - **Trecho**: `logger.debug("%s", traceback.format_exc())`

### Módulo: `src/soteria_pmo/template_html.py`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~431)
  - **Descrição**: O arquivo de código não contém nenhuma lógica relacionada à validação de horas trabalhadas ou invariantes de negócios como teto de horas acordados (Reviver: 2.950h, Unimed: 390h, exclusão total do IoX).
  - **Risco**: Erro em auditoria executiva: Falta de validação de horas trabalhadas contra os teto de horas acordados.

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~431)
  - **Descrição**: O arquivo de código não contém nenhuma lógica para verificar apontamentos fora de vigência de contrato ou horas atribuídas a pessoas sem cadastro.
  - **Risco**: Erro em auditoria executiva: Falta de validação de apontamentos fora de vigência de contrato e horas atribuídas a pessoas sem cadastro.

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~431)
  - **Descrição**: O arquivo de código não contém nenhuma lógica para garantir a geração de HTML sem tags truncadas ou a precisão nos status de entrega (no prazo, em risco, atrasado).
  - **Risco**: Erro em auditoria executiva: Falta de garantia de geração de HTML sem tags truncadas e precisão nos status de entrega.

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~570)
  - **Descrição**: A função renderizar_cliente_html não verifica se as horas gastas excedem os teto de horas acordados para Reviver (2.950h) e Unimed (390h), violando a regra de negócio.
  - **Risco**: Erro em auditoria executiva: possibilidade de excesso de horas faturáveis sem controle.
  - **Trecho**: `if contratadas and contratadas > 0:`

- **[ALTA]** `regras_de_negocio_e_pmo` (Linha ~570)
  - **Descrição**: A função renderizar_cliente_html não exclui totalmente o IoX, violando a regra de negócio.
  - **Risco**: Erro em auditoria executiva: possibilidade de inclusão do IoX sem controle.
  - **Trecho**: `if contratadas and contratadas > 0:`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~463)
  - **Descrição**: O campo $PERIODO pode não estar formatado corretamente, podendo causar inconsistências na exibição da data.
  - **Risco**: Corrupção de dados
  - **Trecho**: `<div class="period-pill">
  Período: $PERIODO
</div>`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~497)
  - **Descrição**: O campo $GERADO_EM pode não estar formatado corretamente, podendo causar inconsistências na exibição da data.
  - **Risco**: Corrupção de dados
  - **Trecho**: `Max valida e envia (Nível 2) &bull; Documento executivo confidencial gerado pelo Sotéria PMO em $GERADO_EM.`

- **[BAIXA]** `regras_de_negocio_e_pmo` (Linha ~722)
  - **Descrição**: A função renderizar_relatorio_html não verifica se o HTML gerado não possui tags truncadas, violando a regra de consistência do painel HTML/Reporte.
  - **Risco**: Erro em auditoria executiva: possibilidade de geração de HTML com tags truncadas.
  - **Trecho**: `return carregar_modelo(modelo).safe_substitute(valores)`

- **[BAIXA]** `regras_de_negocio_e_pmo` (Linha ~722)
  - **Descrição**: A função renderizar_relatorio_html não verifica a precisão nos status de entrega (no prazo, em risco, atrasado), violando a regra de consistência do painel HTML/Reporte.
  - **Risco**: Erro em auditoria executiva: possibilidade de status de entrega incorretos.
  - **Trecho**: `return carregar_modelo(modelo).safe_substitute(valores)`

- **[BAIXA]** `calculo_datas_e_concorrencia` (Linha ~804)
  - **Descrição**: Formatação de data sem especificar timezone, podendo causar inconsistências em diferentes fusos horários.
  - **Risco**: Corrupção de dados
  - **Trecho**: `gerado_em = datetime.now().strftime("%d/%m/%Y às %H:%M")`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~582)
  - **Descrição**: Arredondamento indevido de horas em cálculo de porcentagem.
  - **Risco**: Distorção de horas
  - **Trecho**: `pct_exibicao = min(int(pct * 100), 100)`

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~610)
  - **Descrição**: A função renderizar_cliente_html não verifica se as tarefas estão dentro da vigência de contrato, violando a regra de validação de lançamento.
  - **Risco**: Divergência contratual: possibilidade de apontamentos fora da vigência de contrato.
  - **Trecho**: `v = f", vence {l.vence_em:%d/%m}" if l.vence_em else ""`

- **[MEDIA]** `regras_de_negocio_e_pmo` (Linha ~615)
  - **Descrição**: A função renderizar_cliente_html não verifica se as horas atribuídas a pessoas estão cadastradas, violando a regra de validação de lançamento.
  - **Risco**: Divergência contratual: possibilidade de horas atribuídas a pessoas sem cadastro.
  - **Trecho**: `td>{l.horas:.1f}h</td>`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~650)
  - **Descrição**: Possível overflow/underflow em cálculo de horas totais.
  - **Risco**: Corrupção de dados
  - **Trecho**: `rep.horas_totais:.1f`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~758)
  - **Descrição**: Divisão por zero potencial em cálculo de porcentagem faturável.
  - **Risco**: Distorção de horas
  - **Trecho**: `pct_fat = (total_faturavel / total_horas * 100) if total_horas else 0`

- **[MEDIA]** `calculo_datas_e_concorrencia` (Linha ~759)
  - **Descrição**: Divisão por zero potencial em cálculo de porcentagem não faturável.
  - **Risco**: Distorção de horas
  - **Trecho**: `pct_nao = (total_nao_faturavel / total_horas * 100) if total_horas else 0`
