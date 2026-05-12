#!/usr/bin/env python3
"""
gromacs_plot.py — Publication-quality plotting for GROMACS MD analysis.  |  MOTUS v0.0.1
Reads CSV files produced by gromacs-analysis.sh and generates figures.

Usage:
  python3 gromacs_plot.py <analysis_dir>              # Plot everything
  python3 gromacs_plot.py <analysis_dir> --type energy # Only energy plots

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
# Publication-quality styling
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
    """Read CSV file, return dict of column arrays."""
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


def convert_time(time_ps):
    """Return (time, label) — use ns when >500 ps, else ps."""
    t_max = time_ps[-1] if len(time_ps) > 0 else 0
    if t_max > 500:
        return time_ps / 1000, 'Time (ns)'
    return time_ps, 'Time (ps)'


# ═══════════════════════════════════════════
# Plot functions
# ═══════════════════════════════════════════

def plot_energy_timeseries(adir, outdir):
    """Multi-panel: T, P, E_pot, Volume, Density."""
    csv_path = os.path.join(adir, 'energy_timeseries.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d or 'Time_ps' not in d:
        return

    t, tlabel = convert_time(d['Time_ps'])
    panels = [
        ('Temp_K',        'Temperature (K)',                PALETTE['red']),
        ('Pressure_bar',  'Pressure (bar)',                 PALETTE['blue']),
        ('Pot_E_kJmol',   'E$_{pot}$ (kJ/mol)',            PALETTE['green']),
        ('Vol_nm3',       'Volume (nm$^3$)',               PALETTE['purple']),
        ('Density_kgm3',  'Density (kg/m$^3$)',            PALETTE['orange']),
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
        ('Temp_K',       'Temperature (K)',     PALETTE['red']),
        ('Pot_E_kJmol',  'E$_{pot}$ (kJ/mol)', PALETTE['blue']),
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


def plot_hbonds(adir, outdir):
    csv_path = os.path.join(adir, 'hbonds.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t, tlabel = convert_time(d['Time_ps'])
    counts = d['HBonds']

    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(t, counts, color=PALETTE['teal'], linewidth=0.8, alpha=0.85)
    ax.set_ylabel('H-bond Count')
    ax.set_xlabel(tlabel)
    meanv = np.mean(counts)
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.1f}')
    ax.legend(fontsize=9)
    ax.set_title('Hydrogen Bonds')
    plt.tight_layout()
    save_figure(fig, outdir, 'hbonds')
    plt.close(fig)


def plot_rmsd(adir, outdir):
    csv_path = os.path.join(adir, 'rmsd.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t, tlabel = convert_time(d['Time_ps'])
    rmsd = d['RMSD_nm']  # already in nm, convert to Å

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(t, rmsd, color=PALETTE['red'], linewidth=0.8, alpha=0.85)
    ax.set_ylabel('RMSD (Å)')
    ax.set_xlabel(tlabel)
    meanv = np.mean(rmsd)
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.2f} Å')
    ax.legend(fontsize=9)
    ax.set_title('Root Mean Square Deviation')
    plt.tight_layout()
    save_figure(fig, outdir, 'rmsd')
    plt.close(fig)


def plot_rdf(adir, outdir):
    csv_path = os.path.join(adir, 'rdf.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    r = d['r_nm'] * 10  # nm → Å
    g = d['g_r']

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(r, g, color=PALETTE['blue'], linewidth=1.0, alpha=0.9)
    ax.set_xlabel('r (Å)')
    ax.set_ylabel('g(r)')
    ax.set_xlim(0, r[-1])
    ax.set_title('Radial Distribution Function')
    # Highlight first peak
    if len(r) > 1:
        peak_idx = 1 + np.argmax(g[1:len(g)//4])  # first peak in first quarter
        ax.axvline(r[peak_idx], color=PALETTE['red'], linestyle='--', linewidth=0.6, alpha=0.5)
    plt.tight_layout()
    save_figure(fig, outdir, 'rdf')
    plt.close(fig)


def plot_gyrate(adir, outdir):
    csv_path = os.path.join(adir, 'gyrate.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t, tlabel = convert_time(d['Time_ps'])

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(t, d['Rg_nm'], color=PALETTE['purple'], linewidth=0.8, alpha=0.85)
    ax.set_ylabel('R$_g$ (nm)')
    ax.set_xlabel(tlabel)
    meanv = np.mean(d['Rg_nm'])
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.3f} nm')
    ax.legend(fontsize=9)
    ax.set_title('Radius of Gyration')
    plt.tight_layout()
    save_figure(fig, outdir, 'rgyr')
    plt.close(fig)


def plot_sasa(adir, outdir):
    csv_path = os.path.join(adir, 'sasa.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t, tlabel = convert_time(d['Time_ps'])

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(t, d['Area_nm2'], color=PALETTE['green'], linewidth=0.8, alpha=0.85)
    ax.set_ylabel('SASA (nm$^2$)')
    ax.set_xlabel(tlabel)
    meanv = np.mean(d['Area_nm2'])
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.1f} nm$^2$')
    ax.legend(fontsize=9)
    ax.set_title('Solvent Accessible Surface Area')
    plt.tight_layout()
    save_figure(fig, outdir, 'sasa')
    plt.close(fig)


def plot_density_z(adir, outdir):
    csv_path = os.path.join(adir, 'density_z.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.fill_between(d['Z_nm'], d['Density_kgm3'], color=PALETTE['blue'], alpha=0.3)
    ax.plot(d['Z_nm'], d['Density_kgm3'], color=PALETTE['blue'], linewidth=1.0)
    ax.set_xlabel('Z (nm)')
    ax.set_ylabel('Density (kg/m$^3$)')
    ax.set_title('Density Profile Along Z-axis')
    plt.tight_layout()
    save_figure(fig, outdir, 'density_z')
    plt.close(fig)


def plot_summary_dashboard(adir, outdir):
    """2x2 summary dashboard of key metrics."""
    fig = plt.figure(figsize=(10, 8))
    fig.suptitle('GROMACS MD — Summary Dashboard', fontsize=13, fontweight='bold', y=0.98)

    grid = [(0, 0), (0, 1), (1, 0), (1, 1)]
    idx = 0

    # Panel 1: Energy timeseries (Temperature)
    ecsv = os.path.join(adir, 'energy_timeseries.csv')
    if os.path.exists(ecsv) and idx < 4:
        d = read_csv(ecsv)
        if d and 'Temp_K' in d:
            t, tl = convert_time(d['Time_ps'])
            ax = plt.subplot2grid((2, 2), grid[idx])
            ax.plot(t, d['Temp_K'], color=PALETTE['red'], linewidth=0.5, alpha=0.85)
            ax.set_ylabel('T (K)')
            ax.set_xlabel(tl)
            ax.set_title(f'T μ={np.mean(d["Temp_K"]):.0f}K', fontsize=9)
            idx += 1

    # Panel 2: H-bonds
    hcsv = os.path.join(adir, 'hbonds.csv')
    if os.path.exists(hcsv) and idx < 4:
        d = read_csv(hcsv)
        if d:
            t, tl = convert_time(d['Time_ps'])
            ax = plt.subplot2grid((2, 2), grid[idx])
            ax.plot(t, d['HBonds'], color=PALETTE['teal'], linewidth=0.5, alpha=0.85)
            ax.set_ylabel('H-bonds')
            ax.set_xlabel(tl)
            idx += 1

    # Panel 3: RMSD
    rcsv = os.path.join(adir, 'rmsd.csv')
    if os.path.exists(rcsv) and idx < 4:
        d = read_csv(rcsv)
        if d:
            t, tl = convert_time(d['Time_ps'])
            ax = plt.subplot2grid((2, 2), grid[idx])
            ax.plot(t, d['RMSD_nm'], color=PALETTE['red'], linewidth=0.5, alpha=0.85)
            ax.set_ylabel('RMSD (Å)')
            ax.set_xlabel(tl)
            idx += 1

    # Panel 4: Density
    dcsv = os.path.join(adir, 'density_z.csv')
    if os.path.exists(dcsv) and idx < 4:
        d = read_csv(dcsv)
        if d:
            ax = plt.subplot2grid((2, 2), grid[idx])
            ax.fill_between(d['Z_nm'], d['Density_kgm3'], color=PALETTE['blue'], alpha=0.3)
            ax.plot(d['Z_nm'], d['Density_kgm3'], color=PALETTE['blue'], linewidth=0.8)
            ax.set_xlabel('Z (nm)')
            ax.set_ylabel('ρ (kg/m³)')
            ax.set_title('Density Profile', fontsize=9)
            idx += 1

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save_figure(fig, outdir, 'summary_dashboard')
    plt.close(fig)


def plot_meta_cv_time(adir, outdir):
    """CV time series from metadynamics."""
    csv_path = os.path.join(adir, 'meta_cv_time.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    time_col = 'Time_ps' if 'Time_ps' in d else ('Step' if 'Step' in d else list(d.keys())[0])
    t = d[time_col]
    t, tlabel = convert_time(t)

    # Find all CV columns
    cv_cols = [k for k in d if k.startswith('CV') or k.lower() == 'cv']

    fig, axes = plt.subplots(len(cv_cols), 1, figsize=(7, 3 * len(cv_cols)), sharex=True)
    if len(cv_cols) == 1:
        axes = [axes]

    for ax, col in zip(axes, cv_cols):
        ax.plot(t, d[col], color=PALETTE['red'], linewidth=0.8, alpha=0.85)
        ax.set_ylabel(col)
        meanv = np.mean(d[col])
        ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.7,
                   label=f'Avg = {meanv:.3f}')
        ax.legend(fontsize=8)
    axes[-1].set_xlabel(tlabel)
    axes[0].set_title('Metadynamics — Collective Variable(s)')

    fig.align_ylabels()
    plt.tight_layout()
    save_figure(fig, outdir, 'meta_cv_time')
    plt.close(fig)


def plot_meta_fes(adir, outdir):
    """Free Energy Surface (1D) from metadynamics."""
    csv_path = os.path.join(adir, 'meta_fes_1d.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    # Auto-detect columns: first = CV value, second = FES energy
    cols = [k for k in d if 'energy' in k.lower() or 'fes' in k.lower() or 'free' in k.lower()]
    if not cols:
        # Fallback: second column
        cols = [list(d.keys())[1]] if len(d) >= 2 else []
    if not cols:
        return
    cv_col = list(d.keys())[0]
    energy_col = cols[0]

    cv = d[cv_col]
    fes = d[energy_col]
    # Shift FES so minimum = 0
    fes = fes - np.min(fes)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(cv, fes, color=PALETTE['blue'], linewidth=1.2)
    ax.fill_between(cv, 0, fes, color=PALETTE['blue'], alpha=0.15)
    ax.set_xlabel('Collective Variable')
    ax.set_ylabel('Free Energy (kJ/mol)')
    ax.set_title('Free Energy Surface (1D)')
    plt.tight_layout()
    save_figure(fig, outdir, 'meta_fes_1d')
    plt.close(fig)



def plot_wham_pmf(adir, outdir):
    """PMF from umbrella sampling WHAM reconstruction."""
    csv_path = os.path.join(adir, 'pmf.csv')
    if not os.path.exists(csv_path):
        # Try pmf.xvg directly
        xvg_path = os.path.join(adir, 'pmf.xvg')
        if not os.path.exists(xvg_path):
            return
        # Parse XVG (skip # and @ lines)
        cv_vals, pmf_vals = [], []
        with open(xvg_path) as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ('#', '@'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    cv_vals.append(float(parts[0]))
                    pmf_vals.append(float(parts[1]))
        if not cv_vals:
            return
        cv = np.array(cv_vals)
        pmf = np.array(pmf_vals)
    else:
        d = read_csv(csv_path)
        if not d:
            return
        cv = d.get('CV_nm', list(d.values())[0])
        pmf = d.get('PMF_kJmol', list(d.values())[1] if len(d) > 1 else cv)

    # Shift PMF to minimum = 0
    pmf = pmf - np.min(pmf)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(cv, pmf, color=PALETTE['blue'], linewidth=1.5)
    ax.fill_between(cv, 0, pmf, color=PALETTE['blue'], alpha=0.12)
    ax.set_xlabel('Reaction Coordinate (nm)')
    ax.set_ylabel('PMF (kJ/mol)')
    ax.set_title('Potential of Mean Force — Umbrella Sampling + WHAM')

    # Mark barrier and minima
    if len(pmf) > 1:
        barrier_idx = np.argmax(pmf)
        ax.scatter(cv[barrier_idx], pmf[barrier_idx], color=PALETTE['red'],
                  s=60, zorder=5, label=f'Barrier: {pmf[barrier_idx]:.1f} kJ/mol')
        ax.axvline(cv[barrier_idx], color=PALETTE['red'], linestyle=':', linewidth=0.8, alpha=0.4)

        # Find local minima on each side
        for side, color in [('left', PALETTE['green']), ('right', PALETTE['orange'])]:
            if side == 'left':
                region = pmf[:barrier_idx]
                cv_region = cv[:barrier_idx]
            else:
                region = pmf[barrier_idx+1:]
                cv_region = cv[barrier_idx+1:]
            if len(region) > 0:
                local_min = np.argmin(region)
                ax.scatter(cv_region[local_min], region[local_min], color=color,
                          s=60, zorder=5, marker='v')
        ax.legend(fontsize=8)

    plt.tight_layout()
    save_figure(fig, outdir, 'pmf_wham')
    plt.close(fig)


    # Also plot histogram overlap
    hpath = os.path.join(adir, 'histo.xvg')
    if os.path.exists(hpath):
        # Parse multi-column histogram XVG
        try:
            hist_data = []
            with open(hpath) as f:
                for line in f:
                    line = line.strip()
                    if not line or line[0] in ('#', '@'):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        hist_data.append([float(x) for x in parts])
            if hist_data:
                hist_arr = np.array(hist_data)
                ncols = hist_arr.shape[1]
                cv_h = hist_arr[:, 0]
                hists = [hist_arr[:, i] for i in range(1, ncols)]

                fig, ax = plt.subplots(figsize=(8, 5))
                for i, h in enumerate(hists):
                    alpha = 0.25 + 0.5 * (i / max(1, len(hists) - 1))
                    ax.fill_between(cv_h, h, alpha=alpha, linewidth=0.3,
                                   label=f'Win {i+1}' if i < 12 else None)
                ax.set_xlabel('Reaction Coordinate (nm)')
                ax.set_ylabel('Sampling Count')
                ax.set_title('Umbrella Sampling — Window Histogram Overlap')
                if len(hists) <= 12:
                    ax.legend(fontsize=7, ncol=2)
                plt.tight_layout()
                save_figure(fig, outdir, 'pmf_histograms')
                plt.close(fig)
        except Exception:
            pass


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
    wedges, texts, autotexts = ax2.pie(fractions,
            labels=[f'C{i}' for i in range(1, n+1)],
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
        # Stacked bands: fill each cluster as full-height band
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
        # Multi-column format from Desmond
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


def plot_rmsd_distribution(adir, outdir):
    """RMSD distribution from clustering (pairwise RMSD histogram)."""
    csv_path = os.path.join(adir, 'rmsd_distribution.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    rmsd = d.get('RMSD_nm', list(d.values())[0])
    count = d.get('Count', list(d.values())[1] if len(d) > 1 else rmsd)

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(rmsd, count, color=PALETTE['purple'], linewidth=1.0)
    ax.fill_between(rmsd, 0, count, color=PALETTE['purple'], alpha=0.15)
    ax.set_xlabel('Pairwise RMSD (nm)', fontsize=9)
    ax.set_ylabel('Count', fontsize=9)
    ax.set_title('RMSD Distribution (all frame pairs)', fontsize=11)
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    save_figure(fig, outdir, 'rmsd_distribution')
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

    # Read PCA coordinates
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
    n_clusters = len(unique_clusters)

    # Read variance explained
    var1, var2 = 0.0, 0.0
    if os.path.exists(meta_file):
        with open(meta_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['PC'] == 'PC1':
                    var1 = float(row['Variance_Explained'])
                elif row['PC'] == 'PC2':
                    var2 = float(row['Variance_Explained'])

    # Color palette per cluster (tab10)
    cmap = plt.cm.tab10
    cluster_colors = {c: cmap(i % 10) for i, c in enumerate(unique_clusters)}

    # ── Figure 1: PCA scatter with convex hulls ──
    fig, ax = plt.subplots(figsize=(8, 7))

    # Time-based size scaling (early=small, late=large)
    t_norm = (times - times.min()) / (times.max() - times.min() + 1e-10)
    sizes = 20 + t_norm * 60  # range ~20–80

    for c in unique_clusters:
        mask = clusters == c
        pts = np.column_stack([pc1[mask], pc2[mask]])
        color = cluster_colors[c]

        # Scatter points
        ax.scatter(pc1[mask], pc2[mask], s=sizes[mask], c=[color],
                   alpha=0.7, edgecolors='white', linewidth=0.3,
                   label=f'Cluster {c} ({mask.sum()} frames)')

        # Convex hull polygon (if >=3 points)
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

    # Cluster centroids (white diamonds)
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

    # Legend outside
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


# ═══════════════════════════════════════════
# PCA Plots
# ═══════════════════════════════════════════

def plot_pca_eigenvalues(adir, outdir):
    """Eigenvalue spectrum + cumulative variance."""
    csv_path = os.path.join(adir, 'eigenvalues.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    evals = d.get('Eigenvalue_nm2', list(d.values())[1] if len(d) > 1 else list(d.values())[0])

    total = np.sum(evals)
    cum_var = np.cumsum(evals) / total * 100
    frac = evals / total * 100

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))

    # Left: eigenvalue bar chart
    nshow = min(len(evals), 20)
    ax1.bar(np.arange(1, nshow+1), frac[:nshow], color=PALETTE['blue'], alpha=0.7, edgecolor='white')
    ax1.set_xlabel('Eigenvector Index')
    ax1.set_ylabel('Variance Explained (%)')
    ax1.set_title('Eigenvalue Spectrum')

    # Right: cumulative variance
    ax2.plot(np.arange(1, len(cum_var)+1), cum_var, 'o-', color=PALETTE['red'],
             markersize=3, linewidth=1.2)
    ax2.axhline(80, color='grey', linestyle='--', linewidth=0.7, alpha=0.6, label='80%')
    ax2.set_xlabel('Number of Eigenvectors')
    ax2.set_ylabel('Cumulative Variance (%)')
    ax2.set_title('Cumulative Variance')
    ax2.legend(fontsize=8)
    ax2.set_xlim(1, len(cum_var))

    plt.tight_layout()
    save_figure(fig, outdir, 'pca_eigenvalues')
    plt.close(fig)


def plot_pca_2d(adir, outdir):
    """2D projection PC1 vs PC2."""
    csv_path = os.path.join(adir, 'pc2d.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    pc1 = d.get('PC1', list(d.values())[0])
    pc2 = d.get('PC2', list(d.values())[1] if len(d) > 1 else pc1)

    fig, ax = plt.subplots(figsize=(6, 5.5))
    scatter = ax.scatter(pc1, pc2, c=np.arange(len(pc1)), cmap='viridis',
                        s=8, alpha=0.6, edgecolors='none')
    plt.colorbar(scatter, ax=ax, label='Frame')
    ax.set_xlabel('PC 1')
    ax.set_ylabel('PC 2')
    ax.set_title('PCA — 2D Projection (PC1 vs PC2)')
    ax.axhline(0, color='grey', linewidth=0.5, alpha=0.3)
    ax.axvline(0, color='grey', linewidth=0.5, alpha=0.3)
    plt.tight_layout()
    save_figure(fig, outdir, 'pca_2d_projection')
    plt.close(fig)


def plot_pca_projections(adir, outdir):
    """PC1/PC2/PC3 projections over time."""
    csv_path = os.path.join(adir, 'pc_projections.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t = d.get('Time_ps', list(d.values())[0])
    t, tlabel = convert_time(t)
    pcs = [k for k in d if k.startswith('PC')]

    if not pcs:
        return

    fig, axes = plt.subplots(len(pcs), 1, figsize=(8, 2.5 * len(pcs)), sharex=True)
    if len(pcs) == 1:
        axes = [axes]

    for ax, col in zip(axes, pcs):
        vals = d[col]
        # Remove empty values
        mask = ~np.isnan(vals)
        ax.plot(t[mask], vals[mask], color=PALETTE['blue'], linewidth=0.6, alpha=0.85)
        ax.set_ylabel(col)
        ax.axhline(0, color='grey', linewidth=0.5, alpha=0.3)

    axes[-1].set_xlabel(tlabel)
    axes[0].set_title('Principal Component Projections')
    fig.align_ylabels()
    plt.tight_layout()
    save_figure(fig, outdir, 'pca_projections')
    plt.close(fig)


def plot_pca_rmsf(adir, outdir):
    """Per-atom RMSF from PCA."""
    csv_path = os.path.join(adir, 'pca_rmsf.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    atoms = d.get('Atom', np.arange(len(list(d.values())[0])) + 1)
    rmsf = d.get('RMSF_nm', list(d.values())[1] if len(d) > 1 else list(d.values())[0])

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.bar(atoms, rmsf, color=PALETTE['purple'], alpha=0.7, width=0.8)
    ax.set_xlabel('Atom Index')
    ax.set_ylabel('RMSF (nm)')
    ax.set_title('Per-Atom RMSF from Principal Components')
    plt.tight_layout()
    save_figure(fig, outdir, 'pca_rmsf')
    plt.close(fig)


def plot_angle_timeseries(adir, outdir):
    """Angle/dihedral values over time."""
    csv_path = os.path.join(adir, 'angle_timeseries.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t = d.get('Time_ps', list(d.values())[0])
    t, tlabel = convert_time(t)
    ang_col = [k for k in d if 'deg' in k.lower() or 'angle' in k.lower() or 'dihedral' in k.lower()]
    if not ang_col:
        ang_col = [list(d.keys())[1]] if len(d) > 1 else [list(d.keys())[0]]
    vals = d[ang_col[0]]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(t, vals, color=PALETTE['red'], linewidth=0.6, alpha=0.85)
    ax.set_ylabel(f'{ang_col[0]} (°)')
    ax.set_xlabel(tlabel)
    meanv = np.mean(vals)
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.1f}°')
    ax.legend(fontsize=9)
    ax.set_title(f'{ang_col[0]} Time Series')
    plt.tight_layout()
    save_figure(fig, outdir, 'angle_timeseries')
    plt.close(fig)


def plot_angle_distribution(adir, outdir):
    """Angle/dihedral distribution histogram."""
    csv_path = os.path.join(adir, 'angle_distribution.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    ang_col = [k for k in d if 'deg' in k.lower() or 'angle' in k.lower() or 'dihedral' in k.lower()]
    if not ang_col:
        ang_col = [list(d.keys())[0]]
    count_col = [k for k in d if 'count' in k.lower()]
    if not count_col:
        count_col = [list(d.keys())[1]] if len(d) > 1 else [list(d.keys())[0]]

    angles = d[ang_col[0]]
    counts = d[count_col[0]]
    counts = counts / np.max(counts) if np.max(counts) > 0 else counts

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.fill_between(angles, counts, color=PALETTE['blue'], alpha=0.3)
    ax.plot(angles, counts, color=PALETTE['blue'], linewidth=1.2)
    ax.set_xlabel(f'{ang_col[0]} (°)')
    ax.set_ylabel('Normalized Frequency')
    ax.set_title(f'{ang_col[0]} Distribution')
    plt.tight_layout()
    save_figure(fig, outdir, 'angle_distribution')
    plt.close(fig)


# ═══════════════════════════════════════════
# Contact Map Plots
# ═══════════════════════════════════════════

def plot_contact_matrix(adir, outdir):
    """Heatmap of residue/atom distance contacts."""
    csv_path = os.path.join(adir, 'contact_matrix.csv')
    xpm_path = os.path.join(adir, 'contact_matrix.xpm')

    matrix = None
    if os.path.exists(csv_path):
        d = read_csv(csv_path)
        if d:
            # CSV from parsed XPM
            rows = [list(d[k]) for k in d]
            matrix = np.array(rows)
    elif os.path.exists(xpm_path):
        # Parse XPM directly
        try:
            import re
            xpm_text = open(xpm_path).read()
            colors = {}
            pixels = []
            in_pixels = False
            for line in xpm_text.split('\n'):
                line = line.strip()
                if '/* pixels */' in line:
                    in_pixels = True
                    continue
                if not in_pixels:
                    m = re.match(r'"(\S)\s+c\s+(#\S+)"', line)
                    if m:
                        colors[m.group(1)] = m.group(2)
                else:
                    m = re.match(r'"(.*)"[,;]?', line)
                    if m:
                        pixels.append(list(m.group(1)))
            if pixels and colors:
                def hex_to_val(h):
                    h = h.lstrip('#')
                    return (int(h[0:2],16)+int(h[2:4],16)+int(h[4:6],16))/3.0
                gray_map = {k: hex_to_val(v) for k,v in colors.items()}
                max_g = max(gray_map.values()) if gray_map else 255
                matrix = np.array([[1.0 - gray_map.get(ch,0)/max_g if max_g>0 else 0
                                   for ch in row] for row in pixels])
        except Exception:
            pass

    if matrix is None or matrix.size == 0:
        return

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(matrix, cmap='RdYlBu_r', aspect='auto', origin='upper',
                   vmin=0, vmax=np.percentile(matrix, 95) if matrix.size > 1 else 1)
    plt.colorbar(im, ax=ax, label='Contact Strength', shrink=0.8)
    ax.set_xlabel('Group Index')
    ax.set_ylabel('Group Index')
    ax.set_title('Distance Contact Map')
    plt.tight_layout()
    save_figure(fig, outdir, 'contact_matrix')
    plt.close(fig)


def plot_contact_count(adir, outdir):
    """Number of contacts over time."""
    csv_path = os.path.join(adir, 'contact_count.csv')
    if not os.path.exists(csv_path):
        return
    d = read_csv(csv_path)
    if not d:
        return
    t = d.get('Time_ps', list(d.values())[0])
    t, tlabel = convert_time(t)
    n_col = [k for k in d if 'contact' in k.lower() or 'count' in k.lower()]
    if not n_col:
        n_col = [list(d.keys())[1]] if len(d) > 1 else [list(d.keys())[0]]
    counts = d[n_col[0]]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(t, counts, color=PALETTE['teal'], linewidth=0.8, alpha=0.85)
    ax.set_ylabel('Number of Contacts')
    ax.set_xlabel(tlabel)
    meanv = np.mean(counts)
    ax.axhline(meanv, color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {meanv:.0f}')
    ax.legend(fontsize=9)
    ax.set_title('Contact Count over Time')
    plt.tight_layout()
    save_figure(fig, outdir, 'contact_count')
    plt.close(fig)


# ═══════════════════════════════════════════
# Main dispatch
# ═══════════════════════════════════════════
PLOTTERS = {
    'energy':    [plot_energy_timeseries, plot_energy_distribution],
    'hbonds':    [plot_hbonds],
    'rmsd':      [plot_rmsd],
    'rdf':       [plot_rdf],
    'rgyr':      [plot_gyrate],
    'sasa':      [plot_sasa],
    'density':   [plot_density_z],
    'dashboard': [plot_summary_dashboard],
    'meta':      [plot_meta_cv_time, plot_meta_fes],
    'wham':      [plot_wham_pmf],
    'cluster':   [plot_cluster_sizes, plot_cluster_timeline, plot_rmsd_distribution, plot_cluster_scatter],
    'pca':       [plot_pca_eigenvalues, plot_pca_2d, plot_pca_projections, plot_pca_rmsf],
    'dihedral':  [plot_angle_timeseries, plot_angle_distribution],
    'contacts':  [plot_contact_matrix, plot_contact_count],
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GROMACS MD analysis plotting')
    parser.add_argument('analysis_dir', help='Path to analysis/ directory')
    parser.add_argument('--type', default='all', help='Plot type (energy,hbonds,rmsd,rdf,rgyr,sasa,density,dashboard,all)')
    args = parser.parse_args()

    adir = os.path.abspath(args.analysis_dir)
    outdir = os.path.join(adir, 'figures')
    os.makedirs(outdir, exist_ok=True)

    plot_type = args.type.lower()
    print(f'GROMACS Plot → {adir}')

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
