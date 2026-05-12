#!/usr/bin/env python3
"""
sima_plot.py — Plot Simulation Interactions Diagram (.dat) output for Desmond MD.  |  MOTUS v0.0.1
Style follows /home/xenon/xhy/old-sh/data1/raw-data/*.ipynb conventions.

Usage:
  python3 sima_plot.py <analysis_dir>              # Plot all found .dat files
  python3 sima_plot.py <analysis_dir> --type props  # Properties only
  python3 sima_plot.py <analysis_dir> --type torsion # Torsion plots only
"""

import sys, os, argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
from pathlib import Path

# ═══════════════════════════════════════════
# Styling — matching old-sh conventions
# ═══════════════════════════════════════════
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 11,
    'axes.labelsize': 20,
    'axes.titlesize': 20,
    'xtick.labelsize': 20,
    'ytick.labelsize': 20,
    'legend.fontsize': 9,
    'figure.dpi': 400,
    'savefig.dpi': 400,
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
})

# Colors matching old-sh Properties.ipynb
PROP_COLORS = {
    'rmsd':    '#1f77b4',
    'rgyr':    '#2ca02c',
    'intrahb': '#b763fc',
    'molsa':   '#ff7f0e',
    'sasa':    '#17becf',
    'psa':     '#8c564b',
}
PROP_LABELS = {
    'rmsd': 'RMSD', 'rgyr': 'rGyr', 'intrahb': 'IntraHB',
    'molsa': 'MolSA', 'sasa': 'SASA', 'psa': 'PSA',
}
PROP_UNITS = {
    'rmsd': 'Å', 'rgyr': 'Å', 'intrahb': '', 'molsa': 'Å²', 'sasa': 'Å²', 'psa': 'Å²',
}
Y_TICK_INTERVALS = {
    'rmsd': 2.0, 'rgyr': 2.0, 'intrahb': 1.0, 'molsa': 200, 'sasa': 200, 'psa': 100,
}
HIST_BINS = 10


def save_figure(fig, outdir, name, dpi=400):
    os.makedirs(outdir, exist_ok=True)
    pdf = os.path.join(outdir, f'{name}.pdf')
    png = os.path.join(outdir, f'{name}.png')
    fig.savefig(pdf, format='pdf', dpi=dpi)
    fig.savefig(png, format='png', dpi=dpi)
    print(f'  ✓ {name}.pdf + {name}.png')


