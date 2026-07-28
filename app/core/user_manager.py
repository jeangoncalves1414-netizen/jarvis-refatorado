from __future__ import annotations

import json
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import List


USERS_FILE = Path("data/users.json")


@dataclass
class User:
    id: str
    name: str
    permissions: List[str]


class UserManager:
    """Gerenciamento de usuários."""
    
    def __init__(self):
        self._users = self._load()
    
    def _load(self) -> dict[str, User]:
        if not USERS_FILE.exists():
            return {}
        try:
            data = json.loads(USERS_FILE.read_text())
            return {u["id"]: User(**u) for u in data.get("users", [])}
        except Exception:
            return {}
    
    def save(self) -> None:
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "users": [
                {"id": u.id, "name": u.name, "permissions": u.permissions}
                for u in self._users.values()
            ]
        }
        USERS_FILE.write_text(json.dumps(data, indent=2))
    
    def create(self, name: str, permissions: List[str]) -> User:
        user = User(id=uuid.uuid4().hex[:12], name=name, permissions=permissions)
        self._users[user.id] = user
        self.save()
        return user
    
    def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)
    
    def list(self) -> List[User]:
        return list(self._users.values())
