#!/usr/bin/env python3
"""Generate LAMMPS data files for urea + water systems (ReaxFF and bond/react)."""

import sys, os
import numpy as np

def generate_urea_water_data(outdir, n_water=30, box_size=15.0):
    """Generate urea + n_water molecules in a box.
    
    Urea structure (rough planar):
    O(1)=C(2)-(N(3)H2(4,5))-(N(6)H2(7,8))
    Bond lengths: C=O 1.25, C-N 1.35, N-H 1.01 (Å)
    """
    os.makedirs(outdir, exist_ok=True)
    
    # ── Atom types ──
    # ReaxFF: C=1, H=2, O=3, N=4
    # Bond/react: same mapping
    C, H, O, N = 1, 2, 3, 4
    
    # ── Urea coordinates ──
    urea_coords = np.array([
        [ 0.000,  0.000,  0.000],   # 1: C
        [ 0.000,  1.250,  0.000],   # 2: O (C=O)
        [-1.350, -0.350,  0.000],   # 3: N
        [-1.700, -1.340,  0.160],   # 4: H
        [-2.040,  0.360, -0.250],   # 5: H
        [ 1.350, -0.350,  0.000],   # 6: N
        [ 1.700, -1.340,  0.160],   # 7: H
        [ 2.040,  0.360, -0.250],   # 8: H
    ])
    
    urea_types = [C, O, N, H, H, N, H, H]
    urea_charges = [0.510, -0.510, -0.690, 0.345, 0.345, -0.690, 0.345, 0.345]
    
    # Center urea in box
    urea_coords += box_size / 2
    
    # ── Water molecules ──
    # TIP3P-like: O-H 0.9572, HOH angle 104.52°
    water_coords = np.array([
        [0.000,  0.000,  0.000],           # O
        [0.9572, 0.000,  0.000],           # H1
        [-0.240, 0.927,  0.000],           # H2
    ])
    
    water_types = [O, H, H]
    water_charges = [-0.834, 0.417, 0.417]
    
    # Packmol-style placement (random with minimum distance)
    np.random.seed(42)
    all_atoms = []
    all_types = []
    all_charges = []
    all_mols = []
    all_bonds = []
    all_angles = []
    
    # Add urea (molecule 1)
    for i in range(8):
        all_atoms.append(urea_coords[i])
        all_types.append(urea_types[i])
        all_charges.append(urea_charges[i])
        all_mols.append(1)
    
    # Urea bonds (by global atom index, 1-based)
    # C=O: 1-2, C-N: 1-3, 1-6, N-H: 3-4,3-5, 6-7,6-8
    urea_bonds = [(1,2), (1,3), (1,6), (3,4), (3,5), (6,7), (6,8)]
    all_bonds = list(urea_bonds)
    
    # Urea angles
    urea_angles = [
        (2,1,3), (2,1,6), (3,1,6),   # around C
        (1,3,4), (1,3,5), (4,3,5),   # around N(3)
        (1,6,7), (1,6,8), (7,6,8),   # around N(6)
    ]
    all_angles = list(urea_angles)
    
    # Place waters randomly
    min_dist = 2.5
    max_attempts = 1000
    water_count = 0
    
    for w in range(n_water):
        placed = False
        for attempt in range(max_attempts):
            # Random position
            center = np.random.uniform(min_dist, box_size - min_dist, 3)
            # Random rotation
            theta = np.random.uniform(0, 2*np.pi)
            phi = np.random.uniform(0, np.pi)
            rx = np.random.uniform(0, 2*np.pi)
            # Rotation matrix
            R = np.array([
                [np.cos(theta)*np.cos(phi), -np.sin(theta), np.cos(theta)*np.sin(phi)],
                [np.sin(theta)*np.cos(phi),  np.cos(theta), np.sin(theta)*np.sin(phi)],
                [-np.sin(phi),               0,             np.cos(phi)]
            ])
            water_pos = center + (water_coords @ R.T)
            
            # Check distances to all existing atoms
            too_close = False
            for existing in all_atoms:
                for wp in water_pos:
                    d = np.linalg.norm(wp - existing)
                    if d < min_dist:
                        too_close = True
                        break
                if too_close:
                    break
            
            # Check in box
            if not too_close:
                if np.all(water_pos > 0) and np.all(water_pos < box_size):
                    placed = True
                    mol_id = 2 + w
                    for i in range(3):
                        all_atoms.append(water_pos[i])
                        all_types.append(water_types[i])
                        all_charges.append(water_charges[i])
                        all_mols.append(mol_id)
                    base = len(all_atoms) - 2  # 1-based index of O
                    all_bonds.append((base, base+1))  # O-H1
                    all_bonds.append((base, base+2))  # O-H2
                    all_angles.append((base+1, base, base+2))  # H1-O-H2
                    water_count += 1
                    break
        
        if not placed:
            print(f"  Warning: could not place water {w+1}")
    
    # ── Write ReaxFF data file (atom_style charge) ──
    reaxff_path = os.path.join(outdir, "system_reaxff.data")
    n_atoms = len(all_atoms)
    n_types = 4
    n_bonds = len(all_bonds)
    n_angles = len(all_angles)
    
    with open(reaxff_path, 'w') as f:
        f.write(f"# Urea + {water_count} water — ReaxFF data file\n")
        f.write(f"# Box: {box_size:.1f} Å\n\n")
        f.write(f"{n_atoms} atoms\n")
        f.write(f"{n_bonds} bonds\n")
        f.write(f"{n_angles} angles\n")
        f.write(f"0 dihedrals\n")
        f.write(f"0 impropers\n\n")
        f.write(f"{n_types} atom types\n")
        f.write(f"1 bond types\n")
        f.write(f"1 angle types\n\n")
        
        f.write(f"0.000 {box_size:.1f} xlo xhi\n")
        f.write(f"0.000 {box_size:.1f} ylo yhi\n")
        f.write(f"0.000 {box_size:.1f} zlo zhi\n\n")
        
        f.write("Masses\n\n")
        for t, elem in [(1,'C'), (2,'H'), (3,'O'), (4,'N')]:
            mass = {'C':12.011, 'H':1.008, 'O':15.999, 'N':14.007}[elem]
            f.write(f"{t} {mass:.3f}  # {elem}\n")
        
        f.write("\nAtoms # charge\n\n")
        for i in range(n_atoms):
            aid = i + 1
            f.write(f"{aid} {all_mols[i]} {all_types[i]} {all_charges[i]:.6f} "
                    f"{all_atoms[i][0]:.6f} {all_atoms[i][1]:.6f} {all_atoms[i][2]:.6f}\n")
        
        if n_bonds > 0:
            f.write("\nBonds\n\n")
            for i, (a, b) in enumerate(all_bonds):
                f.write(f"{i+1} 1 {a} {b}\n")
        
        if n_angles > 0:
            f.write("\nAngles\n\n")
            for i, (a, b, c) in enumerate(all_angles):
                f.write(f"{i+1} 1 {a} {b} {c}\n")
    
    print(f"  ✓ ReaxFF data: {reaxff_path} ({n_atoms} atoms)")
    
    # ── Write bond/react data file (atom_style full) ──
    # Same structure but with pair_coeff and bond/angle coeffs
    br_path = os.path.join(outdir, "system_bond_react.data")
    
    with open(br_path, 'w') as f:
        f.write(f"# Urea + {water_count} water — Bond/React data file\n")
        f.write(f"# Box: {box_size:.1f} Å\n\n")
        f.write(f"{n_atoms} atoms\n")
        f.write(f"{n_bonds} bonds\n")
        f.write(f"{n_angles} angles\n")
        f.write(f"0 dihedrals\n")
        f.write(f"0 impropers\n\n")
        f.write(f"{n_types} atom types\n")
        f.write(f"1 bond types\n")
        f.write(f"1 angle types\n\n")
        
        f.write(f"0.000 {box_size:.1f} xlo xhi\n")
        f.write(f"0.000 {box_size:.1f} ylo yhi\n")
        f.write(f"0.000 {box_size:.1f} zlo zhi\n\n")
        
        f.write("Masses\n\n")
        for t, elem in [(1,'C'), (2,'H'), (3,'O'), (4,'N')]:
            mass = {'C':12.011, 'H':1.008, 'O':15.999, 'N':14.007}[elem]
            f.write(f"{t} {mass:.3f}  # {elem}\n")
        
        f.write("\nAtoms # full\n\n")
        for i in range(n_atoms):
            aid = i + 1
            f.write(f"{aid} {all_mols[i]} {all_types[i]} {all_charges[i]:.6f} "
                    f"{all_atoms[i][0]:.6f} {all_atoms[i][1]:.6f} {all_atoms[i][2]:.6f}\n")
        
        if n_bonds > 0:
            f.write("\nBonds\n\n")
            for i, (a, b) in enumerate(all_bonds):
                f.write(f"{i+1} 1 {a} {b}\n")
        
        if n_angles > 0:
            f.write("\nAngles\n\n")
            for i, (a, b, c) in enumerate(all_angles):
                f.write(f"{i+1} 1 {a} {b} {c}\n")
    
    print(f"  ✓ Bond/react data: {br_path} ({n_atoms} atoms)")
    print(f"  Molecules: 1 urea + {water_count} water")
    return reaxff_path, br_path


if __name__ == '__main__':
    outdir = sys.argv[1] if len(sys.argv) > 1 else '/home/xenon/xhy/motus-test/urea_reaxff'
    n_water = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    generate_urea_water_data(outdir, n_water)
