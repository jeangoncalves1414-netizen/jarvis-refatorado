"""Limpeza de memória e hábitos em modo simulação.

Remove duplicatas, linhas de teste e dados antigos de smoke tests.
NUNCA aponta para c:/Users/maria/Desktop/Jarvis/data em --apply.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path


def normalize_name(text: str) -> str:
    """Nome normalizado: sem acento, minúsculo, espaços simples."""
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().split())


def scan_user_profile(data_dir: Path) -> dict:
    """Escaneia USER-PROFILE.md e retorna problemas."""
    profile_path = data_dir / "vault" / "02-User-Profile" / "USER-PROFILE.md"
    if not profile_path.exists():
        return {}
    
    content = profile_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    issues = []
    # Detect duplicates (consecutive lines with same content)
    for i in range(len(lines) - 1):
        if lines[i].strip() and lines[i] == lines[i + 1]:
            issues.append(f"Linha duplicada {i+1}: {lines[i][:60]}")
    
    # Detect template placeholders
    if "Nome**: Usuário" in content or "Nome: Usuário" in content:
        issues.append("Encontrado placeholder 'Nome**: Usuário' ou 'Nome: Usuário'")
    
    # Detect unittest lines
    for i, line in enumerate(lines, 1):
        if "unittest" in line.lower() or "test" in line.lower() and "Testando" in line:
            issues.append(f"Linha {i} parece ser de teste: {line[:60]}")
    
    return {"file": str(profile_path), "issues": issues} if issues else {}


def scan_daily_notes(data_dir: Path) -> dict:
    """Escaneia notas diárias por 'Testando integração do Memory Vault'."""
    vault_dir = data_dir / "vault"
    if not vault_dir.exists():
        return {}
    
    test_notes = []
    for folder in ["01-Daily-Notes", "03-Notes"]:
        folder_path = vault_dir / folder
        if folder_path.exists():
            for md_file in folder_path.glob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    if "Testando integração do Memory Vault" in content:
                        test_notes.append(str(md_file.relative_to(data_dir)))
                except (OSError, UnicodeError):
                    pass
    
    return {"test_notes": test_notes} if test_notes else {}


def scan_memory_json(data_dir: Path) -> dict:
    """Escaneia memory.json por preferências recusadas por context_policy."""
    memory_file = data_dir / "memory.json"
    if not memory_file.exists():
        return {}
    
    try:
        data = json.loads(memory_file.read_text(encoding="utf-8"))
        # Check for preferences that would be refused
        preferences = data.get("preferences", [])
        refused = [p for p in preferences if isinstance(p, dict) and 
                   ("explicit_preference" in str(p).lower() or "smoke" in str(p).lower())]
        return {"refused_preferences": refused} if refused else {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def scan_preferences_json(data_dir: Path) -> dict:
    """Escaneia preferences.json por dados de smoke test (Alex, VS Code)."""
    prefs_file = data_dir / "preferences.json"
    if not prefs_file.exists():
        return {}
    
    try:
        data = json.loads(prefs_file.read_text(encoding="utf-8"))
        smoke_indicators = []
        if data.get("user_name") == "Alex":
            smoke_indicators.append("user_name='Alex'")
        if data.get("preferred_editor") == "VS Code":
            smoke_indicators.append("preferred_editor='VS Code'")
        return {"smoke_test_data": smoke_indicators} if smoke_indicators else {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def scan_duplicate_habits(data_dir: Path) -> dict:
    """Escaneia lifestyle.db por hábitos ativos duplicados (normalize_name)."""
    db_path = data_dir / "lifestyle.db"
    if not db_path.exists():
        return {}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT id, name, created_at FROM habits WHERE archived = 0 ORDER BY created_at ASC")
        habits = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        seen: dict[str, list] = {}
        for habit in habits:
            key = normalize_name(habit["name"])
            if key not in seen:
                seen[key] = []
            seen[key].append(habit)
        
        duplicates = {key: items for key, items in seen.items() if len(items) > 1}
        if duplicates:
            # Would archive newer ones (keep oldest)
            actions = []
            for key, items in duplicates.items():
                for item in items[1:]:  # Skip first (oldest)
                    actions.append({
                        "action": "archive",
                        "id": item["id"],
                        "name": item["name"],
                        "created_at": datetime.fromtimestamp(item["created_at"]).isoformat()
                    })
            return {"duplicate_habits": actions}
        return {}
    except (sqlite3.Error, OSError):
        return {}


def scan_morning_logs_after_noon(data_dir: Path) -> dict:
    """Escaneia habit_logs por 'saudação matinal' a partir das 12h."""
    db_path = data_dir / "lifestyle.db"
    if not db_path.exists():
        return {}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, habit_id, date_str, notes, timestamp FROM habit_logs "
            "WHERE notes LIKE '%saudação matinal%'"
        )
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        invalid = []
        for log in logs:
            ts = datetime.fromtimestamp(log["timestamp"])
            if ts.hour >= 12:
                invalid.append({
                    "id": log["id"],
                    "habit_id": log["habit_id"],
                    "date": log["date_str"],
                    "hour": ts.hour,
                    "notes": log["notes"]
                })
        
        return {"invalid_morning_logs": invalid} if invalid else {}
    except (sqlite3.Error, OSError):
        return {}


def apply_cleanup(data_dir: Path, dry_run_results: dict) -> None:
    """Aplica limpeza (com backup) baseado nos resultados do dry-run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = data_dir / "backups" / f"cleanup-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Backup em: {backup_dir}")
    
    # USER-PROFILE.md
    if "user_profile" in dry_run_results and dry_run_results["user_profile"].get("issues"):
        profile_path = Path(dry_run_results["user_profile"]["file"])
        if profile_path.exists():
            shutil.copy2(profile_path, backup_dir / "USER-PROFILE.md")
            # For simplicity, just report - actual cleaning logic would remove duplicates/placeholders
            print(f"  Copiado {profile_path.name} para backup (limpeza manual necessária)")
    
    # Daily notes
    if "daily_notes" in dry_run_results and dry_run_results["daily_notes"].get("test_notes"):
        for note_rel in dry_run_results["daily_notes"]["test_notes"]:
            note_path = data_dir / note_rel
            if note_path.exists():
                shutil.copy2(note_path, backup_dir / note_path.name)
                note_path.unlink()
                print(f"  Removido: {note_rel}")
    
    # memory.json
    if "memory_json" in dry_run_results and dry_run_results["memory_json"].get("refused_preferences"):
        memory_file = data_dir / "memory.json"
        if memory_file.exists():
            shutil.copy2(memory_file, backup_dir / "memory.json")
            # Clean and rewrite
            data = json.loads(memory_file.read_text(encoding="utf-8"))
            data["preferences"] = [p for p in data.get("preferences", []) 
                                   if not ("explicit_preference" in str(p).lower() or "smoke" in str(p).lower())]
            memory_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Limpo memory.json ({len(dry_run_results['memory_json']['refused_preferences'])} preferências removidas)")
    
    # preferences.json
    if "preferences_json" in dry_run_results and dry_run_results["preferences_json"].get("smoke_test_data"):
        prefs_file = data_dir / "preferences.json"
        if prefs_file.exists():
            shutil.copy2(prefs_file, backup_dir / "preferences.json")
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
            if data.get("user_name") == "Alex":
                data.pop("user_name", None)
            if data.get("preferred_editor") == "VS Code":
                data.pop("preferred_editor", None)
            prefs_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Limpo preferences.json (dados de smoke test removidos)")
    
    # Duplicate habits
    if "duplicate_habits" in dry_run_results and dry_run_results["duplicate_habits"].get("duplicate_habits"):
        db_path = data_dir / "lifestyle.db"
        shutil.copy2(db_path, backup_dir / "lifestyle.db")
        conn = sqlite3.connect(db_path)
        for action in dry_run_results["duplicate_habits"]["duplicate_habits"]:
            conn.execute("UPDATE habits SET archived = 1, updated_at = ? WHERE id = ?",
                         (datetime.now().timestamp(), action["id"]))
        conn.commit()
        conn.close()
        print(f"  Arquivados {len(dry_run_results['duplicate_habits']['duplicate_habits'])} hábitos duplicados")
    
    # Morning logs after noon
    if "morning_logs" in dry_run_results and dry_run_results["morning_logs"].get("invalid_morning_logs"):
        db_path = data_dir / "lifestyle.db"
        if backup_dir / "lifestyle.db" not in backup_dir.iterdir():
            shutil.copy2(db_path, backup_dir / "lifestyle.db")
        conn = sqlite3.connect(db_path)
        for log in dry_run_results["morning_logs"]["invalid_morning_logs"]:
            conn.execute("DELETE FROM habit_logs WHERE id = ?", (log["id"],))
        conn.commit()
        conn.close()
        print(f"  Removidos {len(dry_run_results['morning_logs']['invalid_morning_logs'])} logs de saudação após 12h")


