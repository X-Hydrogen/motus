"""
Tool: build molecular systems for MD — ALL via Packmol.

Pipeline: molecule names → SMILES DB (or PubChem) → OpenBabel 3D → Packmol assembly

NEVER hand-writes coordinates. Uses ~90-molecule built-in SMILES database.
Uncommon molecules fall back to PubChem REST API.
"""
import sys
import subprocess
from pathlib import Path
from motus.registry import registry

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"


def _run_python(script: str, args: str, timeout: int = 300) -> str:
    """Run a Python script and return its output."""
    try:
        r = subprocess.run(
            f"python3 {SCRIPTS / script} {args}",
            shell=True, capture_output=True, text=True, timeout=timeout,
        )
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


def build_system(args: dict) -> str:
    """
    Build molecular system via Packmol.

    args:
        system_type: "water_box", "mixture", "hydrate", "interface"
        job_dir: output directory
        molecules: list of {name, count} dicts
        box_size_nm: float
        (plus optional: interface_z, density)
    """
    job_dir = args.get("job_dir", "/tmp/motus_build")
    stype = args.get("system_type", "water_box")
    box_nm = args.get("box_size_nm", 3.0)
    Path(job_dir).mkdir(parents=True, exist_ok=True)

    # Resolve components based on system_type
    molecules = args.get("molecules", [])

    if stype == "water_box" and not molecules:
        molecules = [{"name": "water", "count": args.get("n_water", 884)}]
    elif stype == "methane_water" and not molecules:
        molecules = [
            {"name": "methane", "count": args.get("n_methane", 30)},
            {"name": "water", "count": args.get("n_water", 884)},
        ]
    elif stype == "hydrate" and not molecules:
        molecules = [
            {"name": "methane", "count": args.get("n_methane", 46)},
            {"name": "water", "count": args.get("n_water", 368)},
        ]

    if not molecules:
        return ("ERROR: No molecules specified. Provide 'molecules' list "
                "or use system_type='water_box'/'methane_water'/'hydrate'.")

    # Step 1: Fetch all molecules
    results = []
    for mol in molecules:
        name = mol["name"]
        out = _run_python("fetch_molecule.py", f"--name {name}", timeout=60)
        results.append(out)
        if "ERROR" in out:
            return (f"Failed to fetch '{name}': {out}\n"
                    f"Try: python3 scripts/fetch_molecule.py --name {name}")

    # Step 2: Build components string for Packmol
    comp_str = ",".join(f"{m['name']}:{m['count']}" for m in molecules)
    extra = ""
    if args.get("interface_z"):
        extra += f" --interface {args['interface_z']}"
    if args.get("tolerance"):
        extra += f" --tolerance {args['tolerance']}"

    out = _run_python(
        "build_by_packmol.py",
        f'--components "{comp_str}" --box {box_nm} --out {job_dir}{extra}',
        timeout=300,
    )

    if "ERROR" in out:
        return out

    # Quick sanity: count atoms
    gro = Path(job_dir) / "system.gro"
    if gro.exists():
        n_lines = len(gro.read_text().splitlines())
        n_atoms = n_lines - 3  # subtract header + box vec + footer
        return (f"{out}\n"
                f"  ✓ Validated: {n_atoms} atoms in system.gro\n"
                f"  ✓ Ready for run_md(engine='gromacs', job_dir='{job_dir}')")

    return out


# Register tool
registry.register(
    name="build_system",
    description=(
        "Build a molecular system for MD via Packmol. ALL systems use this pipeline: "
        "molecule name → built-in SMILES database (~90 molecules) → OpenBabel 3D → Packmol assembly. "
        "NEVER hand-write coordinates. For uncommon molecules, SMILES is looked up from PubChem."
    ),
    parameters={
        "system_type": {
            "type": "string",
            "enum": ["water_box", "methane_water", "hydrate", "interface", "mixture"],
            "description": "Type of system to build. 'mixture' requires explicit molecules list."
        },
        "job_dir": {"type": "string", "description": "Output directory for system files"},
        "molecules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Molecule name (e.g. 'methane', 'ethanol', 'urea')"},
                    "count": {"type": "integer", "description": "Number of molecules"}
                }
            },
            "description": "List of molecules with counts. Required for 'mixture' type."
        },
        "box_size_nm": {"type": "number", "description": "Cubic box size in nm (default 3.0)"},
        "n_water": {"type": "integer", "description": "Number of water molecules (for water_box/methane_water)"},
        "n_methane": {"type": "integer", "description": "Number of methane molecules (for methane_water/hydrate)"},
        "interface_z": {"type": "number", "description": "Z-position of interface in nm (for interface type)"},
        "tolerance": {"type": "number", "description": "Packmol tolerance (default 2.0, lower = tighter packing)"},
    },
    handler=build_system,
    emoji="🧱",
)
