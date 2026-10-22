<#
.SYNOPSIS
    Confere o Autocadinho.exe empacotado: abre o app na autoverificação e lê o relatório.

.DESCRIPTION
    Roda o executável com AUTOCADINHO_SELFTEST (veja self_test em autocadinho/app.py), com as
    preferências e os dados numa pasta temporária, e confere o relatório: desenho de exemplo aberto,
    PDF e imagem gerados, tradução para o inglês, textos do próprio Qt em português, HTTPS para o
    atualizador e, com -Install, o tipo de instalação lido do autocadinho-install.json.

    Pode rodar no seu computador: não mexe nas suas preferências nem nos seus desenhos. A janela do
    app aparece por alguns segundos e fecha sozinha.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\verificar_exe.ps1 dist\Autocadinho\Autocadinho.exe
#>
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$Version = "",
    [string]$Install = "",
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = "Stop"
$Exe = (Resolve-Path $Exe).Path
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("autocadinho-verificar-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
$Relatorio = Join-Path $Tmp "relatorio.json"

$vars = @{
    AUTOCADINHO_SETTINGS_DIR = (Join-Path $Tmp "preferencias")
    AUTOCADINHO_DATA_DIR     = (Join-Path $Tmp "dados")
    AUTOCADINHO_SELFTEST     = $Relatorio
}
$antes = @{}
foreach ($k in $vars.Keys) {
    $antes[$k] = [Environment]::GetEnvironmentVariable($k)
    [Environment]::SetEnvironmentVariable($k, $vars[$k])
}
try {
    Write-Host "Abrindo $Exe na autoverificação..."
    $p = Start-Process -FilePath $Exe -PassThru
    $null = $p.Handle  # sem isto o ExitCode pode vir vazio
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        $p.Kill()
        throw "O app não terminou a autoverificação em $TimeoutSec s."
    }
} finally {
    foreach ($k in $antes.Keys) { [Environment]::SetEnvironmentVariable($k, $antes[$k]) }
}

if (-not (Test-Path $Relatorio)) { throw "O app fechou (código $($p.ExitCode)) sem gravar o relatório." }
$texto = Get-Content $Relatorio -Raw -Encoding UTF8
Write-Host $texto
$r = $texto | ConvertFrom-Json
Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue

$falhas = @()
if (-not $r.ok) { $falhas += "a autoverificação falhou: $($r.error)" }
if ($p.ExitCode -ne 0) { $falhas += "código de saída $($p.ExitCode)" }
if ($Version -and $r.version -ne $Version) { $falhas += "versão $($r.version), esperada $Version" }
if ($r.elements -lt 10) { $falhas += "o desenho de exemplo abriu com $($r.elements) elementos" }
if ($r.pdf -lt 1000) { $falhas += "o PDF não foi gerado" }
if ($r.png -lt 1000) { $falhas += "a imagem não foi gerada" }
if ($r.en -ne "Beam") { $falhas += "sem a tradução para o inglês (autocadinho/locales fora do pacote?)" }
if ($r.qt_pt_BR -ne "&Desfazer") { $falhas += "textos do Qt sem português (qtbase_pt_BR.qm fora do pacote?)" }
if ($r.https -ne $true) { $falhas += "sem HTTPS para o atualizador (ssl fora do pacote?)" }
if ($Install -and $r.install -ne $Install) { $falhas += "instalação '$($r.install)', esperada '$Install' (autocadinho-install.json)" }
if ($falhas.Count -gt 0) { throw ("Autoverificação: " + ($falhas -join "; ")) }
Write-Host "Autoverificação ok: versão $($r.version), PDF de $($r.pdf) bytes, imagem de $($r.png) bytes."
