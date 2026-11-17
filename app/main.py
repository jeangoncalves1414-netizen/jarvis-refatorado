from __future__ import annotations

import argparse
import os
import threading
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from app.core.stdio import configure_utf8_stdio
from app.config import load_settings
from app.agent.orchestrator import AgentOrchestrator
from app.services.llm import LLMService
from app.ui.panel import PanelServer
from app.plugins import PluginManager
from app.agent.agent_model import AgentManager
from app.storage.vector import SemanticMemory
from app.storage.runtime_settings import sync_api_keys_to_env
try:
    from app.ui.desktop import start_desktop
except Exception:  # pragma: no cover - optional dependency
    start_desktop = None

try:
    from app.services.tray import TrayService, BootService
    TRAY_AVAILABLE = True
except Exception:
    TRAY_AVAILABLE = False


def _free_port(port: int) -> None:
    """Mata qualquer processo LISTENING na porta antes de iniciar."""
    import subprocess, platform
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            killed = set()
            for line in result.stdout.strip().splitlines():
                # Apenas linha com LISTENING na porta exata (127.0.0.1:PORT ou 0.0.0.0:PORT)
                if "LISTENING" not in line:
                    continue
                parts = line.split()
                # parts[1] = endereço local (127.0.0.1:8000), parts[-1] = PID
                if len(parts) >= 4:
                    local_addr = parts[1]
                    if local_addr.endswith(f":{port}"):
                        pid = parts[-1]
                        if pid.isdigit() and pid not in killed:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True
                            )
                            killed.add(pid)
            if killed:
                import time
                time.sleep(0.5)  # aguarda OS liberar a porta
    except Exception:
        pass

