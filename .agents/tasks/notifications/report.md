# Relatório de Implementação: Notificações Acionáveis do Windows 10/11 com Ações Rápidas e Deep-Links

**Data:** 09/11/2026  
**Branch:** `feat/actionable-notifications`  
**Worktree:** `c:\Users\maria\Desktop\Jarvis\.worktrees\notifications`

---

## 1. Resumo Executivo

O **Módulo de Notificações Acionáveis do Windows** foi desenvolvido para prover integração profunda e nativa entre o Jarvis e o sistema operacional Windows 10/11. Utilizando a API WinRT (`Windows.UI.Notifications.ToastNotificationManager` e `Windows.Data.Xml.Dom.XmlDocument`) invocada de maneira limpa e não intrusiva via PowerShell inline com codificação Base64 UTF-16LE, o sistema envia notificações Toast nativas com suporte a botões interativos (Ações Rápidas) e deep-links.

Isso permite que o usuário interaja diretamente a partir do Notification Center / Action Center do Windows, mesmo com o painel minimizado ou em segundo plano.

---

## 2. Componentes Desenvolvidos

### 2.1. Serviço Nativo de Notificações (`app/services/windows_notifications.py`)
- **100% Nativo:** Sem necessidade de pacotes pip de terceiros (elimina problemas de compatibilidade e threads com win10toast).
- **Geração Segura de Toast XML (`build_toast_xml`):**
  - Sanitização e escape seguro de entidades XML (`&`, `<`, `>`, `"`, `'`).
  - Suporte a cenários de urgência: `scenario="alarm"` para avisos críticos/altos.
  - Suporte a áudio configurável: respeita configuração global de silêncio (`<audio silent="true"/>`).
  - Montagem de até 5 botões de ação rápida com `activationType="protocol"`.
- **Despacho em Background (`send_notification`):**
  - Despacho assíncrono em thread daemon para não bloquear a chamada principal (com opção `sync=True` para testes e ferramentas síncronas).
  - Consulta automática das configurações em runtime (`enabled`, `sound`).
- **Processamento de Ações Rápidas (`execute_notification_action`):**
  - **"Ouvir Briefing" (`briefing` / `preview-morning`):** Aciona `generate_morning_briefing()`, emite evento WebSocket (`ui_events`) e inicia síntese de voz TTS em background thread.
  - **"Ver Hábitos" (`habits` / `life-os`):** Tenta focar a janela nativa do Jarvis via `WindowControl` e emite evento WebSocket para abrir a aba de hábitos no LifeOS (`open_window` com `window_id="life-os"`).
  - **"Beber Água (+300ml)" (`water`):** Chama o serviço de hidratação `LifeOSService.add_water(amount=300)` e notifica `HabitService` sem exigir que a usuária abra o aplicativo.
  - **"Abrir Link" (`open_link` / `open_url`):** Abre URLs de reuniões ou links externos no navegador padrão via `webbrowser.open()`.
  - **"Testar Notificação" (`test`):** Dispara uma notificação nativa interativa para conferência imediata.

### 2.2. Endpoints HTTP da API (`app/ui/panel/api/notifications.py`)
- **`POST /api/notifications/action`:** Recepção estruturada em JSON para execução de ações disparadas programaticamente ou via scripts.
- **`GET /api/notifications/action`:** Suporte a ativação direta via deep-links HTTP disparados pelos botões do Toast do Windows. Quando requisitado por navegador (`Accept: text/html`), retorna página estilizada na paleta Jarvis (ciano `#00daf8` / escuro `#0b0f19`) com fechamento automático da aba (`window.close()`).
- **`POST /api/notifications/test`:** Disparo de notificação de teste nativa com 3 botões interativos.
- **`POST /api/notifications/send`:** Disparo de notificação rica com título, mensagem, nível de urgência e ações personalizadas.
- **`app/ui/panel/server.py`:** Integração de `handle_notifications_get` e `handle_notifications_post` nos loops principais de despacho HTTP.

### 2.3. Ferramenta Nativa no Action Kernel (`app/agent/tools/notification_tool.py`)
- **Classe `NotificationTool` (nome: `"notification"`):**
  - Permite que o modelo de IA e rotinas agendadas disparem notificações nativas no desktop.
  - Parâmetros: `title` (obrigatório), `message` (obrigatório), `urgency` (`normal`, `low`, `high`, `critical`), e `actions` (lista de botões interativos).
- **Catálogo de Segurança (`app/agent/tools/catalog.py`):**
  - Registrado com risco `low` e reversibilidade `True`, escopo restrito às notificações do sistema operacional.
