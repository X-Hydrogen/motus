#!/usr/bin/env python3
"""
fetch_molecule.py — Reliable 3D structure from molecule name or SMILES.

Pipeline:  name → SMILES (built-in DB or PubChem) → OpenBabel gen3d+MMFF94 → PDB

NEVER hand-write coordinates. All 3D structures come from:
  1. Built-in SMILES database (~90 common molecules, INSTANT)
  2. PubChem REST API (fallback for uncommon molecules)
  3. OpenBabel gen3d + MMFF94 energy minimization (ensures valid geometry)

Output: .pdb file cached in ~/.motus/molecules/, ready for Packmol.

Usage:
    python3 fetch_molecule.py --name methane
    python3 fetch_molecule.py --name ethanol --out /path/to/ethanol.pdb
    python3 fetch_molecule.py --smiles "CCO"
    python3 fetch_molecule.py --name caffeine
    python3 fetch_molecule.py --list              # list all known molecules
    python3 fetch_molecule.py --search "hydrate"  # search by keyword
"""
import sys
import os
import json
import argparse
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request, quote
from urllib.error import URLError

CACHE_DIR = Path.home() / ".motus" / "molecules"
OBABEL = "/home/xenon/.hermes/hermes-agent/venv/bin/obabel"

# Import built-in SMILES DB
sys.path.insert(0, str(Path(__file__).parent.parent))
from motus.smiles_db import get_smiles, get_info, list_all, search as search_db


def _run(cmd: list, timeout: int = 60) -> tuple:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except Exception as e:
        return False, "", str(e)


def smiles_to_pdb(smiles: str, output_path: str, name: str = "molecule") -> tuple[bool, str]:
    """
    Convert SMILES to 3D PDB using OpenBabel.
    Steps: SMILES → 2D SDF → gen3d → MMFF94 minimize → PDB
    After conversion, applies atom name fixes for known force field conventions.
    """
    smi_path = CACHE_DIR / f"_tmp_{name}.smi"
    smi_path.write_text(smiles + "\n")

    ok, out, err = _run([
        OBABEL, "-ismi", str(smi_path),
        "-opdb", "-O", str(output_path),
        "--gen3d", "--minimize", "--ff", "MMFF94",
    ], timeout=120)

    smi_path.unlink(missing_ok=True)

    if ok and Path(output_path).exists() and Path(output_path).stat().st_size > 50:
        # Fix atom names for OPLS-AA compatibility
        _fix_atom_names(output_path, name)
        n_atoms = sum(1 for l in Path(output_path).read_text().splitlines()
                      if l.startswith(("ATOM  ", "HETATM")))
        return True, f"SMILES → 3D MMFF94 → {output_path} [{n_atoms} atoms]"

    return False, f"OpenBabel failed: {err[:300]}"


def _fix_atom_names(pdb_path: str, mol_name: str):
    """
    Fix atom names in PDB to match OPLS-AA force field conventions.
    
    OpenBabel generates generic names (C, H, H, H, H) but force fields expect
    specific names (C, H1, H2, H3, H4 for methane; C, O, H, H for water).

    This function is a registry of known fixes. Add more as needed.
    """
    lines = Path(pdb_path).read_text().splitlines()
    key = mol_name.lower().strip().replace(" ", "_")
    
    fixes = {
        # Methane (CH4): 1 C + 4 H → C, H1, H2, H3, H4
        "methane": {"C": "C", "H": ["H1", "H2", "H3", "H4"]},
        "ch4": {"C": "C", "H": ["H1", "H2", "H3", "H4"]},
        # Water: 1 O + 2 H → OW, HW1, HW2 (SPC/E convention) or O, H1, H2
        "water": {"O": "OW", "H": ["HW1", "HW2"]},
        "h2o": {"O": "OW", "H": ["HW1", "HW2"]},
        # Ammonia (NH3): 1 N + 3 H
        "ammonia": {"N": "N", "H": ["H1", "H2", "H3"]},
        # Ethane (C2H6): 2 C + 6 H
        "ethane": {"C": ["C1", "C2"], "H": ["H1", "H2", "H3", "H4", "H5", "H6"]},
    }

    fix = fixes.get(key)
    if not fix:
        return  # No fix needed for this molecule

    new_lines = []
    element_counters = {}  # Track how many of each element we've seen
    h_count = 0
    c_count = 0

    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")):
            new_lines.append(line)
            continue

        # PDB format: columns 13-16 are atom name
        element = line[76:78].strip() if len(line) > 76 else line[12:16].strip()
        atom_name = line[12:16].strip()

        if element in fix:
            mapping = fix[element]
            if isinstance(mapping, list):
                # Sequential rename (e.g., H → H1, H2, H3, H4)
                count = element_counters.get(element, 0)
                if count < len(mapping):
                    new_name = mapping[count]
                    element_counters[element] = count + 1
                else:
                    new_name = atom_name  # fallback
            else:
                new_name = mapping
            
            # Replace atom name in PDB columns 13-16 (right-justified)
            new_lines.append(line[:12] + f"{new_name:<4s}" + line[16:])
        else:
            new_lines.append(line)

    Path(pdb_path).write_text("\n".join(new_lines) + "\n")


