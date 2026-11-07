import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const frontendDir = path.resolve(__dirname, '..');
const repoRoot = path.resolve(frontendDir, '..');
const distDir = path.resolve(frontendDir, 'dist');
const mobileAssetsDir = path.resolve(repoRoot, 'mobile_app', 'app', 'src', 'main', 'assets');

// Executado somente por `npm run build:mobile`. O build web (`npm run build`)
// gera apenas frontend/dist e não altera mobile_app/.
// A verificação da Orbe foi retirada por decisão da usuária em 2026-11-07.
console.log('--- [SINCRONIZAÇÃO MOBILE] ---');

if (fs.existsSync(distDir) && fs.existsSync(mobileAssetsDir)) {
  const mobileSubAssets = path.join(mobileAssetsDir, 'assets');
  if (fs.existsSync(mobileSubAssets)) {
    fs.rmSync(mobileSubAssets, { recursive: true, force: true });
  }

  // Copia dist para mobileAssetsDir preservando subdiretórios como evolute
  fs.cpSync(distDir, mobileAssetsDir, {
    recursive: true,
    force: true,
    filter: (src) => {
      // Evita sobrescrever pasta evolute caso ela exista exclusivamente no mobile
      return true;
    }
  });

  console.log('✅ Sincronização Mobile: Assets do frontend copiados automaticamente para mobile_app/app/src/main/assets.');
} else {
  console.warn('⚠️ Diretório dist ou mobileAssetsDir não encontrado para sincronização.');
}

console.log('--- [SINCRONIZAÇÃO MOBILE CONCLUÍDA] ---\n');
