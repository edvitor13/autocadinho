@echo off
rem Gera o Autocadinho com o PyInstaller (pasta dist\Autocadinho, com o Autocadinho.exe), confere
rem o executável, monta o .zip portátil e, se o WiX Toolset estiver instalado, o instalador .msi.
rem Detalhes em docs\DESENVOLVIMENTO.md.
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Autocadinho - build

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  O ambiente .venv não existe. Rode primeiro o instalar.bat.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo  Instalando o PyInstaller e o pytest no ambiente .venv...
    ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
    if errorlevel 1 goto fail
)

echo.
echo  Gerando o executável...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean Autocadinho.spec
if errorlevel 1 goto fail

for /f "delims=" %%v in ('.venv\Scripts\python.exe -c "import autocadinho; print(autocadinho.__version__)"') do set VER=%%v
set "BASE=dist\Autocadinho-%VER%-windows-x64"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -File"
set "MSI="

echo.
echo  Conferindo o executável ^(a janela do app abre e fecha sozinha^)...
%PS% packaging\windows\verificar_exe.ps1 dist\Autocadinho\Autocadinho.exe -Version %VER%
if errorlevel 1 goto fail

where wix >nul 2>nul
if errorlevel 1 (
    echo.
    echo  WiX Toolset não encontrado: o instalador .msi não será gerado.
    echo  Para gerar, instale o .NET SDK e rode: dotnet tool install --global wix --version 5.0.2
    goto zip
)
echo.
echo  Gerando o instalador .msi...
%PS% packaging\windows\build_msi.ps1 -SourceDir dist\Autocadinho -Output "%BASE%.msi" -Version %VER% -Python ".venv\Scripts\python.exe"
if errorlevel 1 goto fail
set "MSI=%BASE%.msi"

:zip
echo.
echo  Gerando o .zip portátil...
".venv\Scripts\python.exe" packaging\install_marker.py dist\Autocadinho zip --version %VER%
if errorlevel 1 goto fail
".venv\Scripts\python.exe" packaging\make_zip.py dist\Autocadinho "%BASE%.zip"
if errorlevel 1 goto fail

echo.
echo  Pronto!
echo    Executável: dist\Autocadinho\Autocadinho.exe
if defined MSI echo    Instalador: %MSI%
echo    Portátil:   %BASE%.zip
echo.
pause
exit /b 0

:fail
echo.
echo  O build falhou. Veja as mensagens acima.
echo.
pause
exit /b 1
