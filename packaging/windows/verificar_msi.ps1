<#
.SYNOPSIS
    Testa o .msi do Autocadinho de verdade: instala, confere, atualiza e desinstala.

.DESCRIPTION
    Feito para o CI (runner do GitHub, usuário descartável). NÃO rode no seu computador: o script
    instala e desinstala o Autocadinho do usuário atual.

    1. Instala o .msi (com ABRIR_APOS_INSTALAR=1) e confere pasta, atalhos, associação .cadinho,
       entrada em "Adicionar ou remover programas" e se o app abriu; roda a autoverificação do app
       instalado (verificar_exe.ps1).
    2. Atualiza para um .msi mínimo de versão maior (mesmo UpgradeCode) e confere que a versão
       antiga saiu e que só há uma entrada instalada.
    3. Desinstala e confere que não sobrou nada.
    4. Instala numa pasta escolhida, atualiza sem informar a pasta e confere que a pasta foi
       lembrada; desinstala.
#>
param(
    [Parameter(Mandatory = $true)][string]$Msi,
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Msi = (Resolve-Path $Msi).Path
$Tmp = Join-Path $(if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }) "verificar-msi"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Tmp
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

$Padrao = Join-Path $env:LOCALAPPDATA "Programs\Autocadinho"
$AtalhoMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Autocadinho.lnk"
$AtalhoDesktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Autocadinho.lnk"
$ChaveInstalador = "HKCU:\Software\Autocadinho\Instalador"
$script:falhas = New-Object System.Collections.Generic.List[string]
$script:n = 0

function Confere([bool]$cond, [string]$msg) {
    if ($cond) { Write-Host "  ok      $msg" } else { Write-Host "  FALHOU  $msg"; $script:falhas.Add($msg) }
}

