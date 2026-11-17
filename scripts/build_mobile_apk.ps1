$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'build_mobile_jarvis.ps1') -RebuildWeb
$backup = Join-Path $root 'backups'
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'mobile_app/app/build/outputs/apk/debug/app-debug.apk') -Destination (Join-Path $backup 'jarvis_mobile_versao_oficial_ativa.apk') -Force