def build_app() -> tuple[AgentOrchestrator, PanelServer]:
    settings = load_settings()
    # Sync runtime settings to environment after initialization
    sync_api_keys_to_env()
    llm_service = LLMService(settings=settings)
    from app.storage.memory_store import MemoryStore
    memory_store = MemoryStore()
    
    # Inicializa novos sistemas
    plugin_manager = PluginManager()
    plugin_manager.initialize_all()
    
    agent_manager = AgentManager()
    semantic_memory = SemanticMemory()
    from app.services.profile_memory import ProfileMemoryStore
    profile_memory = ProfileMemoryStore()
    
    from app.mcp.manager import mcp_manager
    
    orchestrator = AgentOrchestrator(
        settings=settings, 
        llm_service=llm_service,
        memory_store=memory_store,
        agent_manager=agent_manager,
        semantic_memory=semantic_memory,
        profile_memory=profile_memory,
        plugin_manager=plugin_manager,
    )

    # Remove entradas técnicas gravadas por versões anteriores; elas não são
    # memória sobre a pessoa e não devem influenciar conversas futuras.
    removed_error_memories = semantic_memory.cleanup_technical_error_memories()
    if removed_error_memories:
        print(f"[Jarvis] {removed_error_memories} memória(s) técnica(s) removida(s).")
    
    mcp_manager.registry = orchestrator.registry
    
    panel = PanelServer(settings=settings)
    # connect orchestrator and voice pipeline to panel server
    try:
        panel.set_orchestrator(orchestrator)
        from app.services.voice.pipeline import VoicePipeline
        vp = VoicePipeline(settings=settings)
        panel.set_voice_pipeline(vp)
        print("[Jarvis] VoicePipeline inicializada com sucesso.")
    except Exception as e:
        print(f"[Jarvis] AVISO: VoicePipeline falhou ao inicializar: {e}")
    return orchestrator, panel


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Jarvis Rebuild: modular desktop assistant")
    parser.add_argument("--demo", action="store_true", help="Executa uma demonstração simples após subir o painel")
    parser.add_argument("--desktop", action="store_true", help="Abre uma janela desktop embutida (pywebview)")
    parser.add_argument("--server", action="store_true", help="Inicia apenas o servidor local, sem abrir janela desktop")
    parser.add_argument("--tray", action="store_true", help="Mostra ícone no System Tray; duplo-clique abre a janela desktop")
    args = parser.parse_args()
    cloud_mode = os.getenv("JARVIS_CLOUD", "").strip().lower() in {"1", "true", "yes", "on"}

    orchestrator, panel = build_app()
    settings = orchestrator.settings
    host = getattr(settings, "host", "127.0.0.1")
    port = getattr(settings, "port", 8000)
    # 0.0.0.0 é válido apenas para o bind do servidor. Navegadores e
    # pywebview precisam de um endereço roteável para abrir a janela local.
    client_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
    url = f"http://{client_host}:{port}"
    desktop_url = f"{url}/app/"

    print(f"Iniciando {settings.app_name}...")
    try:
        settings.validate_control_plane()
    except ValueError as exc:
        print(f"[Jarvis] Configuração de acesso recusada: {exc}")
        return
    _free_port(port)
    from app.ui.panel.paired import DIRECTORY, PairedPanel
    if not cloud_mode and (DIRECTORY / "panel-token").is_file():
        try:
            panel.paired = PairedPanel(settings, DIRECTORY)
        except (OSError, ValueError, KeyError) as error:
            print(f"[Jarvis] Painel Android indisponível: {error}")
    panel.start()
    print(f"Painel disponível em {url} (rede: http://{host}:{port})")
    # Rotinas: agendador ligado só no app real (o PanelServer.start dos testes não liga).
    try:
        import atexit
        from app.routines.service import routine_service
        routine_service.registry = orchestrator.registry
        routine_service.start()
        atexit.register(routine_service.stop)
    except Exception as exc:
        print(f"[Jarvis] AVISO: agendador de rotinas não iniciou: {exc}")

    from app.services.proactive import ProactiveDaemon, ProactiveService
    proactive_daemon: ProactiveDaemon | None = None

    import time as _time
    _time.sleep(0.5)

    # ── Modo Desktop (pywebview) com System Tray integrado ──────────────────
    desktop_mode = not args.server or args.desktop or args.tray
    if desktop_mode and start_desktop is not None:
        # Referência mutável para a janela webview criada dentro de start_desktop
        _webview_window_ref: list = []  # [webview.Window | None]

        def _show_or_create_window() -> None:
            """
            Tenta mostrar a janela pywebview existente.
            Se já foi fechada ou ainda não existe, não faz nada
            (a janela é recriada apenas relanzando o processo).
            """
            try:
                win = _webview_window_ref[0] if _webview_window_ref else None
                if win is not None:
                    try:
                        win.show()  # pywebview hide/show
                    except Exception:
                        pass
            except Exception:
                pass

        tray: "TrayService | None" = None
        if TRAY_AVAILABLE:
            tray = TrayService(
                panel_url=desktop_url,
                on_quit=lambda: os._exit(0),  # força saída imediata de tudo
                on_open=_show_or_create_window,
            )
            tray.start()

        proactive_daemon = ProactiveDaemon(
            ProactiveService(),
            on_notify=tray.notify if tray else lambda title, message: print(f"[{title}] {message}"),
        )
        proactive_daemon.start()

        # Sobrescreve start_desktop para capturar a janela principal criada
        try:
            import webview as _webview

            def _patched_start_desktop(s, ps):
                """Wrapper que captura a referência da janela principal."""
                _host = getattr(s, "host", "127.0.0.1")
                _port = getattr(s, "port", 8000)
                _client_host = "127.0.0.1" if _host in {"0.0.0.0", "::", ""} else _host
                # A versão React é a interface principal da janela desktop.
                # O painel legado continua disponível em / para comparação e backup.
                _url = f"http://{_client_host}:{_port}/app/"
                _spotlight_url = f"http://{_client_host}:{_port}/spotlight"

                from app.ui.desktop import DesktopAPI
                api = DesktopAPI(s, ps)
                # PortAudio init/terminate is not safe concurrently with Microphone().
                ps.start_wake_word()

                window = _webview.create_window(
                    s.app_name,
                    _url,
                    width=1280,
                    height=800,
                    js_api=api,
                )
                _webview_window_ref.append(window)  # salva referência para o tray

                # Intercepta o X: esconde a janela em vez de encerrar o processo
                def on_closing():
                    try:
                        window.hide()
                    except Exception:
                        pass
                    return False  # cancela o fechamento real

                window.events.closing += on_closing

                spotlight_window = _webview.create_window(
                    "Jarvis Spotlight",
                    _spotlight_url,
                    width=600,
                    height=70,
                    frameless=True,
                    easy_drag=True,
                    on_top=True,
                    hidden=True,
                    transparent=True,
                    js_api=api,
                )
                api._spotlight_window = spotlight_window

                # Em algumas versões do backend Win32 do pywebview, `hidden=True`
                # ainda deixa a janela auxiliar visível durante o carregamento.
                # Reforçamos o estado oculto no evento de carregamento para que
                # o Spotlight só apareça quando o usuário usar Alt+Space/Alt+V.
                def hide_spotlight_on_start() -> None:
                    try:
                        spotlight_window.hide()
                    except Exception:
                        pass

                spotlight_window.events.loaded += hide_spotlight_on_start
                threading.Timer(0.25, hide_spotlight_on_start).start()

                def on_loaded():
                    script = """
                        if (!window.JarvisVoice) window.JarvisVoice = {};
                        if (window.pywebview && window.pywebview.api) {
                            window.JarvisVoice.nativeSpeak = (text) => window.pywebview.api.speak(text);
                        }
                    """
                    window.evaluate_js(script)

                window.events.loaded += on_loaded

                def register_hotkeys():
                    try:
                        import keyboard
                        def toggle_spotlight():
                            if spotlight_window:
                                spotlight_window.show()
                        keyboard.add_hotkey("alt+space", toggle_spotlight)

                        def trigger_vision():
                            if spotlight_window:
                                spotlight_window.show()
                                def inject_vision():
                                    import time as _t
                                    _t.sleep(0.3)
                                    try:
                                        spotlight_window.evaluate_js("triggerVisionMode();")
                                    except Exception:
                                        pass
                                threading.Thread(target=inject_vision, daemon=True).start()
                        keyboard.add_hotkey("alt+v", trigger_vision)
                    except Exception as e:
                        print(f"Não foi possível registrar os atalhos globais: {e}")

                threading.Thread(target=register_hotkeys, daemon=True).start()

                # Janela fantasma oculta — mantém o loop pywebview vivo mesmo
                # quando a janela principal está escondida (hide). pywebview só
                # encerra webview.start() quando TODAS as janelas são destruídas.
                _keeper = _webview.create_window(
                    "__jarvis_keepalive__",
                    "about:blank",
                    width=1,
                    height=1,
                    hidden=True,
                )

                profile_path = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'Jarvis', 'WebView')
                os.makedirs(profile_path, exist_ok=True)
                desktop_debug = os.environ.get('JARVIS_DESKTOP_DEBUG') == '1'
                if desktop_debug:
                    _webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
                    _webview.settings['REMOTE_DEBUGGING_PORT'] = 9234
                _webview.start(debug=desktop_debug, private_mode=False, storage_path=profile_path)

            _patched_start_desktop(settings, panel)
        except Exception as exc:
            print(f"[Jarvis] Falha ao iniciar janela desktop: {exc}")
            # Fallback: mantém só o tray vivo
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                pass
        finally:
            if proactive_daemon:
                proactive_daemon.stop()
            if tray:
                tray.stop()
        return

    # ── Modo somente Tray (sem pywebview) ──────────────────────────────────
    if not cloud_mode:
        panel.start_wake_word()
    tray = None
    if TRAY_AVAILABLE and args.tray:
        import webbrowser
        tray = TrayService(
            panel_url=url,
            on_quit=lambda: os._exit(0),
            on_open=lambda: webbrowser.open(url),
        )
        tray.start()

    if args.demo:
        plan = orchestrator.handle_request("Liste meus arquivos na pasta Downloads")
        print("Demonstração:")
        print(f"  Intenção: {plan.intent}")
        print(f"  Resumo: {plan.summary}")
        print(f"  Ações: {plan.actions}")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Encerrando...")
        if tray:
            tray.stop()


if __name__ == "__main__":
    main()
