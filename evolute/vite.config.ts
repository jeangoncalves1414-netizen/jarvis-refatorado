import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  // A interface do PC é publicada em /evolute/. Para o APK, usamos caminhos
  // relativos, pois os arquivos são carregados do pacote Android offline.
  const base = process.env.VITE_EVOLUTE_BASE || '/evolute/';
  return {
    base,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
      proxy: {
        '/api/sync': 'http://127.0.0.1:8000',
        '/api/ai/chat': 'http://127.0.0.1:8000',
        '/api/evolute': 'http://127.0.0.1:8000',
      },
    },
  };
});
