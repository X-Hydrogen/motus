#!/bin/bash
# ============================================================
# gromacs-dihedral.sh — Angle & Dihedral Analysis  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-dihedral.sh <job_dir> [OPTIONS]
#
# Computes angle/dihedral distributions, time series, and
# rotamer transitions from MD trajectories.
#
# Options:
#   --type <t>          angle | dihedral (default: dihedral)
#   --atoms <i j k [l]> Atom indices (3 for angle, 4 for dihedral)
#   --group <sel>       GROMACS selection for auto-detection
#   --plot              Generate figures
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

usage() { head -28 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse ──
ANGLE_TYPE="dihedral"; ATOMS=""; GROUP_SEL=""; DO_PLOT=0; FIG_ONLY=0
JOB_DIR=""; DT=2

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --type)    ANGLE_TYPE="$2"; shift 2 ;;
        --atoms)   ATOMS="$2"; shift 2 ;;
        --group)   GROUP_SEL="$2"; shift 2 ;;
        --dt)      DT="$2"; shift 2 ;;
        --plot)    DO_PLOT=1; shift ;;
        --fig-only) FIG_ONLY=1; DO_PLOT=1; shift ;;
        *)         JOB_DIR="$1"; shift ;;
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
    header "Figure-Only Dihedral: $JOB_NAME"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type dihedral 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
    exit 0
fi

header "GROMACS Angle/Dihedral Analysis: $JOB_NAME"
echo "  Type:    $ANGLE_TYPE"

# ── Build index with atom groups ──
if [[ -n "$ATOMS" ]]; then
    # User specified atom indices
    ATOM_ARR=($ATOMS)
    NAT=${#ATOM_ARR[@]}
    
    if [[ "$ANGLE_TYPE" == "angle" ]] && [[ $NAT -ne 3 ]]; then
        error "Angle requires exactly 3 atoms (got $NAT)"
    elif [[ "$ANGLE_TYPE" == "dihedral" ]] && [[ $NAT -ne 4 ]]; then
        error "Dihedral requires exactly 4 atoms (got $NAT)"
    fi

    # Create index
    NDX="$ANADIR/dihedral_groups.ndx"
    echo "[ angle_group ]" > "$NDX"
    for a in "${ATOM_ARR[@]}"; do echo "$a"; done >> "$NDX"
    echo "  Atoms:    ${ATOM_ARR[*]}"
    GROUP_ARG="-n $NDX"
else
    warn "No --atoms specified. Use --atoms 'i j k l' for a dihedral"
    warn "  or --group 'type HW' for automatic selection."
    exit 0
fi

STUB="${TPR:-$GRO}"

# ═══════════════════════════════════════════
# Step 1: Angle/Dihedral time series
# ═══════════════════════════════════════════
header "1. $ANGLE_TYPE Time Series"

log "Computing $ANGLE_TYPE values over trajectory..."
G1_TYPE="$ANGLE_TYPE"

printf "angle_group\n" | $GMX gangle -f "$XTC" -s "$STUB" $GROUP_ARG \
    -g1 "$G1_TYPE" -group1 angle_group \
    -oall angle_timeseries.xvg -dt "$DT" 2>&1 | tail -3

if [[ -f angle_timeseries.xvg ]]; then
    # Convert to CSV
    grep -v '^[@#]' angle_timeseries.xvg | awk -v t="$ANGLE_TYPE" \
        'BEGIN{printf "Time_ps,'"${ANGLE_TYPE^}"'_deg\n"}{printf "%s,%.2f\n",$1,$2}' \
        > angle_timeseries.csv
    AVG=$(awk -F, 'NR>1{s+=$2;n++}END{printf "%.1f",s/n}' angle_timeseries.csv)
    log "  → angle_timeseries.csv (avg: ${AVG}°)"
fi

# ═══════════════════════════════════════════
# Step 2: Histogram / Distribution
# ═══════════════════════════════════════════
header "2. $ANGLE_TYPE Distribution"

log "Computing histogram..."
printf "angle_group\n" | $GMX gangle -f "$XTC" -s "$STUB" $GROUP_ARG \
    -g1 "$G1_TYPE" -group1 angle_group \
    -oh angle_histogram.xvg -binw 2.0 -dt "$DT" 2>&1 | tail -3

if [[ -f angle_histogram.xvg ]]; then
    grep -v '^[@#]' angle_histogram.xvg | awk -v t="$ANGLE_TYPE" \
        'BEGIN{printf "'"${ANGLE_TYPE^}"'_deg,Count\n"}{printf "%.1f,%s\n",$1,$2}' \
        > angle_distribution.csv
    log "  → angle_distribution.csv"
fi

# ═══════════════════════════════════════════
# Step 3: Transitions (dihedral only)
# ═══════════════════════════════════════════
if [[ "$ANGLE_TYPE" == "dihedral" ]]; then
    header "3. Rotamer Transitions"

    log "Computing transition times..."
    printf "angle_group\n" | $GMX angle -f "$XTC" -n "$NDX" \
        -type dihedral -all -ot dihedral_transitions.xvg 2>&1 | tail -3

    if [[ -f dihedral_transitions.xvg ]]; then
        grep -v '^[@#]' dihedral_transitions.xvg | \
            awk 'BEGIN{print "Time_ps,Trans_State"}{print $1","$2}' > dihedral_transitions.csv
        log "  → dihedral_transitions.csv"
    else
        skip "Transition analysis failed (may need more frames)"
    fi
fi

# ── Plot ──
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "Generating Dihedral Figures"
    python3 "$SCRIPT_DIR/functions/gromacs_plot.py" "$ANADIR" --type dihedral 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
fi

echo ""
log "Angle/Dihedral analysis complete. Results in $ANADIR/"
