#!/bin/bash
# ============================================================
# lammps-bond-react.sh — Bond/React MD Launcher   |  MOTUS v0.0.2
# ============================================================
# Usage:
#   lammps-bond-react.sh --data system.data --reactions reaction.yaml [OPTIONS]
#
# Options:
#   --data FILE         LAMMPS data file
#   --reactions FILE    Reaction definition YAML file
#   --temp N            Simulation temperature (K)        [default: 300]
#   --time N            Simulation time (ps)              [default: 1000]
#   --dt N              Timestep (fs)                     [default: 1.0]
#   --Tdamp N           Temperature damping (fs)          [default: 100]
#   --Pdamp N           Pressure damping (fs)             [default: 1000]
#   --dump-freq N       Dump frequency (steps)            [default: 100]
#   --job NAME          Job name                         [default: bond_react]
#   --ensemble TYPE     NVT or NPT                        [default: NVT]
#   --no-run            Generate input only, don't run
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

# ── Auto-detect LAMMPS ──
LMP="${LMP:-}"
[[ -z "$LMP" ]] && for p in /home/$USER/tools/lammps-*/build/lmp /home/$USER/tools/lammps-*/install/bin/lmp lmp; do
    [[ -x "$p" ]] && LMP="$p" && break
done
[[ -z "$LMP" ]] && error "Cannot find LAMMPS binary. Set LMP env var."

# ── Find bond_react_gen.py ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GEN_SCRIPT="${SCRIPT_DIR}/functions/bond_react_gen.py"
[[ ! -f "$GEN_SCRIPT" ]] && GEN_SCRIPT=$(find /home/xenon/xhy/motus -name bond_react_gen.py -type f 2>/dev/null | head -1)
if [[ ! -f "$GEN_SCRIPT" ]]; then
    warn "bond_react_gen.py not found — skipping template generation"
    GEN_SCRIPT=""
fi

# ── Defaults ──
DATA=""; REACTIONS=""; TEMP=300; SIM_TIME=1000; DT=1.0; TDAMP=100; PDAMP=1000
DUMP_FREQ=100; JOB="bond_react"; ENSEMBLE="NVT"; NO_RUN=0

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --data) DATA="$2"; shift 2 ;;
        --reactions) REACTIONS="$2"; shift 2 ;;
        --temp) TEMP="$2"; shift 2 ;;
        --time) SIM_TIME="$2"; shift 2 ;;
        --dt) DT="$2"; shift 2 ;;
        --Tdamp) TDAMP="$2"; shift 2 ;;
        --Pdamp) PDAMP="$2"; shift 2 ;;
        --dump-freq) DUMP_FREQ="$2"; shift 2 ;;
        --job) JOB="$2"; shift 2 ;;
        --ensemble) ENSEMBLE="$2"; shift 2 ;;
        --no-run) NO_RUN=1; shift ;;
        -h|--help)
            head -36 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

# ── Validate ──
[[ -z "$DATA" ]] && error "Required: --data FILE"
[[ ! -f "$DATA" ]] && error "Data file not found: $DATA"
[[ -z "$REACTIONS" ]] && error "Required: --reactions FILE"
[[ ! -f "$REACTIONS" ]] && error "Reaction file not found: $REACTIONS"

DATA=$(realpath "$DATA")
REACTIONS=$(realpath "$REACTIONS")
JOB_DIR="$(pwd)"

# ── Compute steps ──
NSTEPS=$(awk -v t=${SIM_TIME} -v dt=${DT} 'BEGIN {printf "%d", t * 1000 / dt}')

header "LAMMPS Bond/React MD: $JOB"
log "Data:       $DATA"
log "Reactions:  $REACTIONS"
log "Temperature: ${TEMP} K"
log "Time:       ${SIM_TIME} ps (${NSTEPS} steps × ${DT} fs)"
log "Ensemble:   $ENSEMBLE"

# ── Generate templates from YAML ──
TEMPLATE_DIR="${JOB_DIR}/templates"
if [[ -n "$GEN_SCRIPT" ]]; then
    log "Generating reaction templates..."
    python3 "$GEN_SCRIPT" "$REACTIONS" "$TEMPLATE_DIR" 2>&1 | while read line; do
        log "  $line"
    done
