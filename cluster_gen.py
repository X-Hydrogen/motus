#!/usr/bin/env python3
"""
cluster_gen.py — Conformational Clustering for Desmond MD.  |  MOTUS v0.0.1

Performs RMSD-based conformational clustering:
  1. Computes pairwise RMSD matrix for solute atoms
  2. Hierarchical agglomerative clustering (Ward's method)
  3. Outputs cluster assignments + centroid structures
  4. Generates cluster population statistics

Usage:
  $SCHRODINGER/run python3 cluster_gen.py <cms> <trj> [OUTDIR]
"""

import sys, os, argparse, csv
import numpy as np
from collections import defaultdict
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from schrodinger.application.desmond.packages import traj, topo


def get_element(atom):
    return atom.element.strip().capitalize()


def rmsd_matrix(positions_list, atom_indices):
    """
    Compute pairwise RMSD matrix for selected atoms across frames.
    
    Args:
        positions_list: list of (N×3) position arrays, one per frame
        atom_indices: which atoms to use for RMSD
    
    Returns:
        condensed distance matrix for hierarchical clustering
    """
    n_frames = len(positions_list)
    n_atoms = len(atom_indices)
    
    dists = np.zeros(n_frames * (n_frames - 1) // 2)
    k = 0
    
    for i in range(n_frames):
        pi = positions_list[i][atom_indices]
        for j in range(i + 1, n_frames):
            pj = positions_list[j][atom_indices]
            # RMSD
            diff = pi - pj
            rmsd_val = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
            dists[k] = rmsd_val
            k += 1
    
    return dists


def main():
    parser = argparse.ArgumentParser(description='Conformational clustering for Desmond MD')
    parser.add_argument('cms', help='CMS file')
    parser.add_argument('trj', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser.add_argument('--stride', type=int, default=10, help='Frame stride')
    parser.add_argument('--max-frames', type=int, default=300, help='Max frames')
    parser.add_argument('--n-clusters', type=int, default=5, help='Number of clusters')
    parser.add_argument('--threshold', type=float, default=None,
                        help='RMSD threshold for clustering (overrides --n-clusters)')
    parser.add_argument('--method', default='ward', help='Linkage method')
    args = parser.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 Conformational Clustering')
    print(f'   method={args.method}  n_clusters={args.n_clusters}')

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
    for mn, alist in mol_map.items():
        el_counts = defaultdict(int)
        for a in alist:
            if a['element'] not in ('', 'W'):
                el_counts[a['element']] += 1
        is_water = (all(k in ('O', 'H') for k in el_counts.keys()) and
                    el_counts.get('O', 0) >= 1 and sum(el_counts.values()) <= 4)
        if not is_water:
            solute_mols.add(mn)

    solute_indices = [a['idx'] for a in atoms_info if a['mol'] in solute_mols]
    print(f'   Solute atoms for RMSD: {len(solute_indices)}')

    # Collect positions
    positions_list = []
    times = []
    for frame_idx in frame_indices:
        frame = tr[frame_idx]
        positions_list.append(frame.pos())
        times.append(frame.time)

    # Compute RMSD matrix
    print(f'\n   Computing pairwise RMSD matrix ({n_frames}×{n_frames})...')
    dists = rmsd_matrix(positions_list, solute_indices)

    # Hierarchical clustering
    print(f'   Clustering...')
    Z = linkage(dists, method=args.method)

    if args.threshold is not None:
        clusters = fcluster(Z, t=args.threshold, criterion='distance')
    else:
        clusters = fcluster(Z, t=args.n_clusters, criterion='maxclust')

    n_clusters = len(set(clusters))
    print(f'   Found {n_clusters} clusters')

    # Statistics
    cluster_sizes = {}
    for c in range(1, n_clusters + 1):
        cluster_sizes[c] = np.sum(clusters == c)

    # Find cluster centroids (frame with minimum average RMSD to cluster members)
    centroids = {}
    for c in range(1, n_clusters + 1):
        members = np.where(clusters == c)[0]
        if len(members) == 1:
            centroids[c] = members[0]
        else:
            # Find member with minimum average distance to other members
            best = members[0]
            best_rmsd = float('inf')
            for mi in members:
                rmsd_sum = 0
                for mj in members:
                    if mi == mj:
                        continue
                    if mi < mj:
                        idx = mi * n_frames - mi * (mi + 1) // 2 + mj - mi - 1
                    else:
                        idx = mj * n_frames - mj * (mj + 1) // 2 + mi - mj - 1
                    rmsd_sum += dists[idx]
                avg_rmsd = rmsd_sum / (len(members) - 1)
                if avg_rmsd < best_rmsd:
                    best_rmsd = avg_rmsd
                    best = mi
            centroids[c] = best

    # Save cluster assignments
    fpath = os.path.join(outdir, 'cluster_assignments.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Frame', 'Time_ps', 'Cluster'])
        for i, (fi, t) in enumerate(zip(frame_indices, times)):
            writer.writerow([f'{fi}', f'{t:.3f}', f'{clusters[i]}'])
    print(f'   ✓ cluster_assignments.csv')

    # Save cluster summary
    fpath = os.path.join(outdir, 'cluster_summary.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Cluster', 'Size', 'Fraction', 'Centroid_Frame', 'Centroid_Time_ps'])
        for c in range(1, n_clusters + 1):
            frac = cluster_sizes[c] / n_frames
            cf = frame_indices[centroids[c]]
            ct = times[centroids[c]]
            writer.writerow([f'{c}', f'{cluster_sizes[c]}', f'{frac:.4f}', f'{cf}', f'{ct:.3f}'])
            print(f'   Cluster {c}: {cluster_sizes[c]:4d} frames ({frac*100:5.1f}%)  centroid @ frame {cf}')

    # Save distance matrix for heatmap
    sq_dists = squareform(dists)
    fpath = os.path.join(outdir, 'cluster_rmsd_matrix.csv')
    np.savetxt(fpath, sq_dists, delimiter=',', header='# RMSD matrix (Å)', comments='')
    print(f'   ✓ cluster_rmsd_matrix.csv ({n_frames}×{n_frames})')

    # Cluster timeline
    fpath = os.path.join(outdir, 'cluster_timeline.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_ps'] + [f'Cluster_{c}' for c in range(1, n_clusters + 1)])
        # Create binary membership per time
        membership = np.zeros((n_frames, n_clusters))
        for i, c in enumerate(clusters):
            membership[i, c - 1] = 1
        for i, t in enumerate(times):
            writer.writerow([f'{t:.3f}'] + [f'{int(membership[i, j])}' for j in range(n_clusters)])

    # ── PCA projection for ML-style scatter plot ──
    print(f'\n   Computing PCA on solute atom positions...')
    # Build feature matrix: n_frames × (3 * n_solute_atoms)
    X = np.zeros((n_frames, 3 * len(solute_indices)))
    for i in range(n_frames):
        X[i] = positions_list[i][solute_indices].ravel()

    # Mean-center
    X_mean = X.mean(axis=0)
    X_centered = X - X_mean

    # SVD (faster than eigendecomposition for n_features >> n_frames)
    U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
    # PC scores: U * S (n_frames × n_components)
    pc_scores = U * S

    # Variance explained
    total_var = np.sum(S**2)
    var_pc1 = (S[0]**2 / total_var) * 100
    var_pc2 = (S[1]**2 / total_var) * 100 if len(S) >= 2 else 0.0

    # Save PCA coordinates
    fpath = os.path.join(outdir, 'cluster_pca.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Frame', 'Time_ps', 'PC1', 'PC2', 'Cluster'])
        for i, (fi, t, c) in enumerate(zip(frame_indices, times, clusters)):
            pc1 = pc_scores[i, 0]
            pc2 = pc_scores[i, 1] if pc_scores.shape[1] >= 2 else 0.0
            writer.writerow([f'{fi}', f'{t:.3f}', f'{pc1:.6f}', f'{pc2:.6f}', f'{c}'])
    print(f'   ✓ cluster_pca.csv  (PC1={var_pc1:.1f}%, PC2={var_pc2:.1f}%)')

    # Save PCA metadata
    fpath = os.path.join(outdir, 'cluster_pca_meta.csv')
    with open(fpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['PC', 'Variance_Explained'])
        writer.writerow(['PC1', f'{var_pc1:.2f}'])
        writer.writerow(['PC2', f'{var_pc2:.2f}'])

    print(f'\n✅ Clustering data saved to {outdir}/')


if __name__ == '__main__':
    main()
