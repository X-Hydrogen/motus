"""MOTUS memory — simple JSON-file session store."""
import json
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path.home() / ".motus" / "sessions"


class Memory:
    """Persist conversation history across sessions."""

    def __init__(self, session_id: str = None):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = MEMORY_DIR / f"{self.session_id}.json"
        self.messages: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.messages = json.loads(self.path.read_text())
            except Exception:
                self.messages = []

    def save(self):
        self.path.write_text(json.dumps(self.messages, ensure_ascii=False, indent=2))

    def add(self, role: str, content: str, tool_calls: list = None, tool_call_id: str = None, name: str = None):
        msg = {"role": role}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if tool_call_id:
            msg["tool_call_id"] = tool_call_id
        if name:
            msg["name"] = name
        self.messages.append(msg)
        self.save()

    @staticmethod
    def list_sessions(limit: int = 20) -> list[dict]:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for p in sorted(MEMORY_DIR.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(p.read_text())
                first_msg = next((m.get("content", "")[:100] for m in data if m["role"] == "user"), "")
                sessions.append({
                    "id": p.stem,
                    "messages": len(data),
                    "preview": first_msg,
                    "date": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                })
            except Exception:
                pass
        return sessions