fi

# ── Find template files ──
MAP_FILES=$(ls "$TEMPLATE_DIR"/*.map 2>/dev/null | head -5)
PRE_FILES=$(ls "$TEMPLATE_DIR"/*.pre.template 2>/dev/null | head -5)
POST_FILES=$(ls "$TEMPLATE_DIR"/*.post.template 2>/dev/null | head -5)

if [[ -z "$MAP_FILES" ]]; then
    error "No .map files found in $TEMPLATE_DIR"
fi

# ── Parse reaction probability from YAML ──
PROB=$(python3 -c "
import yaml
with open('$REACTIONS') as f:
    data = yaml.safe_load(f)
print(data['reactions'][0].get('probability', 0.01))
" 2>/dev/null || echo "0.01")

# Build fix bond/react command string
BR_CMD="fix             br all bond/react"
BR_CMD="$BR_CMD stabilization yes"
BR_CMD="$BR_CMD update_edges yes"

for mf in $MAP_FILES; do
    rname=$(basename "$mf" .map)
    pre="${TEMPLATE_DIR}/${rname}.pre.template"
    post="${TEMPLATE_DIR}/${rname}.post.template"
    BR_CMD="$BR_CMD react $rname"
    BR_CMD="$BR_CMD prob $PROB 12345"
    BR_CMD="$BR_CMD map $mf"
    [[ -f "$pre" ]] && BR_CMD="$BR_CMD pre_react_template $pre"
    [[ -f "$post" ]] && BR_CMD="$BR_CMD post_react_template $post"
done

# ── Generate LAMMPS input ──
INPUT="${JOB_DIR}/in.${JOB}"
log "Generating input: $INPUT"

cat > "$INPUT" << EOF
# Bond/React MD — ${JOB}
# Temperature: ${TEMP} K, Time: ${SIM_TIME} ps, Ensemble: ${ENSEMBLE}

units           real
atom_style      full

read_data       ${DATA}

# ── Force Field Parameters ──
# (Read from data file header or default to generic)
pair_style      lj/cut/coul/long 10.0 10.0
kspace_style    pppm 0.0001

# ── Initial velocities ──
velocity        all create ${TEMP} 12345

# ── Ensemble ──
EOF

TDAMP_VAL=$(awk -v td=${TDAMP} 'BEGIN{printf "%.1f", td}')
PDAMP_VAL=$(awk -v pd=${PDAMP} 'BEGIN{printf "%.1f", pd}')
if [[ "$ENSEMBLE" == "NPT" ]]; then
cat >> "$INPUT" << EOF
fix             ensemble all npt temp ${TEMP} ${TEMP} ${TDAMP_VAL} iso 1.0 1.0 ${PDAMP_VAL}
EOF
else
cat >> "$INPUT" << EOF
fix             ensemble all nvt temp ${TEMP} ${TEMP} ${TDAMP_VAL}
EOF
fi

cat >> "$INPUT" << EOF

# ── Bond/React ──
${BR_CMD}

# ── Timestep ──
timestep        ${DT}

# ── Output ──
thermo          ${DUMP_FREQ}
thermo_style    custom step temp press pe ke etotal vol

# Trajectory dump (with molecule ID for species tracking)
dump            traj all custom ${DUMP_FREQ} ${JOB}.lammpstrj id mol type xu yu zu element

# ── Run ──
run             ${NSTEPS}
EOF

log "Input file written: $INPUT"

if [[ "$NO_RUN" -eq 1 ]]; then
    log "Skipping run (--no-run)"
    echo ""
    echo "To run: cd $JOB_DIR && $LMP -in in.$JOB"
    exit 0
fi

# ── Run ──
header "Running LAMMPS..."
$LMP -in "in.$JOB" 2>&1 | tail -5

if [[ -f "${JOB}.lammpstrj" ]]; then
    log "Trajectory: ${JOB_DIR}/${JOB}.lammpstrj"
fi

echo ""
log "Done."
