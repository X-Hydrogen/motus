"""
Tool: model_desmond — Convert Packmol system to Desmond .cms

Pipeline: Packmol PDB → pdbconvert → .mae → multisim (S-OPLS) → .cms

CRITICAL: Uses S-OPLS force field (NOT OPLS4 — triggers mmlewis bug).
Works with raw packed.pdb directly — no residue renaming needed.
"""
import subprocess
from pathlib import Path
from motus.registry import registry

MOTUS = "/home/xenon/xhy/motus"
DESMOND_MODEL_SCRIPT = f"{MOTUS}/desmond-model-md.sh"


def model_desmond(args: dict) -> str:
    """Build a Desmond .cms from an already-built Packmol system."""
    job_dir = args["job_dir"]
    output_name = args.get("output_name", "desmond_model")

    # Verify system exists
    pdb = Path(job_dir) / "packed.pdb"
    if not pdb.exists():
        pdb = Path(job_dir) / "system.pdb"
    if not pdb.exists():
        return (f"ERROR: No packed.pdb or system.pdb in {job_dir}. "
                f"Run build_system first.")

    # Check for Schrödinger
    schrodinger = Path("/home/xenon/tools/schrodinger2025-2")
    if not schrodinger.exists():
        return ("ERROR: Schrödinger not found at /home/xenon/tools/schrodinger2025-2. "
                "Desmond modeling requires Schrödinger suite.")

    # Run the modeling script
    try:
        r = subprocess.run(
            ["bash", DESMOND_MODEL_SCRIPT, job_dir, output_name],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return "Desmond modeling TIMED OUT after 300s."

    stdout = r.stdout.strip()
    stderr = r.stderr.strip()

    # Check for .cms output
    cms_file = Path(job_dir) / f"{output_name}-out.cms"
    if cms_file.exists():
        size_mb = cms_file.stat().st_size / (1024 * 1024)
        return (f"✓ Desmond model ready:\\n"
                f"  Output: {cms_file} ({size_mb:.1f} MB)\\n"
                f"  Force field: S-OPLS\\n"
                f"  Ready for desmond-md.sh {job_dir}")

    # Return errors if failed
    if r.returncode != 0:
        last_lines = "\\n".join((stdout + stderr).split("\\n")[-15:])
        return f"Desmond modeling FAILED:\\n{last_lines}"

    return stdout or "Desmond modeling completed but output not verified."


registry.register(
    name="model_desmond",
    description=(
        "Convert a Packmol-built molecular system (packed.pdb) into a Desmond-ready .cms file. "
        "Uses the S-OPLS force field with build_geometry stage. "
        "Pipeline: pdbconvert → .mae → multisim (S-OPLS + build_geometry) → .cms. "
        "CRITICAL: Must use S-OPLS, not OPLS4 (OPLS4 triggers mmlewis Lewis structure detection bug). "
        "Verified: 10414-atom LiFSI/DME system, ~46 seconds, 8.2 MB .cms output. "
        "Prerequisite: build_system must be run first to create packed.pdb."
    ),
    parameters={
        "job_dir": {
            "type": "string",
            "description": "Directory containing packed.pdb (from build_system)"
        },
        "output_name": {
            "type": "string",
            "description": "Base name for output files (default: desmond_model)"
        },
    },
    handler=model_desmond,
    emoji="🔷",
)