def read_dat(filepath):
    """Read a .dat file, returning (header, 2D numpy array, metadata dict)."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    metadata, comment_lines = {}, []
    for line in lines:
        if line.startswith('#'):
            comment_lines.append(line.strip('#').strip())
        else:
            break
    for cl in comment_lines:
        sep = '=' if '=' in cl else ':'
        if sep in cl:
            k, v = cl.split(sep, 1)
            metadata[k.strip()] = v.strip()
    data_start = 0
    for i, line in enumerate(lines):
        if not line.startswith('#'):
            data_start = i
            break
    first_row = lines[data_start].strip().split()
    header = None
    try:
        float(first_row[0])
    except ValueError:
        header = first_row
        data_start += 1
    data_rows = []
    for line in lines[data_start:]:
        parts = line.strip().split()
        if parts:
            try:
                data_rows.append([float(x) for x in parts])
            except ValueError:
                pass
    data = np.array(data_rows) if data_rows else np.array([])
    return header, data, metadata


def plot_properties(analysis_dir, outdir):
    """Properties with left time-series + right horizontal histogram (5:1 ratio).

    Style: matches /home/xenon/xhy/old-sh/data1/raw-data/Properties.ipynb
    """
    prop_files = [p for p in Path(analysis_dir).glob('*Properties.dat')
                  if 'P-Properties' not in str(p) or 'L-Properties' in str(p)]
    if not prop_files:
        prop_files = list(Path(analysis_dir).glob('*roperties*.dat'))

    for pf in prop_files:
        header, data, meta = read_dat(str(pf))
        if data.size == 0:
            continue
        basename = Path(pf).stem
        system_name = basename.split('-')[0]
        print(f'  ── Properties: {basename} ──')

        time = data[:, 0]
        if time[-1] > 500:
            time_ns = time / 1000
            tlabel = 'Time (ns)'
        else:
            time_ns = time
            tlabel = 'Time (ps)'

        n_props = min(data.shape[1] - 1, 6)
        metrics = ['rmsd', 'rgyr', 'intrahb', 'molsa', 'sasa', 'psa'][:n_props]

        FIG_WIDTH = 12
        FIG_ROW_HEIGHT = 1.8
        fig = plt.figure(figsize=(FIG_WIDTH, FIG_ROW_HEIGHT * n_props))
        gs = gridspec.GridSpec(n_props, 2, width_ratios=[5, 1], wspace=0.08)

        for i, m in enumerate(metrics):
            ax = plt.subplot(gs[i, 0])
            axh = plt.subplot(gs[i, 1], sharey=ax)
            x = time_ns
            y = data[:, i + 1]
            c = PROP_COLORS.get(m, 'black')

            # Main curve
            ax.plot(x, y, lw=1.3, color=c)

            label = PROP_LABELS.get(m, m)
            unit = PROP_UNITS.get(m, '')
            ax.set_ylabel(f'{label} ({unit})' if unit else label)

            # X label only on bottom row
            ax.set_xlabel(tlabel if i == n_props - 1 else '')

            # Auto y-range with 10% padding
            y_min, y_max = np.nanmin(y), np.nanmax(y)
            if y_max > y_min:
                pad = (y_max - y_min) * 0.1
                ax.set_ylim(y_min - pad, y_max + pad)

            # Y tick interval from dict, fallback to auto
            interval = Y_TICK_INTERVALS.get(m)
            if interval and y_max - y_min > interval:
                ax.yaxis.set_major_locator(ticker.MultipleLocator(interval))

            ax.set_xlim(0, x.max())

            # 4-side borders on main plot
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.8)
                spine.set_color('black')

            # Horizontal histogram on the right
            axh.hist(y, bins=HIST_BINS, orientation='horizontal',
                     color=c, alpha=0.8, edgecolor='black', linewidth=0.8)
            axh.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for spine in axh.spines.values():
                spine.set_visible(True)
                spine.set_color('black')
                spine.set_linewidth(0.8)

        fig.suptitle(f'{system_name} – Ligand Properties', fontsize=13, y=0.995)
        plt.subplots_adjust(left=0.1, right=0.95, top=0.96, bottom=0.05)
        save_figure(fig, outdir, f'sima_properties_{basename}', dpi=400)
        plt.close(fig)


def plot_torsions(analysis_dir, outdir):
    """Heatmap + per-torsion time evolution + distribution + radial plots."""
    tors_files = sorted(Path(analysis_dir).glob('*Torsions*.dat'),
                        key=lambda p: ('L_Torsions' not in str(p), str(p)))

    for tf in tors_files:
        header, data, meta = read_dat(str(tf))
        if data.size == 0:
            continue

        basename = Path(tf).stem
        n_torsions = data.shape[1] - 1
        if n_torsions == 0:
            continue

        print(f'  ── Torsions: {basename} ({n_torsions} torsions) ──')

        time = data[:, 0]
        if time[-1] > 500:
            time_ns = time / 1000
            tlabel = 'Time (ns)'
        else:
            time_ns = time
            tlabel = 'Time (ps)'

        # ── 2D Heatmap ──
        plt.rcParams.update({'font.size': 24})
        fig, ax = plt.subplots(figsize=(12, 8))
        torsion_data = data[:, 1:].T
        im = ax.imshow(torsion_data, aspect='auto', cmap='viridis',
                       extent=[time_ns[0], time_ns[-1], 1, n_torsions])
        cbar = plt.colorbar(im, ax=ax, label='Torsion Angle (°)')
        ax.set_xlabel(tlabel)
        ax.set_ylabel('Torsion Index')
        ax.set_yticks(np.arange(1, n_torsions + 1, 1))
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.8)
            spine.set_color('black')
        plt.tight_layout()
        save_figure(fig, outdir, f'sima_torsion_heatmap_{basename}', dpi=400)
        plt.close(fig)

        # Reset font size for subsequent plots
        plt.rcParams.update({'font.size': 14})

        # ── Per-torsion: time evolution + distribution ──
        for i in range(n_torsions):
            vals = data[:, i + 1]

            # Time evolution (figsize=(10,5))
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(time_ns, vals, alpha=0.8, color='#1f77b4')
            ax.set_xlabel(tlabel)
            ax.set_ylabel('Torsion Angle (°)')
            ax.set_title(f'Torsion {i+1} Angle vs Time')
            ax.grid(True, alpha=0.3)
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.8)
                spine.set_color('black')
            plt.tight_layout()
            save_figure(fig, outdir, f'sima_torsion_{i+1}_time_{basename}', dpi=400)
            plt.close(fig)

            # Probability distribution (figsize=(8,5))
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.hist(vals, bins=50, density=True, alpha=0.7, color='#1f77b4',
                    edgecolor='black', linewidth=0.3)
            ax.set_xlabel('Torsion Angle (°)')
            ax.set_ylabel('Density')
            ax.set_title(f'Distribution for Torsion {i+1}')
            ax.grid(True, alpha=0.3)
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.8)
                spine.set_color('black')
            plt.tight_layout()
            save_figure(fig, outdir, f'sima_torsion_{i+1}_dist_{basename}', dpi=400)
            plt.close(fig)

        # ── Radial plots ──
        max_radial = min(6, n_torsions)
        for i in range(max_radial):
            vals = data[:, i + 1]
            angles_rad = np.radians(vals)
            r = time_ns

            fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(6, 6))
            scatter = ax.scatter(angles_rad, r, c=r, cmap='viridis',
                                 s=10, alpha=0.7, marker='x')
            cbar = plt.colorbar(scatter, ax=ax, label='Time (ns)', shrink=0.8, pad=0.1)

            ax.set_ylim(0, r.max())
            time_ticks = np.linspace(0, r.max(), 6)
            ax.set_yticks(time_ticks)
            ax.set_yticklabels([f'{int(t)} ns' for t in time_ticks], fontsize=10)
            angle_ticks = np.radians([0, 45, 90, 135, 180, 225, 270, 315])
            angle_labels = ['0°', '45°', '90°', '135°', '180°', '-135°', '-90°', '-45°']
            ax.set_xticks(angle_ticks)
            ax.set_xticklabels(angle_labels, fontsize=12)
            ax.set_title(f'Radial Plot for Torsion {i+1}', va='bottom')

            plt.tight_layout()
            save_figure(fig, outdir, f'sima_radial_{basename}_{i+1}', dpi=600)
            plt.close(fig)


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description='Plot Simulation Interactions Diagram .dat output')
    parser.add_argument('analysis_dir', help='Directory with .dat files')
    parser.add_argument('--type', choices=['props', 'torsion', 'all'], default='all')
    args = parser.parse_args()

    analysis_dir = os.path.abspath(args.analysis_dir)
    outdir = os.path.join(analysis_dir, 'figures')
    os.makedirs(outdir, exist_ok=True)

    print(f'📊 SIMA Plot — {analysis_dir}')
    print(f'   Output → {outdir}/\n')

    dat_files = list(Path(analysis_dir).glob('*.dat'))
    if not dat_files:
        print('  ⚠ No .dat files found.')
        sys.exit(1)
    print(f'  Found {len(dat_files)} .dat file(s)\n')

    if args.type in ('props', 'all'):
        plot_properties(analysis_dir, outdir)

    if args.type in ('torsion', 'all'):
        plot_torsions(analysis_dir, outdir)

    print(f'\n✅ Done. Figures saved to {outdir}/')


if __name__ == '__main__':
    main()
