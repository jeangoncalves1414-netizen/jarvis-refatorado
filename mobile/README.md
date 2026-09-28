# Jarvis Mobile — descoberta Bluetooth

Este primeiro módulo é deliberadamente seguro: ele procura a lâmpada e lista os
serviços/características GATT, mas ainda não grava nenhum valor. Isso evita
enviar bytes incorretos para um dispositivo Tuya/BLE antes de identificar o
protocolo real.

## Compilar e instalar no Moto E20

```powershell
cd C:\Users\maria\Desktop\Jarvis\mobile
& "$env:USERPROFILE\.gradle\wrapper\dists\gradle-8.4-bin\1w5dpkrfk8irigvoxmyhowfim\gradle-8.4\bin\gradle.bat" assembleDebug
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

Abra **Jarvis Bluetooth Discovery**, permita Bluetooth/localização e informe o
MAC da lâmpada para filtrar a descoberta. O resultado exibirá os UUIDs GATT e
as propriedades de cada característica. Esses UUIDs serão usados para a etapa
seguinte: implementar a leitura/escrita do protocolo, sem depender do Smart
Life.
