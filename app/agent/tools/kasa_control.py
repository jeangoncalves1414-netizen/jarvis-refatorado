from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class KasaControlTool(BaseTool):
    """
    TP-Link Kasa IoT — Controle de tomadas inteligentes e lâmpadas Kasa na rede local.
    Descobre automaticamente os dispositivos e permite ligar/desligar/alternar.
    """

    @property
    def name(self) -> str:
        return "kasa_control"

    @property
    def description(self) -> str:
        return "Descobre e controla dispositivos TP-Link Kasa (tomadas e lâmpadas inteligentes) na rede local. Permite ligar, desligar, alternar e consultar estado dos dispositivos."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["discover", "on", "off", "toggle", "status"],
                    "description": "Ação: discover (listar dispositivos), on/off/toggle/status para controle.",
                },
                "device_alias": {
                    "type": "string",
                    "description": "Nome/alias do dispositivo Kasa (necessário para on/off/toggle/status).",
                },
                "device_ip": {
                    "type": "string",
                    "description": "IP do dispositivo (opcional, usa alias se não fornecido).",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "discover")).lower()
        alias = str(args.get("device_alias", "")).strip()
        ip = str(args.get("device_ip", "")).strip()

        try:
            import asyncio
            from kasa import Discover, SmartDevice

            async def _run():
                if action == "discover":
                    devs = await Discover.discover()
                    device_list = []
                    for addr, dev in devs.items():
                        await dev.update()
                        device_list.append({
                            "alias": dev.alias,
                            "ip": addr,
                            "is_on": dev.is_on,
                            "model": dev.model,
                        })
                    return {"devices": device_list}

                # Find device by IP or discover by alias
                if ip:
                    dev = await Discover.discover_single(ip)
                else:
                    devs = await Discover.discover()
                    dev = None
                    for addr, d in devs.items():
                        await d.update()
                        if d.alias.lower() == alias.lower():
                            dev = d
                            break

                if not dev:
                    return {"error": f"Dispositivo '{alias or ip}' não encontrado na rede."}

                await dev.update()

                if action == "on":
                    await dev.turn_on()
                    return {"status": "on", "alias": dev.alias}
                elif action == "off":
                    await dev.turn_off()
                    return {"status": "off", "alias": dev.alias}
                elif action == "toggle":
                    if dev.is_on:
                        await dev.turn_off()
                        return {"status": "off", "alias": dev.alias}
                    else:
                        await dev.turn_on()
                        return {"status": "on", "alias": dev.alias}
                else:  # status
                    return {"alias": dev.alias, "is_on": dev.is_on, "ip": dev.host}

            result = asyncio.run(_run())
            if "error" in result:
                return ToolResult(ok=False, message=result["error"])

            if action == "discover":
                devs = result["devices"]
                if not devs:
                    return ToolResult(ok=True, message="Nenhum dispositivo Kasa encontrado na rede.", data=result)
                lines = "\n".join(f"💡 {d['alias']} ({d['ip']}) — {'Ligado' if d['is_on'] else 'Desligado'}" for d in devs)
                return ToolResult(ok=True, message=f"Dispositivos Kasa encontrados:\n{lines}", data=result)
            else:
                state = "Ligado" if result.get("status") == "on" or result.get("is_on") else "Desligado"
                return ToolResult(ok=True, message=f"Dispositivo '{result.get('alias')}': {state}.", data=result)

        except ImportError:
            return ToolResult(ok=False, message="Biblioteca 'python-kasa' não instalada. Execute: pip install python-kasa")
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao controlar Kasa: {e}")
