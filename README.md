# Spike LLM vF — baseline cognitivo direto

**Objetivo:** uma única chamada de análise ao GPT-6.1 Sol com **arquivos originais** enviados à OpenAI Files API e a pergunta original. Sem M0/M1/M2, extração local, embeddings, agentes ou seleção de pares.

> Não publique documentos, respostas ou chaves de API no Git. A pasta data/ é ignorada.

## ESM-121 — Teste 3 (OpenAI × Claude), execução e resultados

O roteiro **atualizado em 04/11/2026** para executar os testes offline, consultar os dois resultados reais e abrir **uma nova rodada de inferência isolada** está em [experiments/esm-121/README.md](experiments/esm-121/README.md#guia-operacional-atualizado-04112026). O experimento usa o executor `experiments/esm-121/dual_provider.py`, independente da baseline `direct_baseline.py` descrita abaixo. **Não repita as chamadas já concluídas na pasta histórica**; elas estão protegidas contra repetição e devem ser preservadas.

## Preparação (Windows PowerShell) — baseline direto anterior

Clone a branch feat/direct-file-baseline e, dentro da pasta do projeto:

~~~powershell
py -3 -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path data/input | Out-Null
# Copie todos os arquivos originais para data/input.
py -3 .\direct_baseline.py
~~~

O último comando executa somente o **preview offline**: enumera e verifica os arquivos, mostra SHA-256, tamanhos, avisos de processamento e pergunta literal. Sem upload, custo ou chave.

## Chamada paga (com confirmação explícita)

~~~powershell
$segredo = Read-Host "Cole sua OPENAI_API_KEY" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($segredo)
try {
    $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    Remove-Variable segredo,ptr -ErrorAction SilentlyContinue
}
try {
    py -3 .\direct_baseline.py --execute
} finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
}
~~~

O script exige que você digite **ENVIAR** antes de qualquer upload. Valida disponibilidade do modelo na conta; envia cada arquivo original à Files API com purpose=user_data; anexa os file_id na Responses API junto à pergunta exata em pergunta.md; faz **uma única chamada de análise**. A instrução neutra pede nomes de fontes, separação entre relato/inferência e limite de evidência, sem antecipar achados. store=false; sem File Search e sem ferramentas; sem repetição automática.

## Arquivos de resultado

Todos permanecem no computador em data/results/ID_DA_RODADA/:

- **preflight.json**: pergunta original, fontes, tamanho e SHA-256.
- **manifest.json**: uploads, file_id, tentativas de exclusão.
- **request.json**: parâmetros e conteúdo exatos enviados ao modelo (sem chave).
- **response.json**: resposta bruta, inclusive status e tokens reportados.
- **resposta.md**: resposta integral do modelo somente quando concluída.
- **execucao.json**: status, ID de resposta e consumo.

Após a chamada, o programa tenta excluir cada arquivo remoto. Se o processo for interrompido ou houver falha, alguns uploads podem permanecer na OpenAI. Para repetir a limpeza, sem repetir a análise:

~~~powershell
py -3 .\direct_baseline.py --cleanup-run "data/results/ID_DA_RODADA"
~~~

**Não refaça automaticamente uma chamada após timeout:** a requisição pode ter sido cobrada.

## Limites, custo e validade do teste

- É permitido até **menos de 50 MB** de arquivos por solicitação, em conjunto e por arquivo. Arquivos não suportados, vazios ou duplicados fazem o preview bloquear; nenhuma fonte é omitida silenciosamente.
- A API extrai texto de DOCX e código, mas pode não incluir imagens e gráficos incorporados. PDFs podem consumir tokens de imagem. Planilhas XLSX/CSV passam por processamento resumido (até as primeiras 1.000 linhas por aba); upload não garante leitura integral.
- Preço Standard curto divulgado para GPT-6.1 Sol: US$ 2 por milhão de tokens de entrada e US$ 10 por milhão de tokens de saída. Cenários **hipotéticos**, não garantidos: US$ 0,19 (70k entrada/5k saída), US$ 0,34 (120k/10k), US$ 0,60 (200k/20k). A contagem real depende da API e pode exceder os cenários, especialmente com contexto longo, PDFs, raciocínio e outras condições tarifárias.
- Não há seleção de achados nem resposta humana fornecida ao modelo. Avalie a resposta pelo raciocínio, evidência, descobertas e limitações reconhecidas.

## Testes offline

~~~powershell
py -3 -m unittest discover -s tests -v
~~~

Documentação: https://developers.openai.com/api/docs/guides/file-inputs e https://developers.openai.com/api/reference/resources/files/methods/create
