#!/usr/bin/env python3
"""
cms2gmx.py — Convert Desmond CMS to GROMACS topology + coordinates
Uses Schrödinger Python API + OPLS-AA force field mapping.
"""

import sys, os
from collections import defaultdict

def main():
    if len(sys.argv) < 2:
        print("Usage: cms2gmx.py <input.cms> [output_prefix]")
        sys.exit(1)

    cms_path = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else "system"

    # Load CMS
    from schrodinger.structure import StructureReader
    st = next(StructureReader(cms_path))

    print(f"Atoms: {st.atom_total}, Bonds: {len(list(st.bond))}")

    # ── Map Schrödinger atom types to OPLS-AA ──
    # Based on common OPLS atom type naming
    TYPE_MAP = {
        # Urea
        ('C', 'C2'): 'opls_235',   # C=O carbonyl
        ('O', 'O2'): 'opls_236',   # =O carbonyl oxygen
        ('N', 'N2'): 'opls_238',   # amide N
        ('H', 'H3'): 'opls_240',   # amide H
        # Phosphate
        ('P', 'P5'): 'opls_431',   # phosphate P
        ('O', 'O3'): 'opls_432',   # phosphate O (double bond)
        ('O', 'OM'): 'opls_433',   # phosphate O- (anionic)
        ('O', 'O0'): 'opls_434',   # phosphate OH
        ('H', 'H2'): 'opls_435',   # phosphate OH hydrogen
        # Ammonium
        ('N', 'N5'): 'opls_287',   # ammonium N+
        ('H', 'H4'): 'opls_290',   # ammonium H
    }

    # Bond force constants (kJ/mol/nm^2) — OPLS-AA harmonic bonds
    BOND_K = {
        ('C', 'N'): 282001.6, ('C', 'O'): 476976.0, ('C', 'H'): 284512.0,
        ('N', 'H'): 363171.2, ('P', 'O'): 376560.0, ('O', 'H'): 462750.4,
        ('P', 'P'): 200000.0, ('C', 'C'): 265265.6,
    }
    BOND_R = {
        ('C', 'N'): 0.1335, ('C', 'O'): 0.1229, ('C', 'H'): 0.1090,
        ('N', 'H'): 0.1010, ('P', 'O'): 0.1480, ('O', 'H'): 0.0945,
        ('P', 'P'): 0.2100, ('C', 'C'): 0.1526,
    }
    # Angle force constants (kJ/mol/rad^2) — OPLS-AA harmonic angles
    ANGLE_K = {
        ('C', 'N', 'H'): 292.88, ('H', 'N', 'H'): 292.88,
        ('N', 'C', 'N'): 585.76, ('N', 'C', 'O'): 669.44,
        ('O', 'P', 'O'): 418.40, ('P', 'O', 'H'): 292.88,
        ('H', 'N', 'H'): 292.88,  # ammonium
        ('H', 'O', 'H'): 460.24,  # water
    }
    ANGLE_TH = {
        ('C', 'N', 'H'): 119.8, ('H', 'N', 'H'): 118.0,
        ('N', 'C', 'N'): 115.0, ('N', 'C', 'O'): 123.0,
        ('O', 'P', 'O'): 109.5, ('P', 'O', 'H'): 109.5,
        ('H', 'N', 'H'): 109.5,  # ammonium
        ('H', 'O', 'H'): 104.5,  # water
    }

    def get_opls_type(a):
        """Map to OPLS atom type, with fallback."""
        elem = a.element
        atype = a.atom_type_name
        key = (elem, atype)
        if key in TYPE_MAP:
            return TYPE_MAP[key]
        # Fallback: use element-based generic
        generic = {'H': 'opls_140', 'C': 'opls_135', 'N': 'opls_900',
                    'O': 'opls_154', 'P': 'opls_440', 'S': 'opls_155'}
        return generic.get(elem, f'opls_{a.index:03d}')

    # ── Build molecule-to-atom mapping ──
    mol_atoms = defaultdict(list)
    for a in st.atom:
        mol_atoms[a.molecule_number].append(a)

    # ── Write GRO file ──
    with open(f'{prefix}.gro', 'w') as f:
        f.write(f'Urea system (from Desmond CMS)\n')
        f.write(f'{st.atom_total:5d}\n')
        for a in st.atom:
            res_num = a.molecule_number
            res_name = a.pdbres.strip()[:5]
            atom_name = (a.atom_type_name or a.element)[:5]
            f.write(f'{res_num:5d}{res_name:<5s}{atom_name:>5s}{a.index:5d}'
                    f'{a.x:8.3f}{a.y:8.3f}{a.z:8.3f}\n')
        box = 15.0
        bx = st.property.get('r_chorus_box_ax', box)
        by = st.property.get('r_chorus_box_by', box)
        bz = st.property.get('r_chorus_box_cz', box)
        f.write(f'{bx:10.5f}{by:10.5f}{bz:10.5f}\n')

    print(f"  → {prefix}.gro")

    # ── Write TOP file (with atom types) ──
    # Collect all unique OPLS types and their LJ parameters
    all_types = {}
    for a in st.atom:
        opls = get_opls_type(a)
        if opls not in all_types:
            all_types[opls] = a.element

    # OPLS-AA LJ parameters (sigma in nm, epsilon in kJ/mol)
    # These are approximate for common atom types
    LJ_PARAMS = {
        'opls_235': (0.355, 0.29288),   # C carbonyl
        'opls_236': (0.296, 0.87864),   # O carbonyl
        'opls_238': (0.325, 0.71128),   # N amide
        'opls_240': (0.000, 0.00000),   # H amide (zero in OPLS-AA, on parent)
        'opls_287': (0.325, 0.71128),   # N ammonium
        'opls_290': (0.125, 0.12552),   # H ammonium
        'opls_431': (0.374, 0.83680),   # P phosphate
        'opls_432': (0.296, 0.87864),   # O phosphate =
        'opls_433': (0.296, 0.87864),   # O phosphate -
        'opls_434': (0.300, 0.71128),   # O phosphate OH
        'opls_435': (0.000, 0.00000),   # H phosphate OH
        'opls_154': (0.315, 0.64852),   # O generic (water)
        'opls_135': (0.350, 0.27614),   # C generic
        'opls_140': (0.250, 0.12552),   # H generic
        'opls_440': (0.374, 0.83680),   # P generic
    }

    with open(f'{prefix}.top', 'w') as f:
        f.write('; Topology for urea hydrolysis system\n')
        f.write('; Generated from Desmond CMS by cms2gmx.py\n\n')
        f.write('[ defaults ]\n')
        f.write('; nbfunc  comb-rule  gen-pairs  fudgeLJ  fudgeQQ\n')
        f.write('  1       3           yes        0.5       0.5\n\n')
        
        f.write('[ atomtypes ]\n')
        f.write('; name       at.num   mass      charge   ptype   sigma(nm)   epsilon(kJ/mol)\n')
        for opls, elem in sorted(all_types.items()):
            mass = {'H':1.008, 'C':12.011, 'N':14.007, 'O':15.999, 'P':30.974}.get(elem, 12.0)
            atnum = {'H':1, 'C':6, 'N':7, 'O':8, 'P':15}.get(elem, 6)
            sigma, eps = LJ_PARAMS.get(opls, (0.320, 0.500))
            f.write(f'  {opls:12s}  {atnum:5d}  {mass:10.4f}  0.0000  A  {sigma:10.6f}  {eps:10.6f}\n')
        f.write('\n')
        
        # Include all molecule ITP files
        for mol_num in sorted(mol_atoms.keys()):
            f.write(f'#include "system_{mol_num}.itp"\n')
        f.write('\n')
        
        f.write('[ system ]\n')
        f.write('Urea hydrolysis\n\n')
        f.write('[ molecules ]\n')
        f.write('; molecule_type     count\n')

        # Count molecules by type
        from collections import Counter
        mol_counts = Counter()
        for mol_num in sorted(mol_atoms.keys()):
            atoms = mol_atoms[mol_num]
            res_name = atoms[0].pdbres.strip()
            mol_name = f"{res_name}_{mol_num}"
            mol_counts[mol_name] = 1  # each is unique

        for mol_num in sorted(mol_atoms.keys()):
            atoms = mol_atoms[mol_num]
            res_name = atoms[0].pdbres.strip()
            mol_name = f"{res_name}_{mol_num}"
            f.write(f'{mol_name:20s}  1\n')

        f.write('\n')

    print(f"  → {prefix}.top")

    # ── Write ITP files for each molecule ──
    for mol_num in sorted(mol_atoms.keys()):
        atoms = mol_atoms[mol_num]
        res_name = atoms[0].pdbres.strip()
        mol_name = f"{res_name}_{mol_num}"
        itp_path = f'{prefix}_{mol_num}.itp'

        # Find bonds within this molecule
        mol_indices = {a.index for a in atoms}
        mol_bonds = []
        mol_angles = []
        for b in st.bond:
            i, j = b.atom1.index, b.atom2.index
            if i in mol_indices and j in mol_indices:
                mol_bonds.append((i, j, b.atom1.element, b.atom2.element))

        # Generate angles from bonds (all possible)
        for i in range(len(mol_bonds)):
            for j in range(i+1, len(mol_bonds)):
                bi, bj = mol_bonds[i], mol_bonds[j]
                shared = set(bi[:2]) & set(bj[:2])
                if shared:
                    s = shared.pop()
                    others = [x for x in list(bi[:2]) + list(bj[:2]) if x != s]
                    if len(others) == 2:
                        a1, a2 = others
                        el1 = '?' 
                        el2 = '?'
                        el_s = '?'
                        for a in atoms:
                            if a.index == a1: el1 = a.element
                            if a.index == a2: el2 = a.element
                            if a.index == s: el_s = a.element
                        mol_angles.append((a1, s, a2, el1, el_s, el2))

        with open(itp_path, 'w') as f:
            nrexcl = 3
            f.write(f'[ moleculetype ]\n')
            f.write(f'; name    nrexcl\n')
            f.write(f'{mol_name:10s} {nrexcl}\n\n')

            # Build local index mapping: global CMS index → local ITP index
            local_idx = {a.index: i+1 for i, a in enumerate(atoms)}

            f.write(f'[ atoms ]\n')
            f.write(f'; nr  type       resnr  residue  atom   cgnr  charge     mass\n')
            for a in atoms:
                opls = get_opls_type(a)
                mass = {'H':1.008, 'C':12.011, 'N':14.007, 'O':15.999, 'P':30.974}.get(a.element, 12.0)
                f.write(f'{local_idx[a.index]:5d} {opls:12s} {mol_num:5d}  {res_name:5s}  '
                        f'{a.atom_type_name:5s} {mol_num:5d}  '
                        f'{a.formal_charge:8.4f}  {mass:8.4f}\n')

            f.write(f'\n[ bonds ]\n')
            f.write(f'; ai  aj  funct   r(nm)      k(kJ/mol/nm^2)\n')
            for i, j, e1, e2 in mol_bonds:
                key = tuple(sorted([e1, e2]))
                r = BOND_R.get(key, 0.1500)
                k = BOND_K.get(key, 200000.0)
                f.write(f'{local_idx[i]:5d} {local_idx[j]:5d}  1  {r:10.4f}  {k:12.1f}\n')

            f.write(f'\n[ angles ]\n')
            f.write(f'; ai  aj  ak  funct  theta(deg)  k(kJ/mol/rad^2)\n')
            for i, j, k, e1, e2, e3 in mol_angles:
                key = (e1, e2, e3)
                th = ANGLE_TH.get(key, ANGLE_TH.get((e3, e2, e1), 109.5))
                kq = ANGLE_K.get(key, ANGLE_K.get((e3, e2, e1), 292.88))
                f.write(f'{local_idx[i]:5d} {local_idx[j]:5d} {local_idx[k]:5d}  1  {th:10.3f}  {kq:12.3f}\n')

            # Pairs from angles
            if mol_angles:
                f.write(f'\n[ pairs ]\n')
                f.write(f'; ai  aj  funct\n')
                seen_pairs = set()
                for i, j, k, *_ in mol_angles:
                    pair = tuple(sorted([i, k]))
                    if pair not in seen_pairs:
                        f.write(f'{local_idx[pair[0]]:5d} {local_idx[pair[1]]:5d}  1\n')
                        seen_pairs.add(pair)

        print(f"  → {itp_path} ({len(atoms)} atoms, {len(mol_bonds)} bonds, {len(mol_angles)} angles)")

    print(f"\nDone! Generated {prefix}.gro + {prefix}.top + {len(mol_atoms)} itp files")

if __name__ == '__main__':
    main()
