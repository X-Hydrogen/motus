"""Tool: read MD data files (CSV, XVG, log)."""
from pathlib import Path
from motus.registry import registry


def read_data(args: dict) -> str:
    """Read and return contents of MD data files."""
    path = args["path"]
    max_lines = args.get("max_lines", 80)

    fp = Path(path)
    if fp.is_dir():
        # List directory contents instead of erroring
        files = sorted(fp.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:30]
        listing = "\n".join(f"  {f.name}  ({f.stat().st_size} bytes)" if f.is_file() else f"  {f.name}/" for f in files)
        return f"'{fp}' is a directory. Contents:\n{listing}\n\nUse read_data with a specific file path."
    if not fp.exists():
        return f"File not found: {fp}"

    try:
        text = fp.read_text()
    except Exception as e:
        return f"Error: {e}"

    lines = text.split("\n")
    total = len(lines)

    if fp.suffix == ".csv":
        # Return header + first data rows + column names
        header = lines[0] if lines else ""
        sample = "\n".join(lines[1:max_lines+1])
        return (f"=== {fp.name} ({total} lines) ===\n"
                f"Columns: {header}\n"
                f"--- first {min(max_lines, total-1)} rows ---\n"
                f"{sample}\n"
                f"--- end ---")

    elif fp.suffix in (".xvg", ".log"):
        # Filter out comment lines for XVG
        content_lines = [l for l in lines if not l.startswith(("#", "@"))]
        return (f"=== {fp.name} ({total} lines, {len(content_lines)} data lines) ===\n"
                + "\n".join(content_lines[:max_lines])
                + (f"\n... ({len(content_lines) - max_lines} more lines)" if len(content_lines) > max_lines else ""))

    else:
        return f"=== {fp.name} ({total} lines) ===\n" + "\n".join(lines[:max_lines])


registry.register(
    name="read_data",
    description="Read MD analysis output files (CSV, XVG energy files, log files) to inspect simulation results.",
    parameters={
        "path": {"type": "string", "description": "Path to data file"},
        "max_lines": {"type": "integer", "description": "Max lines to return (default 80)"},
    },
    handler=read_data,
    emoji="📄",
)
