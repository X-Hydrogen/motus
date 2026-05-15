"""
Tool: generate LaTeX publication report from MD analysis data.
Compiles to PDF with pdflatex.
"""
import subprocess
from pathlib import Path
from motus.registry import registry

SCRIPTS = Path(__file__).parent.parent.parent.parent / "gromacs" / "functions"


def generate_report(args: dict) -> str:
    """Generate LaTeX report from existing analysis data and compile to PDF."""
    job_dir = args["job_dir"]
    
    script = SCRIPTS / "gromacs_comprehensive.py"
    cmd = f"python3 {script} {job_dir} --report"
    
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return "Report generation TIMED OUT."
    
    if r.returncode != 0:
        return f"Report ERROR:\n{r.stderr[-1500:]}"
    
    pdf = Path(job_dir) / "analysis" / "report.pdf"
    if pdf.exists():
        return f"✓ Publication report compiled ({pdf.stat().st_size/1024:.0f} KB)\nMEDIA:{pdf}"
    return "Report generation failed — check analysis/ directory for report.tex and report.log"


registry.register(
    name="generate_report",
    description="Generate a LaTeX publication report from completed MD analysis data and compile to PDF. Includes abstract, methods, results, figures, and conclusions. Requires completed comprehensive_analysis first.",
    parameters={
        "job_dir": {"type": "string", "description": "Job directory with analysis/ subdirectory containing XVG/CSV data from comprehensive_analysis"},
    },
    handler=generate_report,
    emoji="📄",
)
