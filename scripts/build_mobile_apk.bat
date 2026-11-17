@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_mobile_apk.ps1"
exit /b %errorlevel%
