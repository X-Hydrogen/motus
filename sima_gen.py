#!/usr/bin/env python3
"""
sima_gen.py — Generate Simulation Interactions Diagram .dat files from Desmond trajectory.  |  MOTUS v0.0.1
Command-line equivalent of Maestro's "Simulation Interactions Diagram" for non-protein systems.

Detects the ligand molecule automatically (largest molecule by molecular weight),
computes all rotatable-bond torsion angles and ligand properties over the trajectory,
and outputs .dat files compatible with sima_plot.py.

Usage:
  $SCHRODINGER/run python3 sima_gen.py <cms_file> <trj_dir> [OUTDIR]
  $SCHRODINGER/run python3 sima_gen.py system-out.cms system_trj/ analysis/
  $SCHRODINGER/run python3 sima_gen.py system-out.cms system_trj/ --mol 2 --stride 5

Output:
  L_Torsions.dat       — torsion angle time series (deg)
  L-Properties.dat     — ligand properties: RMSD, Rg, intraHB, MolSA, SASA, PSA
"""

import sys, os, argparse, csv
import numpy as np

from schrodinger.application.desmond.packages import traj, topo


def find_rotatable_bonds(st, mol_atoms):
    """Find all rotatable bonds within a molecule.

    A rotatable bond is a single bond NOT:
    - in a ring
    - terminal (attached to H only on one end)
    - part of an amide/ester/etc (conjugated double bond adjacent)

    Returns list of (atom1_index, atom2_index) in 1-based indexing.
    """
    # Get ring membership
    ring_atom_set = set()
    try:
        from schrodinger.structutils.analyze import find_rings
        rings = find_rings(st)
        for ring in rings:
            for atom in ring:
                ring_atom_set.add(atom.index)
    except Exception:
        pass

    rotatable = []
    for bond in st.bond:
        a1, a2 = bond.atom1, bond.atom2
        if a1.index not in mol_atoms or a2.index not in mol_atoms:
            continue
        if bond.order != 1:
            continue
        if a1.index in ring_atom_set and a2.index in ring_atom_set:
            continue
        # Check hydrogens: if one end has no heavy-atom neighbors other than the bonded partner, it's terminal
        # Count non-H neighbors for each atom
        def heavy_neighbors(atom, exclude):
            return [a for a in atom.bonded_atoms
                    if a.index in mol_atoms and a.element != 'H' and a.index != exclude]

        h1 = heavy_neighbors(a1, a2.index)
        h2 = heavy_neighbors(a2, a1.index)
        if len(h1) == 0 or len(h2) == 0:
            continue  # terminal (methyl, -OH, etc — skip)
        if len(h1) < 2 and len(h2) < 2:
            continue  # very short chain

        rotatable.append((a1.index, a2.index))

    return rotatable


def compute_torsion(pos, a1, a2, a3, a4, box=None):
    """Compute dihedral angle given 4 atom positions, with PBC correction."""
    p1 = np.array(pos[a1])
    p2 = np.array(pos[a2])
    p3 = np.array(pos[a3])
    p4 = np.array(pos[a4])

    b1 = p2 - p1
    b2 = p3 - p2
    b3 = p4 - p3

    # Apply minimum image if box provided
    if box is not None:
        for v in [b1, b2, b3]:
            for i in range(3):
                if box[i][i] > 0:
                    v[i] -= box[i][i] * round(v[i] / box[i][i])

    b2_norm = b2 / np.linalg.norm(b2)
    n1 = np.cross(b1, b2)
    n1 /= np.linalg.norm(n1)
    n2 = np.cross(b2, b3)
    n2 /= np.linalg.norm(n2)

    # Compute angle
    m1 = np.cross(n1, b2_norm)
    x = np.dot(n1, n2)
    y = np.dot(m1, n2)
    angle = np.degrees(np.arctan2(y, x))
    return angle


