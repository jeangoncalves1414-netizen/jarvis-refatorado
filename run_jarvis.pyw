# Jarvis — Script de inicialização (sem janela de console, compatível com pythonw.exe)
import sys
import os

# Detecta o diretório raiz do projeto automaticamente
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from app.core.stdio import configure_utf8_stdio
configure_utf8_stdio()

from app.main import main
main()
