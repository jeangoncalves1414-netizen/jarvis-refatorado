# Estrutura Detalhada de Pastas do Novo App

## Objetivo
Definir uma estrutura clara para o novo projeto, com módulos pequenos, fáceis de localizar e editar.

## Estrutura proposta

```text
app/
  core/
    __init__.py
    app.py
    config.py
    events.py
    logging.py
  agent/
    __init__.py
    orchestrator.py
    planner.py
    intent.py
  domain/
    __init__.py
    voice/
    vision/
    files/
    productivity/
    automation/
    memory/
  services/
    __init__.py
    llm.py
    stt.py
    tts.py
    storage.py
    vision.py
  ui/
    __init__.py
    panel/
      __init__.py
      app.py
      components.py
      styles.css
      templates/
    widgets/
  storage/
    __init__.py
    sqlite_store.py
    memory_store.py
  shared/
    __init__.py
    models.py
    schemas.py
    utils.py
  main.py
```

## Regras de organização
- cada módulo deve estar em uma pasta própria,
- arquivos de interface não devem conter lógica de negócio,
- serviços devem ser independentes do painel,
- modelos e schemas devem ficar em um local central.

## Ponto inicial recomendado
Começar implementando:
- core/app.py
- agent/orchestrator.py
- storage/memory_store.py
- ui/panel/app.py
- domain/productivity
