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
- OpenAI Master File ID: `file-Ahra6jSXMTMw625SegqSpR`
- Master TXT: `O_Sistema_que_Constroi_o_Software_Master_1.5.1_INTEGRAL.txt`
- Master SHA-256: `baad0b8603753c1bc722874b38ed4a58cd71e12c41c9a43febb6210aef426e66`

A preparação do Claude envia o Master à **Anthropic Files API** apenas quando o operador executar `prepare --with-master`, usando o TXT validado em `Downloads`, cache local ou, opcionalmente, `--master-txt`. Se os 53 arquivos não estiverem preparados, esse comando também os envia à Anthropic. O upload realizado manualmente na interface de chat Claude **não disponibiliza necessariamente um `file_id` na API** e não pode ser presumido como entrada do executor.

## Execução local no PowerShell

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

**Preflight 3B, sem inferência paga:** defina *você* três valores: `--max-output-tokens` (teto técnico de saída), `--budget-usd` (orçamento estimado por provedor) e `--search-token-reserve` (reserva estimada para material recuperado no OpenAI file_search, que não é previsível antes da execução). Não existem escolhas obrigatórias de tamanho de resposta nem limites fixos arbitrários; modelos e custos devem ser avaliados com o corpus real.

```powershell
python experiments/esm-121/dual_provider.py preflight --with-master --max-output-tokens N --budget-usd B --search-token-reserve R
```

Substitua `N`, `B` e `R` por números deliberadamente escolhidos; a linha acima é uma **sintaxe ilustrativa**, não um comando pronto. No preflight, o programa:

1. Confere que a Vector Store OpenAI está `completed`, contém o File ID esperado e que nome/tamanho conferem. Não faz download do `user_data`; portanto não comprova hash remoto.
2. Confere que o TXT do Claude foi preparado com hash igual e que as 53 fontes estão rastreáveis.
3. Consulta `/responses/input_tokens` para a entrada OpenAI e `/messages/count_tokens` com **surrogate inline** das fontes TXT do Claude, pois o contador Anthropic não aceita `document.source=file`. Esta é uma **estimativa**, não contagem exata de documentos.
4. Estima custos considerando margem de 20% de entrada, reserva declarada pelo operador e o adicional de contexto longo do modelo OpenAI quando aplicável. Inclui valor indicativo de **uma** busca; mais buscas custam. Estimativa **não** é teto de cobrança.
5. Registra o fingerprint dos payloads, versão do experimento e limitações separadas por provedor.

Só depois da conferência e autorização explícita será possível executar (a inferência pode ser cobrada):

```powershell
python experiments/esm-121/dual_provider.py both --with-master --max-output-tokens N --budget-usd B --search-token-reserve R --execute
```

O programa não repete automaticamente chamadas incertas ou já realizadas. No modo 3B, se a resposta OpenAI não registrar um resultado recuperado do **arquivo do Master**, preserva o resultado e a marca de chamada, mas **não declara conclusão bem-sucedida**. Não tente repetir sem investigar o ocorrido.

Para inspecionar resultados sem novos custos:

```powershell
python experiments/esm-121/dual_provider.py compare --with-master
```

Sem `--with-master` os comandos de preflight, execução e comparação continuam relativos ao modo 3A; seus resultados não são substituídos pelos de 3B.

## Status de validação

Testes unitários são executados **offline** com simulações das APIs. Eles verificam estrutura de requisições, hashes, proibição de repetição, trilhas separadas e bloqueios. **Ainda não foi realizada integração real ponta a ponta com o corpus do usuário e as duas APIs.** Uma rejeição, limite ou incompatibilidade da API deve bloquear a inferência; não ajustar silenciosamente o corpus ou ignorar ausência de recuperação.

A utilização da Files API do Claude persiste conteúdo no workspace Anthropic; confirme a política de dados apropriada antes do primeiro upload. Não publique tokens, manifestos privados ou respostas no Git.

Referências de API: [OpenAI file_search](https://developers.openai.com/api/docs/guides/tools-file-search), [Claude Files API](https://platform.claude.com/docs/en/build-with-claude/files), [Claude count_tokens](https://platform.claude.com/docs/en/build-with-claude/token-counting).
