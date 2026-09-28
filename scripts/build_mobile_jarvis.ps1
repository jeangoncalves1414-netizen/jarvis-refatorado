param(
    [switch]$Install,
    [switch]$RebuildWeb
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'frontend'
$evolute = Join-Path $root 'evolute'
$assets = Join-Path $root 'mobile_app\app\src\main\assets'
$gradle = Join-Path $root 'mobile_app\gradlew.bat'

function Build-WebApp([string]$Path, [bool]$RelativeBase) {
    Push-Location $Path
    try {
        if ($RelativeBase) { $env:VITE_EVOLUTE_BASE = './' }
        npm run build
    }
    finally {
        if ($RelativeBase) { Remove-Item Env:VITE_EVOLUTE_BASE -ErrorAction SilentlyContinue }
        Pop-Location
    }
}

if ($RebuildWeb) {
    Write-Host "[BUILD] Recompilando frontend e evolute da pasta src..." -ForegroundColor Cyan
    Build-WebApp $frontend $false
    Build-WebApp $evolute $true

    if (Test-Path -LiteralPath $assets) {
        $backupDir = Join-Path $root "backups\assets_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Write-Host "[BACKUP] Salvando backup dos assets atuais em $backupDir" -ForegroundColor Yellow
        Copy-Item -Path $assets -Destination $backupDir -Recurse -Force
        Remove-Item -LiteralPath $assets -Recurse -Force
    }
    New-Item -ItemType Directory -Path $assets -Force | Out-Null
    Copy-Item -Path (Join-Path $frontend 'dist\*') -Destination $assets -Recurse -Force

    $evoluteAssets = Join-Path $assets 'evolute'
    New-Item -ItemType Directory -Path $evoluteAssets -Force | Out-Null
    Copy-Item -Path (Join-Path $evolute 'dist\*') -Destination $evoluteAssets -Recurse -Force
} else {
    Write-Host "[OK] Utilizando assets estaveis verificados em mobile_app/app/src/main/assets" -ForegroundColor Green
}

Push-Location (Join-Path $root 'mobile_app')
try {
    & $gradle assembleDebug
    $apk = Join-Path $root 'mobile_app\app\build\outputs\apk\debug\app-debug.apk'
    Write-Host "APK completo criado: $apk"
    if ($Install) {
        adb install -r $apk
    }
}
finally {
    Pop-Location
}
