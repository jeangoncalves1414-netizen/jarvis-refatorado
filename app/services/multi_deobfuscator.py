"""
Multi-Language Deobfuscator Engine
Inspirado em `go-rust-reverse`, `apk-reverse` e `binary-diff` do reverse-skill.

Suporta:
  - JavaScript: AST un-hex, unicode decode, eval/atob unwrap
  - Python: Base64 encadeado, XOR payload, zlib/bz2 unpacking
  - Binário / Strings executáveis: extração de IPs, URLs, hashes, PE headers
"""
from __future__ import annotations

import re
import base64
import binascii
import zlib
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InputLanguage(str, Enum):
    JAVASCRIPT = "javascript"
    PYTHON = "python"
    BINARY = "binary"
    AUTO = "auto"


@dataclass
class DeobfuscationResult:
    ok: bool
    language: str
    original_length: int
    output: str = ""
    findings: list[str] = field(default_factory=list)
    error: str = ""
    passes_applied: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "language": self.language,
            "original_length": self.original_length,
            "output_length": len(self.output),
            "output": self.output[:4000],  # truncate for display
            "findings": self.findings,
            "passes_applied": self.passes_applied,
            "error": self.error,
        }


class MultiDeobfuscatorEngine:
    """
    Motor de deobfuscamento multi-linguagem.
    Detecta automaticamente o tipo de payload e aplica passes de desofuscação.
    """

    # ── JavaScript ──────────────────────────────────────────────────────────

    def deobfuscate_js(self, code: str) -> DeobfuscationResult:
        result = code
        passes: list[str] = []
        findings: list[str] = []

        # Pass 1: decode \xNN hex sequences
        def decode_hex_seq(m: re.Match) -> str:
            try:
                return bytes.fromhex(m.group(1)).decode("utf-8", errors="replace")
            except Exception:
                return m.group(0)

        new = re.sub(r"\\x([0-9a-fA-F]{2})", decode_hex_seq, result)
        if new != result:
            result = new
            passes.append("hex_escape_decode")

        # Pass 2: decode \uNNNN unicode sequences
        def decode_uni_seq(m: re.Match) -> str:
            try:
                return chr(int(m.group(1), 16))
            except Exception:
                return m.group(0)

        new = re.sub(r"\\u([0-9a-fA-F]{4})", decode_uni_seq, result)
        if new != result:
            result = new
            passes.append("unicode_escape_decode")

        # Pass 3: unwrap atob() base64
        def decode_atob(m: re.Match) -> str:
            try:
                b64 = m.group(1).strip("'\"")
                return f'/* atob decoded: */ "{base64.b64decode(b64).decode("utf-8", errors="replace")}"'
            except Exception:
                return m.group(0)

        new = re.sub(r"atob\(['\"]([A-Za-z0-9+/=]+)['\"]\)", decode_atob, result)
        if new != result:
            result = new
            passes.append("atob_decode")

        # Pass 4: unwrap eval(unescape(...))
        def decode_unescape(m: re.Match) -> str:
            try:
                from urllib.parse import unquote
                inner = m.group(1).strip("'\"")
                return f'/* eval(unescape) decoded: */ {unquote(inner)}'
            except Exception:
                return m.group(0)

        new = re.sub(r"eval\s*\(\s*unescape\s*\(['\"]([^'\"]+)['\"]\)\s*\)", decode_unescape, result)
        if new != result:
            result = new
            passes.append("eval_unescape_decode")

        # Pass 5: String.fromCharCode array decoder
        def decode_charcode(m: re.Match) -> str:
            try:
                nums = [int(n.strip()) for n in m.group(1).split(",")]
                return '"' + "".join(chr(n) for n in nums) + '"'
            except Exception:
                return m.group(0)

        new = re.sub(r"String\.fromCharCode\(([0-9,\s]+)\)", decode_charcode, result)
        if new != result:
            result = new
            passes.append("fromCharCode_decode")

        # Pass 6: find suspicious IOCs
        urls = re.findall(r"https?://[^\s\"'<>]+", result)
        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", result)
        if urls:
            findings.append(f"URLs encontradas: {urls[:5]}")
        if ips:
            findings.append(f"IPs encontrados: {ips[:5]}")

        return DeobfuscationResult(
            ok=True,
            language="javascript",
            original_length=len(code),
            output=result,
            findings=findings,
            passes_applied=passes,
        )

    # ── Python ──────────────────────────────────────────────────────────────

    def deobfuscate_python(self, code: str) -> DeobfuscationResult:
        result = code
        passes: list[str] = []
        findings: list[str] = []

        # Pass 1: decode chained base64
        b64_pattern = re.compile(r"base64\.b64decode\(['\"]([A-Za-z0-9+/=\n]+)['\"]\)")

        def decode_b64(m: re.Match) -> str:
            try:
                decoded = base64.b64decode(m.group(1).replace("\n", "")).decode("utf-8", errors="replace")
                return f"# base64 decoded:\n{decoded}"
            except Exception:
                return m.group(0)

        new = b64_pattern.sub(decode_b64, result)
        if new != result:
            result = new
            passes.append("base64_decode")

        # Pass 2: detect and unwrap zlib.decompress
        zlib_pattern = re.compile(r"zlib\.decompress\(base64\.b64decode\(['\"]([A-Za-z0-9+/=\n]+)['\"]\)\)")

        def decode_zlib(m: re.Match) -> str:
            try:
                raw = base64.b64decode(m.group(1).replace("\n", ""))
                decompressed = zlib.decompress(raw).decode("utf-8", errors="replace")
                return f"# zlib+base64 decoded:\n{decompressed}"
            except Exception:
                return m.group(0)

        new = zlib_pattern.sub(decode_zlib, result)
        if new != result:
            result = new
            passes.append("zlib_b64_decode")

        # Pass 3: XOR decode detection
        xor_pattern = re.compile(r"bytes\(\[b\s*\^\s*(\d+)\s+for\s+b\s+in\s+b?['\"]([^'\"]+)['\"]\]\)")

        def decode_xor(m: re.Match) -> str:
            try:
                key = int(m.group(1))
                payload = m.group(2).encode("latin-1")
                decoded = "".join(chr(b ^ key) for b in payload)
                return f"# XOR(key={key}) decoded: {decoded!r}"
            except Exception:
                return m.group(0)

        new = xor_pattern.sub(decode_xor, result)
        if new != result:
            result = new
            passes.append("xor_decode")

        # Pass 4: raw base64 string blobs
        raw_b64_pattern = re.compile(r"['\"]([A-Za-z0-9+/]{40,}={0,2})['\"]")

        def try_decode_raw_b64(m: re.Match) -> str:
            try:
                decoded = base64.b64decode(m.group(1)).decode("utf-8", errors="replace")
                if any(c.isprintable() for c in decoded[:20]):
                    return f"'/* raw_b64: {decoded[:200]} ...'"
            except Exception:
                pass
            return m.group(0)

        new = raw_b64_pattern.sub(try_decode_raw_b64, result)
        if new != result:
            result = new
            passes.append("raw_b64_blobs")

        # IOC extraction
        urls = re.findall(r"https?://[^\s\"'<>]+", result)
        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", result)
        if urls:
            findings.append(f"URLs: {urls[:5]}")
        if ips:
            findings.append(f"IPs: {ips[:5]}")

        return DeobfuscationResult(
            ok=True,
            language="python",
            original_length=len(code),
            output=result,
            findings=findings,
            passes_applied=passes,
        )

    # ── Binary / Executable Strings ─────────────────────────────────────────

    def analyze_binary(self, data: bytes) -> DeobfuscationResult:
        findings: list[str] = []
        output_lines: list[str] = []

        # Detect PE header
        is_pe = data[:2] == b"MZ"
        if is_pe:
            output_lines.append("✅ PE Header detectado (Windows Executable)")
            findings.append("PE executable")
            try:
                e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
                sig = data[e_lfanew:e_lfanew + 4]
                if sig == b"PE\x00\x00":
                    machine = struct.unpack_from("<H", data, e_lfanew + 4)[0]
                    machine_name = {0x8664: "x64 (AMD64)", 0x014c: "x86 (i386)", 0xAA64: "ARM64"}.get(machine, f"0x{machine:04X}")
                    output_lines.append(f"  Arquitetura: {machine_name}")
                    findings.append(f"arch={machine_name}")
            except Exception:
                pass

        # ELF detection
        if data[:4] == b"\x7fELF":
            output_lines.append("✅ ELF Header detectado (Linux/Unix Executable)")
            findings.append("ELF executable")

        # Extract readable ASCII strings (min length 6)
        strings = re.findall(rb"[ -~]{6,}", data)
        decoded_strings = [s.decode("ascii", errors="replace") for s in strings]

        # IOC extraction from strings
        urls = [s for s in decoded_strings if re.search(r"https?://", s)]
        ips = [s for s in decoded_strings if re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", s)]
        registry = [s for s in decoded_strings if re.search(r"HKEY_|SOFTWARE\\|SYSTEM\\", s)]
        cmd_patterns = [s for s in decoded_strings if re.search(r"cmd\.exe|powershell|bash|/bin/sh", s, re.IGNORECASE)]
        suspicious_apis = [s for s in decoded_strings if re.search(r"CreateProcess|VirtualAlloc|WriteProcessMemory|LoadLibrary|GetProcAddress", s)]

        if urls:
            output_lines.append(f"\n📡 URLs embarcadas ({len(urls)}):")
            output_lines.extend(f"  - {u}" for u in urls[:10])
            findings.append(f"{len(urls)} URLs")

        if ips:
            output_lines.append(f"\n🌐 IPs embarcados ({len(ips)}):")
            output_lines.extend(f"  - {ip}" for ip in ips[:10])
            findings.append(f"{len(ips)} IPs")

        if registry:
            output_lines.append(f"\n🗝️ Chaves de Registro ({len(registry)}):")
            output_lines.extend(f"  - {r}" for r in registry[:5])
            findings.append("registry keys")

        if cmd_patterns:
            output_lines.append(f"\n⚠️ Chamadas de Shell detectadas:")
            output_lines.extend(f"  - {c}" for c in cmd_patterns[:5])
            findings.append("shell commands")

        if suspicious_apis:
            output_lines.append(f"\n🚨 APIs Suspeitas de Injeção/Loading:")
            output_lines.extend(f"  - {a}" for a in suspicious_apis[:5])
            findings.append("suspicious APIs")

        output_lines.append(f"\n📄 Total de strings extraídas: {len(decoded_strings)}")

        return DeobfuscationResult(
            ok=True,
            language="binary",
            original_length=len(data),
            output="\n".join(output_lines),
            findings=findings,
            passes_applied=["string_extraction", "ioc_detection", "pe_elf_header"],
        )

    # ── Auto-detect ─────────────────────────────────────────────────────────

    def auto_deobfuscate(self, payload: str | bytes) -> DeobfuscationResult:
        """Detecta automaticamente o tipo e aplica o deobfuscador correto."""
        if isinstance(payload, bytes):
            return self.analyze_binary(payload)

        code = payload.strip()

        # Heuristic: JS if function/var/eval/const keywords present
        js_markers = re.search(r"\b(function|var |const |let |eval\s*\(|document\.|window\.)\b", code)
        py_markers = re.search(r"\b(import |def |exec\s*\(|base64\.|zlib\.|__import__)\b", code)

        if js_markers and not py_markers:
            return self.deobfuscate_js(code)
        elif py_markers:
            return self.deobfuscate_python(code)
        else:
            # Try JS first, then Python
            js_res = self.deobfuscate_js(code)
            if js_res.passes_applied:
                return js_res
            return self.deobfuscate_python(code)
