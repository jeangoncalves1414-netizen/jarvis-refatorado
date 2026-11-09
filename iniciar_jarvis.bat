@echo off
title Jarvis - Console
cd /d "%~dp0"
echo ========================================================
echo                 Iniciando Jarvis
echo ========================================================
"C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe" run_jarvis.pyw %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Jarvis] Ocorreu um erro ao executar o Jarvis.
    pause
)
