#!/usr/bin/env python3
"""
lammps_plot.py — Publication-quality plotting for LAMMPS MD analysis.  |  MOTUS v0.0.1
Reads CSV files produced by lammps-analysis.sh and generates figures.

Usage:
  python3 lammps_plot.py <analysis_dir>              # Plot everything
  python3 lammps_plot.py <analysis_dir> --type rdf    # Only RDF

Output:
  <analysis_dir>/figures/*.pdf  (vector, for papers)
  <analysis_dir>/figures/*.png  (raster, 300 DPI)
"""

import sys, os, argparse, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path
from scipy.spatial import ConvexHull

# ═══════════════════════════════════════════
# Publication-quality styling (matches GROMACS)
# ═══════════════════════════════════════════
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'axes.linewidth': 1.0,
    'axes.spines.top': True,
    'axes.spines.right': True,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'xtick.major.size': 4,
    'ytick.major.size': 4,
})

PALETTE = {
    'blue':   '#2171B5',
    'red':    '#CB181D',
    'green':  '#238B45',
    'orange': '#E6550D',
    'purple': '#6A51A3',
    'teal':   '#2CA02C',
    'grey':   '#636363',
    'pink':   '#D94894',
}
COLORS = list(PALETTE.values())


def read_csv(path):
    data = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    if not data:
        return None
    result = {}
    for h in data[0].keys():
        try:
            result[h.strip()] = np.array([float(r[h]) for r in data])
        except (ValueError, KeyError):
            pass
    return result


def save_figure(fig, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    pdf_path = os.path.join(outdir, f'{name}.pdf')
    png_path = os.path.join(outdir, f'{name}.png')
    fig.savefig(pdf_path, format='pdf')
    fig.savefig(png_path, format='png')
    print(f'  ✓ {name}.pdf + {name}.png')
    return pdf_path


def convert_time(time_vals):
    """Convert time array to ps or ns. Handles Step indices or Time_fs."""
    if time_vals is None or len(time_vals) == 0:
        return time_vals, 'Step'
    t_max = time_vals[-1]
    if t_max > 1e6:       # fs range → convert to ps
        return time_vals / 1000, 'Time (ps)'
    if t_max > 500000:    # large step count
        return time_vals, 'Step'
    # Already in ps or small step count
    if t_max > 500:       # ps → ns
        return time_vals / 1000, 'Time (ns)'
    return time_vals, 'Time (ps)'


# ═══════════════════════════════════════════
# Plot functions
# ═══════════════════════════════════════════

def plot_energy_timeseries(adir, outdir):
    """Multi-panel: T, P, E_pot, Volume, Density."""
    csv_path = os.path.join(adir, 'energy_timeseries.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    # Find time column: Step, Time_fs, or Time_ps
    time_col = 'Time_fs' if 'Time_fs' in d else ('Time_ps' if 'Time_ps' in d else 'Step')
    if time_col not in d:
        return

    t, tlabel = convert_time(d[time_col])
    panels = [
        ('Temp_K',        'Temperature (K)',                PALETTE['red']),
        ('Press_atm',     'Pressure (atm)',                 PALETTE['blue']),
        ('Pot_E_kcal',    'E$_{pot}$ (kcal/mol)',          PALETTE['green']),
        ('Vol_A3',        'Volume (Å$^3$)',                PALETTE['purple']),
        ('Density_gcc',   'Density (g/cm$^3$)',            PALETTE['orange']),
    ]

    fig, axes = plt.subplots(len(panels), 1, figsize=(7, 11), sharex=True)
    for ax, (col, ylabel, color) in zip(axes, panels):
        if col in d:
            ax.plot(t, d[col], color=color, linewidth=0.6, alpha=0.85)
            ax.set_ylabel(ylabel, fontsize=9)
            meanv = np.mean(d[col])
            ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.7, alpha=0.5)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(5))
    axes[-1].set_xlabel(tlabel)
    fig.align_ylabels()
    plt.tight_layout()
    save_figure(fig, outdir, 'energy_timeseries')
    plt.close(fig)


