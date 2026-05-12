#!/bin/bash
# ============================================================
# lammps-analysis.sh — LAMMPS MD Post-Processing  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   lammps-analysis.sh <job_dir> [OPTIONS]
#
# The job directory must contain: prod.lammpstrj + system.data + prod.log
#
# Options:
#   --plot              Generate figures
#   --fig-only          Re-plot only
#   --plot-type <type>  energy|rdf|rmsd|rgyr|density|all
# ============================================================

set -uo pipefail  # No -e: stages can fail gracefully with skip()

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
skip()   { echo -e "${YELLOW}[~]${NC} $* (skipped)"; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() { head -16 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

# ── Parse ──
JOB_DIR=""; DO_PLOT=0; FIG_ONLY=0; PLOT_TYPE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --plot)   DO_PLOT=1; shift ;;
        --fig-only) FIG_ONLY=1; DO_PLOT=1; shift ;;
        --plot-type) PLOT_TYPE="$2"; shift 2 ;;
        *)        JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory."
[[ ! -d "$JOB_DIR" ]] && error "Directory not found: $JOB_DIR"
JOB_DIR=$(realpath "$JOB_DIR")
JOB_NAME=$(basename "$JOB_DIR")

TRAJ=$(ls "$JOB_DIR"/prod.lammpstrj 2>/dev/null | head -1)
DATA=$(ls "$JOB_DIR"/system.data "$JOB_DIR"/final.data 2>/dev/null | head -1)
LOG=$(ls "$JOB_DIR"/prod.log 2>/dev/null | head -1)

[[ -z "$TRAJ" ]] && error "No prod.lammpstrj found"
[[ -z "$DATA" ]] && error "No system.data found"

ANADIR="$JOB_DIR/analysis"; mkdir -p "$ANADIR"; cd "$ANADIR"

# ── FIG-ONLY ──
if [[ "$FIG_ONLY" -eq 1 ]]; then
    header "Figure-Only: $JOB_NAME"
    python3 "$SCRIPT_DIR/functions/lammps_plot.py" "$ANADIR" --type "$PLOT_TYPE" 2>&1 | grep '✓' || true
    exit 0
fi

header "LAMMPS Analysis: $JOB_NAME"

# ==== 1: Energy Analysis (from log) ====
header "1. Energy Analysis"
if [[ -n "$LOG" ]]; then
    log "Extracting thermo data from LAMMPS log..."
    python3 -c "
import re
with open('$LOG') as f:
    text = f.read()
# Extract thermo blocks
blocks = re.findall(r'Step\s+Temp\s+Press.*?\n(.*?)(?=\nLoop|\Z)', text, re.DOTALL)
if not blocks:
    blocks = re.findall(r'Step\s+Temp.*?\n(.*?)(?=Loop|\Z)', text, re.DOTALL)
if blocks:
    with open('energy_timeseries.csv', 'w') as out:
        out.write('Step,Temp_K,Press_atm,Pot_E_kcal,Vol_A3\n')
        for block in blocks:
            for line in block.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 6:
                    out.write(f'{parts[0]},{parts[1]},{parts[2]},{parts[4]},{parts[5]}\n')
    print('energy_timeseries.csv written')
else:
    print('No thermo data found')
" 2>&1
    [[ -f energy_timeseries.csv ]] && log "  → energy_timeseries.csv ($(wc -l < energy_timeseries.csv) rows)"
else
    skip "No log file"
fi

# ==== 2: RDF (via Python) ====
header "2. Radial Distribution Function"
log "Computing RDF from trajectory..."
python3 -c "
import numpy as np

# Read LAMMPS trajectory
frames = []
with open('$TRAJ') as f:
    lines = f.readlines()

