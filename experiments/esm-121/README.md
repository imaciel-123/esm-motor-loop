# ESM-121 — investigação comparativa OpenAI × Claude

Experimento independente do produto ESM/ERENIQ. Fontes privadas, hashes, prompts e resultados ficam em `data/`, fora do Git. Nenhuma chamada paga é feita sem `--execute`.

## Corpus e limites de evidência

O corpus primário reconstruído a partir de Jira ESM-121 e GitHub contém 98 fontes inventariadas: 53 arquivos selecionados e observações consolidadas acerca dos outros 45. O experimento direto anterior incluiu snapshots de PRs, commits, testes, workflows, reviews, históricos Jira e três documentos de referência. Os cinco anexos Jira foram representados apenas por metadados, não pelo conteúdo. Reviews externos e logs integrais de jobs não estavam acessíveis.

A investigação utiliza `experiments/esm-121/perguntas_teste3.md`. O livro *O Sistema que Constrói o Software — Master 1.5.1* não integrou a primeira entrada de 53 arquivos; incluí-lo constitui um **novo recorte experimental**, não uma reprodução da baseline.

## Testes separados

| Modo | OpenAI | Claude | Resultado |
| --- | --- | --- | --- |
| **3A — 53 fontes** (padrão, sem flag) | Reutiliza 53 `file_id` já existentes; **não reenvia** | Arquivos referenciados pela Files API; DOCX convertidos para texto | `data/results/.../comparacao_h0_teste3/` |
| **3B — 53 + Master** (`--with-master`) | Mesmos 53 IDs + `file_search` na Vector Store `competencias-esm`; requer recuperação efetiva | Mesmas 53 fontes + Master TXT indexado na Files API do Claude | `data/results/.../comparacao_h0_teste3/com_master/` |

**Diferença fundamental:** `file_search` recupera trechos relevantes do Master; o Claude recebe um documento TXT integral. Não é um teste de acesso ao Master sob condições técnicas idênticas. O TXT local é validado por SHA-256. A Vector Store é verificada por status, ID, nome e tamanho; a API não permite baixar arquivos com purpose `user_data` para conferir seus bytes remotos. Não se pode afirmar que a OpenAI consumiu o livro inteiro.

Configuração fixada para **3B**:

- OpenAI Vector Store: `vs_6aeb93fb388481919fdc34fdacd4ffba`
- OpenAI Master File ID: `file-2J9CuGsQXaiuGG9Mn35ebu`
- Master TXT: `O_Sistema_que_Constroi_o_Software_Master_1.5.1_INTEGRAL.txt`
- Master SHA-256: `baad0b8603753c1bc722874b38ed4a58cd71e12c41c9a43febb6210aef426e66`

A preparação do Claude envia o Master à **Anthropic Files API** apenas quando o operador executar `prepare --with-master`, usando o TXT validado em `Downloads`, cache local ou, opcionalmente, `--master-txt`. Se os 53 arquivos não estiverem preparados, esse comando também os envia à Anthropic. O upload realizado manualmente na interface de chat Claude **não disponibiliza necessariamente um `file_id` na API** e não pode ser presumido como entrada do executor.

## Guia operacional atualizado (04/11/2026)

Este guia é a **fonte de execução para o Teste 3 ESM-121**. As seções antigas 3A/3B abaixo documentam a evolução do experimento; não representam os dois recortes efetivamente concluídos. Não é necessário criar PR, carregar fontes ou rodar preflight para consultar os resultados existentes.

### Ambiente, corpus e pergunta

A partir da raiz do repositório `esm-motor-loop`, no **PowerShell (Windows)**, com Python 3.12 disponível como `python`, use a `main` integrada. O arquivo da pergunta é `experiments/esm-121/perguntas_teste3.md`; as observações sobre os outros 45 itens são lidas de `data/results/esm121-h0-revisado/20261102T133522Z/observacoes_consolidadas_45.txt`. São cinco perguntas integradas: transformação da intenção, acontecimentos decisivos, confrontos entre fontes, aprendizagem incorporada e intervenções verificáveis. O experimento **não depende** do produto operacional ESM/ERENIQ.

