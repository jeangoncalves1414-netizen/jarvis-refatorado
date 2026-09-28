@echo off
title Life OS - Servidor Local
cd /d "%~dp0"
echo ========================================================
echo                 LIFE OS - INICIANDO
echo ========================================================
echo.
echo  Servidor rodando em:
echo  - PC:      http://localhost:3000
echo  - Celular: http://192.168.0.44:3000 (mesmo Wi-Fi)
echo.
echo  Pressione Ctrl+C para fechar o servidor quando terminar.
echo ========================================================
echo.

:: Garante o caminho do Bun
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\bun-windows-x64;%PATH%"

:: Abre o navegador padrao no endereco correto
start http://localhost:3000

:: Inicia o servidor em modo producao (usa o dist/ ja compilado)
set NODE_ENV=production
bun server.ts
pause