def compute_intrahb(st, pos, mol_atoms):
    """Count intramolecular H-bonds within the molecule."""
    # Simple geometric criterion: O/N-H ... O/N with distance < 3.5A and angle > 120°
    donors = [a for a in st.atom if a.index in mol_atoms and a.element in ('O', 'N')]
    acceptors = [a for a in st.atom if a.index in mol_atoms and a.element in ('O', 'N')]

    # Find H atoms bonded to donors
    count = 0
    for d in donors:
        for h in d.bonded_atoms:
            if h.element == 'H' and h.index in mol_atoms:
                d_pos = np.array(pos[d.index])
                h_pos = np.array(pos[h.index])
                for a in acceptors:
                    if a.index == d.index:
                        continue
                    a_pos = np.array(pos[a.index])
                    d_a_vec = a_pos - d_pos
                    h_a_vec = a_pos - h_pos
                    dist_ha = np.linalg.norm(h_a_vec)
                    if dist_ha < 2.5:  # H...A distance
                        # Check D-H...A angle
                        dh_vec = h_pos - d_pos
                        cos_ang = np.dot(dh_vec, h_a_vec) / (np.linalg.norm(dh_vec) * dist_ha)
                        angle = np.degrees(np.arccos(np.clip(cos_ang, -1, 1)))
                        if angle > 120:
                            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description='Generate Simulation Interactions Diagram .dat files')
    parser.add_argument('cms', help='CMS file (-out.cms)')
    parser.add_argument('trj', help='Trajectory directory (_trj/)')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory (default: .)')
    parser.add_argument('--mol', type=int, default=0,
                        help='Molecule number to analyze (default: auto-detect largest)')
    parser.add_argument('--stride', type=int, default=1,
                        help='Frame stride (default: 1, use every frame; set higher for speed)')
    parser.add_argument('--max-frames', type=int, default=2000,
                        help='Maximum frames to process (default: 2000)')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 SIMA Generator')
    print(f'   CMS:  {args.cms}')
    print(f'   TRJ:  {args.trj}')
    print(f'   Out:  {outdir}')

    # Load system
    msys, cms_model = topo.read_cms(args.cms)
    st = cms_model
    tr = traj.read_traj(args.trj)

    # Auto-detect ligand molecule
    if args.mol > 0:
        ligand_mol = args.mol
    else:
        # Find largest molecule by number of atoms (excluding water/ions)
        mol_atoms = {}  # mol_number -> set of atom indices
        for atom in st.atom:
            if atom.element == 'W':  # skip TIP3P/SPC water dummy atoms
                continue
            mn = atom.molecule_number
            if mn not in mol_atoms:
                mol_atoms[mn] = set()
            mol_atoms[mn].add(atom.index)

        # Sort by number of atoms, pick largest
        sorted_mols = sorted(mol_atoms.items(), key=lambda x: len(x[1]), reverse=True)
        ligand_mol = sorted_mols[0][0]
        n_atoms = len(sorted_mols[0][1])
        print(f'   Auto-detected ligand: molecule {ligand_mol} ({n_atoms} atoms)')
        if len(sorted_mols) > 1:
            print(f'   Other molecules: {[f"#{m}({len(a)}atoms)" for m,a in sorted_mols[1:5]]}')

    # Get ligand atom indices
    ligand_atoms = set()
    for atom in st.atom:
        if atom.molecule_number == ligand_mol:
            ligand_atoms.add(atom.index)
    print(f'   Ligand atom count: {len(ligand_atoms)}')

    # Find rotatable bonds
    rot_bonds = find_rotatable_bonds(st, ligand_atoms)
    n_tors = len(rot_bonds)
    print(f'   Rotatable bonds found: {n_tors}')

    # For each rotatable bond, find the flanking atoms for torsion definition
    torsion_defs = []  # each: (a1, a2, a3, a4) where a2-a3 is the rotatable bond
    for b1, b2 in rot_bonds:
        atom2 = st.atom[b2]
        atom1_st = st.atom[b1]
        # Find neighbors of b1 (not b2)
        nb1 = [a for a in atom1_st.bonded_atoms
               if a.index in ligand_atoms and a.index != b2]
        # Find neighbors of b2 (not b1)
        nb2 = [a for a in atom2.bonded_atoms
               if a.index in ligand_atoms and a.index != b1]

        if nb1 and nb2:
            torsion_defs.append((nb1[0].index, b1, b2, nb2[0].index))
        elif nb1:
            # Use H if available
            nb1_h = [a for a in atom1_st.bonded_atoms if a.element == 'H']
            if nb1_h:
                torsion_defs.append((nb1_h[0].index, b1, b2, nb1[0].index))
            else:
                torsion_defs.append((nb1[0].index, b1, b2, b1))  # fallback
        elif nb2:
            nb2_h = [a for a in atom2.bonded_atoms if a.element == 'H']
            if nb2_h:
                torsion_defs.append((b2, b1, b2, nb2_h[0].index))
            else:
                torsion_defs.append((b2, b1, b2, nb2[0].index))

    n_tors = len(torsion_defs)
    print(f'   Torsion definitions: {n_tors}')

    # Prepare data collection
    n_frames_total = len(tr)
    stride = max(1, n_frames_total // args.max_frames) if args.stride <= 1 else args.stride
    frames_to_process = list(range(0, n_frames_total, stride))
    n_process = len(frames_to_process)

    print(f'   Processing {n_process} frames (stride={stride}, total={n_frames_total})')

    # Initialize output files
    tors_file = open(os.path.join(outdir, 'L_Torsions.dat'), 'w')
    tors_file.write('# Simulation Interactions Diagram\n')
    tors_file.write('# Ligand Torsions\n')
    tors_file.write('# ' + '  '.join(['Frame_Time'] + [f'Torsion_{i+1}' for i in range(n_tors)]) + '\n')

    props_file = open(os.path.join(outdir, 'L-Properties.dat'), 'w')
    props_file.write('# Simulation Interactions Diagram\n')
    props_file.write('# Ligand Properties\n')
    props_file.write('Time  RMSD  rGyr  intraHB  MolSA  SASA  PSA\n')

    # Reference structure (first frame) for RMSD
    tr0 = tr[0]
    ref_pos = {a.index: tr0.pos(a.index) for a in st.atom if a.index in ligand_atoms}
    ref_com = np.mean([tr0.pos(a.index) for a in st.atom if a.index in ligand_atoms], axis=0)

    for fi, frame_idx in enumerate(frames_to_process):
        frame = tr[frame_idx]
        allpos = frame.pos()
        box = frame.box

        # ── Torsions ──
        torsion_vals = []
        for a1, a2, a3, a4 in torsion_defs:
            angle = compute_torsion(allpos, a1, a2, a3, a4, box)
            torsion_vals.append(f'{angle:.2f}')

        tors_file.write(f'{frame.time:.3f}  ' + '  '.join(torsion_vals) + '\n')

        # ── Properties ──
        # RMSD: align-free, just superposition on reference
        rmsd_val = 0.0
        n_rmsd = 0
        for a in st.atom:
            if a.index in ligand_atoms and a.index in ref_pos:
                dp = np.array(allpos[a.index]) - np.array(ref_pos[a.index])
                # minimum image
                for d in range(3):
                    if box[d][d] > 0:
                        dp[d] -= box[d][d] * round(dp[d] / box[d][d])
                rmsd_val += np.dot(dp, dp)
                n_rmsd += 1
        rmsd_val = np.sqrt(rmsd_val / max(1, n_rmsd))

        # Rg
        lig_pos = np.array([allpos[a.index] for a in st.atom if a.index in ligand_atoms])
        if len(lig_pos) > 0:
            com = np.mean(lig_pos, axis=0)
            rg_sq = np.mean([np.sum((p - com)**2) for p in lig_pos])
            rg_val = np.sqrt(rg_sq)
        else:
            rg_val = 0.0

        # IntraHB
        intrahb_val = compute_intrahb(st, allpos, ligand_atoms)

        # MolSA, SASA, PSA — update structure coords then compute
        molsa_val = 0.0
        sasa_val = 0.0
        psa_val = 0.0
        try:
            from schrodinger.structutils.analyze import calculate_sasa_by_atom
            # Update structure coordinates from frame
            for i in range(st.atom_total):
                p = allpos[i]
                st.atom[i + 1].x = p[0]
                st.atom[i + 1].y = p[1]
                st.atom[i + 1].z = p[2]
            sasa_result = calculate_sasa_by_atom(st, probe_radius=1.4)
            # sasa_result is tuple, 0-indexed (atom_idx → SASA)
            sasa_val = sum(sasa_result[i - 1] for i in ligand_atoms)
            molsa_val = sasa_val
            polar_indices = [i for i in ligand_atoms
                            if st.atom[i].element in ('O', 'N')]
            psa_val = sum(sasa_result[i - 1] for i in polar_indices)
        except Exception:
            pass

        props_file.write(f'{frame.time:.1f}  {rmsd_val:.3f}  {rg_val:.3f}  '
                        f'{intrahb_val}  {molsa_val:.1f}  {sasa_val:.1f}  {psa_val:.1f}\n')

        if fi % max(1, n_process // 10) == 0 or fi == n_process - 1:
            print(f'   Frame {frame_idx}/{n_frames_total}  ({100*(fi+1)//n_process}%)')

    tors_file.close()
    props_file.close()

    print(f'\n✅ Generated:')
    print(f'   {outdir}/L_Torsions.dat  ({n_tors} torsions, {n_process} frames)')
    print(f'   {outdir}/L-Properties.dat  (7 properties, {n_process} frames)')


if __name__ == '__main__':
    main()
