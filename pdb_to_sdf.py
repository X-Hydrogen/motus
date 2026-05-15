#!/usr/bin/env python3
"""
pdb_to_sdf.py — Convert Packmol PDB to SDF with proper bond information.

Reads a Packmol-built PDB and template SDF files for each molecule type,
then generates a combined SDF where every molecule has correct bonds
(at positions from the PDB).

Required for Schrödinger system builder: PDB has no bond info, so Lewis
structure detection fails. SDF provides explicit bonds, solving the issue.

Usage:
    python3 pdb_to_sdf.py <packed.pdb> <packmol.inp> -o <output.sdf> \
        --templates dme:/tmp/dme_3d.sdf,fsi:/tmp/fsi_3d.sdf,li:/tmp/li_3d.sdf

Dependencies: OpenBabel (python3-openbabel)
"""
import sys
import re
import math
import argparse
from pathlib import Path
from collections import OrderedDict


def parse_packmol_inp(path: str) -> list:
    """Parse packmol.inp → [(struct_file, count), ...] in order."""
    text = Path(path).read_text()
    structs = re.findall(r'^\s*structure\s+(\S+)', text, re.MULTILINE)
    numbers = re.findall(r'number\s+(\d+)', text)

    result = []
    for sfile, nstr in zip(structs, numbers):
        n = int(nstr)
        spath = Path(sfile)
        if not spath.is_absolute():
            spath = Path(path).parent / sfile
        result.append((str(spath), n))
    return result


def read_sdf_bonds(sdf_path: str) -> tuple:
    """Read an SDF file and return (atoms_list, bonds_list).

    atoms_list: [(element_symbol, x, y, z, formal_charge), ...]
    bonds_list: [(i, j, order), ...]  (0-indexed)
    """
    with open(sdf_path) as f:
        lines = f.readlines()

    # Parse V2000 header on line 4 (0-indexed: 3)
    header = lines[3].split()
    n_atoms = int(header[0])
    n_bonds = int(header[1])

    atoms = []
    for i in range(n_atoms):
        line = lines[4 + i]
        x = float(line[0:10])
        y = float(line[10:20])
        z = float(line[20:30])
        elem_raw = line[31:34].strip()
        atoms.append((elem_raw, x, y, z, 0))  # Charge filled later from M CHG

    bonds = []
    for i in range(n_bonds):
        line = lines[4 + n_atoms + i]
        a1 = int(line[0:3]) - 1
        a2 = int(line[3:6]) - 1
        order = int(line[6:9])
        bonds.append((a1, a2, order))

    # Parse M CHG lines for formal charges
    chg_start = 4 + n_atoms + n_bonds
    for line in lines[chg_start:]:
        if line.startswith("M  CHG"):
            parts = line.split()
            n_charges = int(parts[2])
            for j in range(n_charges):
                atom_idx = int(parts[3 + 2*j]) - 1  # 1-indexed → 0-indexed
                charge = int(parts[4 + 2*j])
                if 0 <= atom_idx < len(atoms):
                    elem, x, y, z, _ = atoms[atom_idx]
                    atoms[atom_idx] = (elem, x, y, z, charge)

    return atoms, bonds


def atom_element(atomic_num: int) -> str:
    """Convert atomic number to element symbol."""
    elements = [
        "", "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
        "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
    ]
    if 1 <= atomic_num <= len(elements) - 1:
        return elements[atomic_num]
    return ob.OBElements.GetSymbol(atomic_num)


def centroid(atoms_in_residue):
    """Calculate centroid of a residue's atoms."""
    xs = [a[1] for a in atoms_in_residue]
    ys = [a[2] for a in atoms_in_residue]
    zs = [a[3] for a in atoms_in_residue]
    return (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))


