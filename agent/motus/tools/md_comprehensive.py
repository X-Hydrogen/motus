"""
Tool: comprehensive molecular dynamics analysis — all 9 Desmond modules.
Generates publication-quality figures + optional LaTeX report.
"""
import subprocess
from pathlib import Path
from motus.registry import registry

SCRIPTS = Path(__file__).parent.parent.parent.parent / "gromacs" / "functions"


def comprehensive_analyze(args: dict) -> str:
    """Run full Desmond-style comprehensive analysis on a GROMACS job directory."""
    job_dir = args["job_dir"]
    make_report = args.get("make_report", False)
    
    script = SCRIPTS / "gromacs_comprehensive.py"
    cmd = f"python3 {script} {job_dir}"
    if make_report:
        cmd += " --report"
    
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return "Analysis TIMED OUT (>15 min). Try a shorter trajectory or reduce analysis scope."
    
    if r.returncode != 0:
        return f"Analysis ERROR:\n{r.stderr[-1500:]}\n\nSTDOUT:\n{r.stdout[-1000:]}"
    
    ad = Path(job_dir) / "analysis"
    figs = sorted((ad / "figures").glob("*.png")) if (ad / "figures").exists() else []
    
    lines = [r.stdout.strip()]
    if figs:
        lines.append(f"\n✓ Generated {len(figs)} figures:")
        for f in figs:
            lines.append(f"  MEDIA:{f}")
    
    pdf = ad / "report.pdf"
    if pdf.exists():
        lines.append(f"\n✓ Compiled report: MEDIA:{pdf}")
    
    return "\n".join(lines)


registry.register(
    name="comprehensive_analysis",
    description="Run full Desmond-style comprehensive MD analysis on a completed GROMACS job. Generates 9 publication-quality figures covering thermodynamics, MSD/diffusion, RDF+coordination numbers, solvation shells, density profiles, molecular properties, and free volume. Optionally compiles a LaTeX PDF report.",
    parameters={
        "job_dir": {"type": "string", "description": "Job directory containing prod.xtc, prod.gro, prod.edr, and prod.tpr"},
        "make_report": {"type": "boolean", "description": "If True, also generate and compile a LaTeX PDF report"},
    },
    handler=comprehensive_analyze,
    emoji="🔬",
)
