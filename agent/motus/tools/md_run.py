"""Tool: run MD simulation."""
import subprocess
from motus.registry import registry

MOTUS = "/home/xenon/xhy/motus"
GMXRC = "/home/xenon/tools/gromacs-2026/bin/GMXRC"


def run_md(args: dict) -> str:
    """Execute MD simulation pipeline."""
    engine = args.get("engine", "gromacs")
    job_dir = args["job_dir"]
    time_ps = args.get("time_ps", 500)
    temp_k = args.get("temperature_k", 300)
    press_bar = args.get("pressure_bar", 1.0)
    gpu = args.get("gpu", True)

    script = f"{MOTUS}/{engine}/{engine}-md.sh"
    gflag = "--gpu" if gpu else "--no-gpu"
    cmd = f"source '{GMXRC}' 2>/dev/null && bash {script} {job_dir} -t {time_ps} -T {temp_k} -P {press_bar} {gflag}"

    try:
        r = subprocess.run(["bash", "-c", cmd], cwd=job_dir,
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return "MD simulation TIMED OUT after 600s. Reduce time_ps."

    if r.returncode != 0:
        return f"MD FAILED (exit {r.returncode}):\n{r.stderr[-1000:]}"

    # Check output
    from pathlib import Path
    prods = list(Path(job_dir).glob("prod.*"))
    out_files = [f.name for f in prods]
    speed_line = [l for l in r.stdout.split("\n") if "ns/day" in l]
    speed = speed_line[-1].strip() if speed_line else "N/A"

    return (f"✓ MD complete: {time_ps}ps @ {temp_k}K, {press_bar}bar\n"
            f"  Performance: {speed}\n"
            f"  Output: {out_files}\n"
            f"  Ready for motus.analyze on {job_dir}")


registry.register(
    name="run_md",
    description="Run full MD simulation (EM→NVT→NPT→Production). Job dir must already have system files.",
    parameters={
        "engine": {"type": "string", "enum": ["gromacs", "lammps"]},
        "job_dir": {"type": "string", "description": "Job directory with system.gro + topol.top (or system.data)"},
        "time_ps": {"type": "integer", "description": "Production time in ps (start with 200-500)"},
        "temperature_k": {"type": "number", "description": "Temperature in Kelvin"},
        "pressure_bar": {"type": "number", "description": "Pressure in bar"},
        "gpu": {"type": "boolean", "description": "Use GPU (default true)"},
    },
    handler=run_md,
    emoji="⚛️",
)
