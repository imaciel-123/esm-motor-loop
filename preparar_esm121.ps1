$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$seed = Join-Path $HOME "Downloads\ESM121_Fontes_Primarias_Jira_e_Referencias.zip"
if (-not (Test-Path -LiteralPath $seed -PathType Leaf)) {
    Write-Error "Pacote Jira não encontrado em Downloads: $seed. Baixe o ZIP privado fornecido na conversa."
    exit 1
}
py -3 ".\experiments\esm-121\collect_esm121.py" --seed $seed --activate
if ($LASTEXITCODE -ne 0) {
    Write-Error "ESM-121 não ativada. NÃO execute a chamada paga."
    exit $LASTEXITCODE
}
Write-Host "Fontes ESM-121 recuperadas. Revise data\esm121_manifest.json. Nenhum custo OpenAI."
