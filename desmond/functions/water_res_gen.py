#!/usr/bin/env python3
"""
water_res_gen.py — Water Residence Time Analysis for Desmond MD.  |  MOTUS v0.0.1

Computes how long water molecules stay within the first solvation shell
of the solute. Uses an intermittent survival time correlation function
S(t) = average over water molecules of whether they remain in shell.

Key outputs:
  - Residence time τ (from exponential fit to S(t))
  - Survival probability S(t) over time
  - Per-water-molecule exchange events

Usage:
  $SCHRODINGER/run python3 water_res_gen.py <cms> <trj> [OUTDIR]
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo


def get_element(atom):
    return atom.element.strip().capitalize()


def main():
    parser = argparse.ArgumentParser(description='Water residence time analysis')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--cutoff', type=float, default=3.5, help='Shell cutoff in Å')
    parser.add_argument('--stride', type=int, default=10, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 Water Residence Time Analyzer')
    print(f'   cutoff={args.cutoff}Å  stride={args.stride}')

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

    # Classify
    atoms_info = []
    for a in st.atom:
        atoms_info.append({
            'idx': a.index - 1,
            'element': get_element(a),
            'mol': a.molecule_number,
        })

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

    solute_atom_indices = [a['idx'] for a in atoms_info if a['mol'] in solute_mols]
    water_mol_list = sorted(water_mols)
    n_water = len(water_mol_list)

    # Get water oxygen index for each water molecule
    water_o_idx = {}
    for mn in water_mol_list:
        for a in mol_map[mn]:
            if a['element'] == 'O':
                water_o_idx[mn] = a['idx']
                break

    print(f'   Solute atoms: {len(solute_atom_indices)}')
    print(f'   Water molecules: {n_water}')

    # Determine which water molecules are in shell at each frame
    # in_shell[frame_idx][mol_num] = True/False
    in_shell = np.zeros((n_frames, n_water), dtype=bool)

    print(f'\n   Detecting water shell occupancy...')
    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, n_frames // 5) == 0:
            print(f'      Frame {frame_idx}/{n_total}', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()
        box = frame.box

        for wi, mn in enumerate(water_mol_list):
            o_idx = water_o_idx.get(mn)
            if o_idx is None:
                continue
            wp = pos[o_idx]

            # Find minimum distance to any solute atom
            min_d2 = float('inf')
            for si in solute_atom_indices:
                delta = wp - pos[si]
                for d in range(3):
                    if box[d][d] > 0:
                        delta[d] -= box[d][d] * round(delta[d] / box[d][d])
                d2 = np.sum(delta**2)
                if d2 < min_d2:
                    min_d2 = d2

            in_shell[fi, wi] = (min_d2**0.5 < args.cutoff)

    # Compute survival time correlation function S(t)
    # S(τ) = fraction of water initially in shell that remain continuously
    # For intermittent: allow temporary exits of up to 2 frames
    max_gap = 2  # intermittent tolerance

    max_lag = min(n_frames - 1, 200)  # correlations up to 200 frames
    s_t = np.zeros(max_lag + 1)

    # For each water, compute survival
    for wi in range(n_water):
        for t_start in range(n_frames - max_lag):
            if not in_shell[t_start, wi]:
                continue
            for tau in range(max_lag + 1):
                if t_start + tau >= n_frames:
                    break
                # Check if water is in shell at t+tau (intermittent: allow gaps ≤ max_gap)
                in_range = True
                gaps = 0
                for k in range(1, tau + 1):
                    if not in_shell[t_start + k, wi]:
                        gaps += 1
                    else:
                        gaps = 0
                    if gaps > max_gap:
                        in_range = False
                        break
                if in_range:
                    s_t[tau] += 1

    # Normalize
    s_t = s_t / s_t[0] if s_t[0] > 0 else s_t

    # Fit exponential: S(t) ≈ exp(-t/τ)
    # τ from 1/e point
    if s_t[0] > 0:
        for tau in range(1, max_lag + 1):
            if s_t[tau] < 1.0 / np.e:
                tau_e = tau
                break
        else:
            tau_e = max_lag
    else:
        tau_e = 0

    # Frame time
    frame0 = tr[frame_indices[0]]
    dt_frame = stride * (tr[1].time - tr[0].time) if len(tr) > 1 else 1.0
    tau_ps = tau_e * dt_frame
    time_axis = np.arange(max_lag + 1) * dt_frame

    print(f'\n   Results:')
    print(f'   Residence time τ (1/e): {tau_ps:.1f} ps ({tau_e} frames)')

    # Save survival curve
    fpath_s = os.path.join(outdir, 'water_residence_survival.csv')
    with open(fpath_s, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_ps', 'Survival_Probability', 'n_tracked'])
        for i in range(max_lag + 1):
            writer.writerow([f'{time_axis[i]:.3f}', f'{s_t[i]:.6f}',
                             f'{s_t[i] * s_t[0] if s_t[0] > 0 else 0:.0f}'])
    print(f'   ✓ water_residence_survival.csv')

    # Save per-frame shell occupancy count
    shell_counts = in_shell.sum(axis=1)
    fpath_c = os.path.join(outdir, 'water_residence_occupancy.csv')
    with open(fpath_c, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Frame', 'Time_ps', 'Shell_Water_Count'])
        for fi, frame_idx in enumerate(frame_indices):
            frame = tr[frame_idx]
            writer.writerow([f'{fi}', f'{frame.time:.3f}', f'{shell_counts[fi]}'])
    print(f'   ✓ water_residence_occupancy.csv')

    # Summary stats
    total_exchanges = 0
    for wi in range(n_water):
        prev = in_shell[0, wi]
        for fi in range(1, n_frames):
            curr = in_shell[fi, wi]
            if prev and not curr:
                total_exchanges += 1
            prev = curr

    avg_shell = shell_counts.mean()
    print(f'   Avg shell water: {avg_shell:.1f} ± {shell_counts.std():.1f}')
    print(f'   Total exchange events: {total_exchanges}')
    print(f'   Exchange rate: {total_exchanges / (n_frames * dt_frame / 1000):.1f} /ns')

    print(f'\n✅ Water residence data saved to {outdir}/')


if __name__ == '__main__':
    main()
