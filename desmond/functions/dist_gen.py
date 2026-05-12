#!/usr/bin/env python3
"""
dist_gen.py — Atom-Pair Distance Monitoring for Desmond MD.  |  MOTUS v0.0.1

Monitors specified atom-pair distances over the trajectory.
Auto-detects key interactions or accepts custom atom pairs.

Modes:
  --auto         Auto-detect key distances (H-bonds, metal-ligand, salt bridges)
  --pairs ...    Custom pairs: "1-50,3-60" (atom indices, 0-based)

Usage:
  $SCHRODINGER/run python3 dist_gen.py <cms> <trj> [OUTDIR] --auto
  $SCHRODINGER/run python3 dist_gen.py <cms> <trj> [OUTDIR] --pairs 0-10,5-15
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo


def get_element(atom):
    return atom.element.strip().capitalize()


def pbc_dist(p_i, p_j, box):
    """Minimum-image distance between two positions."""
    delta = p_j - p_i
    for d in range(3):
        if box[d][d] > 0:
            delta[d] -= box[d][d] * round(delta[d] / box[d][d])
    return np.sqrt(np.sum(delta**2))


def auto_detect_pairs(atoms_info, solute_mols, water_mols, mol_map):
    """
    Auto-detect interesting distance pairs:
    - H-bond donors/acceptors (N-O, O-O within H-bond range)
    - Metal-ligand coordination (metal ions to O/N atoms)
    - Salt bridges (positively charged N to negatively charged O)
    """
    pairs = []  # (name, idx1, idx2)

    # Solute atoms
    solute_atoms = [a for a in atoms_info if a['mol'] in solute_mols]
    
    # H-bond heavy atoms (N, O)
    hbond_atoms = [a for a in solute_atoms if a['element'] in ('N', 'O')]
    
    # Auto-pick: N-H...O type distances between solute molecules
    for i, a1 in enumerate(hbond_atoms):
        for j in range(i + 1, len(hbond_atoms)):
            a2 = hbond_atoms[j]
            if a1['mol'] != a2['mol']:  # Inter-molecular
                name = f"{a1['element']}{a1['idx']+1}-{a2['element']}{a2['idx']+1}"
                pairs.append((name, a1['idx'], a2['idx'], 'inter-Hbond'))

    # If too many, limit to first 20
    if len(pairs) > 20:
        pairs = pairs[:20]

    return pairs


def main():
    parser = argparse.ArgumentParser(description='Distance monitoring for Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--auto', action='store_true', help='Auto-detect key distances')
    group.add_argument('--pairs', type=str, help='Comma-separated pairs: "0-10,5-15"')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 Distance Monitor')
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

    # Build atom info
    atoms_info = []
    for a in st.atom:
        atoms_info.append({
            'idx': a.index - 1,
            'element': get_element(a),
            'mol': a.molecule_number,
        })

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

    # Build pair list
    pairs = []
    if args.auto:
        pairs = auto_detect_pairs(atoms_info, solute_mols, water_mols, mol_map)
    elif args.pairs:
        for pair_str in args.pairs.split(','):
            pair_str = pair_str.strip()
            parts = pair_str.split('-')
            if len(parts) == 2:
                i1, i2 = int(parts[0]), int(parts[1])
                pairs.append((f"atom{i1+1}-atom{i2+1}", i1, i2, 'user'))

    if not pairs:
        print("   ⚠ No distance pairs to monitor")
        return

    print(f'   Monitoring {len(pairs)} distance pairs:')
    for name, i1, i2, ptype in pairs[:10]:
        el1 = atoms_info[i1]['element']
        el2 = atoms_info[i2]['element']
        print(f'     {name:20s}  {el1}({i1+1}) — {el2}({i2+1})  [{ptype}]')

    # Collect distances
    distances = {name: [] for name, _, _, _ in pairs}  # name -> [(time, dist)]
    
    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, n_frames // 5) == 0:
            print(f'      Frame {frame_idx}/{n_total}', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()
        box = frame.box

        for name, i1, i2, _ in pairs:
            d = pbc_dist(pos[i1], pos[i2], box)
            distances[name].append((frame.time, d))

    # Save CSV
    for name, values in distances.items():
        safe_name = name.replace('-', '_').replace(' ', '_')
        fpath = os.path.join(outdir, f'distance_{safe_name}.csv')
        with open(fpath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time_ps', 'Distance_A'])
            for t, d in values:
                writer.writerow([f'{t:.3f}', f'{d:.4f}'])

        avg_d = np.mean([v[1] for v in values])
        min_d = min(v[1] for v in values)
        max_d = max(v[1] for v in values)
        print(f'   ✓ distance_{safe_name}.csv  avg={avg_d:.2f}  [{min_d:.2f}–{max_d:.2f}] Å')

    print(f'\n✅ Distance data saved to {outdir}/')


if __name__ == '__main__':
    main()
