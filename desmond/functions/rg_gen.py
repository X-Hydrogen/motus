#!/usr/bin/env python3
"""
rg_gen.py — Radius of Gyration (Rg) analysis for Desmond MD.  |  MOTUS v0.0.1

Computes Rg for solute molecules over the trajectory:
  Rg = sqrt( Σ m_i * |r_i - r_cm|² / Σ m_i )

Useful for characterizing molecular compactness, folding/unfolding, and aggregation.

Usage:
  $SCHRODINGER/run python3 rg_gen.py <cms_file> <trj_dir> [OUTDIR]
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo


# Atomic masses (g/mol) — common elements
ATOMIC_MASS = {
    'H': 1.008, 'He': 4.003, 'Li': 6.941, 'Be': 9.012, 'B': 10.811,
    'C': 12.011, 'N': 14.007, 'O': 15.999, 'F': 18.998, 'Ne': 20.180,
    'Na': 22.990, 'Mg': 24.305, 'Al': 26.982, 'Si': 28.086, 'P': 30.974,
    'S': 32.065, 'Cl': 35.453, 'K': 39.098, 'Ca': 40.078, 'Fe': 55.845,
    'Zn': 65.380, 'Br': 79.904, 'I': 126.904,
}


def get_element(atom):
    return atom.element.strip().capitalize()


def compute_rg(positions, masses, box):
    """Compute radius of gyration with PBC-aware center of mass.

    Args:
        positions: N×3 array of coordinates
        masses: length-N array of atomic masses
        box: 3×3 box vectors

    Returns:
        Rg in Å
    """
    n = len(masses)
    if n == 0:
        return 0.0

    total_mass = np.sum(masses)

    # PBC-aware center of mass using angle method
    # Use reference atom (first) and unwrap relative to it
    ref = positions[0].copy()
    unwrapped = positions.copy()
    for d in range(3):
        if box[d][d] > 0:
            delta = positions[:, d] - ref[d]
            delta -= box[d][d] * np.round(delta / box[d][d])
            unwrapped[:, d] = ref[d] + delta

    # Center of mass
    com = np.sum(unwrapped * masses[:, np.newaxis], axis=0) / total_mass

    # Rg² = Σ m_i * |r_i - com|² / Σ m_i
    diff = unwrapped - com
    rg_sq = np.sum(masses * np.sum(diff**2, axis=1)) / total_mass

    return np.sqrt(rg_sq)


def main():
    parser = argparse.ArgumentParser(description='Radius of Gyration analysis for Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 Radius of Gyration Generator')
    print(f'   stride={args.stride}  max_frames={args.max_frames}')

    # Load system
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

    # Classify molecules
    atoms_info = []
    for a in st.atom:
        atoms_info.append({
            'idx': a.index - 1,
            'element': get_element(a),
            'mol': a.molecule_number,
            'mass': ATOMIC_MASS.get(get_element(a), 12.0),
        })

    mol_map = defaultdict(list)
    for a in atoms_info:
        mol_map[a['mol']].append(a)

    # Identify solute molecules
    solute_mols = []
    for mn, alist in mol_map.items():
        el_counts = defaultdict(int)
        for a in alist:
            el = a['element']
            if el not in ('', 'W'):
                el_counts[el] += 1
        is_water = (all(k in ('O', 'H') for k in el_counts.keys()) and
                    el_counts.get('O', 0) >= 1 and sum(el_counts.values()) <= 4)
        if not is_water:
            solute_mols.append(mn)

    # Group solute molecules by type (atom count signature)
    type_groups = defaultdict(list)
    for mn in solute_mols:
        alist = mol_map[mn]
        el_counts = defaultdict(int)
        for a in alist:
            if a['element'] not in ('', 'W'):
                el_counts[a['element']] += 1
        sig = tuple(sorted(el_counts.items()))
        type_groups[sig].append(mn)

    print(f'   Solute molecules: {len(solute_mols)}')
    for sig, mols in type_groups.items():
        sig_str = '_'.join(f'{k}{v}' for k, v in sig)
        print(f'     {len(mols)}× {sig_str}')

    # Compute Rg per frame
    print(f'\n   Computing Rg...')

    # Per-molecule-type Rg (average over identical molecules)
    mol_type_rg = defaultdict(list)  # sig -> [(frame_time, avg_rg)]

    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, n_frames // 5) == 0 or fi == n_frames - 1:
            print(f'      Frame {frame_idx}/{n_total}  ({100*(fi+1)//n_frames}%)', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()
        box = frame.box
        time_ps = frame.time

        for sig, mols in type_groups.items():
            rgs = []
            for mn in mols:
                alist = mol_map[mn]
                indices = [a['idx'] for a in alist]
                masses = np.array([a['mass'] for a in alist])
                coords = np.array([pos[i] for i in indices])
                rg = compute_rg(coords, masses, box)
                rgs.append(rg)
            avg_rg = np.mean(rgs)
            mol_type_rg[sig].append((time_ps, avg_rg, np.std(rgs)))

    # Save CSV
    for sig, values in mol_type_rg.items():
        sig_str = '_'.join(f'{k}{v}' for k, v in sig)
        fpath = os.path.join(outdir, f'rg_{sig_str}.csv')
        with open(fpath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time_ps', 'Rg_A', 'Rg_std_A'])
            for t, rg, rg_std in values:
                writer.writerow([f'{t:.3f}', f'{rg:.4f}', f'{rg_std:.4f}'])

        rg_avg = np.mean([v[1] for v in values])
        rg_std_all = np.std([v[1] for v in values])
        print(f'   ✓ rg_{sig_str}.csv  avg Rg = {rg_avg:.2f} ± {rg_std_all:.2f} Å')

    print(f'\n✅ Rg data saved to {outdir}/')


if __name__ == '__main__':
    main()