A seleção original de 53 arquivos está em `selecao_53_sem_reupload.json`. A execução não deve apagar nem reescrever `data/`, a seleção, `comparacao_h0_teste3/claude_files.json` ou os resultados históricos; dados privados ficam ignorados pelo Git. As credenciais das APIs, quando necessárias para **nova inferência**, devem estar em `OPENAI_API_KEY` ou `ANTHROPIC_API_KEY` no ambiente; **não grave chaves no README ou no terminal compartilhado**.

### A) Testes automatizados offline (sem cobrança)

```powershell
python -m unittest discover -s tests -v
```

Esses testes usam mocks locais. Não enviam documentos nem fazem inferência; verificam a construção de payloads, preservação de hashes, recortes e proteção contra repetição. **PASS offline não equivale a validação das APIs remotas ou dos findings gerados.**

### B) Os dois testes de LLM efetivamente realizados em 04/11/2026

| Execução | Entrada | Modelo / resultado | Pasta local |
| --- | --- | --- | --- |
| OpenAI, **51 fontes + Master** | Recorte `--omit-deleted-references`: 53 originais menos governança e loop operacional; Master 1.5.1 consultado via `file_search` na Vector Store `vs_6aeb93fb388481919fdc34fdacd4ffba` | `gpt-6.1-sol`, **concluído**, `resp_052939170fe8c143006aebb1c9445c87d2b1bca3cf9d0e8532`; 183.786 tokens input e 6.184 output | `comparacao_h0_teste3/com_master_51_fontes/` |
| Claude, **50 fontes sem referências e sem Master** | Recorte `--claude-50-only`: 53 originais menos os três caminhos `reference/`; reuso dos IDs Claude remanescentes sem upload | `claude-sonnet-5-5`, **concluído**, `msg_011CgihChdEHjpuW6u6qDiLm`; 248.522 tokens input e 32.179 output (25.471 thinking) | `comparacao_h0_teste3/claude_50_sem_referencias/` |

**As entradas foram diferentes.** Não há comparação experimental estritamente controlada entre modelos; preservar essa distinção no relatório de comparação. O Master foi consultado por recuperação de trechos na OpenAI; não foi anexado à chamada Claude final. A execução Claude final **não** utilizou `both`.

**Comandos históricos que efetivamente produziram os resultados**, para rastreabilidade; **não rodar novamente na mesma pasta**:

```powershell
# OpenAI: execução concluída; o comando 'both' também tentou Claude,
# que retornou HTTP 404 porque havia arquivos excluídos na Anthropic.
python .\experiments\esm-121\dual_provider.py both --with-master --omit-deleted-references --max-output-tokens 100000 --execute

# Claude: execução posterior isolada e concluída, com recorte diferente.
python .\experiments\esm-121\dual_provider.py claude --claude-50-only --max-output-tokens 100000 --execute
```

O `--max-output-tokens 100000` foi a escolha das execuções históricas, **não é meta de tamanho de relatório nem teto de gasto**. O código requer `--execute` para disparar inferência paga e grava `{provider}.pending.json` antes do POST.

### C) Consultar os resultados sem chamadas aos modelos

```powershell
$base = ".\data\results\esm121-h0-revisado\20261102T133522Z\comparacao_h0_teste3"
notepad (Join-Path $base "com_master_51_fontes\openai_response.md")
notepad (Join-Path $base "claude_50_sem_referencias\claude_response.md")

# Metadados de execução, sem inferência:
python .\experiments\esm-121\dual_provider.py compare --with-master --omit-deleted-references
python .\experiments\esm-121\dual_provider.py compare --claude-50-only
```

Arquivos preservados: `openai_response.md` (texto), `openai_response.json` (resposta API), `openai_master_retrieval.json` (recuperação do Master), `claude_response.md`, `claude_response.json` (resposta API) e `claude.pending.anterior.20261104-194125.json` (tentativa anterior **arquivada**, não uma segunda resposta). O comando `compare` do executor **só imprime metadados de cada recorte**; não avalia automaticamente a qualidade das investigações.

