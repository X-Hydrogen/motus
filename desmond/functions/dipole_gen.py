#!/usr/bin/env python3
"""
dipole_gen.py — Molecular Dipole Moment from Desmond MD.  |  MOTUS v0.0.1

Computes total and per-molecule dipole moments from trajectory
using atomic partial charges from the force field.

Usage:
  $SCHRODINGER/run python3 dipole_gen.py <cms> <trj> [OUTDIR]
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo

# Elementary charge to Debye conversion
E_TO_DEBYE = 4.8032047  # e·Å → Debye


def get_element(atom):
    return atom.element.strip().capitalize()


def get_molecule_label(cms_model, mol_number, atom_in_mol):
    """Generate a readable molecule label: elemental formula."""
    # Use provided atom info for this molecule
    el_counts = defaultdict(int)
    for a in atom_in_mol:
        el = get_element(a)
        if el and el not in ('', 'W'):
            el_counts[el] += 1
    # Format: C1_H4_N2_O1 (sorted by element)
    parts = []
    for el in sorted(el_counts.keys()):
        parts.append(f'{el}{el_counts[el]}')
    return '_'.join(parts) if parts else f'mol{mol_number}'


def main():
    parser = argparse.ArgumentParser(description='Molecular dipole moment from Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'💡 Dipole Moment Analysis')
    print(f'   CMS: {args.cms}')
    print(f'   TRJ: {args.trj}')

    # Load
    msys_model, cms_model = topo.read_cms(args.cms)
    st = cms_model
    tr = traj.read_traj(args.trj)

    n_total = len(tr)
    stride = max(1, n_total // args.max_frames)
    if args.stride > 1:
        stride = args.stride
    frame_indices = list(range(0, n_total, stride))
    n_frames = len(frame_indices)
    print(f'   Frames: {n_frames} (stride={stride})')

    # Build atom info: index (0-based for pos), element, charge, molecule_number
    atoms_info = []
    for a in st.atom:
        prop = a.property
        charge = float(prop.get('r_m_charge1', 0.0)) if 'r_m_charge1' in prop else 0.0
        atoms_info.append({
            'idx': a.index - 1,     # 0-based for trajectory pos[]
            'atom': a,              # Schrödinger Atom object
            'element': get_element(a),
            'charge': charge,
            'mol': a.molecule_number,
        })

    # Group by molecule
    mol_atoms = defaultdict(list)
    for a in atoms_info:
        mol_atoms[a['mol']].append(a)

    # Water indices
    water_mols = set()
    solute_mols = set()
    for mn, alist in mol_atoms.items():
        el_counts = defaultdict(int)
        total_atoms = 0
        for a in alist:
            if a['element'] not in ('', 'W'):
                el_counts[a['element']] += 1
                total_atoms += 1
        if total_atoms == 0:
            continue
        is_water = (all(k in ('O', 'H') for k in el_counts.keys()) and
                    el_counts.get('O', 0) >= 1 and sum(el_counts.values()) <= 4)
        if is_water:
            water_mols.add(mn)
        else:
            solute_mols.add(mn)

    # Prepare per-solute-molecule output writers + cumulative position vectors
    # For each solute molecule, we compute dipole: μ = Σ q_i * r_i
    solute_mol_labels = {}
    for mn in sorted(solute_mols):
        alist = mol_atoms[mn]
        label = get_molecule_label(st, mn, [a['atom'] for a in alist])
        # De-duplicate: if multiple molecules have same formula, number them
        base_label = label
        counter = 1
        while label in solute_mol_labels.values():
            label = f'{base_label}_{counter}'
            counter += 1
        solute_mol_labels[mn] = label

    print(f'   Solute molecules: {len(solute_mols)}')
    for mn, lbl in sorted(solute_mol_labels.items()):
        print(f'      M{mn}: {lbl} ({len(mol_atoms[mn])} atoms)')

    # Open per-molecule CSV writers
    per_mol_writers = {}
    per_mol_files = {}
    for mn, lbl in solute_mol_labels.items():
        fpath = os.path.join(outdir, f'dipole_{lbl}.csv')
        f = open(fpath, 'w', newline='')
        per_mol_files[mn] = f
        w = csv.writer(f)
        w.writerow(['Time_ps', 'Mu_Mag_D', 'Mu_X_D', 'Mu_Y_D', 'Mu_Z_D'])
        per_mol_writers[mn] = w

    # Total dipole writer
    total_fpath = os.path.join(outdir, 'dipole_total.csv')
    total_f = open(total_fpath, 'w', newline='')
    total_w = csv.writer(total_f)
    total_w.writerow(['Time_ps', 'Mu_Mag_D', 'Mu_X_D', 'Mu_Y_D', 'Mu_Z_D'])

    # Process frames
    for i, fi in enumerate(frame_indices):
        frame = tr[fi]
        pos = frame.pos()
        box = frame.box
        t = frame.time

        # Total system dipole
        total_mu = np.zeros(3)
        for a in atoms_info:
            total_mu += a['charge'] * (pos[a['idx']] * E_TO_DEBYE)

        total_mag = np.sqrt(np.sum(total_mu**2))
        total_w.writerow([f'{t:.3f}', f'{total_mag:.4f}',
                          f'{total_mu[0]:.4f}', f'{total_mu[1]:.4f}', f'{total_mu[2]:.4f}'])

        # Per-molecule dipole (use centroid as reference)
        for mn, lbl in solute_mol_labels.items():
            mol_idx_list = [a['idx'] for a in mol_atoms[mn]]
            charges = np.array([atoms_info[idx2]['charge'] for idx2 in mol_idx_list])
            mol_pos = pos[mol_idx_list]
            centroid = mol_pos.mean(axis=0)

            mu = np.zeros(3)
            for j, aidx in enumerate(mol_idx_list):
                r = pos[aidx] - centroid
                # Minimal image w.r.t. centroid
                for d in range(3):
                    r[d] -= box[d][d] * round(r[d] / box[d][d])
                mu += charges[j] * r * E_TO_DEBYE

            mag = np.sqrt(np.sum(mu**2))
            w = per_mol_writers[mn]
            w.writerow([f'{t:.3f}', f'{mag:.4f}',
                        f'{mu[0]:.4f}', f'{mu[1]:.4f}', f'{mu[2]:.4f}'])

        if i % max(1, n_frames // 10) == 0:
            print(f'   Frame {i}/{n_frames}  t={t:.1f} ps  μ_total={total_mag:.2f} D')

    # Close files
    for f in per_mol_files.values():
        f.close()
    total_f.close()

    # Stats
    with open(total_fpath) as f:
        reader = csv.DictReader(f)
        mu_mags = [float(row['Mu_Mag_D']) for row in reader]
    avg_mu = np.mean(mu_mags)
    std_mu = np.std(mu_mags)
    print(f'\n   Total dipole: {avg_mu:.2f} ± {std_mu:.2f} D')
    print(f'   Range: [{np.min(mu_mags):.2f}, {np.max(mu_mags):.2f}] D')

    n_files = len(per_mol_files) + 1
    print(f'\n✅ {n_files} dipole CSV file(s) saved to {outdir}/')


if __name__ == '__main__':
    main()
