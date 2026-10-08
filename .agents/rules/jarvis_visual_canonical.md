---
trigger: always_on
description: Regra obrigatória sobre a Orbe oficial do Jarvis (Quantum Arc Reactor Core) e proteção contra esferas 3D ou linhas amarelas.
---

## Visual Canônico Obrigatório do Jarvis (Quantum Arc Reactor Core)

Regras estritas de design e interface visual:
1. **Orbe Oficial Exclusiva:** O componente visualizador central do Jarvis (em `frontend/src/components/JarvisOrb3D.tsx` e `JarvisOrb.tsx`) DEVE ser SEMPRE o **Quantum Arc Reactor Core** em Canvas 2D de alta definição (anéis holográficos concêntricos em ciano `#00daf8` com contra-rotação, tacômetro circular, anel de ondas senoidais reativo a áudio/voz, partículas orbitais e núcleo quântico com mira HUD central).
2. **Proibições Absolutas:**
   - NUNCA substituir ou trocar a orbe por esferas 3D sólidas, Three.js SphereGeometry, esferas roxas com destaque pontual especular ou modelos tridimensionais opacos.
   - NUNCA introduzir runas amarelas ou esquemas visuais amarelos que descaracterizem o padrão tecnológico holográfico ciano/azul do Jarvis.
3. **Sincronização Mobile Obrigatória:**
   - Sempre que o frontend for modificado ou recompilado (`npm run build`), os arquivos gerados em `frontend/dist` DEVEM ser automaticamente sincronizados com `mobile_app/app/src/main/assets`.
   - O APK em `mobile_app` e o backup oficial em `backups/jarvis_mobile_versao_oficial_ativa.apk` devem sempre conter exatamente essa versão sem assets órfãos antigos.
