#!/bin/bash
# ============================================================
# gromacs-wham.sh — WHAM/BAR PMF Reconstruction  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-wham.sh <windows_dir> [OPTIONS]
#
# Reads all pullx.xvg + prod.tpr files from umbrella sampling windows,
# reconstructs the Potential of Mean Force (PMF) via WHAM.
#
# Options:
#   --bins <N>        Number of bins (default: 200)
#   --temp <K>        Temperature (default: 300)
#   --unit <u>        Energy unit: kJ or kcal (default: kJ)
#   --min <real>      CV minimum override
#   --max <real>      CV maximum override
#   --periodic        Periodic CV
#   --block-size <N>  Bootstrap block size
#   --n-bootstrap <N> Number of bootstrap samples (default: 200)
#   --plot            Generate PMF plot
#   --fig-only        Re-plot only from existing WHAM output
# ============================================================

set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() {
    head -28 "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

# ── Find GROMACS ──
GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse args ──
BINS=200; TEMP=300; UNIT="kJ"; DO_PLOT=0; FIG_ONLY=0
CV_MIN=""; CV_MAX=""; PERIODIC=""; BS_BLOCK=0; N_BOOTSTRAP=200

WINDOWS_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --bins)          BINS="$2"; shift 2 ;;
        --temp)          TEMP="$2"; shift 2 ;;
        --unit)          UNIT="$2"; shift 2 ;;
        --min)           CV_MIN="$2"; shift 2 ;;
        --max)           CV_MAX="$2"; shift 2 ;;
        --periodic)      PERIODIC="-cycl"; shift ;;
        --block-size)    BS_BLOCK="$2"; shift 2 ;;
        --n-bootstrap)   N_BOOTSTRAP="$2"; shift 2 ;;
        --plot)          DO_PLOT=1; shift ;;
        --fig-only)      FIG_ONLY=1; DO_PLOT=1; shift ;;
        *)               WINDOWS_DIR="$1"; shift ;;
    esac
done

[[ -z "$WINDOWS_DIR" ]] && error "No windows directory. Usage: $0 <windows_dir>"
[[ ! -d "$WINDOWS_DIR" ]] && error "Directory not found: $WINDOWS_DIR"
WINDOWS_DIR=$(realpath "$WINDOWS_DIR")
JOB_NAME=$(basename "$(dirname "$WINDOWS_DIR")")

ANADIR="$WINDOWS_DIR/analysis"
mkdir -p "$ANADIR"

# ── FIG-ONLY mode ──
if [[ "$FIG_ONLY" -eq 1 ]]; then
    header "Figure-Only WHAM: $JOB_NAME"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type wham 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
    exit 0
fi

# ── Auto-detect pull files ──
TPR_LIST="$WINDOWS_DIR/tpr-files.dat"
PULLX_LIST="$WINDOWS_DIR/pullx-files.dat"

# If lists don't exist, auto-generate
if [[ ! -f "$TPR_LIST" ]] || [[ ! -f "$PULLX_LIST" ]]; then
    log "Auto-detecting umbrella windows..."
    true > "$TPR_LIST"
    true > "$PULLX_LIST"
    for wdir in "$WINDOWS_DIR"/window_*; do
        [[ -d "$wdir" ]] || continue
        pullx=$(ls "$wdir"/pullx.xvg 2>/dev/null | head -1)
        tpr=$(ls "$wdir"/prod.tpr 2>/dev/null | head -1)
        if [[ -n "$pullx" ]] && [[ -n "$tpr" ]]; then
            echo "$pullx" >> "$PULLX_LIST"
            echo "$tpr" >> "$TPR_LIST"
        fi
    done
fi

if [[ ! -f "$TPR_LIST" ]] || [[ ! -f "$PULLX_LIST" ]]; then
    error "No pullx.xvg / prod.tpr files found in $WINDOWS_DIR"
fi

NW=$(wc -l < "$PULLX_LIST" | tr -d ' ')
[[ $NW -lt 2 ]] && error "Need at least 2 windows for WHAM (found: $NW)"

header "WHAM PMF Reconstruction: $JOB_NAME"
echo "  Windows:  $NW"
echo "  Bins:     $BINS"
echo "  Temp:     $TEMP K"
echo "  Unit:     $UNIT"

# ── Auto-detect CV bounds if not provided ──
if [[ -z "$CV_MIN" ]] || [[ -z "$CV_MAX" ]]; then
    log "Auto-detecting CV bounds from pullx data..."
    CV_MIN_DET=$(cat "$PULLX_LIST" | while read f; do
        grep -v '^[@#]' "$f" | awk '{print $2}' | head -1
    done | sort -n | head -1)
    CV_MAX_DET=$(cat "$PULLX_LIST" | while read f; do
        grep -v '^[@#]' "$f" | awk '{print $2}' | tail -1
    done | sort -n | tail -1)
    CV_MIN=$(python3 -c "print(max(0, float('$CV_MIN_DET') - 0.1))")
    CV_MAX=$(python3 -c "print(float('$CV_MAX_DET') + 0.1)")
    log "  Auto bounds: $CV_MIN → $CV_MAX nm"
fi

# ═══════════════════════════════════════════
# Run WHAM
# ═══════════════════════════════════════════
cd "$ANADIR"

WHAM_ARGS=" -ix $PULLX_LIST -it $TPR_LIST -o pmf.xvg -hist histo.xvg"
WHAM_ARGS+=" -bins $BINS -temp $TEMP -unit $UNIT -b 5"

# Add bootstrap for error bars
if [[ $BS_BLOCK -gt 0 ]]; then
    WHAM_ARGS+=" -nBootstrap $N_BOOTSTRAP -histbs-block $BS_BLOCK"
    log "Bootstrap error analysis: $N_BOOTSTRAP samples, block=$BS_BLOCK"
fi

log "Running gmx wham..."
$GMX wham $WHAM_ARGS 2>&1 | tail -10

# ── Check output ──
if [[ -f pmf.xvg ]]; then
    log "  → pmf.xvg  (PMF)"
    # Convert to CSV for easier processing
    grep -v '^[@#]' pmf.xvg | awk 'BEGIN{print "CV_nm,PMF_kJmol"}{print $1","$2}' > pmf.csv
    log "  → pmf.csv"
else
    error "WHAM failed — no pmf.xvg produced"
fi

if [[ -f histo.xvg ]]; then
    log "  → histo.xvg  (window histograms)"
fi

# ── Compute summary stats ──
header "PMF Summary"
python3 -c "
import numpy as np
data = np.loadtxt('pmf.xvg', comments=('#','@'))
cv = data[:,0]; pmf = data[:,1]
pmf_shifted = pmf - np.min(pmf)
barrier_idx = np.argmax(pmf_shifted)
print(f'  PMF minimum:    {np.min(pmf):.2f} kJ/mol')
print(f'  PMF range:      {np.min(pmf_shifted):.2f} → {np.max(pmf_shifted):.2f} kJ/mol')
if barrier_idx > 0 and barrier_idx < len(cv)-1:
    print(f'  Barrier height: {pmf_shifted[barrier_idx]:.2f} kJ/mol  @ CV={cv[barrier_idx]:.3f} nm')
"

# ═══════════════════════════════════════════
# Plot PMF
# ═══════════════════════════════════════════
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "Generating PMF Figure"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type wham 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
fi

echo ""
log "WHAM analysis complete. Results in $ANADIR/"
