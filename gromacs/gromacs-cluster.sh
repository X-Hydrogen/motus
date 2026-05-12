#!/bin/bash
# ============================================================
# gromacs-cluster.sh — GROMACS Structural Clustering  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-cluster.sh <job_dir> [OPTIONS]
#
# Clusters MD trajectory frames by RMSD. Supports GROMOS, linkage,
# Jarvis-Patrick, and Monte Carlo methods.
#
# Options:
#   --method <m>       gromos | linkage | jarvis-patrick | monte-carlo
#                       (default: gromos)
#   --cutoff <nm>      RMSD cutoff (nm) for neighbor (default: 0.15)
#   --skip <N>         Skip every N frames before clustering (default: 1)
#   --fit-group <g>    Index group for fitting (default: System)
#   --n-clusters <N>   Target number of clusters (GROMOS minstruct)
#   --plot             Generate clustering figures
#   --fig-only         Re-plot from existing data
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

usage() { head -28 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse ──
METHOD="gromos"; CUTOFF=0.15; SKIP_FRAMES=1; N_CLUSTERS=5
FIT_GROUP="System"; DO_PLOT=0; FIG_ONLY=0; JOB_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)     usage ;;
        --method)      METHOD="$2"; shift 2 ;;
        --cutoff)      CUTOFF="$2"; shift 2 ;;
        --skip)        SKIP_FRAMES="$2"; shift 2 ;;
        --fit-group)   FIT_GROUP="$2"; shift 2 ;;
        --n-clusters)  N_CLUSTERS="$2"; shift 2 ;;
        --plot)        DO_PLOT=1; shift ;;
        --fig-only)    FIG_ONLY=1; DO_PLOT=1; shift ;;
        *)             JOB_DIR="$1"; shift ;;
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
    header "Figure-Only Clustering: $JOB_NAME"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type cluster 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
    exit 0
fi

header "GROMACS Clustering: $JOB_NAME"
echo "  Method:    $METHOD"
echo "  Cutoff:    $CUTOFF nm"
echo "  Skip:      every $SKIP_FRAMES frame(s)"
echo "  Target:    $N_CLUSTERS clusters"

# ── Step 1: RMSD Matrix ──
header "1. RMSD Matrix Calculation"
log "Computing pairwise RMSD matrix..."
if [[ -n "$TPR" ]]; then
    if printf "%s\n%s\n" "$FIT_GROUP" "$FIT_GROUP" | \
        $GMX rms -f "$XTC" -s "$TPR" -m rmsd-matrix.xpm \
        -skip "$SKIP_FRAMES" -fit rot+trans 2>&1 | tail -3; then
        log "  → rmsd-matrix.xpm"
    else
        warn "RMS matrix calculation failed — trying with GRO..."
    fi
else
    warn "No .tpr — trying with .gro for fitting..."
fi

# Fallback: use GRO if TPR failed or not available
if [[ ! -f rmsd-matrix.xpm ]]; then
    log "Computing RMSD matrix with GRO structure..."
    if printf "%s\n%s\n" "$FIT_GROUP" "$FIT_GROUP" | \
        $GMX rms -f "$XTC" -s "$GRO" -m rmsd-matrix.xpm \
        -skip "$SKIP_FRAMES" -fit rot+trans 2>&1 | tail -3; then
        log "  → rmsd-matrix.xpm"
    else
        error "RMS matrix calculation failed. Check trajectory and structure files."
    fi
fi

# ── Step 2: Clustering ──
header "2. Clustering ($METHOD)"
log "Running $METHOD clustering..."

CLUSTER_ARGS="-f $XTC -s ${TPR:-$GRO} -dm rmsd-matrix.xpm"
CLUSTER_ARGS+=" -cl clusters.pdb -clid cluster-id.xvg"
CLUSTER_ARGS+=" -sz cluster-sizes.xvg -g cluster.log -dist rmsd-dist.xvg"
CLUSTER_ARGS+=" -method $METHOD -cutoff $CUTOFF -fit -skip $SKIP_FRAMES"

if [[ "$METHOD" == "gromos" ]]; then
    CLUSTER_ARGS+=" -minstruct $N_CLUSTERS"
fi

printf "%s\n%s\n" "$FIT_GROUP" "$FIT_GROUP" | \
    $GMX cluster $CLUSTER_ARGS 2>&1 | tail -8

# ── Step 3: Parse cluster info ──
header "3. Parsing Cluster Results"

# Number of clusters from log
NCLUST=$(grep -c "cluster" cluster.log 2>/dev/null || echo "?")
log "Found $NCLUST clusters (target: $N_CLUSTERS)"

# Cluster sizes → CSV
if [[ -f cluster-sizes.xvg ]]; then
    grep -v '^[@#]' cluster-sizes.xvg | awk 'BEGIN{print "Cluster,Size"}{print $1","$2}' > cluster_sizes.csv
    log "  → cluster_sizes.csv"
    # Show top clusters
    head -5 cluster_sizes.csv
fi

# Cluster assignments over time → CSV
if [[ -f cluster-id.xvg ]]; then
    grep -v '^[@#]' cluster-id.xvg | awk 'BEGIN{print "Time_ps,Cluster_ID"}{print $1","$2}' > cluster_timeline.csv
    log "  → cluster_timeline.csv"
fi

# RMSD distribution → CSV
if [[ -f rmsd-dist.xvg ]]; then
    grep -v '^[@#]' rmsd-dist.xvg | awk 'BEGIN{print "RMSD_nm,Count"}{print $1","$2}' > rmsd_distribution.csv
    log "  → rmsd_distribution.csv"
fi

# ── Step 4: Cluster Transitions ──
header "4. Transition Analysis"
log "Computing cluster transitions..."
if printf "%s\n%s\n" "$FIT_GROUP" "$FIT_GROUP" | \
    $GMX cluster $CLUSTER_ARGS -tr cluster-transitions.xpm -ntr cluster-ntrans.xvg 2>&1 | tail -3; then
    if [[ -f cluster-ntrans.xvg ]]; then
        grep -v '^[@#]' cluster-ntrans.xvg | awk 'BEGIN{print "Cluster,N_Transitions"}{print $1","$2}' > cluster_transitions.csv
        log "  → cluster_transitions.csv"
    fi
fi

# ── Clean up ──
rm -f rmsd.xvg rmsd-matrix.xpm cluster-transitions.xpm 2>/dev/null

# ── Plot ──
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "Generating Cluster Figures"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type cluster 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
fi

echo ""
log "Clustering complete. Results in $ANADIR/"
