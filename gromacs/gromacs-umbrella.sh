#!/bin/bash
# ============================================================
# gromacs-umbrella.sh — GROMACS Umbrella Sampling  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-umbrella.sh <job_dir> [OPTIONS]
#
# Generates umbrella sampling windows along a CV (distance by default),
# then runs MD for each window with the pull code.
#
# Options:
#   --ref-atoms     Reference group atom indices (1-indexed, comma-sep)
#   --target-atoms  Target group atom indices
#   --cv-dist <min> <max>  CV range (nm)
#   --n-windows <N>        Number of windows (default: 20)
#   --force-k <kJ/mol/nm2> Force constant (default: 1000)
#   --prod-time <ps>       Production time per window (default: 500)
#   -t, --temp <K>         Temperature (default: 300)
#   --gpu                   Use GPU
#
# Output:
#   windows/window_XX/  →  prod.tpr, pullx.xvg, pullf.xvg
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

usage() {
    head -24 "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

# ── Find GROMACS ──
GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse args ──
JOB_DIR=""; REF_ATOMS=""; TARGET_ATOMS=""
CV_START=""; CV_END=""; N_WINDOWS=20
FORCE_K=1000; PROD_TIME=500; TEMP=300; USE_GPU=0; DT=0.002
EM_TIME=200; NVT_TIME=50

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --ref-atoms)     REF_ATOMS="$2"; shift 2 ;;
        --target-atoms)  TARGET_ATOMS="$2"; shift 2 ;;
        --cv-dist)       CV_START="$2"; CV_END="$3"; shift 3 ;;
        --n-windows)     N_WINDOWS="$2"; shift 2 ;;
        --force-k)       FORCE_K="$2"; shift 2 ;;
        --prod-time)     PROD_TIME="$2"; shift 2 ;;
        -t|--temp)       TEMP="$2"; shift 2 ;;
        --gpu)           USE_GPU=1; shift ;;
        --dt)            DT="$2"; shift 2 ;;
        *)               JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory. Usage: $0 <job_dir> --ref-atoms A --target-atoms B --cv-dist MIN MAX"
[[ ! -d "$JOB_DIR" ]] && error "Directory not found: $JOB_DIR"
JOB_DIR=$(realpath "$JOB_DIR")

# ── Auto-detect or require CV atoms ──
GRO=$(ls "$JOB_DIR"/system.gro "$JOB_DIR"/step28b.pdb "$JOB_DIR"/em.gro 2>/dev/null | head -1)
TOP=$(ls "$JOB_DIR"/topol.top 2>/dev/null | head -1)

[[ -z "$GRO" ]] && error "No coordinate file (.gro/.pdb) found in $JOB_DIR"
[[ -z "$TOP" ]] && warn "No topology found — will generate one if needed"

if [[ -z "$REF_ATOMS" ]] || [[ -z "$TARGET_ATOMS" ]]; then
    error "Must specify --ref-atoms and --target-atoms. Example: --ref-atoms 1,2 --target-atoms 3,4"
fi
if [[ -z "$CV_START" ]] || [[ -z "$CV_END" ]]; then
    error "Must specify --cv-dist <min> <max>. Example: --cv-dist 0.3 1.5"
fi

# Convert comma-sep atom lists to space-sep for MDP
REF_ATOMS_SPC=$(echo "$REF_ATOMS" | tr ',' ' ')
TARGET_ATOMS_SPC=$(echo "$TARGET_ATOMS" | tr ',' ' ')

# ── Compute window positions ──
# Use Python for floating-point arithmetic
WINDOWS_DIR="$JOB_DIR/windows"
mkdir -p "$WINDOWS_DIR"