def match_residue_to_template(residue_atoms, template_atoms):
    """
    Match Packmol PDB atoms to template SDF atoms by element type.
    Residue atoms are [(element_name, x, y, z), ...] from PDB
    Template atoms are [(element_symbol, x, y, z, formal_charge), ...]
    Returns: (match_map, template_centroid)
      match_map: {pdb_index: template_index}
    """
    pdb_elements = [a[0].upper() for a in residue_atoms]  # Normalize to uppercase
    tpl_elements = [a[0].upper() for a in template_atoms]  # Normalize to uppercase

    if len(pdb_elements) != len(tpl_elements):
        print(f"  WARNING: atom count mismatch: PDB={len(pdb_elements)} vs template={len(tpl_elements)}")
        return None, None

    # Simple element-based matching (same order)
    match_ok = all(p == t for p, t in zip(pdb_elements, tpl_elements))
    if match_ok:
        match_map = {i: i for i in range(len(pdb_elements))}
        tpl_cx = sum(a[1] for a in template_atoms) / len(template_atoms)
        tpl_cy = sum(a[2] for a in template_atoms) / len(template_atoms)
        tpl_cz = sum(a[3] for a in template_atoms) / len(template_atoms)
        return match_map, (tpl_cx, tpl_cy, tpl_cz)

    # Fallback: greedy element matching
    match_map = {}
    used_tpl = set()
    for i, (pe, px, py, pz) in enumerate(residue_atoms):
        best_j = None
        best_dist = float('inf')
        for j, (te, tx, ty, tz, _) in enumerate(template_atoms):
            if j in used_tpl or pe != te.upper():
                continue
            # Check distance (relative to centroids)
            d = math.sqrt((px - tx) ** 2 + (py - ty) ** 2 + (pz - tz) ** 2)
            if d < best_dist:
                best_dist = d
                best_j = j
        if best_j is not None:
            match_map[i] = best_j
            used_tpl.add(best_j)

    if len(match_map) != len(template_atoms):
        return None, None

    tpl_cx = sum(a[1] for a in template_atoms) / len(template_atoms)
    tpl_cy = sum(a[2] for a in template_atoms) / len(template_atoms)
    tpl_cz = sum(a[3] for a in template_atoms) / len(template_atoms)
    return match_map, (tpl_cx, tpl_cy, tpl_cz)


def write_sdf_entry(f, atoms, bonds, residue_id, formal_charges=None):
    """Write one SDF molecule entry with proper M CHG records.

    atoms: [(element_symbol, x, y, z), ...]
    bonds: [(i, j, order), ...]
    """
    n_atoms = len(atoms)
    n_bonds = len(bonds)

    f.write(f"MOTUS_{residue_id}\n")
    f.write("  Generated by MOTUS pdb_to_sdf.py\n")
    f.write("\n")
    f.write(f"{n_atoms:3d}{n_bonds:3d}  0  0  0  0  0  0  0  0999 V2000\n")

    for i, (elem, x, y, z) in enumerate(atoms):
        # Always write 0 in atom block charge field; real charges go in M CHG
        f.write(f"{x:10.4f}{y:10.4f}{z:10.4f} {elem:<3s}  0  0  0  0  0  0  0  0  0  0  0  0\n")

    for i, j, order in bonds:
        f.write(f"{i + 1:3d}{j + 1:3d}{order:3d}  0  0  0  0\n")

    # Write M  CHG record for non-zero formal charges
    if formal_charges:
        charged_atoms = [(i, int(c)) for i, c in enumerate(formal_charges) if int(c) != 0]
        if charged_atoms:
            f.write(f"M  CHG{len(charged_atoms):3d}")
            for atom_idx, charge in charged_atoms:
                f.write(f"{atom_idx + 1:4d}{charge:4d}")
            f.write("\n")

    f.write("M  END\n$$$$\n")


