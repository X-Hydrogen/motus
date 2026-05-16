#!/usr/bin/env python3
"""
MOTUS Agent — Autonomous Molecular Dynamics AI Scientist.

Usage:
    motus                              # Interactive chat
    motus "research question"          # One-shot research
    motus --session <id>               # Resume a session
    motus --list                       # List past sessions
    motus --version                    # Show version
    motus --help                       # Show help

Setup:
    bash install.sh                    # One-time: creates ~/.motus/.env, pip install
    nano ~/.motus/.env                 # Set your DeepSeek API key

Version: 1.0.0
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from motus import __version__
from motus.loop import MOTUSAgent
from motus.memory.store import Memory

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich import box
    from rich.text import Text
    from rich.live import Live
    from rich.spinner import Spinner
    RICH_OK = True
except ImportError:
    RICH_OK = False

BANNER = r"""
╔══════════════════════════════════════════════════════╗
║               🧬  M O T U S   A g e n t  🧬          ║
║       Autonomous Molecular Dynamics Scientist        ║
║                                                      ║
║   "I simulate molecules. I analyze data.              ║
║    I write papers. I am a scientist."                 ║
╚══════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
🧬 **MOTUS Agent** — AI Scientist for Molecular Dynamics

**Commands:**
  `/help`      — Show this help
  `/sessions`  — List past research sessions
  `/new`       — Start a new session
  `/quit`      — Exit MOTUS
  `/q`         — Exit (shorthand)

**Setup:**
  API key → `~/.motus/.env` (or `MOTUS_DEEPSEEK_KEY` env var)
  Install → `bash install.sh` (one-time per server)

**Anything else** is treated as a research question. MOTUS will:
  1. Design and build your molecular system
  2. Run MD simulations (GROMACS / LAMMPS)
  3. Analyze results with publication-quality plots
  4. Write a scientific paper with LaTeX

