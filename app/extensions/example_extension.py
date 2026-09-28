"""
Example Extension - Extensão de exemplo para Jarvis
Demonstra o uso do sistema de extensões.
"""

from typing import Any

EXTENSION_METADATA = type("Metadata", (), {
    "name": "example_extension",
    "version": "1.0.0",
    "author": "Jarvis Team",
    "description": "Extensão de exemplo que demonstra hooks básicos",
    "dependencies": []
})()


def on_startup():
    """Hook chamado na inicialização do Jarvis."""
    print("[ExampleExtension] Jarvis está iniciando!")
    print("[ExampleExtension] Esta extensão demonstra o sistema de hooks")


def on_shutdown():
    """Hook chamado no encerramento do Jarvis."""
    print("[ExampleExtension] Jarvis está encerrando. Até logo!")


def on_command(command: str, context: dict):
    """Hook chamado quando um comando é recebido."""
    print(f"[ExampleExtension] Comando recebido: {command}")
    # Retorne True para marcar o comando como handled e impedir processamento adicional
    return False


def on_voice_start():
    """Hook chamado quando a gravação de voz começa."""
    print("[ExampleExtension] Gravação de voz iniciada")


def on_voice_end(transcript: str):
    """Hook chamado quando a gravação de voz termina."""
    print(f"[ExampleExtension] Gravação de voz finalizada. Transcript: {transcript}")


def on_tool_call(tool_name: str, args: dict):
    """Hook chamado quando uma ferramenta é invocada."""
    print(f"[ExampleExtension] Ferramenta chamada: {tool_name} com args: {args}")


def on_memory_write(key: str, value: any):
    """Hook chamado quando algo é escrito na memória."""
    print(f"[ExampleExtension] Memória escrita: {key} = {value}")
