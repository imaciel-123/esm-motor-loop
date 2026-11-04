# Experimento ESM-121 — comparação com a investigação inicial

**Mesmo caso e solicitação literal.** Este experimento é independente do produto ESM/ERENIQ; consulta as fontes do caso como corpus, sem alterar os sistemas consultados.

## Corpus primário

1. Snapshot **privado** do Jira ESM-121 (issue, cinco comentários, 22 mudanças de histórico, metadados dos cinco anexos).
2. Nove PRs do repo privado `imaciel-123/esm`: descrições integrais, 39 commits, patches dos arquivos, reviews e comentários (inclusive listas vazias), 18 execuções de workflows, jobs e snapshots de código nos merges #221 e #229.
3. Três documentos originais de referência (governança, loop, relatório de transformação). **Nenhum relatório retrospectivo anterior entra na entrada da LLM.**

Os cinco anexos Jira em si não foram recuperados pela investigação humana original e não entram no recorte comparável; só metadados. O livro Master 1.5.1 não é anexado porque o arquivo excede sozinho o limite de 50 MB. Reviews externos e logs completos de jobs também continuam indisponíveis. A mudança de descrição de 13/10 está resumida no changelog do snapshot, não é transcrição integral dessa edição. O coletor não deve apresentar esses materiais ausentes como examinados.

## Preparação (PowerShell na raiz de spike-llm-vF)

O operador baixa o **ZIP privado** disponibilizado na conversa, sem publicar os dados no repositório. Mantenha-o em Downloads.

```powershell
git fetch origin
git switch feat/esm121-comparable-corpus
git pull --ff-only origin feat/esm121-comparable-corpus

py -3 .\experiments\esm-121\collect_esm121.py --seed "$HOME\Downloads\ESM121_Fontes_Primarias_Jira_e_Referencias.zip" --activate
```

O coletor usa credencial existente do GitHub CLI (`gh auth token`), depois GH_TOKEN/GITHUB_TOKEN, ou Git Credential Manager (`git credential fill`). **Nunca copie tokens nesta conversa.** Apenas consultas GET ao repositório privado; nada é postado no GitHub. Se não houver credencial, a preparação bloqueia antes de ativar o corpus.

O comando só ativa `data/input` depois de conferir nove PRs, 39 commits e pelo menos 18 execuções de workflow. Preserva o antigo `data/input` em `data/archive`. Os resultados anteriores em `data/results` não são alterados.

A saída detalhada e sua proveniência ficam em `data/esm121_manifest.json`.

## Chamada direta à LLM (somente após corpus validado)

O **mesmo** programa da V0 continua responsável por uploads e inferência:

```powershell
py -3 .\direct_baseline.py --dir data/input --question experiments/esm-121/pergunta_original.md --execute
```

Como antes, é obrigatório informar OPENAI_API_KEY no ambiente e digitar ENVIAR. Uma inferência paga; os uploads são separados. A pergunta permanece literal. **Não execute se o materializador falhou**, se houver limitação de contexto ou se o corpus não for o esperado.

## O que será comparado

- Achados da resposta direta da LLM vs. auditoria humana anterior, descoberta por descoberta.
- Evidência citada e verificação independente em fontes primárias; hipótese vs. fato.
- Proveitos de investigação dinâmica vs. análise de um corpus congelado.

As diferenças de modelo, temporização, conjunto de ferramentas e materiais indisponíveis serão declaradas; não alegar experimento controlado perfeito.

**A PR contém só código e a pergunta; fontes Jira, PRs privados e resultados permanecem fora do Git.**

## Teste H0 número 3 — comparação OpenAI × Claude sem novo upload na OpenAI

A implementação adicionada em `dual_provider.py` é distinta do experimento histórico de pergunta original. Ela lê o manifesto da seleção validada em `data/results/esm121-h0-revisado/20261102T133522Z/selecao_53_sem_reupload.json`, **reutiliza os 53 IDs existentes da OpenAI**, recupera e confere os bytes das fontes por SHA-256 e prepara a mesma seleção na Files API do Claude. Nenhuma fonte ou resposta é commitada (`data/` fica fora do Git).

Arquivos DOCX são extraídos para texto antes do envio ao Claude (imagens e elementos não textuais podem ficar fora do corpus Claude). Essa diferença de representação fica registrada com hashes de origem e texto preparado; não alegar equivalência perfeita de parser entre provedores.

Com as chaves definidas apenas no ambiente e o manifesto local presente:

```powershell
py -3 experiments/esm-121/dual_provider.py prepare
py -3 experiments/esm-121/dual_provider.py preflight --max-output-tokens 24000 --budget-usd 5
py -3 experiments/esm-121/dual_provider.py both --max-output-tokens 24000 --budget-usd 5 --execute
py -3 experiments/esm-121/dual_provider.py compare
```

**Os valores 24.000 e US$ 5 são somente exemplos, não limites escolhidos pelo projeto.** A pessoa operadora deve escolher explicitamente orçamento e limite de saída antes do preflight; uma estimativa não constitui teto absoluto de cobrança. A execução paga exige `--execute` e um preflight compatível. O executor conserva resposta, metadados, tokens e marcadores de chamada em `data/`; uma chamada de resultado incerto nunca é repetida automaticamente.

`prepare` envia as fontes à Anthropic, mas não executa inferência. Não faz upload, exclusão ou alteração de arquivos na OpenAI. Verificar a política de dados aplicável antes de enviar documentos a um segundo provedor.

**Limite de validação:** testes automáticos offline não substituem um ensaio real de integração com chaves e corpus válidos. Uma falha de acesso à API ou incompatibilidade de formatos deve bloquear a inferência; nunca ajustar silenciosamente os 53 arquivos.
