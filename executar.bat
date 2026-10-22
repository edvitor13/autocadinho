@echo off
rem Abre o Autocadinho sem janela de console. Desenhos .cadinho passados como argumento
rem (ou arrastados sobre este .bat) são abertos direto no app.
chcp 65001 >nul
set "AC_DIR=%~dp0"

if not exist "%AC_DIR%.venv\Scripts\pythonw.exe" (
    echo.
    echo  O ambiente do Autocadinho ainda não foi criado.
    echo  Rode primeiro o instalar.bat.
    echo.
    pause
    exit /b 1
)

start "" "%AC_DIR%.venv\Scripts\pythonw.exe" "%AC_DIR%Autocadinho.pyw" %*
