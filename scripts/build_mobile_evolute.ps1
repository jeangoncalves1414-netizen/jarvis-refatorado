param([switch]$Install)

# Compatibility name: the phone package is now the complete Jarvis dashboard,
# with Evolute included as its Evolution panel.
& (Join-Path $PSScriptRoot 'build_mobile_jarvis.ps1') @PSBoundParameters
