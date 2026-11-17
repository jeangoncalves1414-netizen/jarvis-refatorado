param([switch]$Install, [switch]$RebuildWeb)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if ($RebuildWeb) {
        $runner = if (Get-Command npm -ErrorAction SilentlyContinue) { 'npm' } else { 'bun' }
        foreach ($project in @('frontend', 'evolute')) {
            Push-Location $project
            try {
                & $runner run build
                if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar $project." }
            } finally { Pop-Location }
        }
    }
    if (!(Test-Path 'frontend/dist/index.html')) { throw 'Compile o painel com -RebuildWeb.' }
    if ($Install -or (Test-Path (Join-Path $env:LOCALAPPDATA 'Jarvis/routine-wifi/config.json'))) {
        python -m scripts.mobile_panel prepare
        if ($LASTEXITCODE -ne 0) { throw 'Verifique o pareamento Wi-Fi com o PC.' }
    }
    & .\mobile_app\gradlew.bat -p mobile_app assembleDebug
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o aplicativo Android.' }
    $apk = Join-Path $root 'mobile_app/app/build/outputs/apk/debug/app-debug.apk'
    if ($Install) {
        adb -d install -r $apk
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao atualizar o APK pelo cabo USB.' }
        python -m scripts.mobile_panel provision
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao provisionar o painel pelo cabo USB.' }
    }
    Write-Output $apk
} finally { Pop-Location }
