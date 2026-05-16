"""
MOTUS Agent — core conversation loop with streaming support.

Mirrors Hermes Agent architecture: LLM receives system prompt + tools,
iteratively chooses and executes tool calls until it delivers a final response.
Supports real-time streaming of LLM tokens to the UI.
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Callable, Optional

from motus.registry import registry, discover_tools
from motus.memory.store import Memory

DEEPSEEK_KEY = os.environ.get("MOTUS_DEEPSEEK_KEY", "")
if not DEEPSEEK_KEY:
    env_file = Path.home() / ".motus" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("MOTUS_DEEPSEEK_KEY="):
                DEEPSEEK_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_ITER = 500  # Effectively unlimited — agent works until task is done

MOTUS_SYSTEM_PROMPT = """You are **MOTUS** — an autonomous AI molecular scientist. You communicate like an experienced researcher, never showing raw tool outputs to the user.

## CRITICAL: Communication Rules
1. **NEVER show raw terminal output, file paths, or command results to the user.** Interpret everything into clear scientific prose.
2. **When you use tools, describe WHAT you're doing, not HOW.** Say "I'm now setting up the molecular system..." not "Running terminal command gmx..."
3. **Present results as a scientist would**: with context, interpretation, and clear conclusions.
4. **Report numbers in proper units with physical meaning.** "The Li⁺ diffusion coefficient is 0.31 ×10⁻⁵ cm²/s" NOT "D[Li] = 0.3071".
5. **Match the user's language strictly.** If the user writes in English, respond in English ONLY — every message, tool description, report, and status update must be English. If the user writes in Chinese, respond in Chinese. Never mix languages. Default to English when uncertain.
6. **Use Markdown formatting** for readability — headers, lists, bold for emphasis.

## Your Role
You are an autonomous MD scientist. You can:
- Design and build molecular simulation systems (SMILES → 3D → Packmol → run MD)
- Run GROMACS and LAMMPS simulations on GPU
- Analyze results comprehensively (energy, MSD, RDF, solvation, density, free volume, etc.)
- Generate publication-quality figures and LaTeX reports
- Teach molecular dynamics concepts when asked

## Available Tools
- **build_system** — Build molecular systems via Packmol (~90 molecules in SMILES DB)
- **run_md** — Execute full MD workflow (EM → NVT → NPT → Production) on GROMACS or LAMMPS
- **model_desmond** — Convert a Packmol-built system (packed.pdb) to a Desmond-ready .cms file using S-OPLS force field
- **comprehensive_analysis** — Run ALL 9 Desmond-style analysis modules + 9 publication figures. Covers thermodynamics, diffusion, RDF+CN, solvation shells, density profiles, molecular properties, free volume.
- **generate_report** — Generate and compile a LaTeX PDF report from completed analysis
- **render_system** — VMD molecular structure snapshots
- **read_file / write_file / search_files / terminal** — File and system operations

## Workflow for a Research Request
1. **Understand** — Parse what system and properties the user wants
2. **Build** — Use build_system with molecule names (leverages SMILES DB)
3. **Model for Desmond** (optional) — If user wants Desmond MD, use model_desmond after build_system to create .cms
4. **Simulate** — run_md: EM, NVT, NPT, Production (supports GROMACS, LAMMPS, Desmond)
5. **Analyze** — comprehensive_analysis: all 9 modules + figures
6. **Report** — generate_report: LaTeX → PDF
7. **Present** — Summarize findings in clear scientific language

## Environment
- GROMACS 2026 at /home/xenon/tools/gromacs-2026/
- GPU: NVIDIA RTX 3060 Ti (8 GB)
- LaTeX (pdflatex), VMD + Xvfb for rendering
- MOTUS scripts at /home/xenon/xhy/motus/