def main():
    parser = argparse.ArgumentParser(description="Limpeza de memória e hábitos (modo simulação padrão)")
    parser.add_argument("--data-dir", default="data", help="Diretório de dados (padrão: data)")
    parser.add_argument("--apply", action="store_true", help="Aplicar mudanças (cria backup antes)")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir).resolve()
    
    # Safety: refuse to apply to real data directory
    if args.apply and "Desktop" in str(data_dir) and "Jarvis" in str(data_dir) and data_dir.name == "data":
        print("ERRO: Recusado aplicar --apply no diretório de dados real do projeto.", file=sys.stderr)
        print(f"  Caminho: {data_dir}", file=sys.stderr)
        print("  Use um diretório temporário para testes.", file=sys.stderr)
        sys.exit(1)
    
    if not data_dir.exists():
        print(f"ERRO: Diretório {data_dir} não existe.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Escaneando: {data_dir}")
    print()
    
    results = {
        "user_profile": scan_user_profile(data_dir),
        "daily_notes": scan_daily_notes(data_dir),
        "memory_json": scan_memory_json(data_dir),
        "preferences_json": scan_preferences_json(data_dir),
        "duplicate_habits": scan_duplicate_habits(data_dir),
        "morning_logs": scan_morning_logs_after_noon(data_dir),
    }
    
    has_issues = any(v for v in results.values())
    
    if not has_issues:
        print("✓ Nenhum problema encontrado.")
        return
    
    print("PROBLEMAS ENCONTRADOS:\n")
    
    for key, data in results.items():
        if not data:
            continue
        
        if key == "user_profile":
            print(f"USER-PROFILE.md ({data['file']}):")
            for issue in data["issues"]:
                print(f"  - {issue}")
            print()
        
        elif key == "daily_notes":
            print(f"Notas diárias com 'Testando integração do Memory Vault':")
            for note in data["test_notes"]:
                print(f"  - {note}")
            print()
        
        elif key == "memory_json":
            print(f"memory.json - preferências recusadas:")
            for pref in data["refused_preferences"]:
                print(f"  - {pref}")
            print()
        
        elif key == "preferences_json":
            print(f"preferences.json - dados de smoke test:")
            for indicator in data["smoke_test_data"]:
                print(f"  - {indicator}")
            print()
        
        elif key == "duplicate_habits":
            print(f"Hábitos ativos duplicados (arquivaria os mais novos):")
            for action in data["duplicate_habits"]:
                print(f"  - {action['name']} (id={action['id']}, criado em {action['created_at']})")
            print()
        
        elif key == "morning_logs":
            print(f"Logs de 'saudação matinal' a partir das 12h (removeria):")
            for log in data["invalid_morning_logs"]:
                print(f"  - {log['date']} às {log['hour']}h (habit_id={log['habit_id']})")
            print()
    
    if not args.apply:
        print("Modo simulação. Use --apply para aplicar as mudanças (com backup).")
    else:
        print("Aplicando mudanças...")
        apply_cleanup(data_dir, results)
        print("\n✓ Limpeza concluída.")


if __name__ == "__main__":
    main()
