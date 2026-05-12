#!/usr/bin/env python3
"""
desmond_plot.py — Publication-quality plotting for Desmond MD analysis.  |  MOTUS v0.0.1
Reads CSV files produced by desmond-analysis.sh and generates figures.

Usage:
  python3 desmond_plot.py <analysis_dir>                # Plot everything found
  python3 desmond_plot.py <analysis_dir> --type energy   # Only energy plots
  python3 desmond_plot.py <analysis_dir> --no-show       # Don't display, just save

Output:
  <analysis_dir>/figures/*.pdf   (vector, for papers)
  <analysis_dir>/figures/*.png   (raster preview, 300 DPI)
"""

import sys, os, argparse, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')  # headless backend
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path
from collections import defaultdict
from scipy.spatial import ConvexHull

# ═══════════════════════════════════════════
# Publication-quality styling
# ═══════════════════════════════════════════
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans', 'Helvetica'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'axes.linewidth': 1.0,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'xtick.major.size': 4,
    'ytick.major.size': 4,
})

# Nature-inspired color palette
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

def read_csv(path, cols=None):
    """Read CSV file, return dict of column arrays."""
    data = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    if not data:
        return None

    result = {}
    headers = list(data[0].keys())
    for h in headers:
        try:
            result[h.strip()] = np.array([float(r[h]) for r in data])
        except (ValueError, KeyError):
            pass
    return result


def save_figure(fig, outdir, name):
    """Save figure as both PDF and PNG."""
    os.makedirs(outdir, exist_ok=True)
    pdf_path = os.path.join(outdir, f'{name}.pdf')
    png_path = os.path.join(outdir, f'{name}.png')
    fig.savefig(pdf_path, format='pdf')
    fig.savefig(png_path, format='png')
    print(f'  ✓ {name}.pdf + {name}.png')
    return pdf_path


def convert_time_to_ns(time_ps):
    """Convert ps to ns, return time array + unit label."""
    t_max = time_ps[-1] if len(time_ps) > 0 else 0
    if t_max > 5000:
        return time_ps / 1000, 'Time (ns)'
    else:
        return time_ps, 'Time (ps)'


# ═══════════════════════════════════════════
# Individual plot functions
# ═══════════════════════════════════════════

def plot_energy_timeseries(csv_path, outdir):
    """Multi-panel energy time series: T, P, E_pot, Volume."""
    data = read_csv(csv_path)
    if not data:
        print('  ⚠ No energy CSV data found')
        return

    t, tlabel = convert_time_to_ns(data['Time_ps'])

    fig, axes = plt.subplots(4, 1, figsize=(7, 9), sharex=True)

    # Temperature
    ax = axes[0]
    ax.plot(t, data['Temp_K'], color=PALETTE['red'], linewidth=0.6, alpha=0.8)
    ax.set_ylabel('Temperature (K)')
    ax.axhline(np.mean(data['Temp_K']), color='grey', linestyle='--', linewidth=0.8, alpha=0.6)

    # Pressure
    ax = axes[1]
    ax.plot(t, data['Pressure_bar'], color=PALETTE['blue'], linewidth=0.6, alpha=0.8)
    ax.set_ylabel('Pressure (bar)')
    ax.axhline(np.mean(data['Pressure_bar']), color='grey', linestyle='--', linewidth=0.8, alpha=0.6)

    # Potential Energy
    ax = axes[2]
    ax.plot(t, data['Pot_E_kcal'], color=PALETTE['green'], linewidth=0.6, alpha=0.8)
    ax.set_ylabel('$E_{pot}$ (kcal/mol)')

    # Volume
    ax = axes[3]
    ax.plot(t, data['Vol_A3'], color=PALETTE['purple'], linewidth=0.6, alpha=0.8)
    ax.set_ylabel('Volume (Å³)')
    ax.set_xlabel(tlabel)

    for ax in axes:
        ax.ticklabel_format(axis='y', style='scientific', scilimits=(-2, 3))
        ax.yaxis.set_major_locator(ticker.MaxNLocator(5))

    fig.align_ylabels()
    plt.tight_layout()
    save_figure(fig, outdir, 'energy_timeseries')
    plt.close(fig)


def plot_energy_distribution(csv_path, outdir):
    """Distribution histograms for T and E_pot."""
    data = read_csv(csv_path)
    if not data:
        return

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))

    # Temperature distribution
    ax = axes[0]
    temps = data['Temp_K']
    ax.hist(temps, bins=40, color=PALETTE['red'], alpha=0.7, edgecolor='white', linewidth=0.3)
    ax.axvline(np.mean(temps), color='black', linestyle='--', linewidth=1, label=f'Mean = {np.mean(temps):.1f} K')
    ax.axvline(np.mean(temps) - np.std(temps), color='grey', linestyle=':', linewidth=0.8)
    ax.axvline(np.mean(temps) + np.std(temps), color='grey', linestyle=':', linewidth=0.8)
    ax.set_xlabel('Temperature (K)')
    ax.set_ylabel('Frequency')
    ax.legend(fontsize=8)

    # Potential Energy distribution
    ax = axes[1]
    epot = data['Pot_E_kcal']
    ax.hist(epot, bins=40, color=PALETTE['blue'], alpha=0.7, edgecolor='white', linewidth=0.3)
    ax.axvline(np.mean(epot), color='black', linestyle='--', linewidth=1, label=f'Mean = {np.mean(epot):.1f}')
    ax.set_xlabel('$E_{pot}$ (kcal/mol)')
    ax.set_ylabel('Frequency')
    ax.legend(fontsize=8)

    plt.tight_layout()
    save_figure(fig, outdir, 'energy_distribution')
    plt.close(fig)


def plot_hbonds(csv_path, outdir, label=''):
    """H-bond count over time."""
    data = read_csv(csv_path)
    if not data:
        return

    # Find time and count columns
    time_col = None
    count_col = None
    for h in data:
        if 'time' in h.lower() or 'frame' in h.lower():
            time_col = h
        if 'hbond' in h.lower() or 'count' in h.lower() or 'num' in h.lower():
            count_col = h

    if count_col is None:
        # Fallback: assume column 1 is time, column 2 is count
        cols = list(data.keys())
        time_col = cols[0] if len(cols) >= 1 else None
        count_col = cols[1] if len(cols) >= 2 else None

    if time_col is None or count_col is None:
        print('  ⚠ Cannot identify H-bond columns')
        return

    t = data[time_col]
    counts = data[count_col]
    t, tlabel = convert_time_to_ns(t)

    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(t, counts, color=PALETTE['teal'], linewidth=0.8, alpha=0.8)
    ax.set_ylabel('Number of H-bonds')
    ax.set_xlabel(tlabel)
    ax.axhline(np.mean(counts), color='grey', linestyle='--', linewidth=0.8,
               label=f'Avg = {np.mean(counts):.1f}')
    ax.legend(fontsize=9)
    ax.set_title(f'Hydrogen Bonds {label}')

    plt.tight_layout()
    name = f'hbonds{label.replace(" ", "_").lower()}'
    save_figure(fig, outdir, name)
    plt.close(fig)