### D) Como executar **outra rodada** do Claude, com identidade e resultado separados (cobrança real)

O executor **não suporta sobrescrever** um resultado: com `claude_response.json` ou `claude.pending.json` presente, bloqueia a tentativa. Não apague o registro de uma resposta concluída, não limpe `data/` e não use `both` para repetir Claude. Para uma nova rodada, **crie um `--folder` novo** com cópias dos três arquivos de configuração locais. Isso reutiliza os IDs remotos existentes e gera um diretório novo para respostas, sem upload:

```powershell
$old = ".\data\results\esm121-h0-revisado\20261102T133522Z"
$new = ".\data\results\esm121-rodada-" + (Get-Date -Format "yyyyMMdd-HHmmss")
if (Test-Path $new) { throw "Pasta de rodada ja existe; nao sobrescrever" }
New-Item -ItemType Directory -Force -Path (Join-Path $new "comparacao_h0_teste3") | Out-Null
Copy-Item (Join-Path $old "selecao_53_sem_reupload.json") $new
Copy-Item (Join-Path $old "observacoes_consolidadas_45.txt") $new
Copy-Item (Join-Path $old "comparacao_h0_teste3\claude_files.json") (Join-Path $new "comparacao_h0_teste3")

# Conferir se os caches referenciados em claude_files.json ainda existem.
# Com ANTHROPIC_API_KEY configurada, inicia UMA chamada Claude paga:
python .\experiments\esm-121\dual_provider.py claude --folder $new --claude-50-only --max-output-tokens 100000 --execute
```

**Atenção:** `claude_files.json` guarda caminhos de cache para os arquivos preparados na rodada original. O exemplo só funciona enquanto esses arquivos locais e os IDs das **50 fontes remanescentes no workspace Anthropic** ainda existirem. Se a API responder 404, não faça `prepare` automaticamente; recupere o arquivo/ID faltante e reavalie o escopo antes de qualquer reupload. A seleção de documentos e as observações são as mesmas, mas **uma nova chamada é uma nova amostra não determinística e pode ter novo custo**.

### E) Falhas, marcadores e prevenção de cobrança duplicada

- Se aparecer `BLOQUEADO: Chamada já realizada ou indeterminada; não repetir`, verifique os arquivos `{provider}.pending.json` e `{provider}_response.json` **na pasta do recorte**. `_response.json` presente: preserve e inspecione o resultado; não reinicie. Apenas `.pending.json`: chamada inconclusiva **do ponto de vista do executor**; não é prova de cobrança, timeout nem resposta.
- Em 04/11/2026, uma primeira tentativa Claude criou `claude.pending.json`; após consentimento humano explícito, o marcador foi **movido** para `claude.pending.anterior.20261104-194125.json` e a segunda chamada concluiu. Isso foi uma exceção controlada com risco reconhecido de custo duplicado, **não uma instrução para apagar marcadores ou repetir automaticamente**.
- Se houver erro HTTP, timeout, falha de rede ou resposta incompleta, interrompa; preserve JSONs e IDs da tentativa. Uma falha após envio pode ter gerado cobrança. **Não infira que 404, erro local, ausência de `.md` ou ausência de resposta JSON são a mesma coisa.**
- Para nova investigação ou avaliação, preserve o par de relatórios original; identifique sempre modelo, prompt, seleção, presença do Master, data, IDs e custos reais informados pelas APIs.

---

## Execução local no PowerShell (histórico das opções 3A/3B — não executar em dados já concluídos)

Use Python 3.12 disponível como `python`; não dependa do launcher `py -3` quando aponta para uma instalação inexistente. Trabalhe com a `main` integrada depois de aprovação humana da PR. O repositório local precisa conter `.git`, e o manifesto deve existir em `data/results/esm121-h0-revisado/20261102T133522Z/selecao_53_sem_reupload.json`. **Os originais das 53 fontes precisam existir localmente** (em `data/input`, cache ou `data/archive`). Arquivos enviados à OpenAI com purpose `user_data` não podem ser baixados pelo executor. As 53 fontes são verificadas por SHA-256 antes de qualquer upload ao Claude. **Não apague nem recrie `data/`**.

