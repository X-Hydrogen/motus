"""Tool: build molecular systems for MD."""
import subprocess
from pathlib import Path
from motus.registry import registry

GMXRC = "/home/xenon/tools/gromacs-2026/bin/GMXRC"


def _bash(cmd: str, cwd: str, timeout: int = 120) -> dict:
    wrapped = f'source "{GMXRC}" 2>/dev/null && {cmd}'
    r = subprocess.run(["bash", "-c", wrapped], cwd=cwd,
                       capture_output=True, text=True, timeout=timeout)
    return {"ok": r.returncode == 0, "out": r.stdout, "err": r.stderr}


def build_system(args: dict) -> str:
    """Build molecular system for MD."""
    stype = args.get("system_type", "water_box")
    job_dir = args.get("job_dir", "/tmp/motus_build")
    params = args.get("params", {})

    Path(job_dir).mkdir(parents=True, exist_ok=True)

    if stype == "water_box":
        box = params.get("box_size_nm", 3.0)
        r = _bash(f"gmx solvate -cs spc216.gro -o system.gro -box {box} {box} {box}", job_dir)
        if not r["ok"]:
            return f"FAILED: {r['err'][:500]}"

        # Count actual waters and build topology
        r2 = _bash("N=$(awk 'NR==2{print int($1/3)}' system.gro) && echo $N", job_dir)
        n_wat = r2["out"].strip()
        topo = (
            '#include "oplsaa.ff/forcefield.itp"\n'
            '#include "oplsaa.ff/spce.itp"\n'
            '[ System ]\nPure Water\n[ Molecules ]\n'
            f'SOL    {n_wat}\n'
        )
        (Path(job_dir) / "topol.top").write_text(topo)
        return f"Built {n_wat} SPC/E water molecules in {box}nm box at {job_dir}"

    elif stype == "methane_water":
        n_ch4 = params.get("n_methane", 30)
        box = params.get("box_size_nm", 3.0)
        script = "/home/xenon/xhy/motus/agent/scripts/build_hydrate_system.py"
        r = _bash(f"python3 {script} dissolved --n_methane {n_ch4} --box_size {box} --out {job_dir}",
                  job_dir, timeout=120)
        return r["out"] if r["ok"] else f"FAILED: {r['err'][:500]}"

    elif stype == "methane_hydrate":
        nc = params.get("unit_cells", 2)
        script = "/home/xenon/xhy/motus/agent/scripts/build_hydrate_system.py"
        r = _bash(f"python3 {script} hydrate --unit_cells {nc} --out {job_dir}",
                  job_dir, timeout=120)
        return r["out"] if r["ok"] else f"FAILED: {r['err'][:500]}"

    return f"Unknown system_type: {stype}"


registry.register(
    name="build_system",
    description="Build a molecular system for MD simulation (water box, methane-water mixture, methane hydrate).",
    parameters={
        "system_type": {"type": "string", "enum": ["water_box", "methane_water", "methane_hydrate"]},
        "job_dir": {"type": "string", "description": "Directory to create system files in"},
        "params": {"type": "object", "description": "Extra params: box_size_nm, n_methane, unit_cells"},
    },
    handler=build_system,
    emoji="🧱",
)