def plot_water_shells(csv_path, outdir):
    """Water shell populations: bound (<3.5Å), 2nd shell (3.5–5Å), free (>5Å)."""
    data = read_csv(csv_path)
    if not data:
        return

    time_col = [k for k in data if 'time' in k.lower() and 'ps' in k.lower()]
    if not time_col:
        time_col = [k for k in data if 'time' in k.lower()]
    if not time_col:
        time_col = ['Frame']
    time_col = time_col[0]

    # Detect shell columns (Bound, Second, Free, or fallback: water/contact columns)
    shell_keys = []
    for k in data:
        kl = k.lower()
        if kl in ('bound_1st', 'second', 'free'):
            shell_keys.append(k)
    if not shell_keys:
        # Fallback to old format
        val_cols = [k for k in data if 'water' in k.lower() or 'contact' in k.lower()]
        if not val_cols:
            return
        t = data[time_col]
        t, tlabel = convert_time_to_ns(t)
        fig, ax = plt.subplots(figsize=(7, 3))
        for i, col in enumerate(val_cols[:3]):
            ax.plot(t, data[col], color=COLORS[i], linewidth=0.8, alpha=0.7, label=col)
        ax.set_ylabel('Water Count')
        ax.set_xlabel(tlabel)
        ax.legend(fontsize=8)
        ax.set_title('Solute–Water Contacts')
        plt.tight_layout()
        save_figure(fig, outdir, 'solute_water_contacts')
        plt.close(fig)
        return

    t = data[time_col]
    t, tlabel = convert_time_to_ns(t)

    # Dual panel: stacked area over time + average pie
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4),
                                    gridspec_kw={'width_ratios': [2, 1]})

    shell_colors = {'Bound_1st': PALETTE['red'], 'Second': PALETTE['orange'],
                    'Free': PALETTE['blue']}
    shell_labels = {'Bound_1st': 'Bound (<3.5 Å)', 'Second': '2nd shell (3.5–5 Å)',
                    'Free': 'Free (>5 Å)'}

    # Stacked area
    y_stack = np.zeros(len(t))
    for sk in shell_keys:
        vals = data[sk]
        color = shell_colors.get(sk, COLORS[shell_keys.index(sk) % len(COLORS)])
        label = shell_labels.get(sk, sk)
        ax1.fill_between(t, y_stack, y_stack + vals, color=color, alpha=0.55,
                         linewidth=0.3, label=label)
        y_stack = y_stack + vals

    ax1.set_ylabel('Water Molecules')
    ax1.set_xlabel(tlabel)
    ax1.legend(fontsize=8, loc='upper right')
    ax1.set_title('Water Shell Populations')

    # Average pie chart
    avg_vals = [np.mean(data[sk]) for sk in shell_keys]
    pie_labels = [shell_labels.get(sk, sk) for sk in shell_keys]
    pie_colors = [shell_colors.get(sk, COLORS[i % len(COLORS)]) for i, sk in enumerate(shell_keys)]
    wedges, texts, autotexts = ax2.pie(avg_vals, labels=pie_labels, colors=pie_colors,
            autopct='%1.1f%%', textprops={'fontsize': 8})
    ax2.set_title('Average Distribution', fontsize=10)

    plt.tight_layout()
    save_figure(fig, outdir, 'water_shells')
    plt.close(fig)


def plot_contacts(csv_path, outdir):
    """Backward-compatible wrapper for old solute_water_contacts.csv."""
    return plot_water_shells(csv_path, outdir)


def plot_rmsd(csv_path, outdir):
    """RMSD over time (from analyze_simulation output)."""
    data = read_csv(csv_path)
    if not data:
        return

    # Auto-detect columns
    time_col = None
    rmsd_cols = [k for k in data if 'rmsd' in k.lower()]

    for k in data:
        if 'time' in k.lower() or k.lower() == 'frame':
            time_col = k
            break
    if time_col is None:
        time_col = list(data.keys())[0]

    if not rmsd_cols:
        print('  ⚠ No RMSD column found')
        return

    t = data[time_col]
    t, tlabel = convert_time_to_ns(t)

    fig, ax = plt.subplots(figsize=(7, 3.5))
    for i, col in enumerate(rmsd_cols[:4]):
        ax.plot(t, data[col], color=COLORS[i], linewidth=0.8, alpha=0.8, label=col)

    ax.set_ylabel('RMSD (Å)')
    ax.set_xlabel(tlabel)
    ax.legend(fontsize=8)
    ax.set_title('Root Mean Square Deviation')

    plt.tight_layout()
    save_figure(fig, outdir, 'rmsd')
    plt.close(fig)


def plot_rmsf(csv_path, outdir):
    """RMSF / B-factor per residue."""
    data = read_csv(csv_path)
    if not data:
        return

    # Find residue and RMSF columns
    res_col = [k for k in data if 'res' in k.lower() or 'residue' in k.lower()]
    val_col = [k for k in data if 'rmsf' in k.lower() or 'bfactor' in k.lower() or 'bfact' in k.lower()]

    if not res_col:
        res_col = [list(data.keys())[0]]
    if not val_col:
        return

    residues = data[res_col[0]]
    values = data[val_col[0]]

    # If residue column is numeric, use as x directly
    if residues.dtype.kind in 'if':
        x = residues
    else:
        x = np.arange(len(residues))

    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(x, values, color=PALETTE['purple'], alpha=0.7, width=0.8)
    ax.set_ylabel('RMSF (Å)')
    ax.set_xlabel('Residue Index')
    ax.set_title('Per-Residue RMSF / B-Factor')

    plt.tight_layout()
    save_figure(fig, outdir, 'rmsf_bfactor')
    plt.close(fig)


