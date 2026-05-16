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
│   │   ├── md_build.py       # build_system: SMILES → Packmol assembly
│   │   ├── md_run.py         # run_md: GROMACS / LAMMPS / Desmond
│   │   ├── md_desmond.py     # model_desmond: Packmol PDB → Desmond .cms
│   │   ├── md_analyze.py     # analyze: energy, RDF, RMSD, H-bonds...
│   │   ├── md_comprehensive.py  # comprehensive_analysis: 9 modules + figures
│   │   ├── md_render.py      # render_system: VMD + Tachyon
│   │   ├── md_report.py      # generate_report: LaTeX → PDF (gold-standard template)
│   │   ├── md_read.py        # read_data: CSV/XVG/log inspection
│   │   └── md_system.py      # terminal, read_file, write_file, search_files
│   ├── templates/            # Paper templates
│   │   ├── paper-template-desmond.tex  # Gold standard (579 lines)
│   │   └── paper-reference.pdf         # Reference PDF (16pp, ~8000 words)
│   └── web/
│       ├── app.py           # Flask web server (port 8848)
│       └── tunnel.py        # Public tunnel helper (serveo)
├── scripts/
│   ├── build_hydrate_system.py  # Methane hydrate system builder
│   ├── build_by_packmol.py      # Multi-component Packmol assembly
│   └── fetch_molecule.py        # SMILES DB → 3D PDB
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

### Desmond Modeling Pipeline

The `model_desmond` tool converts Packmol-built PDBs to Desmond .cms files:

```
Packmol packed.pdb → pdbconvert → .mae → multisim (S-OPLS) → .cms
```

Critical rules (discovered through extensive testing):
- **Must use S-OPLS** — OPLS4 triggers mmlewis Lewis structure detection bug
- **Must use raw packed.pdb** — residue renaming breaks multisim post-processing
- **Must include build_geometry stage** in .msj with explicit box size
- Performance: ~46s for 10414-atom system (build_geometry 23s + forcefield 22s)

### Adding New Tools

1. Create `motus/tools/your_tool.py`
2. Define a handler function
3. Call `registry.register(name, desc, params, handler, emoji)`
4. The tool is auto-discovered by `discover_tools()`

### Running

```bash
# First-time setup on a new server
bash install.sh                  # Creates ~/.motus/.env and installs package

# CLI
motus "study methane hydrate formation"
motus                             # interactive

# Web
motus-web                         # http://localhost:8848
```

### Paper Quality Standards

The MOTUS Agent enforces a gold-standard paper template (16 pages, ~8000 words) for all Desmond publications. Key requirements:
- **11 mandatory rules** in the system prompt (loop.py Report Standards)
- Template at `motus/templates/paper-template-desmond.tex` (579 lines)
- Reference PDF at `motus/templates/paper-reference.pdf`
- Desmond auto-publish: `desmond/desmond-publish.sh` (one-click from analysis data)
- All figures use `[!ht]` + `\raggedbottom` + `\FloatBarrier` to prevent float-only pages
- Never mention Schrödinger (commercial) — use "Desmond engine" or "Desmond 8.2" only