- **Registro do Agente (`app/agent/tools/registry.py`):**
  - Adicionado a `GENERAL_TOOL_NAMES`, palavras-chave do Groq (`GROQ_KEYWORD_TOOLS`) e registrado no `ToolRegistry`.

### 2.4. Integração com Alertas e Rotinas (`app/routines/watcher.py`)
- **Alertas de Sistema e Hardware:**
  - Alertas de CPU, RAM e Disco elevados agora disparam notificações nativas com botões de ação rápida ("Ver Hábitos", "Ouvir Briefing") e urgência alta (`urgency="high"`).
- **Alertas de Calendário e Reuniões (`calendar_before`):**
  - Quando um compromisso tem link de videoconferência (Google Meet, Zoom, Teams, URL), a notificação nativa inclui o botão "Abrir Reunião" (`open_link`), permitindo entrar na reunião com um clique direto da notificação, além do botão "Ouvir Briefing".
- **`_fire_alert` Atualizado:**
  - Despacha simultaneamente o popup interno do painel (`popups.emit`), o registro na rotina (`store().add_run`), o evento via WebSocket (`ui_events.publish`) e a notificação Toast nativa (`send_notification`).

### 2.5. Configurações em Runtime e Frontend (`app/storage/runtime_settings.py` e `SettingsPage.tsx`)
- **Persistência de Configurações:**
  - `get_notification_settings()` e `set_notification_settings()` em `app/storage/runtime_settings.py`.
  - Rotas `/api/settings/notifications` (GET e POST) em `app/ui/panel/api/settings.py`.
- **Componente React (`frontend/src/components/WindowsNotificationSettings.tsx`):**
  - Switch para ativar/desativar notificações nativas do Windows.
  - Switch para ativar/desativar efeitos sonoros de notificação.
  - Botão de salvar configurações com feedback de status.
  - Botão interativo "Testar notificação do Windows" com animação de envio e sucesso.
- **Integração na `SettingsPage.tsx`:**
  - Inserido na aba "Agente e popups" para computadores desktop.

---

## 3. Cobertura de Testes Unitários (`tests/test_windows_notifications.py`)

Foram criados 20 testes unitários abrangentes cobrindo 100% dos fluxos críticos:
1. `test_build_toast_xml_basic`: Estrutura básica do Toast XML.
2. `test_build_toast_xml_escapes_special_characters`: Escape seguro de entidades XML (`&`, `<`, `>`, `"`).
3. `test_build_toast_xml_with_actions`: Montagem de botões interativos e URLs.
4. `test_build_toast_xml_urgency_scenario`: Ativação de `scenario="alarm"` para urgências críticas.
5. `test_send_notification_disabled`: Bloqueio quando desativado pelo usuário.
6. `test_send_notification_enabled_success`: Despacho via PowerShell subprocess mockado.
7. `test_execute_notification_action_water`: Incremento de água e persistência no LifeOS.
8. `test_execute_notification_action_briefing`: Geração de briefing e despacho de TTS/evento.
9. `test_execute_notification_action_habits`: Foco de janela e abertura da aba de hábitos.
10. `test_execute_notification_action_open_link`: Abertura de link externo no navegador.
11. `test_execute_notification_action_unknown`: Tratamento gracioso de ações inválidas.
12. `test_handle_notifications_post_action`: Endpoint POST `/api/notifications/action`.
13. `test_handle_notifications_post_invalid_json`: Validação de JSON malformado.
14. `test_handle_notifications_post_missing_action`: Validação de parâmetros obrigatórios.
15. `test_handle_notifications_get_action`: Endpoint GET `/api/notifications/action` (JSON).
16. `test_handle_notifications_get_action_html`: Endpoint GET `/api/notifications/action` (HTML de fechamento automático).
17. `test_notification_tool_execution`: Execução da ferramenta NotificationTool.
18. `test_notification_tool_requires_message`: Validação de mensagem obrigatória.
19. `test_notification_tool_in_catalog_and_registry`: Metadados no Action Kernel e presença no ToolRegistry.
20. `test_watcher_fires_actionable_notification_on_cpu_threshold`: Disparo de notificação acionável pelo EventWatcher.

**Resultado da suíte:**
```text
20 passed, 3 warnings in 5.29s
```

---

## 4. Validação do Frontend

- `npx tsc --noEmit`: Concluído sem erros (Exit code 0).
- `npm run build`: Concluído com sucesso gerando bundle de produção minificado e otimizado (Exit code 0).

---

## 5. Conclusão

O Módulo de Notificações Acionáveis do Windows 10/11 foi implementado com fidelidade arquitetural, sem dependências externas adicionais, totalmente integrado às rotinas, ao Action Kernel e ao painel de configurações, pronto para merge na branch principal (`main`).
