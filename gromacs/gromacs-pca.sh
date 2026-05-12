#!/bin/bash
# ============================================================
# gromacs-pca.sh — GROMACS PCA / Essential Dynamics  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-pca.sh <job_dir> [OPTIONS]
#
# Performs Principal Component Analysis (PCA) on an MD trajectory:
#   1. Build covariance matrix  (gmx covar)
#   2. Project onto eigenvectors (gmx anaeig)
#   3. Compute per-residue RMSF, 2D projections, eigenvalue spectrum
#
# Options:
#   --fit-group <g>     Index group for fitting (default: System)
#   --ana-group <g>     Index group for covariance analysis (default: same as fit)
#   --n-evecs <N>       Number of eigenvectors (default: 10)
#   --skip <N>          Skip every N frames (default: 1)
#   --plot              Generate PCA figures
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

usage() { head -30 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse ──
FIT_GROUP="System"; ANA_GROUP=""; N_EVECS=10; SKIP_FRAMES=1
DO_PLOT=0; FIG_ONLY=0; JOB_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)     usage ;;
        --fit-group)   FIT_GROUP="$2"; shift 2 ;;
        --ana-group)   ANA_GROUP="$2"; shift 2 ;;
        --n-evecs)     N_EVECS="$2"; shift 2 ;;
        --skip)        SKIP_FRAMES="$2"; shift 2 ;;
        --plot)        DO_PLOT=1; shift ;;
        --fig-only)    FIG_ONLY=1; DO_PLOT=1; shift ;;
        *)             JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$ANA_GROUP" ]] && ANA_GROUP="$FIT_GROUP"

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
    header "Figure-Only PCA: $JOB_NAME"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type pca 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
    exit 0
fi

header "GROMACS PCA / Essential Dynamics: $JOB_NAME"
echo "  Fit group:  $FIT_GROUP"
echo "  Ana group:  $ANA_GROUP"
echo "  Eigenvecs:  $N_EVECS"
echo "  Skip:       every $SKIP_FRAMES frame(s)"

STUB="${TPR:-$GRO}"

# ═══════════════════════════════════════════
# Step 1: Covariance Matrix
# ═══════════════════════════════════════════
header "1. Covariance Matrix"

# Build index with both groups if needed
if [[ "$FIT_GROUP" != "System" ]] || [[ "$ANA_GROUP" != "System" ]]; then
    log "Building custom index for fit + analysis groups..."
    {
        echo "[ fit ]"
        printf "%s\n" "$FIT_GROUP"  # will be parsed by gmx
        echo "[ analysis ]"
        printf "%s\n" "$ANA_GROUP"
    } > pca_groups.ndx
fi

log "Computing and diagonalizing covariance matrix..."

DT_FACTOR=$(( SKIP_FRAMES * 2 ))  # dt for covar (ps, since dt=0.002)

if printf "%s\n%s\n" "$FIT_GROUP" "$ANA_GROUP" | \
    $GMX covar -f "$XTC" -s "$STUB" \
    -o eigenvalues.xvg -v eigenvectors.trr -av average.pdb \
    -l covar.log -dt "$DT_FACTOR" -last "$N_EVECS" -nofit 2>&1 | tail -5; then

    if [[ -f eigenvalues.xvg ]]; then
        log "  → eigenvalues.xvg"
        # Convert eigenvalues to CSV
        grep -v '^[@#]' eigenvalues.xvg | awk 'BEGIN{print "Eigenvector,Eigenvalue_nm2"}{print $1","$2}' > eigenvalues.csv
        log "  → eigenvalues.csv"

        # Show variance explained
        python3 -c "
import numpy as np
vals = []
with open('eigenvalues.xvg') as f:
    for line in f:
        if line[0] in ('#','@'): continue
        parts = line.split()
        if len(parts) >= 2:
            vals.append(float(parts[1]))
if vals:
    total = sum(vals)
    cum = 0
    print(f'  Total variance: {total:.2f} nm²')
    for i, v in enumerate(vals[:min(5,len(vals))]):
        cum += v
        print(f'  PC{i+1}: {v:.3f} nm² ({100*v/total:.1f}%)  cumulative: {100*cum/total:.1f}%')
" 2>&1
    fi

    if [[ -f eigenvectors.trr ]]; then
        log "  → eigenvectors.trr"
    fi
else
    error "Covariance matrix calculation failed."
fi

# ═══════════════════════════════════════════
# Step 2: Project onto PCs
# ═══════════════════════════════════════════
header "2. Projecting Trajectory onto PCs"