## Scientific Standards
- Always validate: check T, P, density, energy convergence
- Start conservative: 500ps-1ns first, then scale up
- Cite numbers with units and physical meaning
- Be honest about limitations (classical MD can't do bond breaking, etc.)

## Important Rules
- **You have effectively unlimited steps.** Keep working until the research is complete — build → simulate → analyze → report.
- **Don't get stuck retrying the same thing.** If a tool fails the same way 3 times, accept the result and try a different approach or move forward.
- **Progress over perfection.** An imperfect simulation that finishes is better than a perfect one that never starts.
- **When analysis or MD fails**, diagnose ONCE, fix ONCE, then move on.

## Report Standards (CRITICAL — MUST meet this quality bar)
When the research is complete, write the final report as LaTeX directly (use write_file, NOT generate_report template). The report MUST meet or exceed the quality of the reference paper at `/home/xenon/xhy/motus/agent/motus/templates/paper-reference.pdf` (16 pages, ~8000 words). Use `read_file` to load the reference LaTeX template from `/home/xenon/xhy/motus/agent/motus/templates/paper-template-desmond.tex` for structure guidance.

**MANDATORY requirements (paper will be REJECTED if missing):**

1. **Document class**: `\documentclass[twocolumn,10pt]{article}`, 2cm margins. Packages: graphicx, amsmath, booktabs, hyperref, caption, subcaption, siunitx, float, xcolor, enumitem, cleveref, placeins.
2. **Float placement**: `\raggedbottom`, `\renewcommand{\floatpagefraction}{0.7}`, ALL figures/tables use `[!ht]` (NOT `[htbp]`), `\FloatBarrier` before References.
3. **Abstract**: Inside `\twocolumn[...]` with `\maketitle` + abstract text + `\vspace{18pt}` (inside the bracket, not after `]`). Single paragraph, no subsection breaks. Followed by Keywords line.
4. **Title/Author**: Title = single bold line, no subtitle. Author = three-line MOTUS Agent format. `\date{}` (empty, no date).
5. **Structure** (all required — min 12 pages output):
   - **Introduction** (≥4 paragraphs): Background → problem → prior work → MOTUS → this work
   - **Computational Methods** (≥4 subsections): System Construction (SMILES, Packmol, composition), Force Field, Simulation Protocol (staged equilibration with timing), Analysis Pipeline (table of modules), Key Data Conventions (.ene columns, equilibration cutoff, API indexing)
   - **Results** (≥8 subsections): Each subsection MUST have ≥3 sentences of scientific discussion BEFORE the figure, and ≥2 sentences AFTER. Never stack figures without intervening text. Include: Performance, Thermodynamics (timeseries + distribution), Density, Spatial Profiles (1D + 2D), Radius of Gyration (formula + per-species analysis), Distance Monitoring (3 observations: short contacts, diffusive behavior, no association), Dipole Analysis (dielectric implications), Clustering + PCA (cluster stats + PCA variance explained + timeline interpretation), SIMA (bullet key observations), Dashboard
   - **Discussion** (≥6 subsections): Pipeline Performance (with timing table), Force Field Considerations, Simulation Timescale Limitations (3 bullet items), Computational Scalability Challenges, Comparison with Prior Studies, Future Directions (8 numbered items)
   - **Conclusion** (6 numbered contributions + concluding paragraph)
   - **References** (≥10, real citations)
6. **Figures**: `\linewidth`, `[!ht]`. Captions describe what reader sees AND physical meaning. Figure 1 = 5-panel system structure composite (VMD snapshot + molecule diagrams + pie chart + params).
7. **Tables**: `booktabs` style, `p{}` column widths to prevent overflow. Must include: Table 1 (simulation parameters), Table 2 (analysis modules with status), Table 3 (wall-clock performance).
8. **Numbers**: always with units (± uncertainty). Compare to experimental values.
9. **VMD rendering**: Licorice bond-line, `color Display Background white`, `axes location Off`, `scale by 1.2`, TachyonInternal → TGA → PNG.
10. **NEVER mention Schrödinger** (commercial software). Say "Desmond 8.2" or "Desmond engine" only.
11. **Limitations section MANDATORY**: bullet list explicitly separating classical MD capabilities from requirements for reactive/interfacial/electronic methods.
"""


class MOTUSAgent:
    """Autonomous MD research scientist with streaming support."""

    def __init__(self, session_id: str = None, abort_event=None):
        discover_tools()
        self.memory = Memory(session_id)
        self.workspace = Path("/home/xenon/xhy/motus/agent/workspaces") / self.memory.session_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tool_callback = None      # (iteration, fn_name, args, result) -> None
        self._text_callback = None      # (chunk: str) -> None  — streaming text tokens
        self._stage_callback = None     # (stage: str) -> None  — progress stage changes
        self._abort_event = abort_event # threading.Event to signal stop

    def set_stream_callbacks(self, text_cb=None, stage_cb=None):
        """Set callbacks for real-time streaming to UI."""
        self._text_callback = text_cb
        self._stage_callback = stage_cb

    def _emit_stage(self, stage: str):
        if self._stage_callback:
            self._stage_callback(stage)

    def _emit_text(self, chunk: str):
        if self._text_callback:
            self._text_callback(chunk)

    def chat(self, user_message: str) -> str:
        """Single-turn chat -- returns final response after tool-calling loop.

        Uses streaming API so text tokens are emitted in real-time via _text_callback.
        """
        if not self.memory.messages:
            self.memory.add("system", MOTUS_SYSTEM_PROMPT)

        self.memory.add("user", user_message)

        iteration = 0
        recent_calls = []  # Track recent tool calls for loop detection
        while iteration < MAX_ITER:
            # Check for abort signal
            if self._abort_event and self._abort_event.is_set():
                return "⏹️ Task stopped by user."
            
            iteration += 1
            self._emit_stage("reasoning")
            resp = self._call_llm_streaming()

            choice = resp["choices"][0]
            msg = choice["message"]
            finish = choice.get("finish_reason", "")

            if msg.get("tool_calls") and finish != "stop":
                # LLM wants to call tools
                self.memory.add("assistant", msg.get("content") or "", tool_calls=msg["tool_calls"])

                for tc in msg["tool_calls"]:
                    fn = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError as e:
                        fixed = raw_args.strip()
                        open_braces = fixed.count('{') - fixed.count('}')
                        open_brackets = fixed.count('[') - fixed.count(']')
                        fixed += '}' * open_braces + ']' * open_brackets
                        if not (fixed.rstrip().endswith('"') or fixed.rstrip().endswith('}')):
                            last_quote = max(fixed.rfind('"'), fixed.rfind("'"))
                            if last_quote > 0 and fixed.count('"') % 2 == 1:
                                fixed += '"'
                        try:
                            args = json.loads(fixed)
                            print(f"  [WARN] Fixed JSON for {fn}: {str(e)[:80]}")
                        except json.JSONDecodeError:
                            print(f"  [ERROR] Cannot parse tool args for {fn}: {raw_args[:200]}")
                            result = f"Error: Invalid arguments for {fn}: {str(e)}"
                            self.memory.add("tool", result, tool_call_id=tc["id"], name=fn)
                            continue
                    
                    # === LOOP DETECTION ===
                    # Track this call and check for repetition
                    call_key = f"{fn}:{json.dumps(args, sort_keys=True)}"
                    recent_calls.append(call_key)
                    if len(recent_calls) > 10:
                        recent_calls.pop(0)
                    # If same call appears 3+ times in recent history, inject a nudge
                    same_count = recent_calls.count(call_key)
                    if same_count >= 3:
                        print(f"  [LOOP] Detected {fn} called {same_count}x — injecting nudge")
                        self.memory.add("tool", 
                            f"⚠️ You've called {fn} with the same arguments {same_count} times. "
                            f"Stop retrying. Accept the current state and move forward. "
                            f"If something failed, try a DIFFERENT approach or skip this step.",
                            tool_call_id=tc["id"], name="system_nudge")
                        recent_calls = []  # Reset to give the nudge a chance
                        continue
                    
                    if fn in ("build_system", "run_md", "analyze"):
                        args["job_dir"] = str(self.workspace)

                    # Map tool to stage
                    stage_map = {
                        "build_system": "building",
                        "run_md": "simulating",
                        "comprehensive_analysis": "analyzing",
                        "generate_report": "writing",
                    }
                    self._emit_stage(stage_map.get(fn, "executing"))

                    result = registry.dispatch(fn, args)
                    if len(result) > 6000:
                        result = result[:6000] + f"\n... [truncated, {len(result)} total]"

                    self.memory.add("tool", result, tool_call_id=tc["id"], name=fn)

                    if self._tool_callback:
                        self._tool_callback(iteration, fn, args, result)
                    else:
                        short_args = {k: v for k, v in args.items() if k != "job_dir"}
                        print(f"  [{iteration}] {fn}({json.dumps(short_args, ensure_ascii=False)})")
                        print(f"       → {result[:150]}...")
            else:
                content = msg.get("content", "")
                self.memory.add("assistant", content)
                return content

        return ("I've completed extensive work on this research task but haven't yet reached a final conclusion. "
                "The work in progress is saved. You can ask me to continue or start a new direction.")

    def _call_llm_streaming(self) -> dict:
        """Call DeepSeek API with stream=True. Emits text tokens in real-time.

        Accumulates tool_calls across chunks and returns the full reconstructed response.
        """
        headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL,
            "messages": self.memory.messages,
            "tools": registry.get_schemas(),
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": True,
        }

        for attempt in range(3):
            try:
                r = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=120, stream=True)
                if r.status_code != 200:
                    print(f"  [API] {r.status_code}, retrying...")
                    time.sleep(2 ** attempt)
                    continue

                # Accumulate across streaming chunks
                text_content = ""
                tool_call_buf = {}  # index -> {id, function: {name, arguments}}
                finish_reason = None

                for line in r.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    finish_reason = chunk.get("choices", [{}])[0].get("finish_reason") or finish_reason

                    # Stream text tokens
                    if delta.get("content"):
                        text_content += delta["content"]
                        self._emit_text(delta["content"])

                    # Accumulate tool_calls
                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        if idx not in tool_call_buf:
                            tool_call_buf[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_call_buf[idx]
                        if tc.get("id"):
                            entry["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            entry["function"]["name"] += tc["function"]["name"]
                        if tc.get("function", {}).get("arguments"):
                            entry["function"]["arguments"] += tc["function"]["arguments"]

                # Build final response
                tool_calls = [tool_call_buf[i] for i in sorted(tool_call_buf.keys())] if tool_call_buf else None

                return {
                    "choices": [{
                        "finish_reason": finish_reason or "stop",
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": text_content or None,
                            **({"tool_calls": tool_calls} if tool_calls else {}),
                        },
                    }],
                }

            except Exception as e:
                print(f"  [API] {e}, retrying...")
                time.sleep(2 ** attempt)

        raise RuntimeError("DeepSeek API failed after 3 attempts")

    def _call_llm(self) -> dict:
        """Non-streaming fallback (used when streaming not desired)."""
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
