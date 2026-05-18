#!/usr/bin/env python3
"""
water_shell_fast.py — Vectorized Water Shell Classification for Large Systems
==============================================================================
Replaces the O(water × solute) Python loop with fully vectorized numpy
broadcasting. 100-1000× faster for systems >5000 atoms.

Algorithm: per frame, compute all water_O-solute distances in one
(water, solute, 3) broadcast operation → argmin → classify into shells.

Usage:
  $SCHRODINGER/run python3 water_shell_fast.py <cms> <trj> <outdir>
"""

import sys, os, csv
import numpy as np
from schrodinger.application.desmond.packages import traj, topo


def main():
    if len(sys.argv) < 4:
        print("Usage: water_shell_fast.py <cms> <trj> <outdir> [--stride N] [--max-frames N]")
        sys.exit(1)

    cms_file = sys.argv[1]
    trj_dir  = sys.argv[2]
    outdir   = sys.argv[3]

    stride     = 10
    max_frames = 500
    i = 4
    while i < len(sys.argv):
        if sys.argv[i] == '--stride':
            stride = int(sys.argv[i+1]); i += 2
        elif sys.argv[i] == '--max-frames':
            max_frames = int(sys.argv[i+1]); i += 2
        else:
            i += 1

    os.makedirs(outdir, exist_ok=True)

    # Shell definitions
    shells = [
        ('Bound_1st',   0.0,  3.5),
        ('Second',      3.5,  5.0),
        ('Free',        5.0, 1e10),
    ]

    # Load
    print("📊 Water Shell Analysis (vectorized)")
    msys_model, cms_model = topo.read_cms(cms_file)
    st = cms_model
    tr = traj.read_traj(trj_dir)

    n_total = len(tr)
    step = max(1, n_total // max_frames)
    if stride > 1:
        step = stride
    frame_indices = list(range(0, n_total, step))
    n_frames = len(frame_indices)
    print(f"   Frames: {n_frames} (stride={step}, total={n_total})")

    # Classify atoms
    solute_aids = list(cms_model.select_atom('solute'))
    water_aids  = list(cms_model.select_atom('water'))

    # Get water oxygen indices (0-based)
    water_o_indices = []
    for a in water_aids:
        atom = cms_model.atom[a]
        if atom.element == 'O':
            water_o_indices.append(a)

    solute_indices = list(solute_aids)  # 0-based

    n_water = len(water_o_indices)
    n_solute = len(solute_indices)
    total_water = n_water
    print(f"   Water O atoms: {n_water}")
    print(f"   Solute atoms:  {n_solute}")

    # Pre-convert to numpy arrays for speed
    water_o_arr = np.array(water_o_indices, dtype=int)
    solute_arr  = np.array(solute_indices, dtype=int)

    # Output CSV
    csv_path = os.path.join(outdir, 'solute_water_shells.csv')
    shell_names = [s[0] for s in shells]

    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Frame', 'Time_ps', 'Total_Water'] + shell_names)

        for fi_count, fi in enumerate(frame_indices):
            if fi_count % max(1, n_frames // 5) == 0:
                print(f"      Frame {fi}/{n_total}  ({100*(fi_count+1)//n_frames}%)", flush=True)

            frame = tr[fi]
            all_pos = frame.pos()     # (N_atoms, 3)
            box = frame.box           # 3×3

            # ── Vectorized distance computation ──
            water_pos = all_pos[water_o_arr]      # (n_water, 3)
            solute_pos = all_pos[solute_arr]       # (n_solute, 3)

            # Broadcast: diff[i,j,d] = water_pos[i,d] - solute_pos[j,d]
            diff = water_pos[:, np.newaxis, :] - solute_pos[np.newaxis, :, :]  # (n_water, n_solute, 3)

            # PBC correction (vectorized)
            for d in range(3):
                L = box[d][d]
                if L > 0:
                    diff[:, :, d] -= L * np.round(diff[:, :, d] / L)

            # Squared distances → min per water
            dist2 = np.sum(diff**2, axis=2)          # (n_water, n_solute)
            min_d = np.sqrt(np.min(dist2, axis=1))   # (n_water,)

            # Classify into shells (vectorized)
            counts = [0, 0, 0]
            counts[0] = int(np.sum(min_d < 3.5))
            counts[1] = int(np.sum((min_d >= 3.5) & (min_d < 5.0)))
            counts[2] = int(np.sum(min_d >= 5.0))

            writer.writerow([fi+1, f'{frame.time:.3f}', total_water] + counts)

    print(f"   DONE: {n_frames} frames processed")
    print(f"   ✓ {csv_path}")

    # Stats
    all_data = np.genfromtxt(csv_path, delimiter=',', skip_header=1, usecols=(3,4,5))
    for si, (name, lo, hi) in enumerate(shells):
        avg = all_data[:, si].mean()
        print(f"   {name:>12s} ({lo:.0f}-{hi:.0f}Å): {avg:.1f} avg")

    print(f"\n✅ Water shell analysis complete.")


if __name__ == '__main__':
    main()
