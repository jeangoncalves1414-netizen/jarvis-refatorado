# Jarvis UI

Nova interface React do Jarvis. Ela consome o servidor Python existente e não substitui o painel legado durante a migração.

## Desenvolvimento

1. Na raiz do projeto, inicie o nucleo Python:

   ```powershell
   python -m app.main
   ```

2. Em outro terminal, entre nesta pasta e rode:

   ```powershell
   npm install
   npm run dev
   ```

3. Abra `http://localhost:5173`.

O Vite encaminha chamadas `/api` para `http://127.0.0.1:8000`. O Cinema aceita URLs diretas MP4, WebM e HLS (`.m3u8`) e inclui um vídeo público do Pexels para teste.

Depois de `npm run build`, o servidor Python tambem entrega a interface React em `http://127.0.0.1:8000/app/`. O Vite serve apenas para desenvolvimento.