log "Computing PC projections..."
if printf "%s\n%s\n" "$FIT_GROUP" "$ANA_GROUP" | \
    $GMX anaeig -v eigenvectors.trr -f "$XTC" -s "$STUB" \
    -proj pc_projections.xvg -first 1 -last 3 \
    -dt "$DT_FACTOR" 2>&1 | tail -3; then

    if [[ -f pc_projections.xvg ]]; then
        # Convert to CSV (multi-column: time, PC1, PC2, PC3)
        grep -v '^[@#]' pc_projections.xvg | \
            awk 'BEGIN{printf "Time_ps,PC1,PC2,PC3\n"}{printf "%s,%s,%s,%s\n",$1,$2,$3,$4}' > pc_projections.csv
        log "  → pc_projections.csv"
    fi
else
    warn "PC projection failed. Trying with fewer eigenvectors..."
    if printf "%s\n%s\n" "$FIT_GROUP" "$ANA_GROUP" | \
        $GMX anaeig -v eigenvectors.trr -f "$XTC" -s "$STUB" \
        -proj pc_projections.xvg -first 1 -last 2 \
        -dt "$DT_FACTOR" 2>&1 | tail -3; then
        if [[ -f pc_projections.xvg ]]; then
            grep -v '^[@#]' pc_projections.xvg | \
                awk 'BEGIN{printf "Time_ps,PC1,PC2,PC3\n"}{if(NF>=3) printf "%s,%s,%s,%s\n",$1,$2,$3,(NF>=4?$4:""); else printf "%s,%s,%s,\n",$1,$2,$3}' > pc_projections.csv
            log "  → pc_projections.csv (2 PCs)"
        fi
    fi
fi

# ═══════════════════════════════════════════
# Step 3: 2D Projection
# ═══════════════════════════════════════════
header "3. 2D Projection (PC1 vs PC2)"

log "Computing 2D projection..."
if printf "%s\n%s\n" "$FIT_GROUP" "$ANA_GROUP" | \
    $GMX anaeig -v eigenvectors.trr -f "$XTC" -s "$STUB" \
    -2d pc2d.xvg -first 1 -last 2 \
    -dt "$DT_FACTOR" 2>&1 | tail -3; then
    if [[ -f pc2d.xvg ]]; then
        grep -v '^[@#]' pc2d.xvg | awk 'BEGIN{print "PC1,PC2"}{print $1","$2}' > pc2d.csv
        log "  → pc2d.csv"
    fi
else
    skip "2D projection failed"
fi

# ═══════════════════════════════════════════
# Step 4: Per-eigenvector RMSF
# ═══════════════════════════════════════════
header "4. Eigenvector Fluctuations"

log "Computing per-eigenvector RMSF..."
if printf "%s\n%s\n" "$FIT_GROUP" "$ANA_GROUP" | \
    $GMX anaeig -v eigenvectors.trr -f "$XTC" -s "$STUB" \
    -rmsf eigen_rmsf.xvg -first 1 -last 3 \
    -dt "$DT_FACTOR" 2>&1 | tail -3; then
    if [[ -f eigen_rmsf.xvg ]]; then
        # Parse XVG robustly (may have mid-file @ blocks)
        python3 -c "
import re
data_blocks = []
current_block = []
with open('eigen_rmsf.xvg') as f:
    for line in f:
        if line.startswith(('#','@')):
            if current_block:
                data_blocks.append(current_block)
                current_block = []
            continue
        parts = line.strip().split()
        if len(parts) >= 2:
            try:
                current_block.append([float(parts[0]), float(parts[1])])
            except ValueError:
                continue
if current_block:
    data_blocks.append(current_block)

if not data_blocks:
    print('No data blocks found in eigen_rmsf.xvg')
else:
    import numpy as np
    # Use first data block (eigenvector 1 RMSF per atom)
    arr = np.array(data_blocks[0])
    rmsf = arr[:, 1]
    with open('pca_rmsf.csv', 'w') as f:
        f.write('Atom,RMSF_nm\n')
        for i, r in enumerate(rmsf):
            f.write(f'{i+1},{r:.4f}\n')
    print(f'  → pca_rmsf.csv ({len(rmsf)} atoms)')
" 2>&1
        [[ -f pca_rmsf.csv ]] && log "  → pca_rmsf.csv"
    fi
fi

# Clean up large files
rm -f eigenvectors.trr average.pdb covar.log pca_groups.ndx 2>/dev/null

# ── Plot ──
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "Generating PCA Figures"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type pca 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
fi

echo ""
log "PCA analysis complete. Results in $ANADIR/"
