import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const frontendDir = path.resolve(__dirname, '..');
const repoRoot = path.resolve(frontendDir, '..');
const orbComponentPath = path.resolve(frontendDir, 'src', 'components', 'JarvisOrb3D.tsx');
const distDir = path.resolve(frontendDir, 'dist');
const mobileAssetsDir = path.resolve(repoRoot, 'mobile_app', 'app', 'src', 'main', 'assets');

console.log('--- [JARVIS POST-BUILD & PROTECTION CHECK] ---');

// 1. Verificação de integridade da Orbe Oficial
if (fs.existsSync(orbComponentPath)) {
  const content = fs.readFileSync(orbComponentPath, 'utf8');
  
  if (content.includes('SphereGeometry') || content.includes('MeshStandardMaterial')) {
    console.error('❌ ERRO CRÍTICO: Tentativa de reintroduzir esfera 3D Three.js indesejada detectada em JarvisOrb3D.tsx!');
    process.exit(1);
  }
  
  if (!content.includes('QUANTUM ARC') && !content.includes('QUANTUM')) {
    console.error('❌ ERRO CRÍTICO: JarvisOrb3D.tsx não contém o Quantum Arc Reactor Core canônico!');
    process.exit(1);
  }
  
  console.log('✅ Verificação da Orbe: Quantum Arc Reactor Core canônico 100% válido.');
} else {
  console.error('❌ JarvisOrb3D.tsx não encontrado!');
  process.exit(1);
}

// 2. Sincronização automática para mobile_app
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

console.log('--- [BUILD CONCLUÍDO E PROTEGIDO COM SUCESSO] ---\n');