Example: `Please study the formation mechanism of methane hydrate`
"""


def _banner():
    if RICH_OK:
        c = Console()
        c.print(Panel.fit(
            "[bold cyan]🧬  M O T U S   A g e n t[/bold cyan]\n"
            "[dim]Autonomous Molecular Dynamics Scientist[/dim]\n\n"
            '[italic]"I simulate molecules. I analyze data.\n'
            'I write papers. I am a scientist."[/italic]',
            border_style="cyan",
            padding=(1, 3),
        ))
    else:
        print(BANNER)


def _tool_display(iteration: int, tool_name: str, args: dict, result: str):
    """Display a tool invocation compactly."""
    if RICH_OK:
        c = Console()
        emoji_map = {
            "build_system": "🏗️", "run_md": "⚡", "analyze": "📊",
            "read_data": "📖", "render_system": "🎨", "terminal": "💻",
            "read_file": "📄", "write_file": "✏️", "search_files": "🔍",
        }
        emoji = emoji_map.get(tool_name, "🔧")
        short_args = {k: v for k, v in args.items() if k != "job_dir"}
        args_str = ", ".join(f"{k}={v}" for k, v in short_args.items())
        if len(args_str) > 80:
            args_str = args_str[:77] + "..."
        c.print(f"  [{iteration}] {emoji} [bold]{tool_name}[/bold]({args_str})")
        # Print first line of result
        result_first = result.split("\n")[0].strip()[:120]
        if result_first:
            c.print(f"       [dim]→ {result_first}[/dim]")
    else:
        print(f"  [{iteration}] {tool_name}({args})")
        print(f"       → {result[:150]}...")


def interactive(session_id: str = None):
    """Rich interactive mode."""
    _banner()
    agent = MOTUSAgent(session_id)

    if RICH_OK:
        c = Console()
        c.print(f"[dim]Session: {agent.memory.session_id}[/dim]")
        c.print(f"[dim]Workspace: {agent.workspace}[/dim]\n")
        c.print("[dim]Type your research question, or /help for commands.[/dim]\n")
    else:
        print(f"Session: {agent.memory.session_id}")
        print(f"Workspace: {agent.workspace}\n")
        print("Type your research question, or /help for commands.\n")

    while True:
        try:
            if RICH_OK:
                from rich.prompt import Prompt
                user_input = Prompt.ask("\n[bold green]🧑 You[/bold green]").strip()
            else:
                user_input = input("🧑 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/q", "/exit"):
            print("👋 Goodbye!")
            break
        if user_input == "/help":
            if RICH_OK:
                c = Console()
                c.print(Markdown(HELP_TEXT))
            else:
                print("Commands: /quit, /sessions, /new, /help")
            continue
        if user_input == "/sessions":
            sessions = Memory.list_sessions(10)
            if RICH_OK:
                table = Table(title="Past MOTUS Sessions", box=box.ROUNDED)
                table.add_column("ID", style="cyan")
                table.add_column("Msgs", justify="right")
                table.add_column("Preview", style="dim")
                for s in sessions:
                    table.add_row(s["id"], str(s["messages"]), s["preview"][:60])
                c.print(table)
            else:
                for s in sessions:
                    print(f"  {s['id']}  [{s['messages']} msgs] {s['preview'][:60]}...")
            continue
        if user_input == "/new":
            agent = MOTUSAgent()
            if RICH_OK:
                c.print(f"[bold green]New session:[/bold green] [cyan]{agent.memory.session_id}[/cyan]")
            else:
                print(f"New session: {agent.memory.session_id}")
            continue

        # Inject tool display callback
        agent._tool_callback = _tool_display

        if RICH_OK:
            c.print()
            with c.status("[bold cyan]🔬 MOTUS is thinking...[/bold cyan]", spinner="dots"):
                response = agent.chat(user_input)
            c.print()
            c.print(Panel.fit(
                Markdown(response),
                title="🔬 MOTUS",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            ))
        else:
            print("🔬 MOTUS: ", end="", flush=True)
            response = agent.chat(user_input)
            print(response)
            print()


def one_shot(question: str, session_id: str = None):
    """Run a single research question."""
    _banner()
    agent = MOTUSAgent(session_id)
    agent._tool_callback = _tool_display

    if RICH_OK:
        c = Console()
        c.print(f"[dim]Session: {agent.memory.session_id}[/dim]")
        c.print(f"[bold]Research question:[/bold] {question}\n")
        with c.status("[bold cyan]🔬 MOTUS is working...[/bold cyan]", spinner="dots"):
            response = agent.chat(question)
        c.print()
        c.print(Panel.fit(
            Markdown(response),
            title="🔬 MOTUS",
            title_align="left",
            border_style="cyan",
            padding=(1, 2),
        ))
        c.print(f"\n[dim]Session saved: {agent.memory.session_id}[/dim]")
    else:
        print(f"Session: {agent.memory.session_id}")
        print(f"Question: {question}\n")
        print("🔬 MOTUS: ", end="", flush=True)
        response = agent.chat(question)
        print(response)
        print(f"\nSession saved: {agent.memory.session_id}")


def main():
    args = sys.argv[1:]
    session_id = None

    i = 0
    while i < len(args):
        if args[i] == "--session" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
        elif args[i] == "--list":
            sessions = Memory.list_sessions()
            if RICH_OK:
                c = Console()
                table = Table(title="Past MOTUS Sessions", box=box.ROUNDED)
                table.add_column("ID", style="cyan")
                table.add_column("Msgs", justify="right")
                table.add_column("Date", style="dim")
                table.add_column("Preview")
                for s in sessions:
                    table.add_row(s["id"], str(s["messages"]), s["date"], s["preview"][:80])
                c.print(table)
            else:
                print("Past MOTUS sessions:")
                for s in sessions:
                    print(f"  {s['id']}  [{s['messages']} msgs]  {s['date']}  {s['preview'][:80]}")
            return
        elif args[i] == "--help":
            print(__doc__)
            return
        elif args[i] == "--version":
            print(f"MOTUS Agent v{__version__}")
            return
        else:
            break

    question = " ".join(args[i:]).strip()

    if question:
        one_shot(question, session_id)
    else:
        interactive(session_id)


if __name__ == "__main__":
    main()
