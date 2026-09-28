import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // O build de produção é servido pelo Python em http://127.0.0.1:8000/.
  base: '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': process.env.JARVIS_API_URL || 'http://127.0.0.1:8000',
    },
  },
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-icons': ['lucide-react'],
          'vendor-motion': ['framer-motion'],
          'vendor-hls': ['hls.js'],
          'vendor-mermaid': ['mermaid'],
        },
      },
    },
  },
})
