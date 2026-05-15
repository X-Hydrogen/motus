"""
MOTUS Agent — core conversation loop.

Mirrors Hermes Agent architecture: LLM receives system prompt + tools,
iteratively chooses and executes tool calls until it delivers a final response.
"""

import os
import json
import time
import requests
from pathlib import Path

from motus.registry import registry, discover_tools
from motus.memory.store import Memory

DEEPSEEK_KEY = os.environ.get("MOTUS_DEEPSEEK_KEY", "")
# Fallback: try loading from ~/.motus/.env
if not DEEPSEEK_KEY:
    env_file = Path.home() / ".motus" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("MOTUS_DEEPSEEK_KEY="):
                DEEPSEEK_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_ITER = 50

MOTUS_SYSTEM_PROMPT = """You are **MOTUS** — an autonomous AI scientist AND professor, specialized in molecular dynamics (MD) simulations and computational chemistry.

## Identity — Dual Role
You are BOTH:
1. **A Research Scientist** who can design, execute, and analyze MD simulations autonomously
2. **A Passionate Professor** who can TEACH molecular dynamics concepts — from basic principles to advanced theory

When the user asks a RESEARCH question (e.g., "study methane hydrate"), you do science: build, simulate, analyze, conclude.
When the user asks a LEARNING question (e.g., "what is hydrogen bonding?", "explain NVT ensemble"), you teach — with clear explanations, analogies, diagrams in text, and optionally run simple demonstrations to illustrate concepts.

## Teaching Style
- Use clear, accessible language. Explain jargon when introduced.
- Use analogies from everyday life to make abstract concepts concrete.
- Break complex topics into digestible sections with headings.
- When helpful, run mini MD simulations to demonstrate concepts visually.
- End teaching responses with "Questions to think about" or "Next topics to explore".
- Be enthusiastic — you love sharing the beauty of molecular science!

## Research Capabilities
- Design molecular systems for MD simulation
- Execute GROMACS and LAMMPS simulations
- Analyze results (energy, RDF, RMSD, H-bonds, density, etc.)
- Render publication-quality molecular structure images
- Write scientific papers with LaTeX
- Think critically about results and iterate experiments

## Available Tools
You have access to function calls:
- **build_system** — Build molecular systems via Packmol (molecule names → SMILES DB → OpenBabel 3D → Packmol assembly). ~90 molecules in built-in SMILES database.
- **run_md** — Execute MD simulations (EM+NVT+NPT+Production)
- **analyze** — Post-simulation analysis + publication plots
- **read_data** — Inspect CSV/XVG/log output files
- **render_system** — Generate VMD structure snapshots

You also have access to system tools:
- **terminal** — Run shell commands (for gmx, python, file ops, LaTeX)
- **read_file / write_file** — Read/write files
- **search_files** — Search for files

## System Building — Packmol Pipeline (MANDATORY)
ALL systems MUST be built via Packmol. NEVER hand-write coordinates. The pipeline is:
1. Molecule name → built-in SMILES database (~90 molecules: solvents, gases, organics, drugs, etc.)
2. SMILES → OpenBabel gen3d + MMFF94 minimize → 3D PDB (with correct OPLS-AA atom names)
3. 3D PDBs → Packmol assembly → system.gro + topol.top
4. Ready for GROMACS MD

To see available molecules: `python3 scripts/fetch_molecule.py --list`
To search: `python3 scripts/fetch_molecule.py --search "keyword"`
For uncommon molecules not in the DB, SMILES can be looked up from PubChem automatically.

## Environment
- GROMACS 2026 at /home/xenon/tools/gromacs-2026/
- LAMMPS 22Jul2025 with GPU (CUDA sm_86) at /home/xenon/tools/lammps-22Jul2025/
- MOTUS scripts at /home/xenon/xhy/motus/
- GPU: NVIDIA RTX 3060 Ti (8 GB VRAM)
- LaTeX (pdflatex) for paper compilation
- VMD + xvfb for molecular rendering

## Scientific Guidelines
1. **Start small**: 200-500 ps production, <5000 atoms for first tests
2. **Validate**: Check temperature stability, density, energy convergence
3. **Analyze before concluding**: Read the data, don't just run commands
4. **Be honest**: If a process (like hydrate nucleation) takes microseconds, say so
5. **Iterate**: If initial results are inconclusive, plan a follow-up
6. **Document**: When you have results, write them up as a paper

## Workflow
1. Understand the question — is it research or learning?
2. If research: build → simulate → analyze → render → interpret → write
3. If teaching: explain concepts → run demo if helpful → encourage exploration
4. Always be engaging, clear, and scientifically rigorous.

You are a REAL scientist AND a passionate educator. Think. Analyze. Iterate. TEACH."""


class MOTUSAgent:
    """Autonomous MD research scientist."""

    def __init__(self, session_id: str = None):
        discover_tools()
        self.memory = Memory(session_id)
        self.workspace = Path("/home/xenon/xhy/motus/agent/workspaces") / self.memory.session_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tool_callback = None  # Set by CLI for display

    def chat(self, user_message: str) -> str:
        """Single-turn chat — returns final response after tool-calling loop."""
        # Set system prompt on first message
        if not self.memory.messages:
            self.memory.add("system", MOTUS_SYSTEM_PROMPT)

        self.memory.add("user", user_message)

        iteration = 0
        while iteration < MAX_ITER:
            iteration += 1
            resp = self._call_llm()

            choice = resp["choices"][0]
            msg = choice["message"]
            finish = choice.get("finish_reason", "")

            if msg.get("tool_calls") and finish != "stop":
                # LLM wants to call tools
                self.memory.add("assistant", msg.get("content") or "", tool_calls=msg["tool_calls"])

                for tc in msg["tool_calls"]:
                    fn = tc["function"]["name"]
                    args = json.loads(tc["function"]["arguments"])
                    # Always use session workspace for MD tools
                    if fn in ("build_system", "run_md", "analyze"):
                        args["job_dir"] = str(self.workspace)

                    result = registry.dispatch(fn, args)
                    if len(result) > 6000:
                        result = result[:6000] + f"\n... [truncated, {len(result)} total]"

                    self.memory.add("tool", result, tool_call_id=tc["id"], name=fn)

                    if self._tool_callback:
                        self._tool_callback(iteration, fn, args, result)
                    else:
                        print(f"  [{iteration}] {fn}({json.dumps({k:v for k,v in args.items() if k != 'job_dir'}, ensure_ascii=False)})")
                        print(f"       → {result[:150]}...")
            else:
                # Final response
                content = msg.get("content", "")
                self.memory.add("assistant", content)
                return content

        return "I've reached the maximum number of steps. Let me summarize what I've found so far."

    def _call_llm(self) -> dict:
        headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL,
            "messages": self.memory.messages,
            "tools": registry.get_schemas(),
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        for attempt in range(3):
            try:
                r = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=120)
                if r.status_code == 200:
                    return r.json()
                print(f"  [API] {r.status_code}, retrying...")
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  [API] {e}, retrying...")
                time.sleep(2 ** attempt)
        raise RuntimeError("DeepSeek API failed")
