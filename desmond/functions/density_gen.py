#!/usr/bin/env python3
"""
density_gen.py — 1D/2D Density Cross-Section Analysis for Desmond MD.  |  MOTUS v0.0.1

Computes spatial density distributions from trajectory data:
  1. 1D density profile along X, Y, Z axes (slab density)
  2. 2D density map projected onto XY, XZ, YZ planes
  3. Auto-detects selections: water, solute, all, or custom ASL

Usage:
  $SCHRODINGER/run python3 density_gen.py <cms_file> <trj_dir> [OUTDIR]
  $SCHRODINGER/run python3 density_gen.py system-out.cms system_trj/ analysis/ --bins 100
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo


def compute_1d_density(frame_positions, atom_indices, box, bins=100, axis=2):
    """
    Compute 1D density profile along specified axis.

    Args:
        frame_positions: all positions for this frame (N_atoms x 3)
        atom_indices: list of atom indices to include (0-based)
        box: box vectors
        bins: number of bins along axis
        axis: 0=X, 1=Y, 2=Z

    Returns:
        bin_centers, density_profile (normalized to average=1)
    """
    axis_len = box[axis][axis]
    positions = frame_positions[atom_indices, axis]
    
    # Apply PBC: wrap into [0, axis_len)
    positions = positions % axis_len
    
    hist, edges = np.histogram(positions, bins=bins, range=(0, axis_len))
    bin_centers = (edges[:-1] + edges[1:]) / 2
    
    # Normalize: divide by bin volume (area × bin_width)
    area = 1.0
    for d in range(3):
        if d != axis:
            area *= box[d][d]
    bin_volume = area * (axis_len / bins)
    density = hist / bin_volume  # atoms/Å³
    
    # Normalize to average = 1
    if density.mean() > 0:
        density = density / density.mean()
    
    return bin_centers, density


def compute_2d_density(frame_positions, atom_indices, box, bins=80, axes=(0, 1)):
    """
    Compute 2D density histogram projected onto a plane.

    Args:
        frame_positions: all positions (N_atoms x 3)
        atom_indices: list of atom indices (0-based)
        box: box vectors
        bins: number of bins per dimension
        axes: tuple (ax1, ax2) — e.g. (0,1) = XY plane

    Returns:
        x_edges, y_edges, density_2d (normalized)
    """
    a1, a2 = axes
    L1 = box[a1][a1]
    L2 = box[a2][a2]
    
    positions = frame_positions[atom_indices]
    x = positions[:, a1] % L1
    y = positions[:, a2] % L2
    
    hist, x_edges, y_edges = np.histogram2d(x, y, bins=bins, range=[[0, L1], [0, L2]])
    
    # Normalize to average = 1
    if hist.mean() > 0:
        hist = hist / hist.mean()
    
    return x_edges, y_edges, hist


def get_element(atom):
    """Map element symbol to standard form."""
    return atom.element.strip().capitalize()


def main():
    parser = argparse.ArgumentParser(description='Density cross-section analysis for Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride')
    parser.add_argument('--bins', type=int, default=100, help='Number of bins per dimension')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames to process')
    parser.add_argument('--selections', nargs='*', default=None,
                        help='Atom selections: water, solute, all (default: water solute all)')
    parser.add_argument('--2d', action='store_true', default=True, help='Compute 2D density maps')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    if args.selections is None:
        args.selections = ['water', 'solute', 'all']
    do_2d = getattr(args, '2d', True)  # argparse stores as '2d' internally

    print(f'📊 Density Cross-Section Generator')
    print(f'   bins={args.bins}  stride={args.stride}  max_frames={args.max_frames}')
    print(f'   selections: {args.selections}')

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
    print(f'   Frames: {n_frames} (stride={stride}, total={n_total})')

    # System info
    atoms = []
    for a in st.atom:
        atoms.append({
            'idx': a.index - 1,  # 0-based for pos()
            'element': get_element(a),
            'mol': a.molecule_number,
        })
    n_atoms = len(atoms)
    print(f'   Atoms: {n_atoms}')

    # Classify molecules
    mol_map = defaultdict(list)
    for a in atoms:
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

    # Build selection indices
    sel_indices = {}
    for sel_name in args.selections:
        if sel_name == 'all':
            sel_indices['all'] = list(range(n_atoms))
        elif sel_name == 'water':
            sel_indices['water'] = [a['idx'] for a in atoms if a['mol'] in water_mols]
        elif sel_name == 'solute':
            sel_indices['solute'] = [a['idx'] for a in atoms if a['mol'] in solute_mols]
        else:
            # Try ASL
            try:
                aids = st.select_atom(sel_name)
                sel_indices[sel_name] = [i - 1 for i in aids]
            except:
                print(f'   ⚠ Unknown selection: {sel_name}')
    
    for name, idxs in sel_indices.items():
        print(f'   {name}: {len(idxs)} atoms')

    # Collect density data across frames
    axis_names = ['X', 'Y', 'Z']
    
    # Accumulators for 1D profiles
    for sel_name in sel_indices.keys():
        for axis in range(3):
            key = f'density_1d_{sel_name}_{axis_names[axis]}'
            fpath = os.path.join(outdir, f'{key}.csv')
            # We'll accumulate histograms and write at the end

    print(f'\n   Computing density profiles...')
    
    # Per-frame accumulators
    total_hist_1d = {}  # key -> np.array
    total_hist_2d = {}  # key -> np.array
    total_box = np.zeros((3, 3))
    n_frames_processed = 0

    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, n_frames // 5) == 0 or fi == n_frames - 1:
            print(f'      Frame {frame_idx}/{n_total}  ({100*(fi+1)//n_frames}%)', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()  # N×3
        box = frame.box
        total_box += box
        n_frames_processed += 1

        for sel_name, sel_idxs in sel_indices.items():
            if not sel_idxs:
                continue
            
            # 1D profiles along X, Y, Z
            for axis in range(3):
                key = f'1d_{sel_name}_{axis_names[axis]}'
                centers, density = compute_1d_density(pos, sel_idxs, box, bins=args.bins, axis=axis)
                if key not in total_hist_1d:
                    total_hist_1d[key] = np.zeros(args.bins)
                total_hist_1d[key] += density

            # 2D maps (XY, XZ, YZ)
            if do_2d:
                for (a1, a2), plane_name in [((0, 1), 'XY'), ((0, 2), 'XZ'), ((1, 2), 'YZ')]:
                    key = f'2d_{sel_name}_{plane_name}'
                    x_edges, y_edges, hist = compute_2d_density(pos, sel_idxs, box, bins=args.bins, axes=(a1, a2))
                    if key not in total_hist_2d:
                        total_hist_2d[key] = np.zeros((args.bins, args.bins))
                    total_hist_2d[key] += hist

    # Average and save
    print(f'\n   Saving density data...')
    avg_box = total_box / n_frames_processed

    # Save 1D profiles
    for key in sorted(total_hist_1d.keys()):
        avg_density = total_hist_1d[key] / n_frames_processed
        # Generate bin centers
        parts = key.split('_')
        axis_name = parts[-1]  # X, Y, Z
        axis_idx = axis_names.index(axis_name)
        axis_len = avg_box[axis_idx][axis_idx]
        bin_centers = np.linspace(0, axis_len, args.bins)
        
        fname = f'density_{key}.csv'
        fpath = os.path.join(outdir, fname)
        with open(fpath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([f'{axis_name}_A', 'relative_density'])
            for i in range(args.bins):
                writer.writerow([f'{bin_centers[i]:.4f}', f'{avg_density[i]:.6f}'])
        print(f'   ✓ {fname}')

    # Save 2D maps
    if do_2d:
        for key in sorted(total_hist_2d.keys()):
            avg_hist = total_hist_2d[key] / n_frames_processed
            fname = f'density_{key}.csv'
            fpath = os.path.join(outdir, fname)
            np.savetxt(fpath, avg_hist, delimiter=',', header=f'# 2D density map ({key})', comments='')
            print(f'   ✓ {fname}')

    print(f'\n✅ Density data saved to {outdir}/')


if __name__ == '__main__':
    main()