def pubchem_smiles(name: str) -> str | None:
    """Try to get SMILES from PubChem by name."""
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name)}/property/CanonicalSMILES/JSON"
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            props = data.get("PropertyTable", {}).get("Properties", [])
            if props:
                return props[0].get("CanonicalSMILES")
    except Exception:
        pass
    return None


def fetch(name: str = None, smiles: str = None) -> tuple[str | None, str, str]:
    """
    Fetch 3D PDB for a molecule.

    Returns: (pdb_path_or_None, source, message)
    """
    key = (name or "smiles").lower().strip().replace(" ", "_")

    # 1. Check cache
    cache_path = CACHE_DIR / f"{key}.pdb"
    if cache_path.exists() and cache_path.stat().st_size > 50:
        return str(cache_path), "cache", f"Cached: {cache_path}"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Resolve SMILES
    smi = None
    source = "unknown"

    if smiles:
        smi = smiles.strip()
        source = "user-provided SMILES"
    elif name:
        # Try built-in DB
        smi = get_smiles(name)
        if smi:
            source = f"built-in DB ({name})"
        else:
            # Try PubChem
            smi = pubchem_smiles(name)
            if smi:
                source = f"PubChem ({name})"

    if not smi:
        return None, "none", (f"No SMILES found for '{name}'. "
                              f"Provide --smiles directly or add to smiles_db.py.")

    # 3. Convert to 3D
    ok, msg = smiles_to_pdb(smi, str(cache_path), key)
    if ok:
        return str(cache_path), source, msg

    return None, "none", msg


def fetch_cli(args: dict) -> str:
    """Unified interface for MOTUS Agent tools."""
    pdb, source, msg = fetch(name=args.get("name"), smiles=args.get("smiles"))
    if pdb:
        return f"✓ [{source}] {msg}"
    return f"ERROR: {msg}"


# ===== CLI =====
def main():
    p = argparse.ArgumentParser(description="Fetch 3D molecule structure")
    p.add_argument("--name", help="Molecule name")
    p.add_argument("--smiles", help="SMILES string")
    p.add_argument("--out", help="Output PDB path (overrides cache)")
    p.add_argument("--list", action="store_true", help="List all known molecules")
    p.add_argument("--search", help="Search molecules by keyword")
    p.add_argument("--charge", type=int, default=0)
    args = p.parse_args()

    if args.list:
        mols = list_all()
        print(f"Known molecules ({len(mols)}):")
        for m in mols:
            info = get_info(m)
            print(f"  {m:20s}  {info['smiles']:30s}  [{info['category']}]")
        return

    if args.search:
        results = search_db(args.search)
        if results:
            print(f"Matching '{args.search}':")
            for m in results:
                info = get_info(m)
                print(f"  {m:20s}  {info['smiles']:30s}  [{info['category']}]  {info['notes']}")
        else:
            print(f"No matches for '{args.search}'")
        return

    if not args.name and not args.smiles:
        p.print_help()
        return

    pdb, source, msg = fetch(name=args.name, smiles=args.smiles)
    print(f"[{source}] {msg}")

    if args.out and pdb and Path(pdb).exists():
        import shutil
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdb, args.out)
        print(f"Copied → {args.out}")

    sys.exit(0 if pdb else 1)


if __name__ == "__main__":
    main()
