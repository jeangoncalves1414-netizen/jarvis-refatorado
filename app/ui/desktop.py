from __future__ import annotations

from typing import Any
import os
import threading
import time

def _panel_html() -> str:
    return (
        "<html><head><title>Jarvis Rebuild</title></head>"
        "<body style='background:#111;color:#eee;font-family:Segoe UI,Arial,sans-serif;'>"
        "<h1>Jarvis Rebuild</h1>"
        "<p>Interface inicial do painel modular (desktop embed).</p>"
        "</body></html>"
    )

class DesktopAPI:
    def __init__(self, settings: Any, panel_server: Any = None):
        self._settings = settings
        self._panel_server = panel_server
        self._is_recording = False
        self._recorded_text = ""
        self._speak_enabled = True
        self._stop_listening_fn = None
        
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            self._has_sr = True
        except (ImportError, OSError, AttributeError):
            self._has_sr = False
            print("AVISO: microfone nativo indisponível. A interface continua disponível.")

    def startRecording(self):
        if not self._has_sr:
            return "Erro: microfone nativo indisponível."
            
        self._is_recording = True
        self._recorded_text = ""
        
        def callback(recognizer, audio):
            if not self._is_recording:
                return
            try:
                # Usa a API nativa do google
                text = recognizer.recognize_google(audio, language="pt-BR")
                if text:
                    self._recorded_text += text + " "
            except Exception:
                pass
                
        try:
            self._stop_listening_fn = self._recognizer.listen_in_background(self._microphone, callback)
        except Exception as e:
            self._is_recording = False
            print(f"Erro ao iniciar gravação nativa: {e}")
            return "Erro: não foi possível iniciar a gravação."
        return "Started"

    def stopRecording(self):
        self._is_recording = False
        if self._stop_listening_fn:
            self._stop_listening_fn(wait_for_stop=False)
            self._stop_listening_fn = None
            
        # Pequeno delay para garantir que a última callback do background processe
        time.sleep(0.5)
        return self._recorded_text.strip()
        
    def speak(self, text):
        if not self._speak_enabled:
            return
            
        print(f"[JarvisVoice Native] Falando: {text}")
        
        try:
            from app.services.voice.tts import TTSService
            voice = getattr(self._settings, "tts_voice", "pt-BR-AntonioNeural")
            tts = TTSService(
                voice=voice,
                tts_provider=getattr(self._settings, "tts_provider", "fish") or "fish",
                gemini_api_keys=getattr(self._settings, "gemini_api_keys", []) or [],
                gemini_voice=getattr(self._settings, "tts_gemini_voice", "Charon") or "Charon",
                fish_api_key=getattr(self._settings, "fish_api_key", "") or "",
                fish_reference_id=getattr(self._settings, "fish_reference_id", "") or "78d40157e19a43ebb725f09fc6125585",
                fish_model=getattr(self._settings, "fish_tts_model", "s2.1-pro-free") or "s2.1-pro-free",
                fish_auto_emotions=bool(getattr(self._settings, "fish_auto_emotions", True)),
            )
            threading.Thread(target=tts.speak, args=(text, True), daemon=True).start()
        except Exception as e:
            print(f"Erro ao falar nativamente: {e}")
            
        return True
        
    def getSpeakEnabled(self):
        return self._speak_enabled
        
    def setSpeakEnabled(self, val):
        self._speak_enabled = bool(val)
        return True
        
    def captureVision(self):
        """Captura tela e retorna base64 para uso no Spotlight."""
        try:
            from mss import mss
            from PIL import Image
            from io import BytesIO
            import base64
            with mss() as sct:
                monitor = sct.monitors[0]
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                if img.width > 1280 or img.height > 720:
                    img.thumbnail((1280, 720))
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=80)
                encoded = base64.b64encode(buf.getvalue()).decode()
                return {"ok": True, "image": encoded}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def hideSpotlight(self):
        if hasattr(self, '_spotlight_window') and self._spotlight_window:
            self._spotlight_window.hide()
        return True

    def openEvolute(self):
        if hasattr(self, '_evolute_window') and self._evolute_window:
            try:
                self._evolute_window.show()
                self._evolute_window.restore()
                self._evolute_is_shown = True
            except Exception as e:
                print(f"[DesktopAPI] Erro ao abrir Evolute: {e}")
        return True

    def hideEvolute(self):
        if hasattr(self, '_evolute_window') and self._evolute_window:
            try:
                self._evolute_window.hide()
                self._evolute_is_shown = False
            except Exception as e:
                print(f"[DesktopAPI] Erro ao ocultar Evolute: {e}")
        return True

    def toggleEvolute(self):
        if hasattr(self, '_evolute_window') and self._evolute_window:
            if getattr(self, '_evolute_is_shown', False):
                self.hideEvolute()
            else:
                self.openEvolute()
        return True


