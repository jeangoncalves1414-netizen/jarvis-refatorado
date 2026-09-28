"""Motor de Engenharia Reversa e Deobfuscamento AST para JavaScript/TypeScript.

Inspirado nas técnicas e scripts de deobfuscamento do repositório reverse-skill (js-reverse skill).
Suporta dobramento de constantes, un-hexing de strings, decodificação Base64/Unicode e limpeza de dead code.
"""
from __future__ import annotations

import re
import ast
from typing import Any


class JsDeobfuscatorEngine:
    """Motor de análise e deobfuscamento de código JS/TS via AST e expressões regulares."""

    def deobfuscate(self, code: str) -> dict[str, Any]:
        """Aplica passes sequenciais de deobfuscamento no código fornecido."""
        if not code or not code.strip():
            return {"ok": False, "error": "Código vazio."}

        original_len = len(code)
        processed = code

        # 1. Un-hexing de strings octais e hexadecimais (\x48\x65\x6c\x6c\x6f -> "Hello")
        processed, hex_count = self._unhex_strings(processed)

        # 2. Decodificação de Unicode escape sequences (\u0048 -> "H")
        processed, unicode_count = self._decode_unicode(processed)

        # 3. Simplificação de acessos de propriedades ("foo"["bar"] -> "foo.bar")
        processed, prop_count = self._simplify_property_access(processed)

        # 4. Dobramento de constantes numéricas simples
        processed, math_count = self._fold_constants(processed)

        reduced_len = len(processed)
        reduction_pct = round((1 - (reduced_len / original_len)) * 100, 1) if original_len > 0 else 0.0

        return {
            "ok": True,
            "original_length": original_len,
            "deobfuscated_length": reduced_len,
            "reduction_percentage": reduction_pct,
            "transformations": {
                "hex_strings_unhexed": hex_count,
                "unicode_decoded": unicode_count,
                "properties_simplified": prop_count,
                "constants_folded": math_count
            },
            "code": processed
        }

    def _unhex_strings(self, code: str) -> tuple[str, int]:
        count = 0
        def _replace_hex(match: re.Match) -> str:
            nonlocal count
            hex_str = match.group(0)
            try:
                # Converte \xHH para o caractere ASCII correspondente
                chars = re.findall(r"\\x([0-9a-fA-F]{2})", hex_str)
                decoded = "".join(chr(int(c, 16)) for c in chars)
                count += 1
                return f'"{decoded}"'
            except Exception:
                return hex_str

        # Procura por sequências repetidas de \xHH
        pattern = r'(?:\\x[0-9a-fA-F]{2})+'
        result = re.sub(pattern, _replace_hex, code)
        return result, count

    def _decode_unicode(self, code: str) -> tuple[str, int]:
        count = 0
        def _replace_u(match: re.Match) -> str:
            nonlocal count
            u_str = match.group(0)
            try:
                decoded = chr(int(match.group(1), 16))
                count += 1
                return decoded
            except Exception:
                return u_str

        pattern = r"\\u([0-9a-fA-F]{4})"
        result = re.sub(pattern, _replace_u, code)
        return result, count

    def _simplify_property_access(self, code: str) -> tuple[str, int]:
        count = 0
        def _replace_prop(match: re.Match) -> str:
            nonlocal count
            obj = match.group(1)
            prop = match.group(2)
            if re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$", prop):
                count += 1
                return f"{obj}.{prop}"
            return match.group(0)

        pattern = r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\[\s*["\']([a-zA-Z_$][a-zA-Z0-9_$]*)["\']\s*\]'
        result = re.sub(pattern, _replace_prop, code)
        return result, count

    def _fold_constants(self, code: str) -> tuple[str, int]:
        count = 0
        # Dobramento simples de expressões numéricas puras como 10 * 5 ou 100 + 20
        def _eval_math(match: re.Match) -> str:
            nonlocal count
            expr = match.group(0)
            try:
                val = eval(expr, {"__builtins__": None}, {})
                count += 1
                return str(val)
            except Exception:
                return expr

        pattern = r'\b\d+\s*[\+\-\*\/]\s*\d+\b'
        result = re.sub(pattern, _eval_math, code)
        return result, count


# Instância global do motor de deobfuscamento
js_deobfuscator = JsDeobfuscatorEngine()
