"""
MOTUS Tool Registry — Hermes-style auto-discovery.

Tool modules in motus/tools/ call registry.register() at module level.
discover_tools() auto-imports them. The agent loop queries registry for schemas.
"""

import importlib
from pathlib import Path
from typing import Callable, Optional


class ToolEntry:
    __slots__ = ("name", "description", "parameters", "handler", "emoji")

    def __init__(self, name: str, description: str, parameters: dict,
                 handler: Callable, emoji: str = "🔧"):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.emoji = emoji

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys()),
                },
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolEntry] = {}

    def register(self, name: str, description: str, parameters: dict,
                 handler: Callable, emoji: str = "🔧") -> None:
        self._tools[name] = ToolEntry(name, description, parameters, handler, emoji)

    def get(self, name: str) -> Optional[ToolEntry]:
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def get_all_names(self) -> list[str]:
        return list(self._tools.keys())

    def dispatch(self, name: str, args: dict) -> str:
        entry = self.get(name)
        if not entry:
            return f"Unknown tool: {name}"
        try:
            return entry.handler(args)
        except Exception as e:
            import traceback
            return f"Tool error: {e}\n{traceback.format_exc()[:500]}"


# Singleton
registry = ToolRegistry()


def discover_tools(package: str = "motus.tools") -> list[str]:
    """Import all tool modules in the package. Returns list of module names."""
    import motus.tools
    tools_dir = Path(motus.tools.__path__[0])
    imported = []
    for path in sorted(tools_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod_name = f"{package}.{path.stem}"
        try:
            importlib.import_module(mod_name)
            imported.append(mod_name)
        except Exception as e:
            print(f"  [WARN] Failed to import {mod_name}: {e}")
    return imported
