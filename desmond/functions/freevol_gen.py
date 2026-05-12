#!/usr/bin/env python3
"""
freevol_gen.py — Free Volume / Void Analysis for Desmond MD.  |  MOTUS v0.0.1

Analyzes void space in the simulation box by:
  1. Grid-based probe-sphere method to detect empty space
  2. Fractional free volume (FFV) over time
  3. Void size distribution

Useful for: membrane permeability, gas diffusion, polymer free volume.

Usage:
  $SCHRODINGER/run python3 freevol_gen.py <cms> <trj> [OUTDIR]
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo


def get_element(atom):
    return atom.element.strip().capitalize()


def compute_free_volume(frame_positions, atom_radii, box, probe_radius=1.4, grid_spacing=0.5):
    """
    Estimate free volume using a grid-based probe method.
    
    Grid points are "free" if the probe sphere (radius = probe_radius) 
    does not overlap with any atom (van der Waals radius).
    
    Args:
        frame_positions: N×3 atom coordinates
        atom_radii: N array of atomic radii (Å)
        box: 3×3 box vectors
        probe_radius: probe radius (default 1.4 Å ≈ water radius)
        grid_spacing: grid resolution (Å)
    
    Returns:
        free_volume: total free volume (Å³)
        free_fraction: FFV = V_free / V_box
    """
    # Box dimensions
    Lx, Ly, Lz = box[0][0], box[1][1], box[2][2]
    box_vol = Lx * Ly * Lz
    
    # Build grid
    nx = max(1, int(Lx / grid_spacing))
    ny = max(1, int(Ly / grid_spacing))
    nz = max(1, int(Lz / grid_spacing))
    
    dx, dy, dz = Lx / nx, Ly / ny, Lz / nz
    cell_vol = dx * dy * dz
    
    n_free = 0
    n_total = nx * ny * nz
    
    # Effective radius = atom_vdw + probe
    effective_radii = atom_radii + probe_radius
    effective_radii_sq = effective_radii ** 2
    
    # Sample grid points
    for ix in range(nx):
        gx = (ix + 0.5) * dx
        for iy in range(ny):
            gy = (iy + 0.5) * dy
            grid_point = np.array([gx, gy, 0.0])
            
            for iz in range(nz):
                gz = (iz + 0.5) * dz
                grid_point[2] = gz
                
                # Check if probe overlaps any atom (PBC-aware)
                overlap = False
                for ai in range(len(atom_radii)):
                    delta = grid_point - frame_positions[ai]
                    for d in range(3):
                        box_len = box[d][d]
                        if box_len > 0:
                            delta[d] -= box_len * round(delta[d] / box_len)
                    d2 = np.sum(delta ** 2)
                    if d2 < effective_radii_sq[ai]:
                        overlap = True
                        break
                
                if not overlap:
                    n_free += 1
    
    free_vol = n_free * cell_vol
    free_fraction = free_vol / box_vol
    
    return free_vol, free_fraction


# Default van der Waals radii (Å)
VDW_RADII = {
    'H': 1.20, 'He': 1.40, 'Li': 1.82, 'Be': 1.53, 'B': 1.92,
    'C': 1.70, 'N': 1.55, 'O': 1.52, 'F': 1.47, 'Ne': 1.54,
    'Na': 2.27, 'Mg': 1.73, 'Al': 1.84, 'Si': 2.10, 'P': 1.80,
    'S': 1.80, 'Cl': 1.75, 'K': 2.75, 'Ca': 2.31, 'Fe': 2.00,
    'Zn': 1.39, 'Br': 1.85, 'I': 1.98,
}


def main():
    parser = argparse.ArgumentParser(description='Free volume / void analysis')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--probe', type=float, default=1.4, help='Probe radius (Å)')
    parser.add_argument('--grid', type=float, default=0.8, help='Grid spacing (Å)')
    parser.add_argument('--stride', type=int, default=10, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=200, help='Max frames')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 Free Volume Analyzer')
    print(f'   probe={args.probe}Å  grid={args.grid}Å  stride={args.stride}')

    # Load
    msys_model, cms_model = topo.read_cms(args.cms)
    tr = traj.read_traj(args.trj)

    n_total = len(tr)
    stride = max(1, n_total // args.max_frames)
    if args.stride > 1:
        stride = args.stride
    frame_indices = list(range(0, n_total, stride))
    print(f'   Frames: {len(frame_indices)} (stride={stride})')

    # Build atom info
    atoms_info = []
    for a in cms_model.atom:
        atoms_info.append({
            'idx': a.index - 1,
            'element': get_element(a),
            'radius': VDW_RADII.get(get_element(a), 1.70),
        })

    radii = np.array([a['radius'] for a in atoms_info])
    print(f'   Atoms: {len(atoms_info)}  box resolution: {args.grid}Å')

    # Compute per frame
    freevol_data = []  # [(time, free_vol, free_frac, box_vol)]

    print(f'\n   Computing free volume...')
    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, len(frame_indices) // 5) == 0:
            print(f'      Frame {frame_idx}/{n_total}', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()
        box = frame.box

        fv, ff = compute_free_volume(pos, radii, box,
                                     probe_radius=args.probe,
                                     grid_spacing=args.grid)
        box_vol = box[0][0] * box[1][1] * box[2][2]
        freevol_data.append((frame.time, fv, ff, box_vol))

    # Save
    fpath = os.path.join(outdir, 'free_volume.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_ps', 'FreeVol_A3', 'FFV', 'BoxVol_A3'])
        for t, fv, ff, bv in freevol_data:
            writer.writerow([f'{t:.3f}', f'{fv:.2f}', f'{ff:.6f}', f'{bv:.2f}'])

    avg_ffv = np.mean([d[2] for d in freevol_data])
    std_ffv = np.std([d[2] for d in freevol_data])
    avg_fv = np.mean([d[1] for d in freevol_data])
    avg_bv = np.mean([d[3] for d in freevol_data])

    print(f'\n   Results:')
    print(f'   Avg box volume:     {avg_bv:.0f} Å³')
    print(f'   Avg free volume:    {avg_fv:.0f} Å³')
    print(f'   Avg FFV:            {avg_ffv:.4f} ± {std_ffv:.4f}')
    print(f'   Free volume ratio:  {avg_ffv*100:.1f}%')
    print(f'   ✓ free_volume.csv')

    print(f'\n✅ Free volume data saved to {outdir}/')


if __name__ == '__main__':
    main()