Na raiz do repositório:

```powershell
python -m unittest discover -s tests -v
```

Preparar **3A** (envia somente ao Claude os 53 arquivos ainda não cadastrados; reutiliza IDs OpenAI):

```powershell
python experiments/esm-121/dual_provider.py prepare
```

Preparar **3B** (envia apenas o Master adicional se os 53 já estiverem preparados):

```powershell
python experiments/esm-121/dual_provider.py prepare --with-master
```

O script encontra o TXT validado automaticamente no cache ou em `Downloads`; `--master-txt` continua opcional. Este comando verifica SHA-256 antes de enviar o Master. Os IDs Claude ficam em `data/results/.../comparacao_h0_teste3/claude_files.json`; o Master local validado é copiado para `master_integral.txt` dentro dessa mesma área ignorada pelo Git. Nenhum upload é feito à OpenAI.

**Preflight 3B OPCIONAL, sem inferência paga:** defina *você* três valores: `--max-output-tokens` (teto técnico de saída), `--budget-usd` (orçamento estimado por provedor) e `--search-token-reserve` (reserva estimada para material recuperado no OpenAI file_search, que não é previsível antes da execução). Não existem escolhas obrigatórias de tamanho de resposta nem limites fixos arbitrários; modelos e custos devem ser avaliados com o corpus real.

```powershell
python experiments/esm-121/dual_provider.py preflight --with-master --max-output-tokens N --budget-usd B --search-token-reserve R
```

Substitua `N`, `B` e `R` por números deliberadamente escolhidos; a linha acima é uma **sintaxe ilustrativa**, não um comando pronto. No preflight, o programa:

1. Confere que a Vector Store OpenAI está `completed`, contém o File ID esperado e que nome/tamanho conferem. Não faz download do `user_data`; portanto não comprova hash remoto.
2. Confere que o TXT do Claude foi preparado com hash igual e que as 53 fontes estão rastreáveis.
3. Consulta `/responses/input_tokens` para a entrada OpenAI e `/messages/count_tokens` com **surrogate inline** das fontes TXT do Claude, pois o contador Anthropic não aceita `document.source=file`. Esta é uma **estimativa**, não contagem exata de documentos.
4. Estima custos considerando margem de 20% de entrada, reserva declarada pelo operador e o adicional de contexto longo do modelo OpenAI quando aplicável. Inclui valor indicativo de **uma** busca; mais buscas custam. Estimativa **não** é teto de cobrança.
5. Registra o fingerprint dos payloads, versão do experimento e limitações separadas por provedor.

**Execução direta, SEM preflight obrigatório e SEM upload** (a inferência pode ser cobrada):

```powershell
python experiments/esm-121/dual_provider.py both --with-master --max-output-tokens 12000 --execute
```

O preflight é uma ferramenta opcional e não bloqueia a inferência. `--execute` continua obrigatório; o executor usa os IDs existentes e grava um marcador `.pending.json` ANTES de cada chamada paga para impedir repetição acidental. `--max-output-tokens` limita a saída, não a cobrança total. **Atualização 04/11/2026:** a chamada OpenAI real foi concluída e o JSON retornou resultados de `file_search` do Master com ID `file-2J9CuGsQXaiuGG9Mn35ebu`; a ausência de recuperação não é mais uma incerteza desta execução histórica. Não é prova de leitura integral do Master.

O programa não repete automaticamente chamadas incertas ou já realizadas. No modo 3B, se a resposta OpenAI não registrar um resultado recuperado do **arquivo do Master**, preserva o resultado e a marca de chamada, mas **não declara conclusão bem-sucedida**. Não tente repetir sem investigar o ocorrido.

Para inspecionar resultados sem novos custos:

```powershell
python experiments/esm-121/dual_provider.py compare --with-master
```

Sem `--with-master` os comandos de preflight, execução e comparação continuam relativos ao modo 3A; seus resultados não são substituídos pelos de 3B.

## Status de validação