def main():
    parser = argparse.ArgumentParser(description="Convert Packmol PDB to SDF with bonds")
    parser.add_argument("pdb", help="Packmol output PDB (packed.pdb)")
    parser.add_argument("packmol_inp", help="packmol.inp file")
    parser.add_argument("-o", "--output", default=None, help="Output SDF file")
    parser.add_argument("--templates", required=True,
                        help="Template SDF mapping: name1:path1,name2:path2,...")
    parser.add_argument("-b", "--box", type=float, default=None,
                        help="Box size in nm (reads from packmol.inp if not given)")
    args = parser.parse_args()

    if args.output is None:
        args.output = Path(args.pdb).with_suffix('.sdf')

    # Parse template mapping
    template_map = {}
    for item in args.templates.split(","):
        name, path = item.split(":", 1)
        template_map[name.lower()] = path

    # Parse packmol.inp
    mol_seq = parse_packmol_inp(args.packmol_inp)
    print(f"Packmol sequence: {mol_seq}")

    # Read template SDF molecules
    templates = {}
    for name, sdf_path in template_map.items():
        atoms, bonds = read_sdf_bonds(sdf_path)
        templates[name] = (atoms, bonds)
        print(f"Template {name}: {len(atoms)} atoms, {len(bonds)} bonds")

    # Read PDB and group by residue
    pdb_lines = Path(args.pdb).read_text().splitlines()
    residues = OrderedDict()  # {(resname, resid): [(elem, x, y, z), ...]}
    residue_order = []

    for line in pdb_lines:
        if not line.startswith(('ATOM', 'HETATM')):
            continue
        # Read element from cols 77-78 (PDB v3 standard)
        # Fall back to atom name column (13-16) if element column is empty
        elem = line[76:78].strip()
        if not elem:
            elem = line[12:16].strip()
            # Take only alphabetic part of atom name (e.g., "C2" → "C")
            elem = ''.join(c for c in elem if c.isalpha())
        elem = elem.upper()
        resname = line[17:20].strip()
        resid = int(line[22:26])
        x = float(line[30:38])
        y = float(line[38:46])
        z = float(line[46:54])

        key = (resname, resid)
        if key not in residues:
            residues[key] = []
            residue_order.append(key)
        residues[key].append((elem, x, y, z))

    print(f"PDB: {len(residue_order)} residues, {sum(len(v) for v in residues.values())} atoms")

    # Map packmol.inp molecule names to template names
    # Build a mapping from packmol structure file basename to template name
    name_to_template = {}
    for name in template_map:
        name_to_template[name.lower()] = name.lower()

    # Also try to infer from packmol.inp structure files
    mol_files = [Path(s[0]).stem.lower() for s in mol_seq]
    print(f"Molecule files: {mol_files}")
    print(f"Template names: {list(template_map.keys())}")

    # Build the residue sequence matching packmol.inp
    total_pdb_residues = len(residue_order)
    expected_molecules = []
    for sfile, count in mol_seq:
        name = Path(sfile).stem.lower()
        expected_molecules.extend([name] * count)

    if len(expected_molecules) != total_pdb_residues:
        print(f"WARNING: Expected {len(expected_molecules)} residues from packmol.inp, "
              f"got {total_pdb_residues} from PDB")
        # Try to proceed anyway
        if len(expected_molecules) == 0:
            expected_molecules = [r[0].lower() for r in residue_order]

    print(f"Expected: {len(expected_molecules)} molecules")
    for i, (name, count) in enumerate(mol_seq):
        print(f"  {Path(name).stem}: {count}")

    # Match each PDB residue to a template
    residue_to_template = []  # [(resid_key, template_name), ...]

    # Build mapping from packmol file names to template names
    # The packmol files have names like "dme.pdb", "fsi-.pdb", "li+.pdb"
    # Templates are named like "dme", "fsi", "li"
    fname_to_tpl = {}
    for tpl_name in template_map:
        fname_to_tpl[tpl_name] = tpl_name

    for i, exp_name in enumerate(expected_molecules):
        if i < len(residue_order):
            key = residue_order[i]
            # Find matching template
            tpl_name = exp_name
            # Clean up: remove +, -, and take first meaningful chars
            clean = exp_name.replace('+', '').replace('-', '')
            if clean in template_map:
                tpl_name = clean
            elif exp_name in template_map:
                tpl_name = exp_name
            # Try partial match
            else:
                for tn in template_map:
                    if tn in exp_name or exp_name in tn:
                        tpl_name = tn
                        break
            residue_to_template.append((key, tpl_name))

    print(f"\nMatched {len(residue_to_template)} residues to templates")

    # Write combined SDF
    total_atoms = 0
    with open(args.output, 'w') as f:
        for idx, (res_key, tpl_name) in enumerate(residue_to_template):
            if tpl_name not in templates:
                print(f"  SKIP residue {res_key}: no template for '{tpl_name}'")
                continue

            tpl_atoms, tpl_bonds = templates[tpl_name]
            pdb_atoms_all = residues[res_key]

            # Match PDB atoms to template atoms
            match_map, tpl_center = match_residue_to_template(pdb_atoms_all, tpl_atoms)

            if match_map is None:
                print(f"  WARNING: Could not match residue {res_key} to template {tpl_name}")
                continue

            # Translate template atoms to PDB positions using centroid offset
            pdb_center = centroid(pdb_atoms_all)
            dx = pdb_center[0] - tpl_center[0]
            dy = pdb_center[1] - tpl_center[1]
            dz = pdb_center[2] - tpl_center[2]

            # Build atom list: sort by TEMPLATE index so bond table stays correct
            # Reverse map: template_index → pdb_index
            tpl_to_pdb = {tpl_i: pdb_i for pdb_i, tpl_i in match_map.items()}
            sdf_atoms = []
            formal_charges = []
            for tpl_i in sorted(tpl_to_pdb.keys()):
                pdb_i = tpl_to_pdb[tpl_i]
                elem = tpl_atoms[tpl_i][0]  # Element symbol from template
                px, py, pz = pdb_atoms_all[pdb_i][1], pdb_atoms_all[pdb_i][2], pdb_atoms_all[pdb_i][3]
                sdf_atoms.append((elem, px, py, pz))
                formal_charges.append(tpl_atoms[tpl_i][4])  # Charge from template

            # Write SDF entry
            resid_str = f"{res_key[0]}_{res_key[1]}"
            write_sdf_entry(f, sdf_atoms, tpl_bonds, resid_str, formal_charges)
            total_atoms += len(sdf_atoms)

    print(f"\n✓ Written {args.output}: {total_atoms} atoms, {len(residue_to_template)} molecules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
