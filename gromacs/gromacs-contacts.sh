#!/bin/bash
# ============================================================
# gromacs-contacts.sh — Distance Contact Maps  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-contacts.sh <job_dir> [OPTIONS]
#
# Generates residue/atom distance contact matrices and contact
# count time series from MD trajectories.
#
# Options:
#   --group1 <sel>      First group selection (default: System)
#   --group2 <sel>      Second group selection (default: same as group1)
#   --cutoff <nm>       Contact cutoff distance (default: 0.6)
#   --plot              Generate contact map figures
#   --fig-only          Re-plot from existing data
# ============================================================

set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
skip()   { echo -e "${YELLOW}[~]${NC} $* (skipped)"; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() { head -26 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse ──
GROUP1="System"; GROUP2=""; CUTOFF=0.6; DO_PLOT=0; FIG_ONLY=0
JOB_DIR=""; DT=10

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)  usage ;;
        --group1)   GROUP1="$2"; shift 2 ;;
        --group2)   GROUP2="$2"; shift 2 ;;
        --cutoff)   CUTOFF="$2"; shift 2 ;;
        --dt)       DT="$2"; shift 2 ;;
        --plot)     DO_PLOT=1; shift ;;
        --fig-only) FIG_ONLY=1; DO_PLOT=1; shift ;;
        *)          JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory."
[[ ! -d "$JOB_DIR" ]] && error "Directory not found: $JOB_DIR"
JOB_DIR=$(realpath "$JOB_DIR")
JOB_NAME=$(basename "$JOB_DIR")

XTC=$(ls "$JOB_DIR"/prod.xtc 2>/dev/null | head -1)
GRO=$(ls "$JOB_DIR"/prod.gro "$JOB_DIR"/npt.gro "$JOB_DIR"/em.gro 2>/dev/null | head -1)
TPR=$(ls "$JOB_DIR"/prod.tpr 2>/dev/null | head -1)

[[ -z "$XTC" ]] && error "No prod.xtc found in $JOB_DIR"
[[ -z "$GRO" ]] && error "No .gro found in $JOB_DIR"

ANADIR="$JOB_DIR/analysis"; mkdir -p "$ANADIR"; cd "$ANADIR"

# ── FIG-ONLY ──
if [[ "$FIG_ONLY" -eq 1 ]]; then
    header "Figure-Only Contacts: $JOB_NAME"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type contacts 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
    exit 0
fi

header "GROMACS Contact Map: $JOB_NAME"
echo "  Group1:   $GROUP1"
[[ -n "$GROUP2" ]] && echo "  Group2:   $GROUP2"
echo "  Cutoff:   $CUTOFF nm"
echo "  dt:       $DT ps"

STUB="${TPR:-$GRO}"

# ═══════════════════════════════════════════
# Step 1: Average Distance Matrix
# ═══════════════════════════════════════════
header "1. Average Distance Matrix"

log "Computing average distance matrix..."
# mdmat expects residue groups from the index
# For non-protein systems, use make_ndx to create custom groups
NDX="$ANADIR/contact_groups.ndx"

if [[ "$GROUP1" == "System" ]] && [[ -z "$GROUP2" ]]; then
    # Use whole system → mdmat groups by residue automatically
    printf "%s\n%s\nq\n" "$GROUP1" "$GROUP1" | $GMX mdmat -f "$XTC" -s "$STUB" \
        -mean contact_matrix.xpm -no contact_count.xvg \
        -dt "$DT" 2>&1 | tail -3
else
    # Custom groups: build index
    echo "[ group1 ]" > "$NDX"
    # For selection-based groups, we need atom indices
    warn "Custom groups require atom indices — using System fallback"
    printf "System\nSystem\n" | $GMX mdmat -f "$XTC" -s "$STUB" \
        -mean contact_matrix.xpm -no contact_count.xvg \
        -dt "$DT" 2>&1 | tail -3
fi

if [[ -f contact_matrix.xpm ]]; then
    log "  → contact_matrix.xpm"
    # Extract data from XPM for CSV
    python3 -c "
import re
xpm_text = open('contact_matrix.xpm').read()
# Extract matrix dimensions
dims = re.search(r'\"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\"', xpm_text)
if dims:
    nrows, ncols = int(dims.group(1)), int(dims.group(2))
    # Extract color map and data
    color_map = {}
    data_start = False
    matrix = []
    for line in xpm_text.split('\n'):
        line = line.strip()
        if line.startswith('\"') and not data_start:
            m = re.match(r'\"(.)\s+c\s+(\S+)', line)
            if m:
                color_map[m.group(1)] = m.group(2)
        if line == '/* pixels */':
            data_start = True
            continue
        if data_start and line.startswith('\"'):
            row = line.strip('\" ,')
            matrix.append(list(row))
    # Convert to numeric values
    if matrix and color_map:
        # Parse hex colors to distances
        def hex_to_gray(h):
            h = h.lstrip('#')
            if len(h) == 6:
                return (int(h[0:2],16) + int(h[2:4],16) + int(h[4:6],16)) / 3.0
            return 0
        gray_map = {k: hex_to_gray(v) for k, v in color_map.items()}
        max_gray = max(gray_map.values()) if gray_map else 255
        with open('contact_matrix.csv', 'w') as f:
            for row in matrix:
                vals = [str(1.0 - gray_map.get(ch, 0)/max_gray) if max_gray > 0 else '0' for ch in row]
                f.write(','.join(vals) + '\n')
        print(f'  → contact_matrix.csv ({len(matrix)}x{len(matrix[0]) if matrix else 0})')
" 2>&1
    [[ -f contact_matrix.csv ]] && log "  → contact_matrix.csv"
else
    warn "mdmat failed — trying gmx mindist fallback..."
    # Fallback: minimum distance between groups
    printf "%s\n%s\n" "$GROUP1" "${GROUP2:-$GROUP1}" | \
        $GMX mindist -f "$XTC" -s "$STUB" -od contact_distance.xvg -dt "$DT" 2>&1 | tail -3
    if [[ -f contact_distance.xvg ]]; then
        grep -v '^[@#]' contact_distance.xvg | \
            awk 'BEGIN{print "Time_ps,MinDist_nm"}{print $1","$2}' > contact_distance.csv
        log "  → contact_distance.csv (fallback)"
    fi
fi

# ═══════════════════════════════════════════
# Step 2: Contact Count over Time
# ═══════════════════════════════════════════
if [[ -f contact_count.xvg ]]; then
    header "2. Contact Count"
    grep -v '^[@#]' contact_count.xvg | \
        awk 'BEGIN{print "Time_ps,N_Contacts"}{print $1","$2}' > contact_count.csv
    AVG=$(awk -F, 'NR>1{s+=$2;n++}END{printf "%.0f",s/n}' contact_count.csv)
    log "  → contact_count.csv (avg: $AVG contacts/frame)"
fi

# ── Plot ──
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "Generating Contact Figures"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type contacts 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
fi

echo ""
log "Contact analysis complete. Results in $ANADIR/"
