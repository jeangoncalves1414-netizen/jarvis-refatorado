# JARVIS MOBILE APK BUILD - PROTECAO CANONICA ATIVA
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$frontendDir = Join-Path $repoRoot "frontend"
$mobileDir = Join-Path $repoRoot "mobile_app"
$backupApk = Join-Path $repoRoot "backups\jarvis_mobile_versao_oficial_ativa.apk"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  JARVIS MOBILE APK BUILD - PROTECAO CANONICA ATIVA" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Compilando frontend e sincronizando assets protegidos..." -ForegroundColor Yellow
Set-Location $frontendDir
npm run build:mobile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha no build do frontend ou na sincronização dos assets Android!"
}

Write-Host "`n[2/3] Compilando APK Android com Gradle..." -ForegroundColor Yellow
Set-Location $mobileDir
cmd.exe /c "gradlew.bat assembleDebug"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha na compilação do APK pelo Gradle!"
}

Write-Host "`n[3/3] Atualizando backup oficial ativo..." -ForegroundColor Yellow
$builtApk = Join-Path $mobileDir "app\build\outputs\apk\debug\app-debug.apk"
Copy-Item -Path $builtApk -Destination $backupApk -Force

Write-Host "`n===================================================" -ForegroundColor Green
Write-Host "[SUCESSO] APK compilado e protegido:" -ForegroundColor Green
Write-Host " - $builtApk" -ForegroundColor Green
Write-Host " - $backupApk" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
