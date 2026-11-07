@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   JARVIS MOBILE APK BUILD - PROTECAO CANONICA ATIVA
echo ===================================================

cd /d "%~dp0\..\frontend"
echo [1/3] Compilando frontend e sincronizando assets protegidos...
call npm run build:mobile
if %errorlevel% neq 0 (
    echo [ERRO] Falha no build do frontend ou violacao de integridade da Orbe!
    exit /b %errorlevel%
)

cd /d "%~dp0\..\mobile_app"
echo [2/3] Compilando APK Android com Gradle...
call gradlew.bat assembleDebug
if %errorlevel% neq 0 (
    echo [ERRO] Falha na compilacao do APK pelo Gradle!
    exit /b %errorlevel%
)

echo [3/3] Atualizando backup oficial ativo...
copy /Y "app\build\outputs\apk\debug\app-debug.apk" "..\backups\jarvis_mobile_versao_oficial_ativa.apk"

echo ===================================================
echo [SUCESSO] APK compilado e protegido:
echo  - mobile_app\app\build\outputs\apk\debug\app-debug.apk
echo  - backups\jarvis_mobile_versao_oficial_ativa.apk
echo ===================================================
