# Jarvis Mobile independente — Railway

Esta configuração publica o mesmo painel React e o núcleo Jarvis na Railway.
O celular deixa de depender do computador ligado. O Supabase continua sendo a
sincronização dos dados, não o executor do Jarvis.

## Segurança escolhida

O APK recebe uma credencial privada por aparelho, gravada no armazenamento
privado do Android. A Railway exige essa credencial para API e WebSocket. A
senha exibida no painel é apenas uma segunda trava opcional do celular; ao
desativá-la, o painel **não** se torna público. Não há cadastro facial nem
identificação por voz no fluxo mobile. O microfone permanece disponível para
voice call.

Não copie a credencial para Git, Supabase, chat, ou variáveis `VITE_*`.

## Publicação

1. Envie o código para o repositório GitHub e crie um projeto Railway a partir
   dele. O `railway.toml` seleciona o `Dockerfile`.
2. Crie um Volume Railway montado em `/app/data`. Sem ele, conversas,
   preferências e o bloqueio do painel se perdem a cada nova imagem.
3. Gere uma credencial local segura, por exemplo no PowerShell:

   ```powershell
   [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
   ```

4. Nas variáveis da Railway, configure os valores abaixo. Substitua o domínio
   pelo domínio HTTPS que a Railway gerar para o serviço.

   ```text
   JARVIS_CLOUD=1
   APP_HOST=127.0.0.1
   APP_PORT=8000
   APP_DATA_DIR=/app/data
   APP_ACCESS_MODE=lan
   APP_LAN_ENABLED=1
   JARVIS_CONTROL_TOKEN=<credencial-gerada-no-passo-3>
   APP_TRUSTED_ORIGINS=https://<dominio>.up.railway.app
   FISH_API_KEY=<sua-chave-fish>
   FISH_REFERENCE_ID=78d40157e19a43ebb725f09fc6125585
   TTS_PROVIDER=fish
   ```

   Inclua também as chaves do provedor de chat e STT que já usa, como
   `GEMINI_API_KEY`, `GROQ_API_KEY` ou `OXYY_API_KEY`. Elas ficam somente no
   backend Railway.
5. Após o deploy, abra `https://<dominio>/api/health`. A resposta deve ser
   `{"ok": true, "mode": "cloud"}`. Uma abertura comum no navegador não
   terá acesso às APIs; isso é esperado.

## Preparar e instalar o APK cloud

Use o domínio definitivo. Primeiro gera os recursos que apontam para a Railway;
depois compile/instale normalmente o APK. Só então fornece a credencial ao APK
por ADB, sem colocá-la no código-fonte.

```powershell
python -m scripts.mobile_panel prepare-cloud --origin https://<dominio>.up.railway.app
cd mobile_app
.\gradlew.bat assembleDebug
adb install -r app\build\outputs\apk\debug\app-debug.apk

$env:JARVIS_CONTROL_TOKEN = '<a-mesma-credencial-da-railway>'
cd ..
python -m scripts.mobile_panel provision-cloud --origin https://<dominio>.up.railway.app
```

Depois disso, o aplicativo abre direto na Railway, inclusive com o PC desligado.
No app, em Configurações, a opção **Senha no celular** pode ser desativada se
quiser abrir sem a segunda trava.

## Limites intencionais do modo cloud

Chat, memória persistida, Fish Audio, alarmes locais e voice call funcionam sem
o PC. Comandos que dependem fisicamente do Windows — arquivos locais, câmera
do PC, automação de mouse/teclado, microfone global e controle do desktop — não
existem na Railway. Eles continuam exclusivos da instalação do computador.
