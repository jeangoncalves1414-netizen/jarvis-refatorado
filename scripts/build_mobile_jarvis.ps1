param(
    [switch]$Install
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

# Jarvis is the app root; Evolute remains a panel at /evolute/.
Build-WebApp $frontend $false
Build-WebApp $evolute $true

if (Test-Path -LiteralPath $assets) {
    Remove-Item -LiteralPath $assets -Recurse -Force
}
New-Item -ItemType Directory -Path $assets -Force | Out-Null
Copy-Item -Path (Join-Path $frontend 'dist\*') -Destination $assets -Recurse -Force

$evoluteAssets = Join-Path $assets 'evolute'
New-Item -ItemType Directory -Path $evoluteAssets -Force | Out-Null
Copy-Item -Path (Join-Path $evolute 'dist\*') -Destination $evoluteAssets -Recurse -Force

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
