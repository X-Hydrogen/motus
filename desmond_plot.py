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


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Desmond MD publication-quality plotting')
    parser.add_argument('analysis_dir', help='Path to analysis directory (with CSV files)')
    parser.add_argument('--type', choices=['energy', 'hbonds', 'water_shells', 'contacts', 'rmsd', 'rmsf', 'rdf', 'dashboard', 'all'],
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
            if 'rmsd' in fname.lower() and fname != 'rmsf_bfactor.csv':
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

    # Summary dashboard
    if plot_type in ('dashboard', 'all'):
        print('── Summary Dashboard ──')
        plot_summary_dashboard(analysis_dir, outdir)

    print(f'\n✅ Done. Figures saved to {outdir}/')


if __name__ == '__main__':
    main()
