---
trigger: always_on
description: OBSOLETA desde 2026-11-07 (decisão da usuária). A única regra que continua valendo é que os assets Android só são sincronizados por `npm run build:mobile`.
---

## OBSOLETA desde 2026-11-07

**Motivo.** Decisão da usuária em 7 de novembro de 2026. O produto adota a identidade neutra Workspace e não terá a Orbe. Um personagem 3D pode vir no futuro, como última prioridade. A Orbe não é mais requisito visual, e a verificação dela não bloqueia nenhum build, nem o web nem o do APK. Os componentes `JarvisOrb3D.tsx` e `JarvisOrb.tsx` continuam no código por enquanto, sem esforço extra.

**Única regra ainda válida.** Os assets Android em `mobile_app/app/src/main/assets` só são sincronizados por `npm run build:mobile`, executado em `frontend/`. O build web (`npm run build`) gera apenas `frontend/dist`, que o desktop serve, e nunca altera `mobile_app/`.

O texto original fica abaixo apenas como histórico. Ele não deve ser seguido.

---

<details>
<summary>Texto original (histórico, não seguir)</summary>

Descrição original: Regra obrigatória sobre a Orbe oficial do Jarvis (Quantum Arc Reactor Core) e proteção contra esferas 3D ou linhas amarelas.

## Visual Canônico Obrigatório do Jarvis (Quantum Arc Reactor Core)

Regras estritas de design e interface visual:
1. **Orbe Oficial Exclusiva:** O componente visualizador central do Jarvis (em `frontend/src/components/JarvisOrb3D.tsx` e `JarvisOrb.tsx`) DEVE ser SEMPRE o **Quantum Arc Reactor Core** em Canvas 2D de alta definição (anéis holográficos concêntricos em ciano `#00daf8` com contra-rotação, tacômetro circular, anel de ondas senoidais reativo a áudio/voz, partículas orbitais e núcleo quântico com mira HUD central).
2. **Proibições Absolutas:**
   - NUNCA substituir ou trocar a orbe por esferas 3D sólidas, Three.js SphereGeometry, esferas roxas com destaque pontual especular ou modelos tridimensionais opacos.
   - NUNCA introduzir runas amarelas ou esquemas visuais amarelos que descaracterizem o padrão tecnológico holográfico ciano/azul do Jarvis.
3. **Sincronização Mobile Obrigatória:**
   - Sempre que o frontend for modificado ou recompilado (`npm run build`), os arquivos gerados em `frontend/dist` DEVEM ser automaticamente sincronizados com `mobile_app/app/src/main/assets`.
   - O APK em `mobile_app` e o backup oficial em `backups/jarvis_mobile_versao_oficial_ativa.apk` devem sempre conter exatamente essa versão sem assets órfãos antigos.

</details>