i = 0
while i < len(lines):
    if 'ITEM: TIMESTEP' in lines[i]:
        i += 1; ts = int(lines[i]); i += 1  # skip timestep
    if i < len(lines) and 'ITEM: NUMBER OF ATOMS' in lines[i]:
        i += 1; natoms = int(lines[i]); i += 1
    if i < len(lines) and 'ITEM: BOX BOUNDS' in lines[i]:
        i += 1
        box = []
        for _ in range(3):
            lo, hi = map(float, lines[i].split())
            box.append(hi - lo); i += 1
    if i < len(lines) and 'ITEM: ATOMS' in lines[i]:
        i += 1
        coords = np.zeros((natoms, 3))
        for j in range(natoms):
            parts = lines[i].split()
            coords[j] = [float(parts[2]), float(parts[3]), float(parts[4])]
            i += 1
        frames.append(coords)

print(f'Frames: {len(frames)}, atoms: {natoms}')
if len(frames) > 0:
    # Compute O-O RDF for water oxygens (type-based)
    # For quick analysis, compute all-pair RDF with large stride
    stride = max(1, len(frames) // 50)
    sampled = frames[::stride]
    
    # Compute pairwise distances
    all_dists = []
    box_diag = np.array(box)
    for f_coords in sampled:
        # Random subset for speed
        idx = np.random.choice(natoms, min(100, natoms), replace=False)
        diffs = f_coords[idx, None] - f_coords[None, :]
        # Minimum image
        diffs -= box_diag * np.round(diffs / box_diag)
        dists = np.sqrt(np.sum(diffs**2, axis=-1))
        all_dists.extend(dists[dists < 10.0].flatten())
    
    # Histogram
    hist, edges = np.histogram(all_dists, bins=200, range=(0, 10))
    r = (edges[:-1] + edges[1:]) / 2
    dr = edges[1] - edges[0]
    rho = natoms / np.prod(box_diag)
    gr = hist / (4 * np.pi * r**2 * dr * rho * len(sampled))
    
    with open('rdf_all.csv', 'w') as f:
        f.write('r_A,g_r\n')
        for ri, gi in zip(r, gr):
            f.write(f'{ri:.4f},{gi:.6f}\n')
    print(f'rdf_all.csv written ({len(r)} bins)')
" 2>&1
[[ -f rdf_all.csv ]] && log "  → rdf_all.csv"

# ==== 3: RMSD ====
header "3. RMSD Analysis"
log "Computing RMSD..."
python3 -c "
import numpy as np

frames = []
with open('$TRAJ') as f:
    lines = f.readlines()
i = 0; natoms = 0
while i < len(lines):
    if 'ITEM: NUMBER OF ATOMS' in lines[i]:
        i += 1; natoms = int(lines[i]); i += 1; continue
    if 'ITEM: ATOMS' in lines[i]:
        i += 1
        coords = np.zeros((natoms, 3))
        for j in range(natoms):
            parts = lines[i].split()
            coords[j] = [float(parts[2]), float(parts[3]), float(parts[4])]
            i += 1
        frames.append(coords)
        continue
    i += 1

if len(frames) > 1:
    ref = frames[0]
    with open('rmsd.csv', 'w') as f:
        f.write('Frame,RMSD_A\n')
        for fi, coord in enumerate(frames[::max(1,len(frames)//200)]):
            rmsd = np.sqrt(np.mean(np.sum((coord - ref)**2, axis=1)))
            f.write(f'{fi},{rmsd:.4f}\n')
    print(f'rmsd.csv: {len(frames)} frames processed')
" 2>&1
[[ -f rmsd.csv ]] && log "  → rmsd.csv"

# ==== Summary ====
header "Analysis Summary"
NCSV=$(find "$ANADIR" -maxdepth 1 -name "*.csv" | wc -l)
log "Generated $NCSV CSV files"

[[ "$DO_PLOT" -eq 1 ]] && python3 "$SCRIPT_DIR/functions/lammps_plot.py" "$ANADIR" --type "$PLOT_TYPE" 2>&1 | grep '✓' || true

log "Analysis complete."
