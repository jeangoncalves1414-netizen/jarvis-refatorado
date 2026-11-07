import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const frontendDir = fileURLToPath(new URL('.', import.meta.url))
const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string }

// Sem git disponível (por exemplo, pendrive desconectado), o painel mostra apenas versão e data.
function git(args: string[]) {
  try {
    return execFileSync('git', args, { cwd: frontendDir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 3000 }).trim()
  } catch {
    return ''
  }
}

const commit = git(['rev-parse', '--short', 'HEAD'])
// Pacote gerado com alterações não commitadas em frontend/ (inclui arquivos novos não ignorados).
const dirty = Boolean(commit) && Boolean(git(['status', '--porcelain', '--', '.']))

export default defineConfig({
  // O build de produção é servido pelo Python em http://127.0.0.1:8000/.
  base: '/',
  plugins: [react()],
  define: {
    __PANEL_BUILD__: JSON.stringify({ version, commit, dirty, builtAt: new Date().toISOString() }),
  },
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
