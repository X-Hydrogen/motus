"""Tool: analyze MD results + generate plots."""
import subprocess
from pathlib import Path
from motus.registry import registry

MOTUS = "/home/xenon/xhy/motus"
GMXRC = "/home/xenon/tools/gromacs-2026/bin/GMXRC"


def analyze(args: dict) -> str:
    """Run post-MD analysis."""
    engine = args.get("engine", "gromacs")
    job_dir = args["job_dir"]
    plot_type = args.get("plot_type", "all")

    script = f"{MOTUS}/{engine}/{engine}-analysis.sh"
    cmd = f"source '{GMXRC}' 2>/dev/null && bash {script} {job_dir} --plot --plot-type {plot_type}"

    try:
        r = subprocess.run(["bash", "-c", cmd], cwd=job_dir,
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return "Analysis TIMED OUT. Try reducing plot_type scope."

    if r.returncode != 0:
        return f"Analysis had issues:\n{r.stderr[-1000:]}\n\nSTDOUT:\n{r.stdout[-1000:]}"

    adir = Path(job_dir) / "analysis"
    csvs = sorted(adir.glob("*.csv")) if adir.exists() else []
    figs_dir = adir / "figures"
    figs = sorted(figs_dir.glob("*.png")) if figs_dir.exists() else []
    pdfs = sorted(figs_dir.glob("*.pdf")) if figs_dir.exists() else []

    lines = [f"✓ Analysis complete for {job_dir}"]
    if csvs:
        lines.append(f"  CSV files ({len(csvs)}): {', '.join(f.name for f in csvs)}")
    if figs:
        lines.append(f"  Figures ({len(figs)}): {', '.join(f.name for f in figs)}")
    return "\n".join(lines)


registry.register(
    name="analyze",
    description="Run post-simulation analysis and generate publication-quality plots (energy, RDF, RMSD, H-bonds, density, etc.).",
    parameters={
        "engine": {"type": "string", "enum": ["gromacs", "lammps"]},
        "job_dir": {"type": "string", "description": "Job directory with production output (prod.xtc, prod.edr, etc.)"},
        "plot_type": {"type": "string", "description": "Plot type: energy, rdf, rmsd, hbonds, density, dashboard, all"},
    },
    handler=analyze,
    emoji="📊",
)
