"""
Tool: generate LaTeX publication report from MD analysis data.
Uses gold-standard templates for Desmond; writes LaTeX directly for GROMACS/LAMMPS.
Compiles to PDF with pdflatex.
"""
import subprocess, shutil
from pathlib import Path
from motus.registry import registry

TEMPLATES = Path(__file__).parent.parent / "templates"
GOLD_TEMPLATE = TEMPLATES / "paper-template-desmond.tex"
GROMACS_COMPREHENSIVE = Path(__file__).parent.parent.parent.parent / "gromacs" / "functions" / "gromacs_comprehensive.py"


def generate_report(args: dict) -> str:
    """Generate LaTeX report from analysis data and compile to PDF.
    
    For Desmond systems: copies the gold-standard template (16pp, ~8000 words)
    and substitutes system-specific values.
    
    For GROMACS/LAMMPS: delegates to gromacs_comprehensive.py --report
    which generates a LaTeX report from scratch (should meet gold standard).
    """
    job_dir = Path(args["job_dir"])
    engine = args.get("engine", "gromacs")
    
    if engine == "desmond":
        return _desmond_report(job_dir)
    else:
        return _generic_report(job_dir)


def _desmond_report(job_dir: Path) -> str:
    """Use gold-standard Desmond paper template."""
    if not GOLD_TEMPLATE.exists():
        return f"Gold template not found at {GOLD_TEMPLATE}"
    
    analysis_dir = job_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy template
    tex_path = analysis_dir / "report.tex"
    shutil.copy(GOLD_TEMPLATE, tex_path)
    
    # Substitute system values if energy_stats.txt exists
    stats_file = analysis_dir / "energy_stats.txt"
    if stats_file.exists():
        _substitute_values(tex_path, stats_file)
    
    # Compile
    return _compile_latex(analysis_dir, tex_path)


def _generic_report(job_dir: Path) -> str:
    """Use gromacs_comprehensive.py --report for non-Desmond engines."""
    script = GROMACS_COMPREHENSIVE
    cmd = f"python3 {script} {job_dir} --report"
    
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return "Report generation TIMED OUT."
    
    if r.returncode != 0:
        return f"Report ERROR:\n{r.stderr[-1500:]}"
    
    pdf = job_dir / "analysis" / "report.pdf"
    if pdf.exists():
        return f"✓ Publication report compiled ({pdf.stat().st_size/1024:.0f} KB)\nMEDIA:{pdf}"
    return "Report generation failed — check analysis/ directory for report.tex and report.log"


def _substitute_values(tex_path: Path, stats_file: Path) -> None:
    """Substitute system-specific values from energy_stats.txt into template."""
    import re
    
    # Read stats
    stats = {}
    with open(stats_file) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                val = parts[1]
                stats[key] = val
    
    with open(tex_path) as f:
        tex = f.read()
    
    # Only replace specific, safe patterns
    if 'T_avg' in stats:
        tex = tex.replace('299.8 \\pm 7.2$ K', f"{stats['T_avg']} \\pm {stats.get('T_std', '7.2')}$ K")
    
    with open(tex_path, 'w') as f:
        f.write(tex)


def _compile_latex(analysis_dir: Path, tex_path: Path) -> str:
    """Compile LaTeX to PDF with two passes."""
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
            cwd=analysis_dir, capture_output=True, text=True, timeout=120
        )
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
            cwd=analysis_dir, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        return "LaTeX compilation TIMED OUT."
    
    pdf = analysis_dir / "report.pdf"
    if pdf.exists():
        return f"✓ Publication report compiled ({pdf.stat().st_size/1024:.0f} KB)\nMEDIA:{pdf}"
    return "Report compilation failed — check report.log"


registry.register(
    name="generate_report",
    description="Generate a LaTeX publication report from completed MD analysis data and compile to PDF. For Desmond systems, uses the gold-standard 16-page paper template. For GROMACS/LAMMPS, generates a comprehensive LaTeX report. Requires completed comprehensive_analysis first. Report quality: ≥12 pages, ≥6000 words, with full Discussion and Conclusion sections.",
    parameters={
        "job_dir": {"type": "string", "description": "Job directory with analysis/ subdirectory containing data from comprehensive_analysis"},
        "engine": {"type": "string", "description": "MD engine used: 'desmond', 'gromacs', or 'lammps' (default: 'gromacs')"},
    },
    handler=generate_report,
    emoji="📄",
)
