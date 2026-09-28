# Jarvis no celular

O APK em `mobile_app` empacota o painel Jarvis (frontend) e o Life OS
(evolute) num WebView. **Não é o mesmo runtime do PC.**

## O que funciona no celular (standalone)

- Chat direto com Groq / Oxyy / Gemini (chaves em Configurações).
- Ligação e microfone via **STT/TTS nativos do Android** (Google/teclado).
- Painel Evolução (Life OS) e sync Supabase.
- Câmera do aparelho, quando o WebView pedir permissão.

## O que fica no PC

- Automação de desktop, cinema local, visão da tela, ponte de dispositivos,
  missões, Tool Forge, wake word do núcleo Python e `/api/voice/*`.

Esses botões são ocultos ou degradados no APK para não parecerem quebrados.

## Como gerar e instalar

Com um Android conectado por ADB:

```powershell
.\scripts\build_mobile_jarvis.ps1 -Install
```

O APK fica em `mobile_app/app/build/outputs/apk/debug/app-debug.apk`.

## Evolução / Life OS

A mesma interface React do Evolute é compilada para o painel do PC e para
`/evolute/` no APK. APIs, nuvem e PC sync ficam em **Jarvis → Configurações**.

## Atualizações

Há duas classes de atualização:

1. Interface e regras do Evolute: devem ser publicadas como aplicação web/PWA.
   O cliente baixa a versão nova ao abrir, sem reinstalar APK.
2. Recursos nativos (permissões, microfone, notificações, integração Android):
   exigem novo APK. Android não permite instalação silenciosa por um app comum;
   o Jarvis pode baixar o pacote assinado e abrir o instalador do sistema para
   confirmação do usuário, ou distribuir pela Play Store/F-Droid, que cuidam da
   atualização automática.

Não é seguro colocar no celular o token administrativo do PC. A sincronização
remota usa uma conta de usuário do Supabase. A chave `service_role` nunca deve
ser usada pelo aplicativo.

## Ativar a nuvem com Supabase

1. O projeto **Jarvis Evolução** já está criado em São Paulo e a migração já foi aplicada.
2. No Evolute, abra **Configurações → Nuvem privada — Supabase** e crie sua
   conta ou entre nela. A URL e a chave publicável já vêm preenchidas.
3. Repita o login no PC e no celular. Cada conta acessa somente a própria
   evolução por Row Level Security; a tabela não é pública.

O app usa uma revisão atômica para evitar que a cópia de um dispositivo apague
silenciosamente uma alteração mais nova do outro. Uma divergência preserva a
cópia local para resolução posterior.
