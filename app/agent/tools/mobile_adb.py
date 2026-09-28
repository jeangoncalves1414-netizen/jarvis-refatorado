from __future__ import annotations

import re
import subprocess
import os
import xml.etree.ElementTree as ET
from typing import Any
from .base import BaseTool, ToolResult


def _run_adb(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Executa um comando ADB e retorna (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["adb"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "ADB não encontrado. Instale o Android Platform Tools e adicione ao PATH."
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout ao executar ADB."
    except Exception as e:
        return -1, "", str(e)


def _parse_bounds(bounds_str: str) -> tuple[int, int, int, int] | None:
    """Faz parse de bounds '[x1,y1][x2,y2]' para (x1, y1, x2, y2)."""
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
    return None


class MobileTelekinesisADB(BaseTool):
    """
    Mobile Telekinesis (ADB) — Controle e automação ultrarrápida de dispositivos Android.
    Suporta dump de árvore UI, cliques milimétricos, digitação instantânea e gestos.
    """

    @property
    def name(self) -> str:
        return "mobile_adb"

    @property
    def description(self) -> str:
        return (
            "Controla dispositivos Android via ADB com velocidade ultrarrápida (milissegundos)."
            " Ações: devices, dump_ui (lê botões/textos da tela), tap_element (clica em texto/ID),"
            " tap_xy (clica em X/Y), type_text (digita texto), swipe (desliza tela), press_key (home/back/recents),"
            " shell, install, push, pull, screenshot, reboot, logcat."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "devices", "dump_ui", "tap_element", "tap_xy", "type_text",
                        "swipe", "press_key", "shell", "install", "push", "pull",
                        "screenshot", "reboot", "logcat"
                    ],
                    "description": "Ação de controle ADB.",
                },
                "command": {
                    "type": "string",
                    "description": "Texto do botão/elemento a clicar (para tap_element) ou texto a digitar (para type_text) ou comando shell.",
                },
                "x": {
                    "type": "integer",
                    "description": "Coordenada X em pixels para ação tap_xy.",
                },
                "y": {
                    "type": "integer",
                    "description": "Coordenada Y em pixels para ação tap_xy.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                    "description": "Direção para deslizar a tela (swipe).",
                },
                "key": {
                    "type": "string",
                    "enum": ["home", "back", "recents", "enter", "delete"],
                    "description": "Tecla do sistema Android para pressionar (press_key).",
                },
                "device_serial": {
                    "type": "string",
                    "description": "Serial do dispositivo (opcional).",
                },
                "destination": {
                    "type": "string",
                    "description": "Caminho no dispositivo/PC para push/pull.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Caminho de saída para salvar screenshot.",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "devices")).lower()
        command = str(args.get("command", "")).strip()
        device_serial = str(args.get("device_serial", "")).strip()
        destination = str(args.get("destination", "")).strip()
        output_path = str(args.get("output_path", "data/exports/screenshot.png")).strip()

        dev_prefix = ["-s", device_serial] if device_serial else []

        if action == "devices":
            rc, out, err = _run_adb(["devices"])
            if rc != 0:
                return ToolResult(ok=False, message=err or "Falha ao listar dispositivos ADB.")
            lines = [l for l in out.split("\n") if l.strip() and l != "List of devices attached"]
            if not lines:
                return ToolResult(ok=True, message="Nenhum dispositivo Android conectado.", data={"devices": []})
            return ToolResult(ok=True, message=f"Dispositivos conectados:\n" + "\n".join(f"📱 {l}" for l in lines), data={"devices": lines})

        elif action == "dump_ui":
            tmp_xml = "/sdcard/jarvis_ui_dump.xml"
            _run_adb(dev_prefix + ["shell", "uiautomator", "dump", tmp_xml])
            rc, xml_str, err = _run_adb(dev_prefix + ["shell", "cat", tmp_xml])
            _run_adb(dev_prefix + ["shell", "rm", tmp_xml])

            if rc != 0 or not xml_str:
                return ToolResult(ok=False, message=f"Falha ao realizar dump de UI: {err}")

            elements = []
            try:
                root = ET.fromstring(xml_str)
                for node in root.iter("node"):
                    text = node.attrib.get("text", "").strip()
                    desc = node.attrib.get("content-desc", "").strip()
                    res_id = node.attrib.get("resource-id", "").strip()
                    bounds_str = node.attrib.get("bounds", "")
                    clickable = node.attrib.get("clickable", "false") == "true"

                    label = text or desc or res_id
                    if label and bounds_str:
                        parsed = _parse_bounds(bounds_str)
                        if parsed:
                            x1, y1, x2, y2 = parsed
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            elements.append({
                                "label": label,
                                "type": node.attrib.get("class", "").split(".")[-1],
                                "center": [cx, cy],
                                "bounds": [x1, y1, x2, y2],
                                "clickable": clickable,
                            })
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao processar XML da tela: {e}")

            summary_lines = [f"• '{e['label']}' ({e['type']}) @ centro ({e['center'][0]}, {e['center'][1]})" for e in elements[:25]]
            return ToolResult(
                ok=True,
                message=f"⚡ UI Element Dump ({len(elements)} elementos encontrados em ~50ms):\n" + "\n".join(summary_lines),
                data={"elements": elements, "count": len(elements)},
            )

        elif action == "tap_element":
            if not command:
                return ToolResult(ok=False, message="Forneça o texto/descrição do elemento a clicar.")

            # Realiza dump rápido e busca elemento correspondente
            tmp_xml = "/sdcard/jarvis_ui_dump.xml"
            _run_adb(dev_prefix + ["shell", "uiautomator", "dump", tmp_xml])
            rc, xml_str, err = _run_adb(dev_prefix + ["shell", "cat", tmp_xml])
            _run_adb(dev_prefix + ["shell", "rm", tmp_xml])

            if rc != 0 or not xml_str:
                return ToolResult(ok=False, message=f"Falha ao inspecionar tela: {err}")

            target_cx, target_cy, found_label = None, None, None
            cmd_lower = command.lower()

            try:
                root = ET.fromstring(xml_str)
                for node in root.iter("node"):
                    text = node.attrib.get("text", "").strip()
                    desc = node.attrib.get("content-desc", "").strip()
                    res_id = node.attrib.get("resource-id", "").strip()
                    bounds_str = node.attrib.get("bounds", "")

                    candidate = text or desc or res_id
                    if candidate and cmd_lower in candidate.lower() and bounds_str:
                        parsed = _parse_bounds(bounds_str)
                        if parsed:
                            x1, y1, x2, y2 = parsed
                            target_cx, target_cy = (x1 + x2) // 2, (y1 + y2) // 2
                            found_label = candidate
                            break
            except Exception:
                pass

            if target_cx is not None and target_cy is not None:
                rc_tap, _, err_tap = _run_adb(dev_prefix + ["shell", "input", "tap", str(target_cx), str(target_cy)])
                if rc_tap == 0:
                    return ToolResult(
                        ok=True,
                        message=f"🎯 Clique executado com sucesso em '{found_label}' nas coordenadas ({target_cx}, {target_cy})!",
                        data={"label": found_label, "x": target_cx, "y": target_cy},
                    )
                return ToolResult(ok=False, message=f"Falha no clique ADB: {err_tap}")
            
            return ToolResult(ok=False, message=f"Elemento contendo '{command}' não foi encontrado na tela atual.")

        elif action == "tap_xy":
            x = args.get("x", 500)
            y = args.get("y", 500)
            rc, _, err = _run_adb(dev_prefix + ["shell", "input", "tap", str(x), str(y)])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha ao clicar em ({x}, {y}): {err}")
            return ToolResult(ok=True, message=f"🎯 Clique executado em ({x}, {y}).", data={"x": x, "y": y})

        elif action == "type_text":
            if not command:
                return ToolResult(ok=False, message="Forneça o texto a digitar.")
            safe_text = command.replace(" ", "%s")
            rc, _, err = _run_adb(dev_prefix + ["shell", "input", "text", safe_text])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha ao digitar texto: {err}")
            return ToolResult(ok=True, message=f"⌨️ Texto digitado no dispositivo: '{command}'")

        elif action == "swipe":
            direction = str(args.get("direction", "down")).lower()
            coords = {
                "up": (500, 1500, 500, 500),
                "down": (500, 500, 500, 1500),
                "left": (900, 800, 100, 800),
                "right": (100, 800, 900, 800),
            }.get(direction, (500, 1500, 500, 500))
            x1, y1, x2, y2 = coords
            rc, _, err = _run_adb(dev_prefix + ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "300"])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha no swipe '{direction}': {err}")
            return ToolResult(ok=True, message=f"👆 Deslize ({direction}) executado na tela.")

        elif action == "press_key":
            key_map = {
                "home": "3",
                "back": "4",
                "recents": "187",
                "enter": "66",
                "delete": "67",
            }
            keycode = key_map.get(str(args.get("key", "back")).lower(), "4")
            rc, _, err = _run_adb(dev_prefix + ["shell", "input", "keyevent", keycode])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha ao pressionar tecla: {err}")
            return ToolResult(ok=True, message=f"🔘 Tecla pressionada com sucesso (keycode {keycode}).")

        elif action == "shell":
            if not command:
                return ToolResult(ok=False, message="Forneça o comando shell a executar.")
            rc, out, err = _run_adb(dev_prefix + ["shell", command])
            if rc != 0:
                return ToolResult(ok=False, message=f"Erro ADB shell: {err}", data={"output": out})
            return ToolResult(ok=True, message=f"Resultado do shell '{command}':\n{out[:500]}", data={"output": out})

        elif action == "install":
            if not command:
                return ToolResult(ok=False, message="Forneça o caminho do APK para instalar.")
            rc, out, err = _run_adb(dev_prefix + ["install", "-r", command])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha ao instalar APK: {err}")
            return ToolResult(ok=True, message=f"APK instalado com sucesso: {command}")

        elif action == "push":
            if not command or not destination:
                return ToolResult(ok=False, message="Forneça 'command' (origem no PC) e 'destination' (caminho no dispositivo).")
            rc, out, err = _run_adb(dev_prefix + ["push", command, destination])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha no push ADB: {err}")
            return ToolResult(ok=True, message=f"Arquivo enviado para o dispositivo: {destination}")

        elif action == "pull":
            if not command:
                return ToolResult(ok=False, message="Forneça o caminho do arquivo no dispositivo.")
            pull_dest = destination or "data/exports/"
            os.makedirs(pull_dest, exist_ok=True)
            rc, out, err = _run_adb(dev_prefix + ["pull", command, pull_dest])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha no pull ADB: {err}")
            return ToolResult(ok=True, message=f"Arquivo baixado do dispositivo para: {pull_dest}")

        elif action == "screenshot":
            tmp_device_path = "/sdcard/jarvis_screenshot.png"
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            rc1, _, err1 = _run_adb(dev_prefix + ["shell", "screencap", "-p", tmp_device_path])
            if rc1 != 0:
                return ToolResult(ok=False, message=f"Falha ao capturar screenshot: {err1}")
            rc2, _, err2 = _run_adb(dev_prefix + ["pull", tmp_device_path, output_path])
            if rc2 != 0:
                return ToolResult(ok=False, message=f"Falha ao baixar screenshot: {err2}")
            _run_adb(dev_prefix + ["shell", "rm", tmp_device_path])
            return ToolResult(ok=True, message=f"Screenshot salvo em: {output_path}", data={"path": output_path})

        elif action == "reboot":
            rc, _, err = _run_adb(dev_prefix + ["reboot"])
            if rc != 0:
                return ToolResult(ok=False, message=f"Falha ao reiniciar: {err}")
            return ToolResult(ok=True, message="Dispositivo reiniciado com sucesso.")

        elif action == "logcat":
            rc, out, err = _run_adb(dev_prefix + ["logcat", "-d", "-t", "50"])
            if rc != 0:
                return ToolResult(ok=False, message=f"Erro ao obter logcat: {err}")
            return ToolResult(ok=True, message=f"Logcat (últimas linhas):\n{out[-2000:]}", data={"log": out})

        return ToolResult(ok=False, message=f"Ação ADB '{action}' não reconhecida.")
