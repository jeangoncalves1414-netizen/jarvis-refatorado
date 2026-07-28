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
                "goal": {
                    "type": "string",
                    "description": "O que você quer que o agente faça no navegador (ex: 'pesquisar passagem para SP', 'verificar o primeiro email')."
                },
                "start_url": {
                    "type": "string",
                    "description": "URL inicial opcional (default: https://google.com)"
                }
            },
            "required": ["goal"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        goal = args.get("goal")
        if not goal:
            return ToolResult(ok=False, message="Objetivo (goal) é obrigatório.")
        
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
        browser_service = context.get("browser")
        
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
                        return ToolResult(ok=True, message=msg, data={"result": result, "capture_filename": final_filename})
                        
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
            return ToolResult(ok=True, message=msg, data={"capture_filename": final_filename})
        finally:
            if not context.get("browser"):
                browser_service.stop()
