# Jarvis — Script de inicialização (sem janela de console, compatível com pythonw.exe)
import sys
import os

# Detecta o diretório raiz do projeto automaticamente
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from app.core.stdio import configure_utf8_stdio
configure_utf8_stdio()

# A paired phone can sync while this launcher is running.
if os.path.isfile(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Jarvis", "routine-wifi", "config.json")):
    import threading
    def run_routine_sync():
        from scripts.mobile_wifi import serve
        try:
            serve()
        except OSError as error:
            if getattr(error, "winerror", None) != 10048:
                import logging
                logging.getLogger(__name__).warning("Sincronização móvel indisponível: %s", error)
    threading.Thread(target=run_routine_sync, name="mobile-routine", daemon=True).start()

from app.main import main
main()