POSITIONS=$(python3 -c "
import numpy as np
positions = np.linspace(float('$CV_START'), float('$CV_END'), int('$N_WINDOWS'))
print(' '.join([f'{p:.4f}' for p in positions]))
")
N_POS=$(echo "$POSITIONS" | wc -w)

header "Umbrella Sampling Setup"
echo "  CV range:    $CV_START → $CV_END nm"
echo "  Windows:     $N_WINDOWS (computed: $N_POS)"
echo "  Force k:     $FORCE_K kJ/(mol·nm²)"
echo "  Prod/window: $PROD_TIME ps"
echo "  Ref atoms:   $REF_ATOMS_SPC"
echo "  Tgt atoms:   $TARGET_ATOMS_SPC"

# ── Create index groups for pull ──
header "Creating Pull Index Groups"
NDX="$WINDOWS_DIR/pull_groups.ndx"

# Get total atom count from GRO file
NATOMS=$(awk 'NR==2{print $1; exit}' "$GRO")
{
    echo "[ System ]"
    seq 1 $NATOMS
    echo ""
    echo "[ ref_group ]"
    for a in $REF_ATOMS_SPC; do echo "$a"; done
    echo "[ target_group ]"
    for a in $TARGET_ATOMS_SPC; do echo "$a"; done
} > "$NDX"
log "Created pull index: $NDX"

# ── Generate base MDP (shared by all windows) ──
MDP_BASE="$WINDOWS_DIR/_base.mdp"
cat > "$MDP_BASE" << MDPMARK
; ── Run control ──
integrator               = md
dt                       = $DT
nsteps                   = $(( PROD_TIME * 500 ))  ; dt=0.002 → 500 steps/ps

; ── Output ──
nstxout-compressed       = $(( 500 * 500 ))
nstenergy                = $(( 500 * 500 ))
nstlog                   = $(( 500 * 500 ))

; ── Temperature coupling ──
tcoupl                   = v-rescale
tc-grps                  = System
tau_t                    = 0.1
ref_t                    = $TEMP

; ── Pressure coupling ──
pcoupl                   = C-rescale
pcoupltype               = isotropic
tau_p                    = 2.0
ref_p                    = 1.0
compressibility          = 4.5e-5

; ── Neighbor searching ──
cutoff-scheme            = Verlet
nstlist                  = 10
rlist                    = 1.0
rcoulomb                 = 1.0
rvdw                     = 1.0
coulombtype              = PME
pme_order                = 4
fourierspacing           = 0.16

; ── Constraints ──
constraints              = h-bonds
constraint-algorithm     = LINCS

; ── Pull code (per-window → pull-coord1-init differs) ──
pull                     = yes
pull-ngroups             = 2
pull-ncoords             = 1

pull-group1-name         = ref_group
pull-group2-name         = target_group

pull-coord1-type         = umbrella
pull-coord1-geometry     = distance
pull-coord1-groups       = 1 2
pull-coord1-dim          = Y Y Y
pull-coord1-rate         = 0.0
pull-coord1-k            = $FORCE_K
pull-coord1-start        = yes
MDPMARK
log "Base MDP template created"

# ── Pre-equilibration (EM) if starting from raw structure ──
GRO_EQ="$GRO"
header "Pre-equilibration"
EMDIR="$WINDOWS_DIR/_em"
mkdir -p "$EMDIR"

cat > "$EMDIR/em.mdp" << EMMDP
integrator      = steep
nsteps          = 5000
emtol           = 100
emstep          = 0.01
nstxout         = 0
nstlog          = 1000
cutoff-scheme   = Verlet
nstlist         = 10
rlist           = 1.0
rcoulomb        = 1.0
rvdw            = 1.0
coulombtype     = PME
pme_order       = 4
fourierspacing  = 0.16
constraints     = h-bonds
constraint-algorithm = LINCS
EMMDP

$GMX grompp -f "$EMDIR/em.mdp" -c "$GRO" -p "$TOP" -o "$EMDIR/em.tpr" -po "$EMDIR/em_out.mdp" -maxwarn 10 2>&1 | tail -1
if [[ -f "$EMDIR/em.tpr" ]]; then
    $GMX mdrun -s "$EMDIR/em.tpr" -deffnm "$EMDIR/em" -ntmpi 1 -ntomp 4 2>&1 | tail -2
    if [[ -f "$EMDIR/em.gro" ]]; then
        GRO_EQ="$EMDIR/em.gro"
        check_energy=$(grep "Potential Energy" "$EMDIR/em.log" 2>/dev/null | tail -1 | awk '{print $NF}')
        log "EM done, Fmax=$(grep "Fmax" "$EMDIR/em.log" 2>/dev/null | tail -1 | awk '{print $2}')"
    else
        GRO_EQ="$GRO"
        warn "EM failed, using raw structure"
    fi
else
    GRO_EQ="$GRO"
fi
WIN=0; PASS=0; FAIL=0
for POS in $POSITIONS; do
    WIN=$((WIN + 1))
    WDIR="$WINDOWS_DIR/window_$(printf "%03d" $WIN)"
    mkdir -p "$WDIR"

    header "Window $WIN/$N_WINDOWS  (pull @ ${POS} nm)"

    # ── Build window-specific MDP ──
    MDP_WIN="$WDIR/prod.mdp"
    cp "$MDP_BASE" "$MDP_WIN"
    echo "pull-coord1-init         = $POS" >> "$MDP_WIN"

    # ── grompp → tpr ──
    if [[ -n "$TOP" ]]; then
        $GMX grompp -f "$MDP_WIN" -c "$GRO_EQ" -p "$TOP" -n "$NDX" \
            -o "$WDIR/prod.tpr" -po "$WDIR/mdout.mdp" -maxwarn 10 2>&1 | tail -2
    else
        error "No topology file available for window $WIN"
    fi

    if [[ ! -f "$WDIR/prod.tpr" ]]; then
        warn "grompp failed for window $WIN — skipping"
        FAIL=$((FAIL + 1))
        continue
    fi

    # ── mdrun (short prod per window) ──
    GPU_OPTS=""
    if [[ "$USE_GPU" -eq 1 ]]; then
        if nvidia-smi &>/dev/null 2>&1; then
            GPU_OPTS="-nb gpu -pme gpu -bonded gpu"
        fi
    fi

    START=$(date +%s)
    $GMX mdrun -s "$WDIR/prod.tpr" -deffnm "$WDIR/prod" \
        -px "$WDIR/pullx.xvg" -pf "$WDIR/pullf.xvg" \
        $GPU_OPTS -ntmpi 1 -ntomp 4 2>&1 | tail -3

    RET=$?
    END=$(date +%s)

    if [[ $RET -eq 0 ]] && [[ -f "$WDIR/pullx.xvg" ]]; then
        log "Window $WIN: ${POS} nm  →  $((END-START))s  ✓"
        PASS=$((PASS + 1))
    else
        warn "Window $WIN failed (exit=$RET)"
        FAIL=$((FAIL + 1))
    fi

    # Clean up heavy files
    rm -f "$WDIR"/prod.trr "$WDIR"/prod.xtc "$WDIR"/prod.edr 2>/dev/null
done

# ═══════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════
echo ""
header "Umbrella Sampling Complete"
echo "  Windows:   $PASS passed / $FAIL failed / $WIN total"
echo "  Output:    $WINDOWS_DIR/window_*/pullx.xvg"

# ── Generate WHAM input files ──
log "Generating WHAM input lists..."
TPR_LIST="$WINDOWS_DIR/tpr-files.dat"
PULLX_LIST="$WINDOWS_DIR/pullx-files.dat"
true > "$TPR_LIST"
true > "$PULLX_LIST"

for wdir in "$WINDOWS_DIR"/window_*; do
    [[ -d "$wdir" ]] || continue
    pullx=$(realpath "$wdir/pullx.xvg" 2>/dev/null)
    tpr=$(realpath "$wdir/prod.tpr" 2>/dev/null)
    if [[ -f "$pullx" ]] && [[ -f "$tpr" ]]; then
        echo "$pullx" >> "$PULLX_LIST"
        echo "$tpr" >> "$TPR_LIST"
    fi
done

NW=$(wc -l < "$PULLX_LIST" | tr -d ' ')
log "  → tpr-files.dat  ($NW entries)"
log "  → pullx-files.dat ($NW entries)"
log "Ready for WHAM: gmx wham -ix $WINDOWS_DIR/pullx-files.dat -it $WINDOWS_DIR/tpr-files.dat -o pmf.xvg -hist histo.xvg"