def plot_energy_distribution(adir, outdir):
    csv_path = os.path.join(adir, 'energy_timeseries.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return

    items = [
        ('Temp_K',      'Temperature (K)',      PALETTE['red']),
        ('Pot_E_kcal',  'E$_{pot}$ (kcal/mol)', PALETTE['blue']),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    for ax, (col, xlabel, color) in zip(axes, items):
        if col not in d:
            continue
        vals = d[col]
        ax.hist(vals, bins=40, color=color, alpha=0.7, edgecolor='white', linewidth=0.3)
        ax.axvline(np.mean(vals), color='black', linestyle='--', linewidth=1,
                   label=f'μ = {np.mean(vals):.1f}')
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Frequency')
        ax.legend(fontsize=8)
    plt.tight_layout()
    save_figure(fig, outdir, 'energy_distribution')
    plt.close(fig)


def plot_rdf(adir, outdir):
    """Dual-axis: g(r) + n(r) coordination number."""
    csv_path = os.path.join(adir, 'rdf_all.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d or 'r_A' not in d:
        return

    r = d['r_A']
    g = d['g_r']

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.plot(r, g, color=PALETTE['blue'], linewidth=1.0, alpha=0.9, label='g(r)')
    ax1.set_xlabel('r (Å)')
    ax1.set_ylabel('g(r)', color=PALETTE['blue'])
    ax1.tick_params(axis='y', labelcolor=PALETTE['blue'])
    ax1.set_xlim(0, r[-1])
    ax1.set_title('Radial Distribution Function + Coordination Number')

    # Right axis: n(r) if available
    if 'n_r' in d:
        ax2 = ax1.twinx()
        ax2.plot(r, d['n_r'], color=PALETTE['red'], linewidth=0.8, linestyle='--',
                 alpha=0.85, label='n(r)')
        ax2.set_ylabel('n(r)', color=PALETTE['red'])
        ax2.tick_params(axis='y', labelcolor=PALETTE['red'])

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    if 'n_r' in d:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper right')
    else:
        ax1.legend(fontsize=9)

    plt.tight_layout()
    save_figure(fig, outdir, 'rdf')
    plt.close(fig)


def plot_rmsd(adir, outdir):
    csv_path = os.path.join(adir, 'rmsd.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    # LAMMPS RMSD uses Frame index
    frames = d['Frame'] if 'Frame' in d else np.arange(len(d.get('RMSD_A', [])))

    # Find RMSD column
    rmsd_col = 'RMSD_A' if 'RMSD_A' in d else list(d.keys())[1] if len(d) > 1 else None
    if rmsd_col is None:
        return

    rmsd = d[rmsd_col]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(frames, rmsd, color=PALETTE['red'], linewidth=0.8, alpha=0.85)
    ax.set_ylabel('RMSD (Å)')
    ax.set_xlabel('Frame')
    meanv = np.mean(rmsd)
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.2f} Å')
    ax.legend(fontsize=9)
    ax.set_title('Root Mean Square Deviation')
    plt.tight_layout()
    save_figure(fig, outdir, 'rmsd')
    plt.close(fig)


def plot_summary_dashboard(adir, outdir):
    """2x2 summary with key LAMMPS metrics."""
    fig = plt.figure(figsize=(10, 8))
    fig.suptitle('LAMMPS MD — Summary Dashboard', fontsize=13, fontweight='bold', y=0.98)

    grid = [(0, 0), (0, 1), (1, 0), (1, 1)]
    idx = 0

    # Panel 1: Temperature
    ecsv = os.path.join(adir, 'energy_timeseries.csv')
    edata = None
    time_col = 'Step'
    if os.path.exists(ecsv):
        edata = read_csv(ecsv)
        if edata:
            time_col = 'Time_fs' if 'Time_fs' in edata else ('Time_ps' if 'Time_ps' in edata else 'Step')

    # Panel 1: Temperature
    if edata and 'Temp_K' in edata and idx < 4:
        t, tl = convert_time(edata[time_col])
        ax = plt.subplot2grid((2, 2), grid[idx])
        ax.plot(t, edata['Temp_K'], color=PALETTE['red'], linewidth=0.5, alpha=0.85)
        ax.set_ylabel('T (K)')
        ax.set_xlabel(tl)
        ax.set_title(f'T μ={np.mean(edata["Temp_K"]):.0f}K', fontsize=9)
        idx += 1

    # Panel 2: Potential Energy
    if edata and 'Pot_E_kcal' in edata and idx < 4:
        t, tl = convert_time(edata[time_col])
        ax = plt.subplot2grid((2, 2), grid[idx])
        ax.plot(t, edata['Pot_E_kcal'], color=PALETTE['green'], linewidth=0.5, alpha=0.85)
        ax.set_ylabel('E$_{pot}$ (kcal/mol)')
        ax.set_xlabel(tl)
        idx += 1

    # Panel 3: RDF
    rcsv = os.path.join(adir, 'rdf_all.csv')
    if os.path.exists(rcsv) and idx < 4:
        d = read_csv(rcsv)
        if d and 'r_A' in d:
            ax = plt.subplot2grid((2, 2), grid[idx])
            ax.plot(d['r_A'], d['g_r'], color=PALETTE['blue'], linewidth=0.8, alpha=0.9)
            ax.set_xlabel('r (Å)')
            ax.set_ylabel('g(r)')
            ax.set_xlim(0, d['r_A'][-1])
            ax.set_title('Radial Distribution Function', fontsize=9)
            idx += 1

    # Panel 4: Volume
    if edata and 'Vol_A3' in edata and idx < 4:
        t, tl = convert_time(edata[time_col])
        ax = plt.subplot2grid((2, 2), grid[idx])
        ax.plot(t, edata['Vol_A3'], color=PALETTE['purple'], linewidth=0.5, alpha=0.85)
        ax.set_ylabel('Vol (Å³)')
        ax.set_xlabel(tl)
        idx += 1

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save_figure(fig, outdir, 'summary_dashboard')
    plt.close(fig)


# ═══════════════════════════════════════════
# Cluster Analysis Plots (Desmond-style)
# ═══════════════════════════════════════════

def plot_cluster_sizes(adir, outdir):
    """Bar + pie chart of cluster populations (Desmond-style dual panel)."""
    csv_path = os.path.join(adir, 'cluster_sizes.csv')
    if not os.path.exists(csv_path):
        # Fallback: Desmond uses cluster_summary.csv
        csv_path = os.path.join(adir, 'cluster_summary.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    clusters = d.get('Cluster', np.arange(len(list(d.values())[0])) + 1)
    sizes = d.get('Size', list(d.values())[1] if len(d) > 1 else list(d.values())[0])

    n = len(sizes)
    colors = [PALETTE[c] for c in ['blue', 'red', 'green', 'orange', 'purple', 'teal', 'pink', 'grey']]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    # Left: bar chart
    ax1.bar(np.arange(1, n+1), sizes, color=colors[:n], alpha=0.85, edgecolor='white', linewidth=0.5)
    ax1.set_xlabel('Cluster', fontsize=9)
    ax1.set_ylabel('Population (frames)', fontsize=9)
    ax1.set_title('Cluster Populations', fontsize=11)
    ax1.tick_params(labelsize=8)
    ax1.set_xticks(np.arange(1, min(n+1, 21)))

    # Right: pie chart
    fractions = sizes / np.sum(sizes) * 100
    ax2.pie(fractions, labels=[f'C{i}' for i in range(1, n+1)],
            autopct='%1.1f%%', colors=colors[:n],
            textprops={'fontsize': 8})
    ax2.set_title('Cluster Distribution', fontsize=11)

    plt.tight_layout()
    save_figure(fig, outdir, 'cluster_population')
    plt.close(fig)


def plot_cluster_timeline(adir, outdir):
    """Cluster assignment over time with stacked color bands (Desmond-style)."""
    csv_path = os.path.join(adir, 'cluster_timeline.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return

    # Detect format: Cluster_ID column vs Cluster_0/Cluster_1 columns
    if 'Cluster_ID' in d:
        t = d.get('Time_ps', np.arange(len(d['Cluster_ID'])))
        cid = d['Cluster_ID']
        t, tlabel = convert_time(t)
        nclust = int(np.max(cid)) + 1
        colors = [COLORS[i % len(COLORS)] for i in range(nclust)]

        fig, ax = plt.subplots(figsize=(10, 2.5))
        y_bottom = np.zeros(len(t))
        for ci in range(nclust):
            mask = (cid == ci)
            band = np.where(mask, 1.0, 0.0)
            ax.fill_between(t, y_bottom, y_bottom + band,
                            color=colors[ci], alpha=0.7, step='post',
                            label=f'C{ci}')
            y_bottom += band
        ax.set_xlabel(tlabel, fontsize=9)
        ax.set_ylabel('Cluster', fontsize=9)
        ax.set_title('Cluster Timeline', fontsize=11)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        if nclust <= 8:
            ax.legend(fontsize=7, ncol=nclust, loc='upper right')
        ax.tick_params(labelsize=8)
        plt.tight_layout()
        save_figure(fig, outdir, 'cluster_timeline')
        plt.close(fig)

    elif any(k.startswith('Cluster_') for k in d):
        cluster_cols = sorted([k for k in d if k.startswith('Cluster_')])
        t = d['Time_ps']
        t, tlabel = convert_time(t)
        n_clusters = len(cluster_cols)
        colors = [PALETTE[c] for c in ['blue', 'red', 'green', 'orange', 'purple', 'teal', 'pink', 'grey']]

        fig, ax = plt.subplots(figsize=(10, 2.5))
        for ci, col in enumerate(cluster_cols):
            mask = d[col] > 0.5
            ax.fill_between(t, 0, 1, where=mask,
                            color=colors[ci % len(colors)], alpha=0.6,
                            label=f'C{ci}', step='post')
        ax.set_xlabel(tlabel, fontsize=9)
        ax.set_ylabel('Cluster', fontsize=9)
        ax.set_title('Cluster Timeline', fontsize=11)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.legend(fontsize=7, ncol=n_clusters, loc='upper right')
        ax.tick_params(labelsize=8)
        plt.tight_layout()
        save_figure(fig, outdir, 'cluster_timeline')
        plt.close(fig)


def plot_cluster_scatter(adir, outdir):
    """PCA projection scatter colored by cluster with convex hulls (Desmond ML-style).
    Produces TWO figures:
      - cluster_pca_scatter: colored by cluster with hulls + centroids
      - cluster_pca_timeline: colored by time (viridis gradient)
    """
    pca_file = os.path.join(adir, 'cluster_pca.csv')
    meta_file = os.path.join(adir, 'cluster_pca_meta.csv')

    if not os.path.exists(pca_file):
        return False

    pc1, pc2, times, clusters = [], [], [], []
    with open(pca_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc1.append(float(row['PC1']))
            pc2.append(float(row['PC2']))
            times.append(float(row['Time_ps']))
            clusters.append(int(row['Cluster']))

    pc1 = np.array(pc1)
    pc2 = np.array(pc2)
    times = np.array(times)
    clusters = np.array(clusters)
    unique_clusters = sorted(set(clusters))

    var1, var2 = 0.0, 0.0
    if os.path.exists(meta_file):
        with open(meta_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['PC'] == 'PC1':
                    var1 = float(row['Variance_Explained'])
                elif row['PC'] == 'PC2':
                    var2 = float(row['Variance_Explained'])

    cmap = plt.cm.tab10
    cluster_colors = {c: cmap(i % 10) for i, c in enumerate(unique_clusters)}

    # ── Figure 1: PCA scatter with convex hulls ──
    fig, ax = plt.subplots(figsize=(8, 7))
    t_norm = (times - times.min()) / (times.max() - times.min() + 1e-10)
    sizes = 20 + t_norm * 60

    for c in unique_clusters:
        mask = clusters == c
        pts = np.column_stack([pc1[mask], pc2[mask]])
        color = cluster_colors[c]

        ax.scatter(pc1[mask], pc2[mask], s=sizes[mask], c=[color],
                   alpha=0.7, edgecolors='white', linewidth=0.3,
                   label=f'Cluster {c} ({mask.sum()} frames)')

        if mask.sum() >= 3:
            try:
                hull = ConvexHull(pts)
                hull_pts = pts[hull.vertices]
                hull_pts = np.vstack([hull_pts, hull_pts[0]])
                ax.fill(hull_pts[:, 0], hull_pts[:, 1], alpha=0.08,
                        color=color, edgecolor=color, linewidth=0.8,
                        linestyle='--')
            except Exception:
                pass

    for c in unique_clusters:
        mask = clusters == c
        cx, cy = pc1[mask].mean(), pc2[mask].mean()
        ax.scatter([cx], [cy], s=180, c='white', edgecolors=cluster_colors[c],
                   linewidth=2, zorder=10, marker='D')
        ax.annotate(f'{c}', (cx, cy), fontsize=9, ha='center', va='center',
                    fontweight='bold', color=cluster_colors[c], zorder=11)

    ax.set_xlabel(f'PC1 ({var1:.1f}%)' if var1 else 'PC1', fontsize=10)
    ax.set_ylabel(f'PC2 ({var2:.1f}%)' if var2 else 'PC2', fontsize=10)
    ax.set_title('Conformational Landscape — PCA Projection', fontsize=12, fontweight='bold')
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8, loc='upper left', bbox_to_anchor=(1.02, 1),
              framealpha=0.9, edgecolor='gray')

    plt.tight_layout()
    save_figure(fig, outdir, 'cluster_pca_scatter')
    plt.close(fig)

    # ── Figure 2: PCA scatter with time color gradient ──
    fig, ax = plt.subplots(figsize=(8, 7))
    sc = ax.scatter(pc1, pc2, c=times, cmap='viridis', s=sizes,
                    alpha=0.7, edgecolors='white', linewidth=0.3)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.85)
    cbar.set_label('Time (ps)', fontsize=9)
    cbar.ax.tick_params(labelsize=7)

    ax.set_xlabel(f'PC1 ({var1:.1f}%)' if var1 else 'PC1', fontsize=10)
    ax.set_ylabel(f'PC2 ({var2:.1f}%)' if var2 else 'PC2', fontsize=10)
    ax.set_title('Conformational Landscape — Time Evolution', fontsize=12, fontweight='bold')
    ax.tick_params(labelsize=8)

    plt.tight_layout()
    save_figure(fig, outdir, 'cluster_pca_timeline')
    plt.close(fig)

    return True


def plot_meta_cv_time(adir, outdir):
    """CV time series from COLVARS metadynamics."""
    csv_path = os.path.join(adir, 'meta_cv_time.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    time_col = 'Step' if 'Step' in d else ('Time_ps' if 'Time_ps' in d else list(d.keys())[0])
    t = d[time_col]
    t, tlabel = convert_time(t)

    cv_cols = [k for k in d if k.lower() in ('cv', 'cv1') or k.startswith('CV')]
    if not cv_cols:
        cv_cols = [list(d.keys())[1]] if len(d) >= 2 else []

    if not cv_cols:
        return

    fig, axes = plt.subplots(len(cv_cols), 1, figsize=(7, 3 * len(cv_cols)), sharex=True)
    if len(cv_cols) == 1:
        axes = [axes]

    for ax, col in zip(axes, cv_cols):
        ax.plot(t, d[col], color=PALETTE['red'], linewidth=0.8, alpha=0.85)
        ax.set_ylabel('CV')
        meanv = np.mean(d[col])
        ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.7,
                   label=f'Avg = {meanv:.4f}')
        ax.legend(fontsize=8)
    axes[-1].set_xlabel(tlabel)
    axes[0].set_title('LAMMPS Metadynamics — Collective Variable')
    fig.align_ylabels()
    plt.tight_layout()
    save_figure(fig, outdir, 'meta_cv_time')
    plt.close(fig)



# ═══════════════════════════════════════════
# Main dispatch
# ═══════════════════════════════════════════
PLOTTERS = {
    'energy':    [plot_energy_timeseries, plot_energy_distribution],
    'rdf':       [plot_rdf],
    'rmsd':      [plot_rmsd],
    'dashboard': [plot_summary_dashboard],
    'meta':      [plot_meta_cv_time],
    'cluster':   [plot_cluster_sizes, plot_cluster_timeline, plot_cluster_scatter],
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LAMMPS MD analysis plotting')
    parser.add_argument('analysis_dir', help='Path to analysis/ directory')
    parser.add_argument('--type', default='all', help='Plot type (energy,rdf,rmsd,dashboard,meta,cluster,all)')
    args = parser.parse_args()

    adir = os.path.abspath(args.analysis_dir)
    outdir = os.path.join(adir, 'figures')
    os.makedirs(outdir, exist_ok=True)

    plot_type = args.type.lower()
    print(f'LAMMPS Plot → {adir}')

    if plot_type == 'all':
        for ptype, funcs in PLOTTERS.items():
            for fn in funcs:
                fn(adir, outdir)
    elif plot_type in PLOTTERS:
        for fn in PLOTTERS[plot_type]:
            fn(adir, outdir)
    else:
        print(f'Unknown plot type: {plot_type}')
        print(f'Available: {", ".join(PLOTTERS.keys())}, all')
        sys.exit(1)

    n = len(os.listdir(outdir))
    print(f'  → {n} files in {outdir}/')