def start_desktop(settings: Any, panel_server: Any = None) -> None:
    """Start an embedded desktop window using pywebview."""
    try:
        import webview
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pywebview não está instalado. Instale com `pip install pywebview`.") from exc

    host = getattr(settings, "host", "127.0.0.1")
    port = getattr(settings, "port", 8000)
    url = f"http://{host}:{port}/"
    spotlight_url = f"http://{host}:{port}/spotlight"
    
    api = DesktopAPI(settings, panel_server)
    
    window = webview.create_window(
        settings.app_name, 
        url, 
        width=1280, 
        height=800, 
        js_api=api
    )
    
    spotlight_window = webview.create_window(
        "Jarvis Spotlight", 
        spotlight_url, 
        width=600, 
        height=70, 
        frameless=True, 
        easy_drag=True, 
        on_top=True, 
        hidden=True,
        transparent=True,
        js_api=api
    )
    api._spotlight_window = spotlight_window

    evolute_url = f"http://{host}:{port}/evolute"
    evolute_window = webview.create_window(
        "Evolute — Life OS", 
        evolute_url, 
        width=1380, 
        height=850, 
        hidden=True,
        js_api=api
    )
    api._evolute_window = evolute_window

    # Garantia adicional para backends Win32 que ignoram `hidden=True` no
    # primeiro ciclo de renderização.
    def hide_spotlight_on_start() -> None:
        try:
            spotlight_window.hide()
        except Exception:
            pass

    spotlight_window.events.loaded += hide_spotlight_on_start
    threading.Timer(0.25, hide_spotlight_on_start).start()

    def hide_evolute_on_start() -> None:
        try:
            evolute_window.hide()
        except Exception:
            pass

    evolute_window.events.loaded += hide_evolute_on_start
    threading.Timer(0.3, hide_evolute_on_start).start()

    def on_evolute_closing():
        evolute_window.hide()
        api._evolute_is_shown = False
        return False

    evolute_window.events.closing += on_evolute_closing
    
    def on_loaded():
        # Inject JavaScript mapping without overriding voice.js recording engine
        script = """
            if (!window.JarvisVoice) window.JarvisVoice = {};
            if (window.pywebview && window.pywebview.api) {
                window.JarvisVoice.nativeSpeak = (text) => window.pywebview.api.speak(text);
            }
        """
        window.evaluate_js(script)
        
    window.events.loaded += on_loaded

    panel_standby = False

    def set_panel_standby(value: bool) -> None:
        nonlocal panel_standby
        panel_standby = value
        try:
            window.evaluate_js(
                f"window.__jarvisStandby = {'true' if value else 'false'};"
                "window.dispatchEvent(new Event('jarvis:visibility'));"
            )
        except Exception:
            pass  # Página ainda carregando; o evento loaded sincroniza o próximo estado.

    window.events.minimized += lambda: set_panel_standby(True)
    window.events.restored += lambda: set_panel_standby(False)
    window.events.shown += lambda: set_panel_standby(False)
    window.events.loaded += lambda: set_panel_standby(panel_standby)

    # Intercepta o X: esconde a janela em vez de encerrar o processo
    def on_closing():
        set_panel_standby(True)
        window.hide()
        return False  # cancela o fechamento real

    window.events.closing += on_closing


    def register_hotkeys():
        try:
            import keyboard
            
            # Alt+Space: Toggle Spotlight
            def toggle_spotlight():
                if spotlight_window:
                    spotlight_window.show()
            keyboard.add_hotkey('alt+space', toggle_spotlight)
            
            # Alt+E: Toggle Janela Evolute
            def trigger_evolute():
                api.toggleEvolute()
            keyboard.add_hotkey('alt+e', trigger_evolute)

            # Alt+V: Captura de tela + abre Spotlight em modo Visão
            def trigger_vision():
                if spotlight_window:
                    spotlight_window.show()
                    # Injeta comando de visão na janela do Spotlight
                    def inject_vision():
                        time.sleep(0.3)  # Aguarda janela aparecer
                        try:
                            spotlight_window.evaluate_js("triggerVisionMode();")
                        except Exception as e:
                            print(f"Erro ao injetar visão: {e}")
                    threading.Thread(target=inject_vision, daemon=True).start()
            keyboard.add_hotkey('alt+v', trigger_vision)
            
        except Exception as e:
            print(f"Não foi possível registrar os atalhos globais: {e}")
            
    threading.Thread(target=register_hotkeys, daemon=True).start()

    profile_path = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Jarvis", "WebView")
    os.makedirs(profile_path, exist_ok=True)
    webview.start(debug=False, private_mode=False, storage_path=profile_path)