def plot_summary_dashboard(analysis_dir, outdir):
    """Create a summary dashboard combining key metrics."""
    fig = plt.figure(figsize=(10, 8))
    fig.suptitle('MD Simulation Summary Dashboard', fontsize=14, fontweight='bold', y=0.98)

    plots = []
    csv_files = {p.name: p for p in Path(analysis_dir).glob('*.csv')}

    # Grid layout: 2x2
    grid = [(0, 0), (0, 1), (1, 0), (1, 1)]

    idx = 0

    # Energy time series
    if 'energy_timeseries.csv' in csv_files:
        data = read_csv(str(csv_files['energy_timeseries.csv']))
        if data:
            t, tlabel = convert_time_to_ns(data['Time_ps'])
            ax = plt.subplot2grid((2, 2), grid[idx])
            ax.plot(t, data['Temp_K'], color=PALETTE['red'], linewidth=0.5, alpha=0.8)
            ax.set_ylabel('Temperature (K)')
            ax.set_xlabel(tlabel)
            idx += 1

    # Energy distribution
    if 'energy_timeseries.csv' in csv_files and idx < 4:
        ax = plt.subplot2grid((2, 2), grid[idx])
        temps = data['Temp_K']
        ax.hist(temps, bins=30, color=PALETTE['red'], alpha=0.6, edgecolor='white', linewidth=0.2)
        ax.axvline(np.mean(temps), color='black', linestyle='--', linewidth=1)
        ax.set_xlabel(f'T (K), μ={np.mean(temps):.0f}, σ={np.std(temps):.0f}')
        ax.set_ylabel('Count')
        idx += 1

    # H-bonds
    for key in ['hbonds_all.csv', 'hbonds_solute.csv']:
        if key in csv_files and idx < 4:
            hb_data = read_csv(str(csv_files[key]))
            if hb_data:
                ax = plt.subplot2grid((2, 2), grid[idx])
                cols = list(hb_data.keys())
                t = hb_data[cols[0]]
                counts = hb_data[cols[1]] if len(cols) > 1 else hb_data[cols[0]]
                t, tlabel = convert_time_to_ns(t)
                ax.plot(t, counts, color=PALETTE['teal'], linewidth=0.5, alpha=0.8)
                ax.set_ylabel('H-bonds')
                ax.set_xlabel(tlabel)
                ax.set_title(key.replace('hbonds_', '').replace('.csv', ''), fontsize=9)
                idx += 1
                break

    # Solute-water shells
    sw_key = 'solute_water_shells.csv' if 'solute_water_shells.csv' in csv_files else 'solute_water_contacts.csv'
    if sw_key in csv_files and idx < 4:
        sw_data = read_csv(str(csv_files[sw_key]))
        if sw_data:
            ax = plt.subplot2grid((2, 2), grid[idx])
            time_col = [k for k in sw_data if 'time' in k.lower()][0] if any('time' in k.lower() for k in sw_data) else list(sw_data.keys())[1]
            # Try bound column first, else fall back to last column
            bound_cols = [k for k in sw_data if k.lower() in ('bound_1st',)]
            val_col = bound_cols[0] if bound_cols else list(sw_data.keys())[-1]
            t = sw_data[time_col]
            t, tlabel = convert_time_to_ns(t)
            ax.plot(t, sw_data[val_col], color=PALETTE['red'], linewidth=0.5, alpha=0.8, label=val_col)
            ax.set_ylabel('Bound Water')
            ax.set_xlabel(tlabel)
            ax.set_title('Water Shells (Bound <3.5Å)', fontsize=9)
            idx += 1

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save_figure(fig, outdir, 'summary_dashboard')
    plt.close(fig)