function Msiexec([string]$argumentos, [string]$nome) {
    $script:n++
    $log = Join-Path $Tmp ("{0:D2}-{1}.log" -f $script:n, $nome)
    Write-Host ""
    Write-Host "msiexec $argumentos"
    # Sem -Wait (que espera também os processos filhos) e com limite de tempo: uma linha de comando
    # errada faz o msiexec abrir uma janela de ajuda que nunca fecha sozinha.
    $p = Start-Process -FilePath msiexec.exe -ArgumentList "$argumentos /qn /norestart /l*v `"$log`"" -PassThru
    $null = $p.Handle
    if (-not $p.WaitForExit(15 * 60 * 1000)) {
        $p.Kill()
        throw "msiexec ($nome) não terminou em 15 minutos."
    }
    if ($p.ExitCode -ne 0 -and $p.ExitCode -ne 3010) {
        Get-Content $log -Tail 80 -ErrorAction SilentlyContinue
        throw "msiexec ($nome) saiu com o código $($p.ExitCode). Log: $log"
    }
}

# Produtos instalados com o UpgradeCode do Autocadinho (API do Windows Installer: é o que
# "Adicionar ou remover programas" e o MajorUpgrade enxergam).
$UpgradeCode = "{" + ([regex]::Match((Get-Content (Join-Path $PSScriptRoot "Autocadinho.wxs") -Raw),
    'UpgradeCode="([0-9A-Fa-f-]{36})"').Groups[1].Value) + "}"
$Installer = New-Object -ComObject WindowsInstaller.Installer

function Produtos-Instalados {
    # O PowerShell desenrola a coleção COM; @() garante uma lista (vazia ou não).
    $lista = @($Installer.RelatedProducts($UpgradeCode) | Where-Object { $_ })
    , $lista
}

function Info-Produto([string]$codigo, [string]$prop) {
    try { [string]$Installer.ProductInfo($codigo, $prop) } catch { "" }
}

function Valor-Padrao([string]$chave) {
    $item = Get-Item -Path $chave -ErrorAction SilentlyContinue
    if ($item) { $item.GetValue("") } else { $null }
}

function Pare-App {
    Get-Process -Name Autocadinho -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

function Confere-Removido([string]$pasta) {
    Confere (-not (Test-Path $pasta)) "pasta removida ($pasta)"
    Confere ((Produtos-Instalados).Count -eq 0) "nenhum Autocadinho instalado (Windows Installer)"
    Confere (-not (Test-Path "HKCU:\Software\Classes\.cadinho")) "associação .cadinho removida"
    Confere (-not (Test-Path "HKCU:\Software\Classes\Autocadinho.Desenho")) "ProgId removido"
    Confere (-not (Test-Path $AtalhoMenu)) "atalho do Menu Iniciar removido"
    Confere (-not (Test-Path $AtalhoDesktop)) "atalho da Área de Trabalho removido"
    # Só os valores do instalador somem. As preferências do app (HKCU\Software\Autocadinho\Autocadinho,
    # gravadas pelo próprio app) ficam de propósito: numa atualização o MSI também desinstala a versão
    # antiga, e apagá-las ali faria a pessoa perder idioma, tema e desenhos recentes.
    $valores = if (Test-Path $ChaveInstalador) { @((Get-Item $ChaveInstalador).Property) } else { @() }
    Confere ($valores.Count -eq 0) "valores do instalador removidos de $ChaveInstalador ($($valores -join ', '))"
}

# Um .msi mínimo (só o executável principal) com a mesma receita, para testar as atualizações.
function Msi-Minimo([string]$versao) {
    $pasta = Join-Path $Tmp "mini-$versao"
    New-Item -ItemType Directory -Force -Path $pasta | Out-Null
    Copy-Item $script:exeCopia $pasta
    $saida = Join-Path $Tmp "Autocadinho-$versao-mini.msi"
    & (Join-Path $PSScriptRoot "build_msi.ps1") -SourceDir $pasta -Output $saida -Version $versao -Python $Python | Out-Host
    $saida
}

Pare-App

# ---------------------------------------------------------------------------- 1. instalação
Write-Host "== 1. Instalação ($Msi)"
Msiexec "/i `"$Msi`" ABRIR_APOS_INSTALAR=1" "instalar"
$abriu = $false
for ($i = 0; $i -lt 30 -and -not $abriu; $i++) {
    if (Get-Process -Name Autocadinho -ErrorAction SilentlyContinue) { $abriu = $true } else { Start-Sleep -Seconds 1 }
}
Confere $abriu "ABRIR_APOS_INSTALAR=1 abriu o Autocadinho"
Pare-App

$exe = Join-Path $Padrao "Autocadinho.exe"
Confere (Test-Path $exe) "Autocadinho.exe em $Padrao"
Confere (Test-Path (Join-Path $Padrao "_internal\autocadinho\locales\en.json")) "tradução para o inglês instalada"
Confere (Test-Path (Join-Path $Padrao "desenho.ico")) "ícone dos desenhos .cadinho"
$script:exeCopia = Join-Path $Tmp "Autocadinho.exe"
Copy-Item $exe $script:exeCopia

Confere (Test-Path $AtalhoMenu) "atalho no Menu Iniciar"
Confere (Test-Path $AtalhoDesktop) "atalho na Área de Trabalho"
Confere ((Valor-Padrao "HKCU:\Software\Classes\.cadinho") -eq "Autocadinho.Desenho") ".cadinho -> Autocadinho.Desenho"
$cmd = Valor-Padrao "HKCU:\Software\Classes\Autocadinho.Desenho\shell\open\command"
Write-Host "        comando: $cmd"
Confere ($cmd -like "*Autocadinho.exe*" -and $cmd -like '*"%1"*') "comando abrir = Autocadinho.exe `"%1`""
$icone = Valor-Padrao "HKCU:\Software\Classes\Autocadinho.Desenho\DefaultIcon"
Confere ($icone -like "*desenho.ico*") "ícone do tipo .cadinho ($icone)"
$prods = Produtos-Instalados
Confere ($prods.Count -eq 1) "um Autocadinho instalado (Windows Installer, UpgradeCode $UpgradeCode)"
if ($prods.Count -ge 1) {
    $pc = $prods[0]
    Write-Host "        produto: $pc  $(Info-Produto $pc 'ProductName') $(Info-Produto $pc 'VersionString')"
    Confere ((Info-Produto $pc "VersionString") -eq $Version) "versão registrada = $Version"
    Confere ((Info-Produto $pc "URLInfoAbout") -like "https://github.com/edvitor13/autocadinho*") "link do repositório em Adicionar ou remover programas"
    Confere ([bool](Info-Produto $pc "ProductIcon")) "ícone em Adicionar ou remover programas"
    Confere ((Info-Produto $pc "AssignmentType") -eq "0") "instalação por usuário (AssignmentType 0)"
}

# O app instalado funciona: abre o exemplo, gera PDF e imagem, traduz (verificar_exe.ps1).
try {
    & (Join-Path $PSScriptRoot "verificar_exe.ps1") -Exe $exe -Version $Version
    Confere $true "autoverificação do app instalado"
} catch {
    Write-Host $_
    Confere $false "autoverificação do app instalado"
}

# ---------------------------------------------------------------------------- 2. atualização
Write-Host ""
Write-Host "== 2. Atualização para uma versão maior"
$mini1 = Msi-Minimo "99.0.0"
Msiexec "/i `"$mini1`"" "atualizar"
$prods = Produtos-Instalados
Confere ($prods.Count -eq 1) "continua um produto só (a versão antiga foi removida)"
if ($prods.Count -ge 1) { Confere ((Info-Produto $prods[0] "VersionString") -eq "99.0.0") "versão nova registrada (99.0.0)" }
Confere (-not (Test-Path (Join-Path $Padrao "_internal"))) "arquivos da versão antiga removidos"
Confere (Test-Path (Join-Path $Padrao "Autocadinho.exe")) "Autocadinho.exe da versão nova no mesmo lugar"

# ---------------------------------------------------------------------------- 3. desinstalação
Write-Host ""
Write-Host "== 3. Desinstalação"
Msiexec "/x `"$mini1`"" "desinstalar"
Confere-Removido $Padrao

# ---------------------------------------------------------------------------- 4. pasta lembrada
Write-Host ""
Write-Host "== 4. Pasta escolhida é mantida nas atualizações"
$pasta = Join-Path $Tmp "Pasta Escolhida\Autocadinho"
Msiexec "/i `"$mini1`" INSTALLFOLDER=`"$pasta\`"" "instalar-pasta"
Confere (Test-Path (Join-Path $pasta "Autocadinho.exe")) "instalado em $pasta"
$mini2 = Msi-Minimo "99.0.1"
Msiexec "/i `"$mini2`"" "atualizar-pasta"
Confere (Test-Path (Join-Path $pasta "Autocadinho.exe")) "atualização ficou em $pasta"
Confere (-not (Test-Path (Join-Path $Padrao "Autocadinho.exe"))) "nada instalado na pasta padrão"
$prods = Produtos-Instalados
if ($prods.Count -ge 1) { Confere ((Info-Produto $prods[0] "VersionString") -eq "99.0.1") "versão 99.0.1 registrada" }
Msiexec "/x `"$mini2`"" "desinstalar-pasta"
Confere-Removido $pasta

Write-Host ""
if ($script:falhas.Count -gt 0) {
    Write-Host "O .msi falhou em $($script:falhas.Count) conferência(s):"
    $script:falhas | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "O .msi passou em todas as conferências."
