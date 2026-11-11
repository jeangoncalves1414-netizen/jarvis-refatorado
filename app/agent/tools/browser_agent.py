from __future__ import annotations

import json
import re
import time
from typing import Any
from .base import BaseTool, ToolResult

JS_MARKER_SCRIPT = """
(function() {
    document.querySelectorAll('.vlm-marker').forEach(e => e.remove());
    
    let counter = 0;
    const elements = document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]:not([tabindex="-1"])');
    window.__vlm_elements = {};
    
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.left >= 0 && rect.top < window.innerHeight && rect.left < window.innerWidth) {
            const isHidden = window.getComputedStyle(el).visibility === 'hidden' || window.getComputedStyle(el).opacity === '0';
            if (isHidden) return;
            
            const marker = document.createElement('div');
            marker.className = 'vlm-marker';
            marker.innerText = counter;
            
            Object.assign(marker.style, {
                position: 'fixed',
                left: Math.max(0, rect.left) + 'px',
                top: Math.max(0, rect.top) + 'px',
                backgroundColor: 'rgba(255, 0, 0, 0.8)',
                color: 'white',
                padding: '2px 4px',
                fontSize: '12px',
                fontWeight: 'bold',
                zIndex: 2147483647,
                pointerEvents: 'none',
                borderRadius: '3px',
                border: '1px solid white'
            });
            
            document.body.appendChild(marker);
            
            const border = document.createElement('div');
            border.className = 'vlm-marker border-marker';
            Object.assign(border.style, {
                position: 'fixed',
                left: rect.left + 'px',
                top: rect.top + 'px',
                width: rect.width + 'px',
                height: rect.height + 'px',
                border: '2px dashed red',
                zIndex: 2147483646,
                pointerEvents: 'none'
            });
            document.body.appendChild(border);
            
            window.__vlm_elements[counter] = el;
            counter++;
        }
    });
    return counter;
})();
"""

BROWSER_PROMPT = """Você é um agente de navegação web autônomo.
Seu objetivo é: {goal}

A imagem em anexo mostra a tela atual do navegador. Elementos interativos estão marcados com números em caixas vermelhas.
Analise a tela e o seu objetivo. Decida QUAL A PRÓXIMA AÇÃO a tomar.

REGRAS:
- Retorne APENAS um objeto JSON válido, sem explicações, sem Markdown.
- Se o objetivo foi concluído ou não pode ser feito, retorne a ação 'done'.

FORMATOS VÁLIDOS:
1. Clicar em um elemento: {{"action": "click", "element_id": 5}}
2. Digitar texto: {{"action": "type", "element_id": 2, "text": "seu texto", "enter": true}}
3. Rolar a página: {{"action": "scroll", "direction": "down"}}  // ou "up"
4. Navegar para URL: {{"action": "navigate", "url": "https://google.com"}}
5. Concluir: {{"action": "done", "result": "Resposta final ou resumo do que foi feito"}}
"""

class BrowserAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "browser_agent"

    @property
    def description(self) -> str:
        return (
            "Navegador Web Autônomo (via Playwright + Visão). "
            "Abre um navegador em segundo plano, interage com sites (clica, digita, rola a página) "
            "e lê os resultados usando Visão Computacional. Use para extrair informações ou interagir com sites."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "deep_search",
                        "clean_text",
                        "interactive_snapshot",
                        "click_element",
                        "type_element",
                        "dump_dom",
                        "click_text",
                        "type_input",
                    ],
                    "description": (
                        "Modo ou ação a executar: "
                        "'deep_search' (busca e sintetiza conteúdo de múltiplos sites em paralelo citando fontes), "
                        "'clean_text' (extrai conteúdo textual limpo da página sem anúncios, menus ou cookies), "
                        "'interactive_snapshot' (mapeia botões, links e campos com números [1], [2] para cliques precisos), "
                        "'click_element' (clica no elemento indicado pelo ID numérico do snapshot), "
                        "'type_element' (digita texto no elemento pelo ID numérico do snapshot), "
                        "'auto' (agente autônomo com visão computacional para cumprir o objetivo informado)."
                    ),
                },
                "goal": {
                    "type": "string",
                    "description": "Objetivo geral da tarefa no navegador ou termo de busca para deep_search.",
                },
                "query": {
                    "type": "string",
                    "description": "Termo de busca para a ação 'deep_search'.",
                },
                "max_sites": {
                    "type": "integer",
                    "description": "Número máximo de páginas a ler em paralelo para deep_search (padrão: 3).",
                },
                "element_id": {
                    "type": "integer",
                    "description": "ID numérico do elemento (obtido via interactive_snapshot) para clicar ou digitar.",
                },
                "text": {
                    "type": "string",
                    "description": "Texto a ser digitado na ação 'type_element' ou 'type_input'.",
                },
                "start_url": {
                    "type": "string",
                    "description": "URL inicial para navegação (ex: https://exemplo.com).",
                },
                "url": {
                    "type": "string",
                    "description": "URL de destino para navegação, extração de texto limpo ou snapshot.",
                },
                "fast_action": {
                    "type": "string",
                    "enum": ["auto", "dump_dom", "click_text", "type_input", "clean_text", "interactive_snapshot", "deep_search"],
                    "description": "Modo rápido de execução (compatibilidade).",
                },
                "target_text": {
                    "type": "string",
                    "description": "Texto do botão ou link para ação rápida click_text.",
                },
                "target_selector": {
                    "type": "string",
                    "description": "Seletor CSS para ação rápida type_input (ex: 'input[name=q]').",
                },
            },
        }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Implementação base para o protocolo BaseTool."""
        res = self.execute(kwargs)
        data = dict(res.data) if res.data else {}
        data["ok"] = res.ok
        data["message"] = res.message
        return data

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        args = args or {}
        context = context or {}

        action = str(args.get("action") or args.get("fast_action") or "").strip().lower()

        # 1. AÇÃO: DEEP_SEARCH (não necessita de VLM/Visão)
        if action == "deep_search":
            query = str(args.get("query") or args.get("goal") or "").strip()
            if not query:
                return ToolResult(ok=False, message="Parâmetro 'query' ou 'goal' é obrigatório para deep_search.")
            max_sites = int(args.get("max_sites") or 3)
            from app.services.browser import get_browser_service
            service = context.get("browser") or get_browser_service()
            res = service.deep_search(query=query, max_sites=max_sites)
            ok = res.get("ok", False)
            msg = res.get("message", res.get("synthesis", "Pesquisa concluída."))
            return ToolResult(ok=ok, message=msg, data=res)

        # 2. AÇÃO: CLEAN_TEXT
        if action == "clean_text":
            from app.services.browser import get_browser_service
            service = context.get("browser") or get_browser_service()
            target_url = str(args.get("url") or args.get("start_url") or "").strip()
            if target_url:
                nav = service.navigate(target_url)
                if not nav.get("ok"):
                    return ToolResult(ok=False, message=nav.get("error", "Falha ao navegar."), data=nav)
            clean_str = service.extract_clean_text()
            if not clean_str:
                return ToolResult(ok=False, message="Nenhum conteúdo textual legível encontrado na página.")
            truncated = clean_str[:8000]
            return ToolResult(
                ok=True,
                message=truncated,
                data={"text": clean_str, "total_chars": len(clean_str), "truncated": len(clean_str) > 8000}
            )

        # 3. AÇÃO: INTERACTIVE_SNAPSHOT
        if action == "interactive_snapshot":
            from app.services.browser import get_browser_service
            service = context.get("browser") or get_browser_service()
            target_url = str(args.get("url") or args.get("start_url") or "").strip()
            if target_url:
                nav = service.navigate(target_url)
                if not nav.get("ok"):
                    return ToolResult(ok=False, message=nav.get("error", "Falha ao navegar."), data=nav)
            elements = service.get_interactive_snapshot()
            if not elements:
                return ToolResult(ok=True, message="Nenhum elemento interativo visível encontrado na página.", data={"elements": []})
            summary_lines = [f"Elementos interativos encontrados na página ({len(elements)}):"]
            for el in elements[:40]:
                summary_lines.append(f"  {el.get('label')}")
            if len(elements) > 40:
                summary_lines.append(f"  ... e mais {len(elements) - 40} elementos.")
            msg = "\n".join(summary_lines)
            return ToolResult(ok=True, message=msg, data={"elements": elements, "count": len(elements)})

        # 4. AÇÃO: CLICK_ELEMENT (por ID do snapshot)
        if action == "click_element":
            el_id = args.get("element_id")
            if el_id is None:
                return ToolResult(ok=False, message="Parâmetro 'element_id' é obrigatório para click_element.")
            from app.services.browser import get_browser_service
            service = context.get("browser") or get_browser_service()
            res = service.click_interactive_element(int(el_id))
            ok = res.get("ok", False)
            msg = res.get("message", res.get("error", f"Clique executado no elemento [{el_id}]."))
            return ToolResult(ok=ok, message=msg, data=res)

        # 5. AÇÃO: TYPE_ELEMENT (por ID do snapshot)
        if action == "type_element":
            el_id = args.get("element_id")
            if el_id is None:
                return ToolResult(ok=False, message="Parâmetro 'element_id' é obrigatório para type_element.")
            text = str(args.get("text") or "")
            from app.services.browser import get_browser_service
            service = context.get("browser") or get_browser_service()
            res = service.type_interactive_element(int(el_id), text=text)
            ok = res.get("ok", False)
            msg = res.get("message", res.get("error", f"Texto digitado no elemento [{el_id}]."))
            return ToolResult(ok=ok, message=msg, data=res)

        # 6. MODO AUTO (ou default): AGENTE COM VISÃO MULTIMODAL
        goal = args.get("goal") or args.get("query")
        if not goal:
            return ToolResult(ok=False, message="Objetivo (goal) é obrigatório para navegação autônoma.")
        
        import urllib.parse

        raw_url = str(args.get("start_url") or "").strip()
        if not raw_url:
            if goal.startswith("http://") or goal.startswith("https://"):
                start_url = goal
            else:
                start_url = f"https://www.google.com/search?q={urllib.parse.quote(goal)}"
        elif raw_url.startswith("http://") or raw_url.startswith("https://"):
            start_url = raw_url
        else:
            start_url = f"https://www.google.com/search?q={urllib.parse.quote(raw_url)}"
        
        if not context or "vision" not in context or not context["vision"]:
            return ToolResult(ok=False, message="Serviço de Visão não disponível no contexto. Não posso rodar o Browser Agent.")
            
        vision_service = context["vision"]
        browser_service = context.get("browser_agent") or context.get("browser")
        
        if not browser_service:
            try:
                from app.services.browser_agent import BrowserAgent
                browser_service = BrowserAgent(headless=True)
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao instanciar BrowserAgent: {e}")

        try:
            browser_service.start()
            browser_service.goto(start_url)
            page = browser_service._page
            if not page:
                return ToolResult(ok=False, message="Falha ao iniciar a página do Playwright.")
        except Exception as e:
            return ToolResult(ok=False, message=f"Falha ao carregar a página inicial: {e}")

        try:
            max_steps = 10
            final_filename = ""
            visited = {}
            for step in range(max_steps):
                time.sleep(1.5)
                
                # Executa script de marcação na página
                num_elements = page.evaluate(JS_MARKER_SCRIPT)
                print(f"[BrowserAgent] Passo {step+1}: Encontrou {num_elements} elementos clicáveis.")
                
                # Tira screenshot da página atual do navegador
                screenshot_bytes = page.screenshot(type="png", full_page=False)
                
                # Remove os marcadores imediatamente para não atrapalhar
                page.evaluate("document.querySelectorAll('.vlm-marker').forEach(e => e.remove());")
                
                # Consulta VLM usando analyze_bytes
                prompt = BROWSER_PROMPT.format(goal=goal)
                print(f"[BrowserAgent] Consultando modelo de visão...")
                try:
                    vlm_response = vision_service.analyze_bytes(prompt, image_bytes=screenshot_bytes)
                    if isinstance(page.url, str):
                        from app.agent.tool_activity import report_progress
                        visited[page.url] = {"url": page.url, "read_status": "read"}
                        report_progress({"sources": list(visited.values())}, "Investigando páginas…")
                except Exception as e:
                    return ToolResult(ok=False, message=f"Erro na consulta de visão: {e}")
                    
                vlm_response = vlm_response.strip()
                vlm_response = re.sub(r"```(?:json)?", "", vlm_response).strip().rstrip("`").strip()
                
                print(f"[BrowserAgent] Resposta VLM:\n{vlm_response}")
                
                action_obj = None
                try:
                    action_obj = json.loads(vlm_response)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", vlm_response, re.DOTALL)
                    if match:
                        try:
                            action_obj = json.loads(match.group(0))
                        except Exception:
                            pass
                
                if not action_obj or not isinstance(action_obj, dict):
                    print("[BrowserAgent] [Warning] VLM não retornou JSON válido.")
                    continue
                
                action = action_obj.get("action")
                print(f"[BrowserAgent] [Action] Ação: {action}")
                
                try:
                    if action == "done":
                        result = action_obj.get("result", "Navegação e tarefas concluídas com sucesso.")
                        try:
                            _, final_filename = browser_service.save_screenshot("browser_step")
                        except Exception:
                            pass
                        msg = f"[Visão Computacional - Captura: {final_filename}]\n{result}" if final_filename else f"Navegação concluída: {result}"
                        return ToolResult(ok=True, message=msg, data={"result": result, "capture_filename": final_filename, "sources": list(visited.values())})
                        
                    elif action == "click":
                        el_id = action_obj.get("element_id")
                        if el_id is not None:
                            page.evaluate(f"if (window.__vlm_elements[{el_id}]) window.__vlm_elements[{el_id}].click();")
                        else:
                            print("[BrowserAgent] [Warning] ID do elemento não fornecido no click.")
                            
                    elif action == "type":
                        el_id = action_obj.get("element_id")
                        text = action_obj.get("text", "")
                        enter = action_obj.get("enter", False)
                        if el_id is not None:
                            page.evaluate(f"if (window.__vlm_elements[{el_id}]) window.__vlm_elements[{el_id}].focus();")
                            page.keyboard.type(text)
                            if enter:
                                page.keyboard.press("Enter")
                        else:
                            print("[BrowserAgent] [Warning] ID do elemento não fornecido no type.")
                            
                    elif action == "scroll":
                        direction = action_obj.get("direction", "down")
                        if direction == "down":
                            page.mouse.wheel(0, 800)
                        else:
                            page.mouse.wheel(0, -800)
                            
                    elif action == "navigate":
                        url = action_obj.get("url")
                        if url:
                            page.goto(url, wait_until="domcontentloaded")
                            
                    else:
                        print(f"[BrowserAgent] [Warning] Ação desconhecida: {action}")
                
                except Exception as e:
                    print(f"[BrowserAgent] [Error] Erro ao executar ação '{action}': {e}")
            
            try:
                _, final_filename = browser_service.save_screenshot("browser_step")
            except Exception:
                pass
            msg = f"[Visão Computacional - Captura: {final_filename}]\nNavegação encerrada após limite de passos." if final_filename else "Navegação interrompida. Máximo de passos atingido."
            return ToolResult(ok=True, message=msg, data={"capture_filename": final_filename, "sources": list(visited.values())})
        finally:
            if not (context.get("browser_agent") or context.get("browser")):
                browser_service.stop()
