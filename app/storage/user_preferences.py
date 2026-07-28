from __future__ import annotations

import json
import os
import re
from typing import List, Dict

DATA_DIR = os.path.join(os.getcwd(), "data")
PREFERENCES_FILE = os.path.join(DATA_DIR, "preferences.json")
os.makedirs(DATA_DIR, exist_ok=True)

class PreferenceStore:
    def __init__(self) -> None:
        self.file_path = PREFERENCES_FILE

    def _read(self) -> Dict[str, List[str]]:
        if not os.path.exists(self.file_path):
            return {"preferences": []}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"preferences": []}

    def _write(self, data: Dict[str, List[str]]) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[PreferenceStore] Erro ao salvar preferências: {e}")

    def add_preference(self, pref: str) -> bool:
        pref = pref.strip()
        if not pref or len(pref) < 3:
            return False
        data = self._read()
        prefs = data.get("preferences", [])
        if pref not in prefs:
            prefs.append(pref)
            data["preferences"] = prefs
            self._write(data)
            return True
        return False

    def get_preferences(self) -> List[str]:
        return self._read().get("preferences", [])

    def extract_from_text(self, text: str) -> List[str]:
        """Detecta expressões típicas de preferências no texto do usuário."""
        patterns = [
            (r"(?:eu\s+)?prefiro\s+([^.,;!\n]+)", "Preferência: prefere "),
            (r"(?:minha\s+)?preferência\s+é\s+([^.,;!\n]+)", "Preferência: "),
            (r"não\s+gosto\s+de\s+([^.,;!\n]+)", "Preferência: não gosta de "),
            (r"eu\s+gosto\s+de\s+([^.,;!\n]+)", "Preferência: gosta de "),
            (r"meu\s+nome\s+é\s+([^.,;!\n]+)", "Nome do Usuário: "),
            (r"pode\s+me\s+chamar\s+de\s+([^.,;!\n]+)", "Nome preferido: "),
        ]
        found = []
        for pat, prefix in patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                m_clean = m.strip()
                if m_clean and len(m_clean) >= 2:
                    entry = f"{prefix}{m_clean}"
                    found.append(entry)
                    self.add_preference(entry)
        return found

preference_store = PreferenceStore()
