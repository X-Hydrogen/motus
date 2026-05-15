#!/usr/bin/env python3
"""
fix_pdb_for_schrodinger.py — Convert Packmol PDB to Schrödinger-compatible format.

Reads packmol.inp to determine molecule types and atom counts, then assigns
proper residue names and chain IDs to the combined Packmol output PDB.
"""
import sys, re, os
from pathlib import Path
from collections import Counter

def main():
    pdb_in = Path(sys.argv[1])
    pdb_out = Path(sys.argv[2])
    project_dir = Path(sys.argv[3])
    
    # Parse packmol.inp for molecule structure
    packmol_inp = project_dir / "packmol.inp"
    mol_types = {}  # {name: atoms_per_molecule}
    mol_seq = []    # [(name, count), ...] ordered
    
    if packmol_inp.exists():
        text = packmol_inp.read_text()
        structs = re.findall(r'^[ \t]*structure\s+(\S+)', text, re.MULTILINE)
        numbers = re.findall(r'number\s+(\d+)', text)
        
        for sfile, nstr in zip(structs, numbers):
            n = int(nstr)
            # Resolve PDB path
            spath = Path(sfile)
            if not spath.is_absolute():
                spath = project_dir / sfile
            if not spath.exists():
                alt = Path.home() / ".motus" / "molecules" / spath.name
                if alt.exists():
                    spath = alt
            
            if spath.exists():
                natoms = len([l for l in spath.read_text().splitlines()
                             if l.startswith(('ATOM','HETATM'))])
                # Clean residue name: remove +, -, digits
                name = spath.stem.upper()
                name = name.replace('+','P').replace('-','M')
                # Take first 3 chars for PDB residue name
                name = name[:3]
                mol_types[name] = natoms
                for _ in range(n):
                    mol_seq.append(name)
                print(f"  {name}: {n} x {natoms} atoms = {n * natoms} total")
            else:
                print(f"  WARNING: {sfile} not found, skipping")
    
    if not mol_seq:
        print("  No molecule types detected — renumbering residues only")
    
    # Read PDB
    lines = pdb_in.read_text().splitlines()
    atom_lines = [l for l in lines if l.startswith(('ATOM','HETATM'))]
    non_atom_lines = [l for l in lines if not l.startswith(('ATOM','HETATM'))]
    
    print(f"  Total atoms in PDB: {len(atom_lines)}")
    
    # Assign residue names based on molecule sequence
    new_lines = []
    if mol_seq:
        mol_ptr = 0
        atom_ptr = 0
        current_resnum = 0
        
        for line in atom_lines:
            if mol_ptr >= len(mol_seq):
                resname = mol_seq[-1] if mol_seq else "UNK"
            else:
                resname = mol_seq[mol_ptr]
                expected = mol_types.get(resname, 999)
                
                if atom_ptr == 0:
                    current_resnum += 1
                    # Reset atom name counter for new residue
                    atom_name_count = {}
                
                atom_ptr += 1
                if atom_ptr >= expected:
                    atom_ptr = 0
                    mol_ptr += 1
            
            # Ensure unique atom names within residue
            orig_name = line[12:16].strip()
            elem = orig_name.rstrip('0123456789')  # Extract element
            cnt = atom_name_count.get(orig_name, 0) + 1
            atom_name_count[orig_name] = cnt
            if cnt > 1 or len(orig_name) < 1:
                # Add numeric suffix for uniqueness
                unique_name = f"{elem}{cnt}"
            else:
                unique_name = orig_name
            
            serial = line[6:11]
            rest = line[26:]
            
            new_line = (f"ATOM  {serial} {unique_name:<4s} {resname:<3.3s} A{current_resnum:4d}{rest}")
            new_lines.append(new_line)
    else:
        for i, line in enumerate(atom_lines):
            new_lines.append(line)
    
    # Write output with header
    with open(pdb_out, 'w') as f:
        f.write(f"HEADER    DESMOND MODEL\n")
        f.write(f"TITLE     Converted from Packmol by MOTUS\n")
        f.write(f"REMARK    Residue names assigned from packmol.inp\n")
        for l in new_lines:
            f.write(l + '\n')
        f.write("END\n")
    
    print(f"  ✓ Output: {pdb_out} ({len(new_lines)} atoms, {current_resnum} residues)")

if __name__ == "__main__":
    main()
