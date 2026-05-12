#!/usr/bin/env python3
"""
cms2lmp.py — Convert Desmond CMS to LAMMPS data file
Uses Schrödinger Python API for coordinate extraction.
"""

import sys
from collections import defaultdict

def main():
    if len(sys.argv) < 2:
        print("Usage: cms2lmp.py <input.cms> [output_prefix]")
        sys.exit(1)

    cms_path = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else "system"

    from schrodinger.structure import StructureReader
    st = next(StructureReader(cms_path))

    print(f"Atoms: {st.atom_total}, Bonds: {len(list(st.bond))}")

    # ── Collect molecules ──
    mol_atoms = defaultdict(list)
    for a in st.atom:
        mol_atoms[a.molecule_number].append(a)

    # ── LAMMPS atom type mapping ──
    # Map element to numeric type
    ELEM_TO_TYPE = {'H': 1, 'C': 2, 'N': 3, 'O': 4, 'P': 5}
    MASSES = {1: 1.008, 2: 12.011, 3: 14.007, 4: 15.999, 5: 30.974}

    used_types = set()
    for a in st.atom:
        used_types.add(ELEM_TO_TYPE.get(a.element, 1))

    # ── Find bonds ──
    bonds_list = []
    for b in st.bond:
        bonds_list.append((b.atom1.index, b.atom2.index))

    # ── Find angles ──
    # Generate from bonds
    bond_set = set()
    bond_neighbors = defaultdict(set)
    for i, j in bonds_list:
        bond_set.add((i, j))
        bond_neighbors[i].add(j)
        bond_neighbors[j].add(i)

    angles_list = []
    for k in bond_neighbors:
        neigh = list(bond_neighbors[k])
        for i_idx in range(len(neigh)):
            for j_idx in range(i_idx+1, len(neigh)):
                angles_list.append((neigh[i_idx], k, neigh[j_idx]))

    # Remove duplicates
    angles_list = list(set(tuple(sorted([a,c])) + (b,) for a, b, c in angles_list))
    angles_list = [(a, b, c) for a, b, c in angles_list]

    # ── Write LAMMPS data file ──
    box = 15.0
    bx = st.property.get('r_chorus_box_ax', box)
    by = st.property.get('r_chorus_box_by', box)
    bz = st.property.get('r_chorus_box_cz', box)

    with open(f'{prefix}.data', 'w') as f:
        f.write(f'LAMMPS data file — urea system (from Desmond CMS)\n\n')
        f.write(f'{st.atom_total} atoms\n')
        f.write(f'{len(bonds_list)} bonds\n')
        f.write(f'{len(angles_list)} angles\n')
        f.write(f'0 dihedrals\n')
        f.write(f'0 impropers\n\n')
        f.write(f'{len(used_types)} atom types\n')
        f.write(f'1 bond types\n')
        f.write(f'1 angle types\n\n')
        f.write(f'0.0 {bx} xlo xhi\n')
        f.write(f'0.0 {by} ylo yhi\n')
        f.write(f'0.0 {bz} zlo zhi\n\n')

        f.write(f'Masses\n\n')
        for t in sorted(used_types):
            f.write(f'{t} {MASSES.get(t, 12.0)}\n')
        f.write('\n')

        f.write(f'Atoms\n\n')
        for a in st.atom:
            atype = ELEM_TO_TYPE.get(a.element, 1)
            mol = a.molecule_number
            f.write(f'{a.index} {mol} {atype} {a.formal_charge:.4f} '
                    f'{a.x:.6f} {a.y:.6f} {a.z:.6f}\n')
        f.write('\n')

        f.write(f'Bonds\n\n')
        for i, j in bonds_list:
            f.write(f'{bonds_list.index((i,j))+1} 1 {i} {j}\n')
        f.write('\n')

        f.write(f'Angles\n\n')
        for idx, (i, j, k) in enumerate(angles_list):
            f.write(f'{idx+1} 1 {i} {j} {k}\n')
        f.write('\n')

    print(f"  → {prefix}.data ({st.atom_total} atoms, {len(bonds_list)} bonds, {len(angles_list)} angles)")

    # ── Write minimal LAMMPS input script ──
    with open(f'{prefix}.in', 'w') as f:
        f.write(f'# LAMMPS input for urea system\n')
        f.write(f'units           real\n')
        f.write(f'atom_style      full\n')
        f.write(f'boundary        p p p\n\n')
        f.write(f'read_data       {prefix}.data\n\n')
        f.write(f'# Force field (simple harmonic)\n')
        f.write(f'pair_style      lj/cut/coul/long 10.0\n')
        f.write(f'pair_coeff      * * 0.1 3.0\n')  # Generic
        f.write(f'kspace_style    pppm 0.0001\n\n')
        f.write(f'bond_style      harmonic\n')
        f.write(f'bond_coeff      1 100.0 1.5\n')
        f.write(f'angle_style     harmonic\n')
        f.write(f'angle_coeff     1 50.0 109.5\n\n')
        f.write(f'# Run\n')
        f.write(f'thermo          100\n')
        f.write(f'thermo_style    custom step temp press pe ke vol density\n')
        f.write(f'velocity        all create 300.0 12345\n')
        f.write(f'fix             1 all nvt temp 300.0 300.0 100.0\n')
        f.write(f'timestep        0.5\n')
        f.write(f'run             1000\n')

    print(f"  → {prefix}.in")

if __name__ == '__main__':
    main()
