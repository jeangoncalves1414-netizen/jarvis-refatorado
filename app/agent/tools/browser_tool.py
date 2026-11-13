"""Ferramenta nativa de automação ativa de navegador web via Playwright."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.core.actions import ToolMetadata
from app.services.browser import get_browser_service, BrowserService


class BrowserTool(BaseTool):
    """Ferramenta nativa do Jarvis para navegação e automação web ativa via Playwright.
    
    DIFERENTE de web_search.open_url (que apenas abre uma aba no navegador padrão do
    sistema sem permitir controle programático ou leitura do DOM), esta ferramenta
    realmente navega, aguarda o carregamento do DOM, extrai textos limpos e links,
    pesquisa conteúdos/preços/status, clica em botões e preenche formulários ativamente.
    """

    def __init__(self, browser_service: BrowserService | None = None) -> None:
        self._service = browser_service

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Automação ativa de navegador web via Playwright. "
            "DIFERENTE de web_search.open_url (que apenas abre uma aba no navegador do sistema sem poder interagir), "
            "esta ferramenta realmente navega dentro de páginas, aguarda o DOM carregar, extrai textos limpos e links, "
            "pesquisa elementos/preços/status, clica em botões e links, e preenche formulários ativamente."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "navigate",
                        "extract",
                        "extract_content",
                        "clean_text",
                        "interactive_snapshot",
                        "deep_search",
                        "search_and_extract",
                        "click",
                        "click_element",
                        "fill_form",
                        "type_element",
                        "screenshot",
                    ],
                    "description": (
                        "Ação a executar no navegador: "
                        "'navigate' (acessa URL e espera DOM), "
                        "'extract' ou 'extract_content' (extrai texto limpo, headings e links da página ou seletor), "
                        "'clean_text' (extrai texto limpo sem anúncios, scripts ou cookies da página web), "
                        "'interactive_snapshot' (mapeia elementos interativos numerados [1], [2] para cliques precisos), "
                        "'deep_search' (pesquisa aprofundada na web lendo páginas em paralelo com fontes), "
                        "'search_and_extract' (pesquisa palavras-chave/preços dentro da página), "
                        "'click' (clica em elemento por seletor CSS), "
                        "'click_element' (clica em elemento por ID numérico do snapshot), "
                        "'fill_form' (preenche campos/inputs com dicionário seletor->valor), "
                        "'type_element' (digita texto em elemento por ID numérico do snapshot), "
                        "'screenshot' (captura imagem da página para diagnósticos)."
                    ),
                },
                "url": {
                    "type": "string",
                    "description": "URL para navegar ou pesquisar (ex: https://exemplo.com).",
                },
                "selector": {
                    "type": "string",
                    "description": "Seletor CSS do elemento para clicar ou de onde extrair conteúdo.",
                },
                "query": {
                    "type": "string",
                    "description": "Termo de busca para search_and_extract ou deep_search.",
                },
                "max_sites": {
                    "type": "integer",
                    "description": "Número máximo de páginas para deep_search ler em paralelo (padrão: 3).",
                },
                "element_id": {
                    "type": "integer",
                    "description": "ID numérico do elemento no snapshot interativo para click_element ou type_element.",
                },
                "text": {
                    "type": "string",
                    "description": "Texto para digitar no elemento em type_element.",
                },
                "fields": {
                    "type": "object",
                    "description": "Dicionário de campos a preencher para fill_form (ex: {'#nome': 'Jarvis', '#email': 'jarvis@local'}).",
                    "additionalProperties": {"type": "string"},
                },
                "full_page": {
                    "type": "boolean",
                    "description": "Para screenshot: se True, captura a rolagem completa da página.",
                },
            },
            "required": ["action"],
        }

    @property
    def metadata(self) -> ToolMetadata:
        from .catalog import metadata_for
        fallback = ToolMetadata(
            capabilities=("browser", "automation"),
            default_risk="high",
            operation_arguments=("action", "command"),
            default_operation="extract",
            operation_risks=(
                ("navigate", "observe"),
                ("extract", "observe"),
                ("extract_content", "observe"),
                ("search_and_extract", "observe"),
                ("screenshot", "observe"),
                ("click", "low"),
                ("fill_form", "high"),
            ),
            target_arguments=("url", "selector", "query"),
            default_target="página web",
            operation_effects=(
                ("navigate", "Acessa a URL e aguarda o carregamento do DOM."),
                ("extract", "Extrai texto, títulos e links da página atual; nada é alterado."),
                ("extract_content", "Extrai texto, títulos e links da página atual; nada é alterado."),
                ("search_and_extract", "Pesquisa palavras-chave e extrai dados relevantes dentro da página; nada é alterado."),
                ("screenshot", "Captura imagem da página atual para diagnósticos; nada é alterado."),
                ("click", "Clica em um elemento da página via navegador automatizado."),
                ("fill_form", "Preenche campos e inputs na página via navegador automatizado."),
            ),
            operation_reversibility=(
                ("navigate", "Nada a desfazer."),
                ("extract", "Nada a desfazer."),
                ("extract_content", "Nada a desfazer."),
                ("search_and_extract", "Nada a desfazer."),
                ("screenshot", "Nada a desfazer."),
                ("click", "Não garantida: cliques podem disparar ações no site."),
                ("fill_form", "Não garantida: formulários enviados não são desfeitos."),
            ),
            scope="Sessão de navegador ativo Playwright isolada.",
        )
        return metadata_for(self.name, fallback)

    def _get_service(self, context: dict[str, Any] | None = None) -> BrowserService:
        if self._service:
            return self._service
        if context and "browser" in context and context["browser"] is not None:
            return context["browser"]
        return get_browser_service()

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Implementação base simplificada para o protocolo BaseTool."""
        action = str(kwargs.get("action") or "").strip().lower()
        service = self._get_service()

        if action == "navigate":
            url = kwargs.get("url") or kwargs.get("query") or ""
            return service.navigate(url)

        if action in {"extract", "extract_content"}:
            return self._extract(service, kwargs)

        if action == "clean_text":
            url = kwargs.get("url")
            if url:
                service.navigate(url)
            txt = service.extract_clean_text()
            return {"ok": bool(txt), "text": txt, "message": txt[:4000]}

        if action == "interactive_snapshot":
            url = kwargs.get("url")
            if url:
                service.navigate(url)
            elements = service.get_interactive_snapshot()
            return {"ok": True, "elements": elements, "count": len(elements)}

        if action == "click_element":
            el_id = kwargs.get("element_id") or 0
            return service.click_interactive_element(int(el_id))

        if action == "type_element":
            el_id = kwargs.get("element_id") or 0
            text = str(kwargs.get("text") or "")
            return service.type_interactive_element(int(el_id), text=text)

        if action == "deep_search":
            query = kwargs.get("query") or kwargs.get("url") or ""
            max_sites = int(kwargs.get("max_sites") or 3)
            return service.deep_search(query=query, max_sites=max_sites)

        if action == "search_and_extract":
            query = kwargs.get("query") or kwargs.get("url") or ""
            url = kwargs.get("url") if kwargs.get("query") else None
            return service.search_and_extract(query=query, url=url)

        if action == "click":
            selector = kwargs.get("selector") or ""
            return service.click(selector)

        if action == "fill_form":
            fields = kwargs.get("fields") or {}
            return service.fill_form(fields)

        if action == "screenshot":
            full_page = bool(kwargs.get("full_page", False))
            path = kwargs.get("path")
            return service.screenshot(path=path, full_page=full_page)

        return {"ok": False, "error": f"Ação desconhecida: '{action}'. Use navigate, extract, search_and_extract, click, fill_form ou screenshot."}

    @staticmethod
    def _extract(service, args):
        if args.get("url"):
            navigation = service.navigate(args["url"])
            if not navigation.get("ok"):
                return navigation
        return service.extract_content(selector=args.get("selector"))

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        args = args or {}
        action = str(args.get("action") or "").strip().lower()
        if not action:
            return ToolResult(ok=False, message="Parâmetro 'action' é obrigatório para a ferramenta browser.")

        service = self._get_service(context)
        try:
            if action == "navigate":
                url = str(args.get("url") or args.get("query") or "").strip()
                if not url:
                    return ToolResult(ok=False, message="URL é obrigatória para a ação navigate.")
                res = service.navigate(url)
                ok = res.get("ok", False)
                msg = res.get("message", res.get("error", "Navegação concluída."))
                return ToolResult(ok=ok, message=msg, data=res)

            elif action in {"extract", "extract_content"}:
                res = self._extract(service, args)
                ok = res.get("ok", False)
                msg = res.get("message", res.get("error", "Conteúdo extraído."))
                return ToolResult(ok=ok, message=msg, data=res)

            elif action == "clean_text":
                url = args.get("url")
                if url:
                    service.navigate(url)
                txt = service.extract_clean_text()
                return ToolResult(ok=bool(txt), message=txt[:4000] if txt else "Nenhum texto encontrado.", data={"text": txt})

            elif action == "interactive_snapshot":
                url = args.get("url")
                if url:
                    service.navigate(url)
                elements = service.get_interactive_snapshot()
                msg = f"Elementos ({len(elements)}):\n" + "\n".join(e["label"] for e in elements[:30])
                return ToolResult(ok=True, message=msg, data={"elements": elements, "count": len(elements)})

            elif action == "click_element":
                el_id = args.get("element_id")
                if el_id is None:
                    return ToolResult(ok=False, message="Parâmetro 'element_id' é obrigatório para click_element.")
                res = service.click_interactive_element(int(el_id))
                return ToolResult(ok=res.get("ok", False), message=res.get("message", res.get("error", "")), data=res)

            elif action == "type_element":
                el_id = args.get("element_id")
                if el_id is None:
                    return ToolResult(ok=False, message="Parâmetro 'element_id' é obrigatório para type_element.")
                text = str(args.get("text") or "")
                res = service.type_interactive_element(int(el_id), text=text)
                return ToolResult(ok=res.get("ok", False), message=res.get("message", res.get("error", "")), data=res)

            elif action == "deep_search":
                query = str(args.get("query") or args.get("url") or "").strip()
                if not query:
                    return ToolResult(ok=False, message="Parâmetro 'query' é obrigatório para deep_search.")
                max_sites = int(args.get("max_sites") or 3)
                res = service.deep_search(query=query, max_sites=max_sites)
                return ToolResult(ok=res.get("ok", False), message=res.get("message", res.get("synthesis", "")), data=res)

            elif action == "search_and_extract":
                query = str(args.get("query") or "").strip()
                url = args.get("url")
                if not query:
                    return ToolResult(ok=False, message="Parâmetro 'query' é obrigatório para search_and_extract.")
                res = service.search_and_extract(query=query, url=url)
                ok = res.get("ok", False)
                msg = res.get("message", res.get("error", "Busca concluída."))
                return ToolResult(ok=ok, message=msg, data=res)

            elif action == "click":
                selector = str(args.get("selector") or "").strip()
                if not selector:
                    return ToolResult(ok=False, message="Parâmetro 'selector' é obrigatório para a ação click.")
                res = service.click(selector)
                ok = res.get("ok", False)
                msg = res.get("message", res.get("error", f"Clique executado em {selector}."))
                return ToolResult(ok=ok, message=msg, data=res)

            elif action == "fill_form":
                fields = args.get("fields")
                if not isinstance(fields, dict) or not fields:
                    return ToolResult(ok=False, message="Parâmetro 'fields' (dicionário seletor -> valor) é obrigatório para fill_form.")
                res = service.fill_form(fields)
                ok = res.get("ok", False)
                msg = res.get("message", res.get("error", "Formulário preenchido."))
                return ToolResult(ok=ok, message=msg, data=res)

            elif action == "screenshot":
                full_page = bool(args.get("full_page", False))
                path = args.get("path")
                res = service.screenshot(path=path, full_page=full_page)
                ok = res.get("ok", False)
                msg = res.get("message", res.get("error", "Screenshot capturado."))
                return ToolResult(ok=ok, message=msg, data=res)

            else:
                return ToolResult(
                    ok=False,
                    message=f"Ação '{action}' desconhecida para browser. Use navigate, extract, search_and_extract, click, fill_form ou screenshot."
                )
        except Exception as exc:
            return ToolResult(ok=False, message=f"Erro ao executar ação '{action}' no navegador: {exc}")