Testes unitários são executados **offline** com simulações das APIs. Eles verificam estrutura de requisições, hashes, proibição de repetição, trilhas separadas e bloqueios. **Em 04/11/2026, as duas chamadas reais foram concluídas nos recortes distintos descritos no guia atualizado acima.** Uma rejeição, limite ou incompatibilidade da API deve bloquear a inferência; não ajustar silenciosamente o corpus ou ignorar ausência de recuperação.

A utilização da Files API do Claude persiste conteúdo no workspace Anthropic; confirme a política de dados apropriada antes do primeiro upload. Não publique tokens, manifestos privados ou respostas no Git.

Referências de API: [OpenAI file_search](https://developers.openai.com/api/docs/guides/tools-file-search), [Claude Files API](https://platform.claude.com/docs/en/build-with-claude/files), [Claude count_tokens](https://platform.claude.com/docs/en/build-with-claude/token-counting).

## Recorte posterior à exclusão manual de duas referências (51 + Master)

O operador removeu **das duas APIs** os arquivos
`reference/ERENIQ_Governanca_Chats_Codex_v1_3_1.docx` e
`reference/Loop_Operacional_Engineering_System_v1.3.docx`.
O manifesto original 53/45, os uploads históricos e o incidente HTTP 404 permanecem preservados.
A opção `--omit-deleted-references` deriva **51 fontes sem reupload** somente para preflight/inferência/comparação.
Os resultados são gravados em `comparacao_h0_teste3/com_master_51_fontes/`,
sem sobrescrever a tentativa anterior em `com_master/`.
O registro `claude_files.json` continua sendo validado pelo manifesto original de 53;
as referências removidas não são enviadas em nenhum dos dois payloads.

```powershell
python .\experiments\esm-121\dual_provider.py both --with-master --omit-deleted-references --max-output-tokens 12000 --execute
```

**Estado histórico atualizado (04/11/2026):** o incidente inicial de indexação foi resolvido antes da chamada paga OpenAI concluída; o Master usado foi `file-2J9CuGsQXaiuGG9Mn35ebu`. A tentativa antiga em `com_master/` continua sendo histórico e não deve ser apagada nem reutilizada.

**Atualização 04/11/2026:** depois da exclusão de uma versão duplicada do Master, o usuário confirmou na interface Storage que a mesma Vector Store contém o arquivo `file-2J9CuGsQXaiuGG9Mn35ebu` (7 MB de índice). O identificador anterior não corresponde mais ao arquivo anexado. A presença na interface não equivale à prova do SHA-256 remoto dos bytes originais; o SHA local do TXT permanece o valor declarado. Não é necessário novo upload para corrigir a referência.

## Claude isolado: 50 fontes, sem referências e sem Master (04/11/2026)

Após o resultado OpenAI já concluído no recorte anterior, o operador excluiu da Anthropic os **três** documentos sob `reference/` e o Master. Para prosseguir **somente no Claude**, use um recorte específico sem reupload:

```powershell
python .\experiments\esm-121\dual_provider.py claude --claude-50-only --max-output-tokens 12000 --execute
```

O recorte usa as **50 fontes restantes** e as observações consolidadas dos 45 itens. Não referencia os três documentos removidos nem o Master, não faz upload e não chama a OpenAI. A referência histórica de 53 arquivos permanece intacta. O `claude_files.json` histórico continua sendo lido para obter os 50 IDs sobreviventes; as exclusões no armazenamento remoto não precisam ser reproduzidas apagando os registros locais. O relatório **já concluído** está em `comparacao_h0_teste3/claude_50_sem_referencias/`, separado da resposta OpenAI em `com_master_51_fontes/` e da tentativa anterior Claude HTTP 404. O bloqueio de repetição do executor permanece ativo. O resultado Claude sem Master e sem referências **não é comparação experimental estritamente equivalente** ao OpenAI já executado com 51 fontes + Master.

`--claude-50-only` só aceita os comandos `claude` e `compare`; rejeita `--with-master`, `both`, `openai` e `prepare`. O teto de tokens de saída informado é escolha do operador e não garante teto financeiro. Se outro ID remoto tiver sido excluído, a API pode responder 404; não repetir automaticamente.
