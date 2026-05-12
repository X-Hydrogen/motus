#!/usr/bin/env python3
"""
rdf_gen.py — Radial Distribution Function analysis for Desmond MD trajectories.  |  MOTUS v0.0.1

Computes three levels of RDF:
  1. Element-pair RDF  —  every element × every other element (e.g., C-O, O-O, ...)
  2. Molecule-type RDF  —  intra-molecular (same mol) vs inter-molecular (different mol)
  3. Water-shell RDF    —  bound (<3.5Å) and free (>5Å) water vs solute

Usage:
  $SCHRODINGER/run python3 rdf_gen.py <cms_file> <trj_dir> [OUTDIR]
  $SCHRODINGER/run python3 rdf_gen.py system-out.cms system_trj/ analysis/
  $SCHRODINGER/run python3 rdf_gen.py system-out.cms system_trj/ --stride 10 --bins 200

Output:
  rdf_element_*.csv       — g(r) for element pairs
  rdf_molecule_*_*.csv    — intra/inter molecular RDF
  rdf_water_*.csv          — bound/free water RDF
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond.packages import traj, topo


def compute_rdf(pairs, box_volume, n_frames, r_max=15.0, n_bins=200, box_diag=None):
    """Compute normalized radial distribution function g(r) and coordination number n(r).

    n(r) = 4πρ ∫₀ʳ r'² g(r') dr'  — cumulative number of neighbors within distance r

    Args:
        pairs: list of (distances_per_frame) arrays, one per frame
        box_volume: float, average box volume
        n_frames: int, number of frames
        r_max: max distance in Å
        n_bins: number of bins
        box_diag: average box diagonal for density normalization

    Returns:
        r_centers: bin centers
        g_r: normalized g(r) array
        n_r: coordination number array
        rho_bulk: bulk number density (pairs/Å³)
    """
    bin_edges = np.linspace(0, r_max, n_bins + 1)
    dr = bin_edges[1] - bin_edges[0]
    r_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    hist_total = np.zeros(n_bins)

    for frame_pairs in pairs:
        if len(frame_pairs) == 0:
            continue
        hist, _ = np.histogram(frame_pairs, bins=bin_edges)
        hist_total += hist

    # Normalize: g(r) = N_pairs(r) / (4π r² Δr ρ_bulk) / n_frames
    total_pairs = sum(len(p) for p in pairs)
    if total_pairs == 0:
        return r_centers, np.zeros(n_bins), np.zeros(n_bins), 0.0

    rho_bulk = total_pairs / (box_volume * n_frames)  # pairs per Å³ per frame

    g_r = np.zeros(n_bins)
    for i in range(n_bins):
        r = r_centers[i]
        shell_vol = 4.0 * np.pi * r * r * dr
        if shell_vol > 0 and rho_bulk > 0:
            g_r[i] = hist_total[i] / (shell_vol * rho_bulk * n_frames)

    # Coordination number: n(r) = 4πρ ∫₀ʳ r'² g(r') dr'
    # Cumulative trapezoidal integration
    integrand = r_centers**2 * g_r
    n_r = 4.0 * np.pi * rho_bulk * np.array([np.trapz(integrand[:i+1], r_centers[:i+1]) if i > 0 else 0.0 for i in range(n_bins)])

    return r_centers, g_r, n_r, rho_bulk


def get_element(atom):
    """Map element symbol to standard form."""
    return atom.element.strip().capitalize()


def main():
    parser = argparse.ArgumentParser(description='RDF analysis for Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride')
    parser.add_argument('--bins', type=int, default=200, help='Number of RDF bins')
    parser.add_argument('--r-max', type=float, default=15.0, help='Max RDF distance (Å)')
    parser.add_argument('--max-frames', type=int, default=500, help='Max frames')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 RDF Generator')
    print(f'   r_max={args.r_max}Å  bins={args.bins}  stride={args.stride}')

    # Load system
    msys, cms = topo.read_cms(args.cms)
    st = cms
    tr = traj.read_traj(args.trj)

    n_total = len(tr)
    stride = max(1, n_total // args.max_frames)
    if args.stride > 1:
        stride = args.stride
    frame_indices = list(range(0, n_total, stride))
    n_frames = len(frame_indices)
    print(f'   Frames: {n_frames} (stride={stride}, total={n_total})')

    # ── System classification ──
    atoms = []
    for a in st.atom:
        atoms.append({
            'idx': a.index,
            'element': get_element(a),
            'mol': a.molecule_number,
            'x': a.x, 'y': a.y, 'z': a.z,
        })
    n_atoms = len(atoms)
    print(f'   Atoms: {n_atoms}')

    # Elements present
    elements = sorted(set(a['element'] for a in atoms if a['element'] not in ('', 'W')))
    print(f'   Elements: {elements}')

    # Molecules — group by molecule number
    mol_map = defaultdict(list)
    for a in atoms:
        mol_map[a['mol']].append(a)
    # Identify unique molecule types (by atom count)
    mol_types = {}  # mol_number -> (atom_count, element_composition)
    for mn, alist in mol_map.items():
        el_counts = defaultdict(int)
        for a in alist:
            if a['element'] not in ('', 'W'):
                el_counts[a['element']] += 1
        signature = tuple(sorted(el_counts.items()))
        mol_types[mn] = (len(alist), signature)

    # Identify solute molecules (non-water, non-ion)
    solute_mols = []
    water_mols = []
    for mn, (n_at, sig) in mol_types.items():
        # Water typically 3-4 atoms, all O and H
        is_water = (1 <= n_at <= 4 and
                    all(k in ('O', 'H') for k, _ in sig) and
                    any(k == 'O' for k, _ in sig))
        if is_water:
            water_mols.append(mn)
        else:
            solute_mols.append(mn)

    print(f'   Solute molecules: {len(solute_mols)}')
    print(f'   Water molecules:   {len(water_mols)}')

    # Water shell classification: bound < 3.5Å, free > 5Å from solute
    # First pass: identify which water molecules are bound/free based on first frame
    frame0 = tr[frame_indices[0]]
    pos0 = frame0.pos()
    box0 = frame0.box

    solute_atom_indices = [a['idx'] for a in atoms if a['mol'] in solute_mols]
    water_atom_indices = [a['idx'] for a in atoms if a['mol'] in water_mols]

    # Classify each water molecule as bound or free
    bound_water_mols = set()
    free_water_mols = set()
    for wm in water_mols:
        w_atoms = [a for a in atoms if a['mol'] == wm]
        min_d2 = float('inf')
        for wa in w_atoms:
            wp = np.array(pos0[wa['idx'] - 1])
            for si in solute_atom_indices:
                sp = np.array(pos0[si - 1])
                dx, dy, dz = wp - sp
                for d in range(3):
                    if box0[d][d] > 0:
                        v = [dx, dy, dz]
                        v[d] -= box0[d][d] * round(v[d] / box0[d][d])
                        dx, dy, dz = v
                d2 = dx*dx + dy*dy + dz*dz
                if d2 < min_d2:
                    min_d2 = d2
        if min_d2**0.5 < 3.5:
            bound_water_mols.add(wm)
        elif min_d2**0.5 > 5.0:
            free_water_mols.add(wm)

    print(f'   Bound water (<3.5Å):  {len(bound_water_mols)} mols')
    print(f'   Free water (>5Å):     {len(free_water_mols)} mols')

    # ── Prepare atom index groupings ──
    element_atoms = defaultdict(list)  # "C" -> [idx1, idx2, ...]
    mol_atom_map = defaultdict(list)   # mol_num -> [idx1, idx2, ...]

    for a in atoms:
        el = a['element']
        if el not in ('', 'W'):
            element_atoms[el].append(a['idx'])
        mol_atom_map[a['mol']].append(a['idx'])

    solute_atom_set = set(solute_atom_indices)
    bound_water_atoms = [a['idx'] for a in atoms if a['mol'] in bound_water_mols]
    free_water_atoms = [a['idx'] for a in atoms if a['mol'] in free_water_mols]

    # ── Collect distances across frames ──
    print(f'\n   Collecting pairwise distances...')

    # Storage: key -> list of distance arrays per frame
    rdf_data = defaultdict(list)  # key -> list of 1D distance arrays

    def add_pair(key, dists):
        """Add distances to the data collector."""
        if key not in rdf_data:
            rdf_data[key] = []
        rdf_data[key].append(np.array(dists) if len(dists) > 0 else np.array([]))

    # 1. Element-pair RDF
    element_pairs = []
    for i, e1 in enumerate(elements):
        for e2 in elements[i:]:  # include i==i and i<j
            element_pairs.append((e1, e2))

    # 2. Molecule-type RDF
    # Classify molecule types by composition
    type_map = {}  # mol_type_key -> list of molecule numbers
    for mn in solute_mols:
        sig = mol_types[mn][1]  # (('C', 4), ('H', 5), ...)
        if sig not in type_map:
            type_map[sig] = []
        type_map[sig].append(mn)

    # 3. Water shell RDF
    water_pairs = [
        ('bound_solute', bound_water_atoms, solute_atom_indices),
        ('free_solute', free_water_atoms, solute_atom_indices),
        ('bound_bound', bound_water_atoms, bound_water_atoms),
        ('free_free', free_water_atoms, free_water_atoms),
    ]

    avg_box_vol = 0.0

    for fi, frame_idx in enumerate(frame_indices):
        if fi % max(1, n_frames // 5) == 0 or fi == n_frames - 1:
            print(f'      Frame {frame_idx}/{n_total}  ({100*(fi+1)//n_frames}%)', flush=True)

        frame = tr[frame_idx]
        pos = frame.pos()
        box = frame.box
        vol = box[0][0] * box[1][1] * box[2][2]
        avg_box_vol += vol

        # Helper: compute minimum-image distance
        def pbc_dist(i, j):
            p_i = np.array(pos[i - 1])
            p_j = np.array(pos[j - 1])
            dx, dy, dz = p_j - p_i
            for d in range(3):
                if box[d][d] > 0:
                    v = [dx, dy, dz]
                    v[d] -= box[d][d] * round(v[d] / box[d][d])
                    dx, dy, dz = v
            return np.sqrt(dx*dx + dy*dy + dz*dz)

        # ── Element-pair distances ──
        for e1, e2 in element_pairs:
            atoms1 = element_atoms.get(e1, [])
            atoms2 = element_atoms.get(e2, [])
            if not atoms1 or not atoms2:
                continue
            dists = []
            if e1 == e2:
                # Same element: pairs i < j
                for a in range(len(atoms1)):
                    for b in range(a + 1, len(atoms1)):
                        d = pbc_dist(atoms1[a], atoms1[b])
                        if d < args.r_max:
                            dists.append(d)
            else:
                for a1 in atoms1:
                    for a2 in atoms2:
                        d = pbc_dist(a1, a2)
                        if d < args.r_max:
                            dists.append(d)
            add_pair(f'element_{e1}_{e2}', dists)

        # ── Molecule-type RDF (intra vs inter for solute only) ──
        for sig, mol_list in type_map.items():
            if len(mol_list) < 2:
                # Only intra-molecular for single molecule
                mol_atoms_list = [mol_atom_map[mn] for mn in mol_list]
                # Intra
                intra_dists = []
                for matoms in mol_atoms_list:
                    for a in range(len(matoms)):
                        for b in range(a + 1, len(matoms)):
                            d = pbc_dist(matoms[a], matoms[b])
                            if d < args.r_max:
                                intra_dists.append(d)
                if intra_dists:
                    sig_key = '_'.join(f'{k}{v}' for k, v in sig)
                    add_pair(f'molecule_{sig_key}_self', intra_dists)
            else:
                # Inter-molecular: atoms from different molecules
                mol_atoms_list = [mol_atom_map[mn] for mn in mol_list]
                inter_dists = []
                for mi in range(len(mol_list)):
                    for mj in range(mi + 1, len(mol_list)):
                        for a1 in mol_atoms_list[mi]:
                            for a2 in mol_atoms_list[mj]:
                                d = pbc_dist(a1, a2)
                                if d < args.r_max:
                                    inter_dists.append(d)
                if inter_dists:
                    sig_key = '_'.join(f'{k}{v}' for k, v in sig)
                    add_pair(f'molecule_{sig_key}_inter', inter_dists)

                # Also intra for each molecule
                intra_dists = []
                for matoms in mol_atoms_list:
                    for a in range(len(matoms)):
                        for b in range(a + 1, len(matoms)):
                            d = pbc_dist(matoms[a], matoms[b])
                            if d < args.r_max:
                                intra_dists.append(d)
                if intra_dists:
                    sig_key = '_'.join(f'{k}{v}' for k, v in sig)
                    add_pair(f'molecule_{sig_key}_self', intra_dists)

        # ── Water-shell RDF ──
        for key, set1, set2 in water_pairs:
            if not set1 or not set2:
                continue
            dists = []
            for a1 in set1:
                for a2 in set2:
                    if a1 == a2:
                        continue
                    d = pbc_dist(a1, a2)
                    if d < args.r_max:
                        dists.append(d)
            add_pair(f'water_{key}', dists)

    avg_box_vol /= n_frames

    # ── Normalize and save ──
    print(f'\n   Computing g(r) + n(r) and saving...')
    header = ['r_A', 'g_r', 'n_r']

    for key in sorted(rdf_data.keys()):
        pair_data = rdf_data[key]
        if not pair_data or all(len(p) == 0 for p in pair_data):
            continue
        r, g, n, rho = compute_rdf(pair_data, avg_box_vol, n_frames,
                           r_max=args.r_max, n_bins=args.bins)
        # Save CSV
        fname = f'rdf_{key}.csv'
        fpath = os.path.join(outdir, fname)
        with open(fpath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for i in range(len(r)):
                writer.writerow([f'{r[i]:.4f}', f'{g[i]:.6f}', f'{n[i]:.4f}'])
        # Print peak info + CN at first shell
        peak_idx = np.argmax(g)
        peak_r = r[peak_idx]
        peak_g = g[peak_idx]
        # Find CN at first minimum after peak (or at r=peak_r+1.0 as fallback)
        if peak_idx + 1 < len(g):
            # Search for first minimum after the peak
            min_after_peak = peak_idx + 1
            for j in range(peak_idx + 1, min(len(g), peak_idx + 50)):
                if g[j] < g[min_after_peak]:
                    min_after_peak = j
                if g[j] > g[min_after_peak] * 1.1:  # valley passed
                    break
            cn_val = n[min_after_peak]
        else:
            cn_val = n[peak_idx]
        print(f'   ✓ {fname:40s}  peak: g({peak_r:.2f})={peak_g:.1f}  CN(1st)= {cn_val:.1f}')

    print(f'\n✅ RDF data saved to {outdir}/')


if __name__ == '__main__':
    main()
