# Jarvis Mobile independente — Cloudflare

Esta implantação substitui apenas o backend **mobile**. O aplicativo Android
continua responsável por alarmes locais; o Worker cuida de chat, transcrição,
voz FishAudio e histórico. Ele não executa comandos do Windows nem mantém
qualquer verificação facial ou por voz.

## Uma vez, na sua conta Cloudflare

1. Crie uma conta gratuita em <https://dash.cloudflare.com/sign-up>. Não
   selecione nenhum plano pago nem informe cartão.
2. No terminal, entre em `deploy/cloudflare` e rode `bun x wrangler login`.
   O navegador pedirá a autorização da sua conta Cloudflare.
3. Crie o banco persistente: `bun x wrangler d1 create jarvis-mobile`.
4. Copie o `database_id` retornado para `deploy/cloudflare/wrangler.toml`, no
   lugar de `REPLACE_WITH_YOUR_D1_DATABASE_ID`.
5. Aplique a estrutura do banco: `bun x wrangler d1 execute JARVIS_DB --remote --file=./schema.sql`.
6. Crie os segredos; cada comando abre uma entrada segura e não grava a chave
   no Git nem no APK:

   ```powershell
   bun x wrangler secret put MOBILE_CONTROL_TOKEN
   bun x wrangler secret put FISH_API_KEY
   bun x wrangler secret put GROQ_API_KEY
   # opcional, caso queira Gemini como fallback em vez de Groq
   bun x wrangler secret put GEMINI_API_KEY
   ```

   Para `MOBILE_CONTROL_TOKEN`, gere localmente um token novo, por exemplo:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Guarde-o
   só até provisionar o celular; ele não deve ser enviado por chat.

7. Publique: `bun x wrangler deploy`.
8. Copie a URL `https://...workers.dev` mostrada ao final. Em seguida prepare
   e provisione o APK:

   ```powershell
   python .\scripts\mobile_panel.py prepare-cloud --origin https://SEU-WORKER.workers.dev
   .\mobile_app\gradlew.bat -p .\mobile_app :app:assembleDebug
   $env:JARVIS_CONTROL_TOKEN = 'o-mesmo-token-gerado-no-passo-6'
   python .\scripts\mobile_panel.py provision-cloud --origin https://SEU-WORKER.workers.dev
   ```

O token é salvo somente no armazenamento privado do app. As chaves Fish,
Groq e Gemini ficam como Secrets no Worker, nunca dentro do APK.

## Variáveis não secretas opcionais

No Dashboard do Worker, em **Settings → Variables**, configure, se desejar:

- `FISH_REFERENCE_ID` = a referência da voz Jarvis já usada no PC;
- `FISH_TTS_MODEL` = `s2.1-pro-free`;
- `GROQ_MODEL` = o modelo de chat desejado;
- `GEMINI_MODEL` = o modelo Gemini desejado.

## Limites conscientes

- Alarmes são programados pelo Android e tocam mesmo sem o PC. O briefing usa
  FishAudio quando houver internet; o som local continua como fallback.
- Chamada por voz usa microfone → Groq STT → chat → FishAudio TTS. Nenhuma
  amostra de voz é usada para identificar a pessoa.
- Recursos exclusivamente do Windows permanecem no app de PC.