def plot_rdf(analysis_dir, outdir):
    """Plot all RDF CSV files with g(r) + coordination number n(r) dual Y-axis."""
    rdf_files = sorted(Path(analysis_dir).glob('rdf_*.csv'))
    if not rdf_files:
        return

    # Group RDFs by category
    element_rdfs = []
    molecule_rdfs = []
    water_rdfs = []

    for f in rdf_files:
        data = read_csv(str(f))
        if not data or 'r_A' not in data or 'g_r' not in data:
            continue
        name = Path(f).stem.replace('rdf_', '')
        if name.startswith('element_'):
            element_rdfs.append((name, data))
        elif name.startswith('molecule_'):
            molecule_rdfs.append((name, data))
        elif name.startswith('water_'):
            water_rdfs.append((name, data))

    # Dual-axis plot helper
    def plot_rdf_cn(ax, d, color_g=PALETTE['blue'], color_n=PALETTE['red'],
                    label_g='g(r)', label_n='n(r)'):
        """Plot g(r) on left axis, n(r) on right axis."""
        r, g = d['r_A'], d['g_r']
        ax.plot(r, g, color=color_g, linewidth=0.8, label=label_g)
        ax.set_xlabel('r (Å)', fontsize=8)
        ax.set_ylabel('g(r)', fontsize=8, color=color_g)
        ax.tick_params(axis='y', labelcolor=color_g, labelsize=7)
        ax.tick_params(axis='x', labelsize=7)
        ax.set_xlim(0, r[-1])

        # Right axis: coordination number
        if 'n_r' in d:
            ax2 = ax.twinx()
            ax2.plot(r, d['n_r'], color=color_n, linewidth=0.8, linestyle='--', label=label_n)
            ax2.set_ylabel('n(r)', fontsize=8, color=color_n)
            ax2.tick_params(axis='y', labelcolor=color_n, labelsize=7)
            # Combine legends
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc='upper left')
        else:
            ax.legend(fontsize=7)

    # ── Element-pair RDFs ──
    if element_rdfs:
        n = len(element_rdfs)
        n_cols = min(3, n)
        n_rows = int(np.ceil(n / n_cols))
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 4.0, n_rows * 3.0),
                                  squeeze=False)
        fig.suptitle('Element-Pair RDF + Coordination Number', fontsize=12, fontweight='bold')
        for idx, (name, d) in enumerate(element_rdfs):
            ax = axes[idx // n_cols][idx % n_cols]
            label = name.replace('element_', '').replace('_', '–')
            plot_rdf_cn(ax, d)
            ax.set_title(label, fontsize=9)
        # Hide unused
        for i in range(n, n_rows * n_cols):
            axes[i // n_cols][i % n_cols].set_visible(False)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        save_figure(fig, outdir, 'rdf_elements')
        plt.close(fig)
        print('  ── RDF: Elements (g(r)+n(r)) ──')
        print(f'    ✓ rdf_elements.pdf + rdf_elements.png')

    # ── Molecule RDFs (self vs inter overlay, each with CN) ──
    if molecule_rdfs:
        self_map = {}
        inter_map = {}
        for name, d in molecule_rdfs:
            sig = name.replace('molecule_', '')
            if sig.endswith('_self'):
                self_map[sig[:-5]] = d
            elif sig.endswith('_inter'):
                inter_map[sig[:-6]] = d
            else:
                self_map[sig] = d

        all_sigs = sorted(set(list(self_map.keys()) + list(inter_map.keys())))
        for sig in all_sigs:
            fig, ax = plt.subplots(figsize=(6, 4.0))
            title = f'Molecular RDF + CN — {sig[:25]}'
            # Plot with distinct colors
            colors_g = [PALETTE['blue'], PALETTE['green']]
            colors_n = [PALETTE['red'], PALETTE['orange']]
            line_idx = 0

            if sig in self_map:
                r, g = self_map[sig]['r_A'], self_map[sig]['g_r']
                ax.plot(r, g, color=colors_g[line_idx], linewidth=0.8, label='g(r) intra')
                if 'n_r' in self_map[sig]:
                    ax2 = ax.twinx()
                    ax2.plot(r, self_map[sig]['n_r'], color=colors_n[line_idx], linewidth=0.8,
                             linestyle='--', label='n(r) intra')
                    ax2.set_ylabel('n(r)', fontsize=8, color=colors_n[line_idx])
                    ax2.tick_params(axis='y', labelcolor=colors_n[line_idx], labelsize=7)
                line_idx = 1
            else:
                ax2 = ax.twinx()
                ax2.set_ylabel('n(r)', fontsize=8)

            if sig in inter_map:
                r, g = inter_map[sig]['r_A'], inter_map[sig]['g_r']
                ax.plot(r, g, color=colors_g[line_idx], linewidth=0.8, label='g(r) inter')
                if 'n_r' in inter_map[sig]:
                    ax2.plot(r, inter_map[sig]['n_r'], color=colors_n[line_idx], linewidth=0.8,
                             linestyle='--', label='n(r) inter')

            ax.set_xlabel('r (Å)')
            ax.set_ylabel('g(r)', fontsize=8, color=PALETTE['blue'])
            ax.tick_params(axis='y', labelcolor=PALETTE['blue'], labelsize=7)
            ax.tick_params(axis='x', labelsize=7)
            ax.set_xlim(0, (self_map.get(sig) or inter_map.get(sig))['r_A'][-1])

            # Merged legend
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc='upper right')
            ax.set_title(title)

            plt.tight_layout()
            save_figure(fig, outdir, f'rdf_molecule_{sig[:20]}')
            plt.close(fig)
        print('  ── RDF: Molecules (g(r)+n(r)) ──')

    # ── Water shell RDFs ──
    if water_rdfs:
        n = len(water_rdfs)
        n_cols = min(2, n)
        n_rows = int(np.ceil(n / n_cols))
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 5.5, n_rows * 3.8),
                                  squeeze=False)
        fig.suptitle('Water Shell RDF + Coordination Number', fontsize=12, fontweight='bold')
        water_labels = {
            'bound_solute': 'Bound Water – Solute',
            'free_solute': 'Free Water – Solute',
            'bound_bound': 'Bound Water – Bound Water',
            'free_free': 'Free Water – Free Water',
        }
        for idx, (name, d) in enumerate(water_rdfs):
            ax = axes[idx // n_cols][idx % n_cols]
            label = water_labels.get(name, name)
            plot_rdf_cn(ax, d)
            # Highlight first peak
            r, g = d['r_A'], d['g_r']
            peak_idx = np.argmax(g)
            ax.axvline(r[peak_idx], color='gray', linestyle=':', linewidth=0.6,
                       label=f'1st peak: {r[peak_idx]:.2f} Å')
            ax.set_title(label)
        for i in range(n, n_rows * n_cols):
            axes[i // n_cols][i % n_cols].set_visible(False)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        save_figure(fig, outdir, 'rdf_water')
        plt.close(fig)
        print('  ── RDF: Water Shells (g(r)+n(r)) ──')
        print(f'    ✓ rdf_water.pdf + rdf_water.png')


def plot_density(analysis_dir, outdir):
    """Plot 1D density profiles and 2D density heatmaps."""
    density_files = sorted(Path(analysis_dir).glob('density_*.csv'))
    if not density_files:
        return

    # Separate 1D and 2D
    files_1d = []  # (name, data)
    files_2d = []

    for f in density_files:
        fname = Path(f).stem.replace('density_', '')
        if '2d' not in fname:
            data = read_csv(str(f))
            if data:
                files_1d.append((fname, data))
        else:
            files_2d.append((fname, f))

    # ── 1D density profiles ──
    if files_1d:
        # Group by selection
        sel_groups = defaultdict(list)
        for name, d in files_1d:
            # name format: 1d_water_X, 1d_solute_Y, etc.
            parts = name.split('_')
            sel_name = parts[1] if len(parts) >= 2 else 'unknown'
            axis = parts[-1] if parts[-1] in ('X', 'Y', 'Z') else '?'
            sel_groups[sel_name].append((axis, d, name))

        for sel_name, items in sel_groups.items():
            fig, axes = plt.subplots(len(items), 1, figsize=(8, 2.2 * len(items)),
                                     squeeze=False)
            fig.suptitle(f'Density Profile — {sel_name}', fontsize=12, fontweight='bold')

            for idx, (axis, d, name) in enumerate(sorted(items)):
                ax = axes[idx][0]
                x_key = [k for k in d.keys() if 'A' in k or 'axis' in k.lower()][0]
                y_key = [k for k in d.keys() if 'density' in k.lower() or 'relative' in k.lower()][0]
                ax.plot(d[x_key], d[y_key], color=PALETTE['blue'], linewidth=1.0)
                ax.fill_between(d[x_key], d[y_key], alpha=0.15, color=PALETTE['blue'])
                ax.axhline(y=1.0, color='grey', linestyle='--', linewidth=0.5, label='Bulk (1.0)')
                ax.set_xlabel(f'{axis} (Å)', fontsize=8)
                ax.set_ylabel('Rel. Density', fontsize=8)
                ax.tick_params(labelsize=7)
                ax.legend(fontsize=7, loc='upper right')

            plt.tight_layout(rect=[0, 0, 1, 0.95])
            save_figure(fig, outdir, f'density_1d_{sel_name}')
            plt.close(fig)

        print('  ── Density: 1D Profiles ──')

    # ── 2D density heatmaps ──
    if files_2d:
        for fname, fpath in files_2d:
            with open(str(fpath)) as fh:
                first_line = fh.readline()
            hist = np.loadtxt(str(fpath), delimiter=',', skiprows=1)
            sel_plane = fname.replace('2d_', '')

            fig, ax = plt.subplots(figsize=(6, 5))
            im = ax.imshow(hist.T, origin='lower', aspect='auto', cmap='YlOrRd',
                           interpolation='bilinear')
            plt.colorbar(im, ax=ax, label='Rel. Density', shrink=0.85)
            ax.set_xlabel(f'{sel_plane.split("_")[-1][0]} (bin)', fontsize=9)
            ax.set_ylabel(f'{sel_plane.split("_")[-1][1]} (bin)', fontsize=9)
            ax.set_title(f'2D Density Map — {sel_plane}', fontsize=11)
            plt.tight_layout()
            save_figure(fig, outdir, f'density_{fname}')
            plt.close(fig)

        print('  ── Density: 2D Maps ──')


def plot_rg(analysis_dir, outdir):
    """Plot radius of gyration over time."""
    rg_files = sorted(Path(analysis_dir).glob('rg_*.csv'))
    if not rg_files:
        return

    for f in rg_files:
        data = read_csv(str(f))
        if not data:
            continue
        mol_name = Path(f).stem.replace('rg_', '')

        t, tlabel = convert_time_to_ns(data['Time_ps'])
        rg = data['Rg_A']

        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.plot(t, rg, color=PALETTE['blue'], linewidth=1.0)
        if 'Rg_std_A' in data:
            ax.fill_between(t, rg - data['Rg_std_A'], rg + data['Rg_std_A'],
                            alpha=0.15, color=PALETTE['blue'])

        ax.axhline(y=np.mean(rg), color=PALETTE['red'], linestyle='--', linewidth=0.6,
                   label=f'Mean: {np.mean(rg):.2f} Å')
        ax.set_xlabel(tlabel, fontsize=9)
        ax.set_ylabel('Rg (Å)', fontsize=9)
        ax.set_title(f'Radius of Gyration — {mol_name}', fontsize=11)
        ax.legend(fontsize=8)
        ax.tick_params(labelsize=8)
        plt.tight_layout()
        save_figure(fig, outdir, f'rg_{mol_name}')
        plt.close(fig)

    print('  ── Radius of Gyration ──')


def plot_distance(analysis_dir, outdir):
    """Plot monitored atom-pair distances over time."""
    dist_files = sorted(Path(analysis_dir).glob('distance_*.csv'))
    if not dist_files:
        return

    if len(dist_files) <= 4:
        # Single panel per distance
        for f in dist_files:
            data = read_csv(str(f))
            if not data:
                continue
            name = Path(f).stem.replace('distance_', '').replace('_', '-')
            t, tlabel = convert_time_to_ns(data['Time_ps'])
            d = data['Distance_A']

            fig, ax = plt.subplots(figsize=(7, 3.5))
            ax.plot(t, d, color=PALETTE['blue'], linewidth=1.0)
            ax.axhline(y=np.mean(d), color=PALETTE['red'], linestyle='--', linewidth=0.6,
                       label=f'Mean: {np.mean(d):.2f} Å')
            ax.set_xlabel(tlabel, fontsize=9)
            ax.set_ylabel('Distance (Å)', fontsize=9)
            ax.set_title(f'Distance — {name}', fontsize=11)
            ax.legend(fontsize=8)
            ax.tick_params(labelsize=8)
            plt.tight_layout()
            save_figure(fig, outdir, f'distance_{Path(f).stem}')
            plt.close(fig)
    else:
        # Multi-panel overview
        n = len(dist_files)
        n_cols = min(2, n)
        n_rows = int(np.ceil(n / n_cols))
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 6, n_rows * 2.5),
                                  squeeze=False)
        fig.suptitle('Monitored Distances', fontsize=12, fontweight='bold')
        for idx, f in enumerate(dist_files):
            ax = axes[idx // n_cols][idx % n_cols]
            data = read_csv(str(f))
            if not data:
                continue
            name = Path(f).stem.replace('distance_', '').replace('_', '-')
            t, tlabel = convert_time_to_ns(data['Time_ps'])
            ax.plot(t, data['Distance_A'], color=PALETTE['blue'], linewidth=0.8)
            ax.set_xlabel(tlabel, fontsize=7)
            ax.set_ylabel('Å', fontsize=7)
            ax.set_title(name, fontsize=8)
            ax.tick_params(labelsize=6)
        for i in range(n, n_rows * n_cols):
            axes[i // n_cols][i % n_cols].set_visible(False)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        save_figure(fig, outdir, 'distance_overview')
        plt.close(fig)

    print('  ── Distance Monitoring ──')


def plot_water_residence(analysis_dir, outdir):
    """Plot water residence time survival curve and shell occupancy."""
    surv_file = Path(analysis_dir) / 'water_residence_survival.csv'
    occ_file = Path(analysis_dir) / 'water_residence_occupancy.csv'

    if not surv_file.exists():
        return

    data_s = read_csv(str(surv_file))
    if not data_s:
        return

    t = data_s['Time_ps']
    s = data_s['Survival_Probability']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Survival curve
    ax1.plot(t, s, color=PALETTE['blue'], linewidth=1.5)
    ax1.axhline(y=1.0/np.e, color='grey', linestyle=':', linewidth=0.6, label='1/e')
    # Find τ
    tau_idx = np.argmin(np.abs(s - 1.0/np.e))
    if tau_idx < len(t):
        ax1.axvline(x=t[tau_idx], color=PALETTE['red'], linestyle='--', linewidth=0.8,
                    label=f'τ = {t[tau_idx]:.1f} ps')
    ax1.set_xlabel('Time (ps)', fontsize=9)
    ax1.set_ylabel('Survival Probability S(t)', fontsize=9)
    ax1.set_title('Water Residence Survival', fontsize=11)
    ax1.legend(fontsize=8)
    ax1.tick_params(labelsize=8)

    # Shell occupancy
    if occ_file.exists():
        data_o = read_csv(str(occ_file))
        if data_o:
            t_o = data_o['Time_ps']
            count = data_o['Shell_Water_Count']
            ax2.plot(t_o, count, color=PALETTE['green'], linewidth=0.8)
            ax2.axhline(y=count.mean(), color=PALETTE['red'], linestyle='--', linewidth=0.6,
                        label=f'Mean: {count.mean():.1f}')
            ax2.set_xlabel('Time (ps)', fontsize=9)
            ax2.set_ylabel('Shell Water Count', fontsize=9)
            ax2.set_title('Shell Occupancy', fontsize=11)
            ax2.legend(fontsize=8)
            ax2.tick_params(labelsize=8)

    plt.tight_layout()
    save_figure(fig, outdir, 'water_residence')
    plt.close(fig)
    print('  ── Water Residence Time ──')


def plot_dipole(analysis_dir, outdir):
    """Plot molecular dipole moment over time."""
    dip_files = sorted(Path(analysis_dir).glob('dipole_*.csv'))
    if not dip_files:
        return

    for f in dip_files:
        data = read_csv(str(f))
        if not data:
            continue
        name = Path(f).stem.replace('dipole_', '')

        t, tlabel = convert_time_to_ns(data['Time_ps'])
        mu_mag = data['Mu_Mag_D']

        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.plot(t, mu_mag, color=PALETTE['purple'], linewidth=1.0)
        ax.axhline(y=np.mean(mu_mag), color=PALETTE['red'], linestyle='--', linewidth=0.6,
                   label=f'Mean: {np.mean(mu_mag):.2f} D')
        ax.fill_between(t, mu_mag, alpha=0.1, color=PALETTE['purple'])
        ax.set_xlabel(tlabel, fontsize=9)
        ax.set_ylabel('Dipole Moment (Debye)', fontsize=9)
        ax.set_title(f'Molecular Dipole — {name}', fontsize=11)
        ax.legend(fontsize=8)
        ax.tick_params(labelsize=8)
        plt.tight_layout()
        save_figure(fig, outdir, f'dipole_{name}')
        plt.close(fig)

    # If total dipole exists, plot components too
    total_file = Path(analysis_dir) / 'dipole_total.csv'
    if total_file.exists():
        data = read_csv(str(total_file))
        if data and all(k in data for k in ['Mu_X_D', 'Mu_Y_D', 'Mu_Z_D']):
            t, tlabel = convert_time_to_ns(data['Time_ps'])
            fig, ax = plt.subplots(figsize=(7, 3.5))
            for comp, color in [('Mu_X_D', PALETTE['red']), ('Mu_Y_D', PALETTE['green']),
                                 ('Mu_Z_D', PALETTE['blue'])]:
                ax.plot(t, data[comp], color=color, linewidth=0.8, label=comp.replace('_D', ''))
            ax.set_xlabel(tlabel, fontsize=9)
            ax.set_ylabel('Dipole (Debye)', fontsize=9)
            ax.set_title('Dipole Moment Components', fontsize=11)
            ax.legend(fontsize=8, ncol=3)
            ax.tick_params(labelsize=8)
            plt.tight_layout()
            save_figure(fig, outdir, 'dipole_components')
            plt.close(fig)

    print('  ── Dipole / ESP ──')


def plot_free_volume(analysis_dir, outdir):
    """Plot free volume and fractional free volume over time."""
    fv_file = Path(analysis_dir) / 'free_volume.csv'
    if not fv_file.exists():
        return

    data = read_csv(str(fv_file))
    if not data:
        return

    t, tlabel = convert_time_to_ns(data['Time_ps'])
    fv = data['FreeVol_A3']
    ffv = data['FFV'] * 100  # percentage
    bv = data['BoxVol_A3']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Free volume
    ax1.plot(t, fv, color=PALETTE['teal'], linewidth=1.0)
    ax1.axhline(y=np.mean(fv), color=PALETTE['red'], linestyle='--', linewidth=0.6,
                label=f'Mean: {np.mean(fv):.0f} Å³')
    ax1.fill_between(t, fv, alpha=0.1, color=PALETTE['teal'])
    ax1.set_xlabel(tlabel, fontsize=9)
    ax1.set_ylabel('Free Volume (Å³)', fontsize=9)
    ax1.set_title('Free Volume', fontsize=11)
    ax1.legend(fontsize=8)
    ax1.tick_params(labelsize=8)

    # FFV
    ax2.plot(t, ffv, color=PALETTE['blue'], linewidth=1.0)
    ax2.axhline(y=np.mean(ffv), color=PALETTE['red'], linestyle='--', linewidth=0.6,
                label=f'Mean: {np.mean(ffv):.1f}%')
    ax2.fill_between(t, ffv, alpha=0.1, color=PALETTE['blue'])
    ax2.set_xlabel(tlabel, fontsize=9)
    ax2.set_ylabel('FFV (%)', fontsize=9)
    ax2.set_title('Fractional Free Volume', fontsize=11)
    ax2.legend(fontsize=8)
    ax2.tick_params(labelsize=8)

    plt.tight_layout()
    save_figure(fig, outdir, 'free_volume')
    plt.close(fig)
    print('  ── Free Volume ──')


def plot_cluster_scatter(analysis_dir, outdir):
    """Plot PCA projection scatter colored by cluster (ML-style)."""
    pca_file = Path(analysis_dir) / 'cluster_pca.csv'
    meta_file = Path(analysis_dir) / 'cluster_pca_meta.csv'

    if not pca_file.exists():
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
    if meta_file.exists():
        with open(meta_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['PC'] == 'PC1':
                    var1 = float(row['Variance_Explained'])
                elif row['PC'] == 'PC2':
                    var2 = float(row['Variance_Explained'])

    # Color palette
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

        # Convex hull polygon (if ≥3 points)
        if mask.sum() >= 3:
            try:
                hull = ConvexHull(pts)
                hull_pts = pts[hull.vertices]
                # Close the polygon
                hull_pts = np.vstack([hull_pts, hull_pts[0]])
                ax.fill(hull_pts[:, 0], hull_pts[:, 1], alpha=0.08,
                        color=color, edgecolor=color, linewidth=0.8,
                        linestyle='--')
            except Exception:
                pass

    # Cluster centroids
    for c in unique_clusters:
        mask = clusters == c
        cx, cy = pc1[mask].mean(), pc2[mask].mean()
        ax.scatter([cx], [cy], s=180, c='white', edgecolors=cluster_colors[c],
                   linewidth=2, zorder=10, marker='D')
        ax.annotate(f'{c}', (cx, cy), fontsize=9, ha='center', va='center',
                    fontweight='bold', color=cluster_colors[c], zorder=11)

    ax.set_xlabel(f'PC1 ({var1:.1f}%)', fontsize=10)
    ax.set_ylabel(f'PC2 ({var2:.1f}%)', fontsize=10)
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

    ax.set_xlabel(f'PC1 ({var1:.1f}%)', fontsize=10)
    ax.set_ylabel(f'PC2 ({var2:.1f}%)', fontsize=10)
    ax.set_title('Conformational Landscape — Time Evolution', fontsize=12, fontweight='bold')
    ax.tick_params(labelsize=8)

    plt.tight_layout()
    save_figure(fig, outdir, 'cluster_pca_timeline')
    plt.close(fig)

    print('  ── PCA Scatter ──')
    return True


def plot_cluster(analysis_dir, outdir):
    """Plot clustering results: RMSD matrix heatmap + cluster timeline."""
    matrix_file = Path(analysis_dir) / 'cluster_rmsd_matrix.csv'
    summary_file = Path(analysis_dir) / 'cluster_summary.csv'
    timeline_file = Path(analysis_dir) / 'cluster_timeline.csv'

    has_data = False

    # RMSD matrix heatmap
    if matrix_file.exists():
        data = np.loadtxt(str(matrix_file), delimiter=',', skiprows=1)
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(data, cmap='YlOrRd', aspect='auto', interpolation='bilinear')
        plt.colorbar(im, ax=ax, label='RMSD (Å)', shrink=0.85)
        ax.set_xlabel('Frame', fontsize=9)
        ax.set_ylabel('Frame', fontsize=9)
        ax.set_title('Pairwise RMSD Matrix', fontsize=11)
        plt.tight_layout()
        save_figure(fig, outdir, 'cluster_rmsd_matrix')
        plt.close(fig)
        has_data = True

    # Cluster sizes bar chart
    if summary_file.exists():
        clusters = []
        sizes = []
        fractions = []
        with open(summary_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                clusters.append(int(row['Cluster']))
                sizes.append(int(row['Size']))
                fractions.append(float(row['Fraction']) * 100)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

        colors = [PALETTE[c] for c in ['blue', 'red', 'green', 'orange', 'purple', 'teal', 'pink', 'grey']]
        ax1.bar(clusters, sizes, color=colors[:len(clusters)])
        ax1.set_xlabel('Cluster', fontsize=9)
        ax1.set_ylabel('Population (frames)', fontsize=9)
        ax1.set_title('Cluster Populations', fontsize=11)
        ax1.tick_params(labelsize=8)

        ax2.pie(fractions, labels=[f'C{c}' for c in clusters],
                autopct='%1.1f%%', colors=colors[:len(clusters)],
                textprops={'fontsize': 8})
        ax2.set_title('Cluster Distribution', fontsize=11)

        plt.tight_layout()
        save_figure(fig, outdir, 'cluster_population')
        plt.close(fig)
        has_data = True

    # Cluster timeline
    if timeline_file.exists():
        data = read_csv(str(timeline_file))
        if data:
            cluster_cols = [k for k in data.keys() if k.startswith('Cluster_')]
            if cluster_cols:
                t = data['Time_ps']
                fig, ax = plt.subplots(figsize=(10, 2.5))
                # Stack cluster membership as colored bands
                n_clusters = len(cluster_cols)
                y = np.zeros(len(t))
                colors = [PALETTE[c] for c in ['blue', 'red', 'green', 'orange', 'purple', 'teal', 'pink', 'grey']]
                for ci, col in enumerate(cluster_cols):
                    mask = data[col] > 0.5
                    ax.fill_between(t, 0, 1, where=mask,
                                    color=colors[ci % len(colors)], alpha=0.6,
                                    label=f'C{ci+1}', step='post')
                ax.set_xlabel('Time (ps)', fontsize=9)
                ax.set_ylabel('Cluster', fontsize=9)
                ax.set_title('Cluster Timeline', fontsize=11)
                ax.set_ylim(0, 1)
                ax.set_yticks([])
                ax.legend(fontsize=7, ncol=n_clusters, loc='upper right')
                ax.tick_params(labelsize=8)
                plt.tight_layout()
                save_figure(fig, outdir, 'cluster_timeline')
                plt.close(fig)
                has_data = True

    if has_data:
        print('  ── Conformational Clustering ──')


def plot_meta(analysis_dir, outdir):
    """Plot metadynamics results: CV timeseries, height, and FES."""
    
    # --- CV Time Series ---
    cv_csv = os.path.join(analysis_dir, 'meta_cv_time.csv')
    if not os.path.exists(cv_csv):
        print('  ⚠ No meta_cv_time.csv found')
        return
    
    data = read_csv(cv_csv)
    if not data:
        return
    
    cv_cols = sorted([k for k in data if k.startswith('CV_')])
    t_raw = data['Time_ps']
    t_label = 'Time (ps)' if t_raw[-1] < 5000 else 'Time (ns)'
    t = t_raw / 1000 if t_raw[-1] > 5000 else t_raw
    
    n_cv = len(cv_cols)
    
    # Figure 1: CV time evolution
    fig, axes = plt.subplots(n_cv, 1, figsize=(8, 2.5 * n_cv), sharex=True)
    if n_cv == 1:
        axes = [axes]
    
    for i, cvk in enumerate(cv_cols):
        ax = axes[i]
        ax.plot(t, data[cvk], color=COLORS[i % len(COLORS)], linewidth=0.6, alpha=0.8)
        ax.set_ylabel(f'CV {i}')
        ax.set_xlabel(t_label)
        ax.grid(True, alpha=0.3)
        # Horizontal reference at y=0
        ax.axhline(y=0, color='grey', linestyle='--', linewidth=0.5, alpha=0.5)
    
    save_figure(fig, outdir, 'meta_cv_time')
    plt.close(fig)
    
    # Figure 2: Height over time
    height_csv = os.path.join(analysis_dir, 'meta_height.csv')
    if os.path.exists(height_csv):
        hdata = read_csv(height_csv)
        if hdata and len(hdata.get('Height_kcal_mol', [])) > 0:
            ht = hdata['Time_ps']
            h_label = 'Time (ps)' if ht[-1] < 5000 else 'Time (ns)'
            ht_plot = ht / 1000 if ht[-1] > 5000 else ht
            
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(ht_plot, hdata['Height_kcal_mol'], color=PALETTE['orange'], linewidth=0.8)
            ax.set_xlabel(h_label)
            ax.set_ylabel('Gaussian Height (kcal/mol)')
            ax.grid(True, alpha=0.3)
            save_figure(fig, outdir, 'meta_height')
            plt.close(fig)
    
    # Figure 3: FES (1D or 2D)
    fes_files = sorted(Path(analysis_dir).glob('meta_fes_*.csv'))
    for fes_path in fes_files:
        fes_data = read_csv(str(fes_path))
        if not fes_data:
            continue
        
        fes_name = fes_path.stem  # meta_fes_1d or meta_fes_2d
        
        if '1d' in fes_name:
            # 1D FES: line plot
            fig, ax = plt.subplots(figsize=(7, 4))
            cv_key = [k for k in fes_data if k.startswith('CV_')][0]
            ax.plot(fes_data[cv_key], fes_data['Free_Energy_kcal_mol'], 
                    color=PALETTE['blue'], linewidth=1.0)
            ax.set_xlabel('CV 0')
            ax.set_ylabel('Free Energy (kcal/mol)')
            ax.grid(True, alpha=0.3)
            save_figure(fig, outdir, 'meta_fes_1d')
            plt.close(fig)
        
        elif '2d' in fes_name:
            # 2D FES: contour + pcolormesh
            # Reconstruct from scattered data
            cv_keys = sorted([k for k in fes_data if k.startswith('CV_')])
            if len(cv_keys) >= 2:
                x = fes_data[cv_keys[0]]
                y = fes_data[cv_keys[1]]
                z = fes_data['Free_Energy_kcal_mol']
                
                # Determine grid dimensions from bins
                n_unique_x = len(set(np.round(x, 6)))
                n_unique_y = len(set(np.round(y, 6)))
                if n_unique_x < 2 or n_unique_y < 2:
                    print(f'  ⚠ FES grid too small: {n_unique_x}×{n_unique_y}')
                    continue
                
                nx = int(np.sqrt(len(x) * n_unique_x / n_unique_y))
                ny = len(x) // nx
                if nx * ny != len(x):
                    # Try to infer from data pattern
                    for test_nx in range(10, 100):
                        if len(x) % test_nx == 0:
                            nx = test_nx
                            ny = len(x) // nx
                            break
                
                try:
                    X = x.reshape(ny, nx)
                    Y = y.reshape(ny, nx)
                    Z = z.reshape(ny, nx)
                except ValueError:
                    print('  ⚠ Could not reshape FES grid')
                    continue
                
                # Shift FES to min=0
                Z = Z - np.nanmin(Z)
                
                fig, ax = plt.subplots(figsize=(8, 6))
                levels = np.linspace(0, np.nanmax(Z) * 0.8, 15)
                cf = ax.contourf(X, Y, Z, levels=levels, cmap='RdYlBu_r', extend='max')
                ax.contour(X, Y, Z, levels=levels, colors='black', linewidths=0.2, alpha=0.5)
                cbar = fig.colorbar(cf, ax=ax, label='Free Energy (kcal/mol)', shrink=0.85)
                ax.set_xlabel('CV 0')
                ax.set_ylabel('CV 1')
                ax.set_title('Free Energy Surface')
                save_figure(fig, outdir, 'meta_fes_2d')
                plt.close(fig)
    
    print('  ── Metadynamics ──')


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Desmond MD publication-quality plotting')
    parser.add_argument('analysis_dir', help='Path to analysis directory (with CSV files)')
    parser.add_argument('--type', choices=['energy', 'hbonds', 'water_shells', 'contacts', 'rmsd', 'rmsf', 'rdf', 'density', 'rg', 'distance', 'water_res', 'dipole', 'freevol', 'cluster', 'meta', 'dashboard', 'all'],
                        default='all', help='Plot type')
    parser.add_argument('--dpi', type=int, default=300, help='Output DPI (default: 300)')
    args = parser.parse_args()

    analysis_dir = os.path.abspath(args.analysis_dir)
    outdir = os.path.join(analysis_dir, 'figures')

    if args.dpi != 300:
        plt.rcParams['savefig.dpi'] = args.dpi

    print(f'📊 Desmond Plot — {analysis_dir}')
    print(f'   Output → {outdir}/\n')

    # Collect available CSV files
    csv_files = {p.name: str(p) for p in Path(analysis_dir).glob('*.csv')}

    if not csv_files:
        print('  ⚠ No CSV files found in analysis directory.')
        sys.exit(1)

    plot_type = args.type

    # Energy plots
    if plot_type in ('energy', 'all'):
        if 'energy_timeseries.csv' in csv_files:
            print('── Energy Time Series ──')
            plot_energy_timeseries(csv_files['energy_timeseries.csv'], outdir)
            print('── Energy Distribution ──')
            plot_energy_distribution(csv_files['energy_timeseries.csv'], outdir)

    # H-bond plots
    if plot_type in ('hbonds', 'all'):
        for key, label_suffix in [('hbonds_all.csv', '(All)'), ('hbonds_solute.csv', '(Solute)')]:
            if key in csv_files:
                print(f'── H-Bonds {label_suffix} ──')
                plot_hbonds(csv_files[key], outdir, label_suffix)

    # Solute-water shells / contacts
    if plot_type in ('water_shells', 'contacts', 'all'):
        shell_csv = csv_files.get('solute_water_shells.csv')
        if shell_csv:
            print('── Water Shells (Free vs Bound) ──')
            plot_water_shells(shell_csv, outdir)
        elif 'solute_water_contacts.csv' in csv_files:
            print('── Solute-Water Contacts ──')
            plot_contacts(csv_files['solute_water_contacts.csv'], outdir)

    # RMSD / RMSF
    if plot_type in ('rmsd', 'rmsf', 'all'):
        for fname in csv_files:
            if 'rmsd' in fname.lower() and fname != 'rmsf_bfactor.csv' and 'cluster' not in fname.lower() and 'matrix' not in fname.lower():
                print(f'── RMSD: {fname} ──')
                plot_rmsd(csv_files[fname], outdir)
            if ('rmsf' in fname.lower() or 'bfactor' in fname.lower()) and fname.endswith('.csv'):
                print(f'── RMSF: {fname} ──')
                plot_rmsf(csv_files[fname], outdir)

    # RDF
    if plot_type in ('rdf', 'all'):
        rdf_files = list(Path(analysis_dir).glob('rdf_*.csv'))
        if rdf_files:
            print('── Radial Distribution Functions ──')
            plot_rdf(analysis_dir, outdir)

    # Density cross-sections
    if plot_type in ('density', 'all'):
        density_files = list(Path(analysis_dir).glob('density_*.csv'))
        if density_files:
            print('── Density Cross-Sections ──')
            plot_density(analysis_dir, outdir)

    # Radius of gyration
    if plot_type in ('rg', 'all'):
        rg_files = list(Path(analysis_dir).glob('rg_*.csv'))
        if rg_files:
            print('── Radius of Gyration ──')
            plot_rg(analysis_dir, outdir)

    # Distance monitoring
    if plot_type in ('distance', 'all'):
        dist_files = list(Path(analysis_dir).glob('distance_*.csv'))
        if dist_files:
            print('── Distance Monitoring ──')
            plot_distance(analysis_dir, outdir)

    # Water residence time
    if plot_type in ('water_res', 'all'):
        if (Path(analysis_dir) / 'water_residence_survival.csv').exists():
            print('── Water Residence Time ──')
            plot_water_residence(analysis_dir, outdir)

    # Dipole / ESP
    if plot_type in ('dipole', 'all'):
        dip_files = list(Path(analysis_dir).glob('dipole_*.csv'))
        if dip_files:
            print('── Dipole Moment ──')
            plot_dipole(analysis_dir, outdir)

    # Free volume
    if plot_type in ('freevol', 'all'):
        if (Path(analysis_dir) / 'free_volume.csv').exists():
            print('── Free Volume ──')
            plot_free_volume(analysis_dir, outdir)

    # Clustering
    if plot_type in ('cluster', 'all'):
        if (Path(analysis_dir) / 'cluster_assignments.csv').exists():
            print('── Conformational Clustering ──')
            plot_cluster_scatter(analysis_dir, outdir)
            plot_cluster(analysis_dir, outdir)

    # Metadynamics
    if plot_type in ('meta', 'all'):
        if (Path(analysis_dir) / 'meta_cv_time.csv').exists():
            print('── Metadynamics ──')
            plot_meta(analysis_dir, outdir)

    # Summary dashboard
    if plot_type in ('dashboard', 'all'):
        print('── Summary Dashboard ──')
        plot_summary_dashboard(analysis_dir, outdir)

    print(f'\n✅ Done. Figures saved to {outdir}/')


if __name__ == '__main__':
    main()
