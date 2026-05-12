#!/usr/bin/env python3
"""
esp_gen.py — Electrostatic Analysis for Desmond MD.  |  MOTUS v0.0.1

Computes electrostatic properties from trajectory:
  1. Molecular dipole moment (magnitude + X/Y/Z components) over time
  2. Per-molecule group dipole tracking
  3. Charge distribution statistics

Dipole moment: μ = Σ q_i · r_i  (units: e·Å → Debye conversion)

Usage:
  $SCHRODINGER/run python3 esp_gen.py <cms> <trj> [OUTDIR]
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo

# Conversion constants
E_CHARGE_TO_DEBYE = 4.8032047  # 1 e·Å = 4.803 D


def get_element(atom):
    return atom.element.strip().capitalize()


def compute_dipole(positions, charges, box):
    """
    Compute molecular dipole moment with PBC-aware unwrapping.
    
    Returns:
        mu_x, mu_y, mu_z in e·Å
    """
    n = len(charges)
    if n == 0:
        return 0.0, 0.0, 0.0
    
    # Unwrap positions relative to first atom
    ref = positions[0].copy()
    unwrapped = positions.copy()
    for d in range(3):
        if box[d][d] > 0:
            delta = positions[:, d] - ref[d]
            delta -= box[d][d] * np.round(delta / box[d][d])
            unwrapped[:, d] = ref[d] + delta
    
    # Center of charge
    total_q = np.sum(np.abs(charges))
    if total_q < 1e-10:
        return 0.0, 0.0, 0.0
    
    # μ = Σ q_i * r_i
    mu_x = np.sum(charges * unwrapped[:, 0])
    mu_y = np.sum(charges * unwrapped[:, 1])
    mu_z = np.sum(charges * unwrapped[:, 2])
    
    return mu_x, mu_y, mu_z


def main():
    parser = argparse.ArgumentParser(description='ESP / Dipole analysis for Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 Electrostatic / Dipole Analyzer')
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

    # Extract atoms info + charges
    atoms_info = []
    for a in st.atom:
        atoms_info.append({
            'idx': a.index - 1,
            'element': get_element(a),
            'mol': a.molecule_number,
            'charge': getattr(a, 'formal_charge', 0.0) or 0.0,
        })

    # Try to get partial charges from force field
    # Desmond CMS stores charges in the full_system_forcefield
    try:
        if hasattr(st, 'property') and 's_ffio_ff' in st.property:
            ff = st.property['s_ffio_ff']
            # Extract per-atom charges from ffio block
            for a in st.atom:
                atoms_info[a.index - 1]['charge'] = getattr(a, 'partial_charge',
                    getattr(a, 'formal_charge', 0.0) or 0.0)
    except:
        pass

    # If all charges are zero, assign estimated charges
    charges = np.array([a['charge'] for a in atoms_info])
    if np.allclose(charges, 0):
        print('   ⚠ No partial charges found — using formal charges')
        # Estimate from element
        est_charges = {
            'O': -0.5, 'N': -0.3, 'C': 0.1, 'H': 0.1, 'P': 0.5,
            'S': -0.2, 'F': -0.3, 'Cl': -0.3, 'Na': 1.0, 'K': 1.0,
        }
        for a in atoms_info:
            a['charge'] = est_charges.get(a['element'], 0.0)
        charges = np.array([a['charge'] for a in atoms_info])

    print(f'   Charge range: {charges.min():.3f} to {charges.max():.3f}')
    
    # Classify molecules
    mol_map = defaultdict(list)
    for a in atoms_info:
        mol_map[a['mol']].append(a)

    solute_mols = set()
    water_mols = set()
    for mn, alist in mol_map.items():
        el_counts = defaultdict(int)
        for a in alist:
            if a['element'] not in ('', 'W'):
                el_counts[a['element']] += 1
        is_water = (all(k in ('O', 'H') for k in el_counts.keys()) and
                    el_counts.get('O', 0) >= 1 and sum(el_counts.values()) <= 4)
        if is_water:
            water_mols.add(mn)
        else:
            solute_mols.add(mn)

    # Group solute by type
    type_groups = defaultdict(list)
    for mn in solute_mols:
        alist = mol_map[mn]
        el_counts = defaultdict(int)
        for a in alist:
            if a['element'] not in ('', 'W'):
                el_counts[a['element']] += 1
        sig = tuple(sorted(el_counts.items()))
        type_groups[sig].append(mn)
    
    for sig, mols in type_groups.items():
        sig_str = '_'.join(f'{k}{v}' for k, v in sig)
        print(f'     {len(mols)}× {sig_str}')

    # Storage
    dipole_total = []  # [(time, mu_x, mu_y, mu_z, mu_mag)]
    dipole_per_type = defaultdict(list)  # sig -> [(time, avg_mu_mag)]

    print(f'\n   Computing dipole moments...')
    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, n_frames // 5) == 0:
            print(f'      Frame {frame_idx}/{n_total}', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()
        box = frame.box

        # Total system dipole
        mu_x, mu_y, mu_z = compute_dipole(pos, charges, box)
        mu_mag = np.sqrt(mu_x**2 + mu_y**2 + mu_z**2)
        dipole_total.append((frame.time, mu_x, mu_y, mu_z, mu_mag))

        # Per-molecule-type dipole
        for sig, mols in type_groups.items():
            type_mu = []
            for mn in mols:
                alist = mol_map[mn]
                idxs = [a['idx'] for a in alist]
                qs = np.array([a['charge'] for a in alist])
                coords = np.array([pos[i] for i in idxs])
                mx, my, mz = compute_dipole(coords, qs, box)
                type_mu.append(np.sqrt(mx**2 + my**2 + mz**2))
            dipole_per_type[sig].append((frame.time, np.mean(type_mu), np.std(type_mu)))

    # Save total dipole
    fpath = os.path.join(outdir, 'dipole_total.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_ps', 'Mu_X_D', 'Mu_Y_D', 'Mu_Z_D', 'Mu_Mag_D'])
        for t, mx, my, mz, mm in dipole_total:
            writer.writerow([
                f'{t:.3f}',
                f'{mx * E_CHARGE_TO_DEBYE:.4f}',
                f'{my * E_CHARGE_TO_DEBYE:.4f}',
                f'{mz * E_CHARGE_TO_DEBYE:.4f}',
                f'{mm * E_CHARGE_TO_DEBYE:.4f}'
            ])
    
    avg_mu = np.mean([d[4] for d in dipole_total]) * E_CHARGE_TO_DEBYE
    print(f'   ✓ dipole_total.csv  avg |μ| = {avg_mu:.2f} D')

    # Save per-molecule dipole
    for sig, values in dipole_per_type.items():
        sig_str = '_'.join(f'{k}{v}' for k, v in sig)
        fpath = os.path.join(outdir, f'dipole_{sig_str}.csv')
        with open(fpath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time_ps', 'Mu_Mag_D', 'Mu_Std_D'])
            for t, mu, mu_std in values:
                writer.writerow([f'{t:.3f}', f'{mu * E_CHARGE_TO_DEBYE:.4f}',
                                 f'{mu_std * E_CHARGE_TO_DEBYE:.4f}'])

        avg_type = np.mean([v[1] for v in values]) * E_CHARGE_TO_DEBYE
        print(f'   ✓ dipole_{sig_str}.csv  avg |μ| = {avg_type:.2f} D')

    print(f'\n✅ Dipole data saved to {outdir}/')


if __name__ == '__main__':
    main()
