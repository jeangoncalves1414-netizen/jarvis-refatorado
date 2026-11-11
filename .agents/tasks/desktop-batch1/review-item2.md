# Risco por operação para `system_control` e `open_windows_app` no Action Kernel

O commit `c8615cb` faz o Action Kernel decidir o risco de `system_control` e `open_windows_app` pela operação pedida, e não mais por um valor fixo por ferramenta. Antes, `system_control` era `observe` e `open_windows_app` era `low`, então fechar um app (terminate e depois kill) rodava sem aprovação. Agora `ToolMetadata` aceita um mapa de operação para risco, `ActionRecord.create` usa esse risco tanto para gravar quanto para decidir `awaiting_confirmation`, e qualquer operação fora do mapa recebe `critical`. O resultado é `close` como `high` com aprovação, volume, mídia e abrir app como `low` sem aprovação, consultas como `observe`, e `kill_process`/`kill`/`shutdown` como `critical` com aprovação. Os quatro arquivos do commit são todos do item, sem segredos, e `desktop_automation` continua fora do registro.

Watch for: `open_windows_app` com `action: "open"` continua `low` para qualquer `app_name`, e `AppManager.open_app` termina em `subprocess.Popen(nome, shell=True)` quando não reconhece o nome, então um comando de shell arbitrário roda sem aprovação (confirmed; o comportamento já existia na base, mas o mapa novo o grava explicitamente como `low`). Um `close` aprovado pode encerrar mais processos do que o nome sugere, e a proposta não mostra o alvo (confirmed, anterior ao commit; a proposta com alvo é outro item já planejado).

**Verdict**: APPROVED

## High-level view

A classificação fica no kernel, não nas ferramentas. `risk_for` lê o valor da primeira chave de `operation_arguments` presente, usa `default_operation` quando nenhuma aparece e devolve `critical` para qualquer valor fora do mapa. A normalização do kernel (`strip().lower()`) é igual ou mais estrita que a de cada ferramenta: onde as duas divergem, a ferramenta cai em "ação desconhecida" ou em `open`, e o kernel classifica como `critical` ou `low`.

Os três chamadores de `ActionExecutor` que executam ferramentas do registro (função nativa, marcadores e ReAct) pegam a metadata por `registry.get_tool_metadata`, que consulta o catálogo, e nenhum outro código chama `close_app` fora do kernel. Em `system_control`, a chave `command` também é lida porque o caminho de marcadores propõe com `{"command": arg}` e só depois `run_by_marker` traduz para `action`. Sem isso, `volume_up` por marcador seria gravado como `telemetry`.

A aprovação de `close` funciona, mas o aprovador vê só "Executar open windows app. Parâmetros registrados de forma protegida." e não sabe qual app será fechado. `close_app` casa processos por substring nos dois sentidos, então o efeito pode ser maior que o nome pedido. A proposta com alvo e efeito foi deixada para outro item, de forma declarada.

O ponto fraco é `open` em `open_windows_app`, cujo risco depende do alvo e não da operação: abrir `chrome` é inofensivo, mas um `app_name` não reconhecido vai para o shell. O commit não piorou isso, porque a ferramenta inteira já era `low`, mas também não corrigiu. A evidência afirma que `open` como `low` "corresponde ao que a ferramenta executa", o que só vale para apps conhecidos.

Os testes novos usam o catálogo real e as ferramentas reais, com `Popen`, `_press_media_key`, `psutil.process_iter` e `close_app` mockados. Eles provam que `close` gera proposta `high` e só executa depois de `authorized`, que `kill_process`/`kill`/`shutdown` param em `critical` sem tocar o sistema e que volume e mídia rodam direto como `low`. O caminho de marcadores com `command` só é coberto no nível de `risk_for`.

<details>
<summary>Issues (3)</summary>

1. **`open` de `open_windows_app` vai ao shell sem aprovação** (non-blocking, confirmed): com um `app_name` não reconhecido, `AppManager.open_app` executa o nome com `shell=True`, e o mapa novo classifica `open` como `low`. Levar à usuária como próximo item: classificar `open` pelo alvo (`low` só quando o nome resolve por alias, registro, `_SYSTEM_COMMANDS` ou URI, `high` nos demais) ou remover o fallback com shell. Corrigir na evidência a frase de que `low` corresponde ao que a ferramenta executa.
2. **`close` aprovado sem ver o alvo, com casamento por substring** (non-blocking, confirmed): a proposta não mostra operação, `app_name` nem processos, e `is_app_running` casa nos dois sentidos. No item de alvo e efeito, mostrar os processos casados na proposta e avaliar casamento exato.
3. **Caminho de marcadores sem teste de ponta a ponta** (non-blocking, confirmed): a leitura da chave `command` só é testada em `risk_for`. Acrescentar um teste com `ActionExecutor` e `legacy_execute` chamando `registry.run_by_marker`, com `{"command": "volume_up"}` executando como `low` e `{"command": "kill_process"}` parando em `critical`.

