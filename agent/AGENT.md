# MOTUS Agent

## Developer Guide

### Architecture

```
agent/
├── motus_cli.py           # CLI entry point (interactive + one-shot)
├── motus/
│   ├── __init__.py         # Version: 1.0.0
│   ├── loop.py             # Core LLM conversation loop (DeepSeek)
│   ├── registry.py         # Tool registry + auto-discovery
│   ├── memory/
│   │   └── store.py        # JSON-file session persistence
│   ├── tools/
│   │   ├── md_build.py     # build_system: water, methane, hydrate
│   │   ├── md_run.py       # run_md: GROMACS / LAMMPS
│   │   ├── md_analyze.py   # analyze: energy, RDF, RMSD, H-bonds...
│   │   ├── md_render.py    # render_system: VMD + Tachyon
│   │   ├── md_read.py      # read_data: CSV/XVG/log inspection
│   │   └── md_system.py    # terminal, read_file, write_file, search_files
│   └── web/
│       ├── app.py           # Flask web server (port 8848)
│       └── tunnel.py        # Public tunnel helper (serveo)
├── scripts/
│   └── build_hydrate_system.py  # Methane hydrate system builder
└── pyproject.toml          # v1.0.0, setuptools
```

### LLM Backend

- **Provider**: DeepSeek (`deepseek-chat`)
- **API Key**: Environment variable `MOTUS_DEEPSEEK_KEY` or file `~/.motus/.env`
- **Endpoint**: `https://api.deepseek.com/v1/chat/completions`

### Tool Execution Loop

Mimics Hermes Agent architecture:
1. LLM receives system prompt + tool schemas
2. Iteratively chooses and executes tool calls
3. Final response delivered to user

### Adding New Tools

1. Create `motus/tools/your_tool.py`
2. Define a handler function
3. Call `registry.register(name, desc, params, handler, emoji)`
4. The tool is auto-discovered by `discover_tools()`

### Running

```bash
# CLI
motus "study methane hydrate formation"
motus                             # interactive

# Web
motus-web                         # http://localhost:8848
```
