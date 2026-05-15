"""
System tools: terminal, read_file, write_file, search_files.
These give MOTUS the same basic capabilities as Hermes.
"""
import subprocess
from pathlib import Path
from motus.registry import registry


def _terminal(args: dict) -> str:
    """Run a shell command."""
    cmd = args.get("command", "")
    timeout = args.get("timeout", 120)
    workdir = args.get("workdir", None)
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=workdir,
        )
        out = r.stdout[-5000:] if r.stdout else ""
        err = r.stderr[-1000:] if r.stderr else ""
        result = out
        if err:
            result += f"\n[stderr]\n{err}"
        if r.returncode != 0:
            result += f"\n[exit={r.returncode}]"
        return result.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Terminal error: {e}"


def _write_file(args: dict) -> str:
    """Write content to a file."""
    path = args.get("path", "")
    content = args.get("content", "")
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"Write error: {e}"


def _read_file(args: dict) -> str:
    """Read a file, optionally with offset/limit."""
    path = args.get("path", "")
    offset = args.get("offset", 1)
    limit = args.get("limit", 500)
    try:
        lines = Path(path).read_text().splitlines()
        total = len(lines)
        start = max(0, offset - 1)
        end = min(start + limit, total)
        result = "\n".join(f"{i+1}|{line}" for i, line in enumerate(lines[start:end], start=start))
        header = f"=== {path} (lines {start+1}-{end} of {total}) ===\n"
        return header + result
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def _search_files(args: dict) -> str:
    """Find files by glob pattern."""
    pattern = args.get("pattern", "*")
    path = args.get("path", ".")
    try:
        matches = list(Path(path).rglob(pattern))
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:50]
        lines = []
        for m in matches:
            size = m.stat().st_size if m.is_file() else 0
            lines.append(f"  {m}  ({size} bytes)" if m.is_file() else f"  {m}/")
        return "\n".join(lines[:50])
    except Exception as e:
        return f"Search error: {e}"


# Register all system tools at import time
registry.register(
    "terminal", "Run a shell command (gmx, python, pdflatex, file ops)",
    {"command": {"type": "string", "description": "Shell command to execute"},
     "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)"},
     "workdir": {"type": "string", "description": "Working directory (optional)"}},
    _terminal, emoji="💻",
)

registry.register(
    "write_file", "Write content to a file, creating parent directories as needed",
    {"path": {"type": "string", "description": "Absolute file path to write"},
     "content": {"type": "string", "description": "File content"}},
    _write_file, emoji="✏️",
)

registry.register(
    "read_file", "Read a text file with line numbers. Use offset and limit for large files.",
    {"path": {"type": "string", "description": "File path to read"},
     "offset": {"type": "integer", "description": "Line number to start from (1-indexed, default 1)"},
     "limit": {"type": "integer", "description": "Max lines (default 500)"}},
    _read_file, emoji="📄",
)

registry.register(
    "search_files", "Find files by glob pattern (e.g. '*.gro', '*.xvg', '*.log')",
    {"pattern": {"type": "string", "description": "Glob pattern to match"},
     "path": {"type": "string", "description": "Directory to search in (default: current)"}},
    _search_files, emoji="🔍",
)