</details>

<details>
<summary>Details</summary>

### `open` como `low` e o fallback com shell em `AppManager.open_app`

`OpenWindowsAppTool.execute` passa `app_name` direto para `AppManager.open_app`, que tenta alias, executável conhecido, comando de sistema, arquivo e URI e, se nada casar, executa o próprio nome no shell (confirmed, `app/services/app_manager.py:197-199` e `246-251`):

```python
resolved = self.find_app(name)
if not resolved:
    resolved = name.lower()
...
# 5. Último recurso: shell genérico
proc = subprocess.Popen(resolved, shell=True, creationflags=0x08000000, ...)
```

O passo 3 também faz `os.startfile` em qualquer arquivo existente (`app_manager.py:232`). O mapa novo dá `low` a `open` sem olhar o alvo. Uma conferência pontual confirmou `TOOL_CATALOG["open_windows_app"].risk_for({"action": "open", "app_name": "cmd /c echo x"}) == "low"`, então essa chamada vira `proposed` e executa sem aprovação. Um resultado de busca ou uma página que induza o modelo a chamar a ferramenta com esse argumento chega ao shell.

Em `system_control`, `open_app` tem o mesmo risco `low`, mas usa uma lista fixa de executáveis e `shell=False`. São duas formas de abrir app com o mesmo risco e garantias bem diferentes.

Isso já acontecia antes do commit e fica fora do pedido do item ("volume e mídia `low`, fechar app ou processo `high`"). Por isso o achado não bloqueia. A correção precisa de uma decisão da usuária, porque há dois caminhos. O primeiro é classificar `open` pelo alvo, o que pede um gancho de classificação por alvo no `ToolMetadata`. O segundo é tirar o fallback com `shell=True` de `open_app`, o que pode quebrar a abertura de apps que hoje só funcionam por esse caminho.

### Fechar app: o efeito pode ser maior que o nome pedido

`is_app_running` casa um processo quando `target_stem in pstem or pstem in target_stem` (confirmed, `app_manager.py:274`), e `close_app` faz terminate e depois kill em todos os que casarem. Um nome curto encerra todos os processos que o contêm, e um alvo como `notepad++` também casa com `notepad`. O commit melhora a situação ao exigir aprovação, mas a proposta não mostra a operação, o `app_name` nem os processos que vão ser encerrados, então o aprovador autoriza sem saber o alvo. O item de alvo e efeito na proposta é o lugar natural para mostrar os processos casados.

### Cobertura

`test_every_declared_control_operation_has_explicit_risk` compara o `enum` de `action` das duas ferramentas com o mapa, então uma operação nova no `enum` sem classificação quebra o teste antes de chegar a produção, onde cairia em `critical`. A evidência traz comandos e resultados (73 testes na suíte pedida e 72 na regressão extra do kernel), e as contagens por arquivo batem com o diff: 9 testes novos no kernel e 26 no catálogo.

Não testado: o caminho de marcadores de ponta a ponta. `{"command": "volume_down"}` e `{"command": "kill_process"}` são cobertos só em `risk_for`. Nenhum teste passa por `ActionExecutor` com `legacy_execute` chamando `registry.run_by_marker`, que é onde a chave `command` importa. Se o orquestrador mudar o formato dos argumentos de marcador, os testes atuais não percebem. O Windows real e o backend real também não foram exercitados.

</details>

<details>
<summary>Arquivos alterados</summary>

- `app/core/actions.py`: `ToolMetadata` com `operation_arguments`, `default_operation`, `operation_risks` e `risk_for`; validação dos riscos do mapa; `ActionRecord.create` usa `risk_for` para risco e gate.
- `app/agent/tools/catalog.py`: helper `_by_operation`; mapas de `system_control` (capacidade `("system", "control")`, chaves `action` e `command`) e `open_windows_app` (chave `action`, padrão `open`), ambos com `default_risk="critical"`.
- `tests/test_tool_catalog.py`: classificação por operação (22 casos), `enum` coberto pelo mapa, ferramenta sem mapa, risco inválido no mapa.
- `tests/test_action_kernel.py`: `_control_executor` com catálogo e ferramentas reais; `close` com aprovação e execução única, operação desconhecida em `critical`, volume e mídia sem aprovação, `open_app` e `list_processes`.

Diff completo: `git -C c:/Users/maria/Desktop/Jarvis show c8615cb`

</details>
