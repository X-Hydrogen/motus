#!/bin/bash
# ============================================================
# lammps-reaxff.sh — Generic ReaxFF MD Launcher   |  MOTUS v0.0.2
# ============================================================
# Usage:
#   lammps-reaxff.sh --data system.data --reaxff ffield.reaxff [OPTIONS]
#
# Options:
#   --data FILE         LAMMPS data file (atom_style charge)
#   --reaxff FILE       ReaxFF force field parameter file
#   --temp N            Simulation temperature (K)        [default: 2500]
#   --time N            Simulation time (ps)              [default: 100]
#   --dt N              Timestep (fs)                     [default: 0.1]
#   --Tdamp N           Temperature damping (fs)          [default: 25]
#   --dump-freq N       Dump frequency (steps)            [default: 100]
#   --species-freq N    Species output frequency (steps)  [default: 100]
#   --job NAME          Job name                         [default: reaxff_md]
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

# ── Defaults ──
DATA=""; REAXFF=""; TEMP=2500; SIM_TIME=100; DT=0.1; TDAMP=25
DUMP_FREQ=100; SPECIES_FREQ=100; JOB="reaxff_md"; NO_RUN=0

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --data) DATA="$2"; shift 2 ;;
        --reaxff) REAXFF="$2"; shift 2 ;;
        --temp) TEMP="$2"; shift 2 ;;
        --time) SIM_TIME="$2"; shift 2 ;;
        --dt) DT="$2"; shift 2 ;;
        --Tdamp) TDAMP="$2"; shift 2 ;;
        --dump-freq) DUMP_FREQ="$2"; shift 2 ;;
        --species-freq) SPECIES_FREQ="$2"; shift 2 ;;
        --job) JOB="$2"; shift 2 ;;
        --no-run) NO_RUN=1; shift ;;
        -h|--help)
            head -30 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

# ── Validate ──
[[ -z "$DATA" ]] && error "Required: --data FILE"
[[ ! -f "$DATA" ]] && error "Data file not found: $DATA"
[[ -z "$REAXFF" ]] && error "Required: --reaxff FILE"
[[ ! -f "$REAXFF" ]] && error "ReaxFF file not found: $REAXFF"

DATA=$(realpath "$DATA")
REAXFF=$(realpath "$REAXFF")
JOB_DIR="$(pwd)"

# ── Compute steps ──
NSTEPS=$(awk -v t=${SIM_TIME} -v dt=${DT} 'BEGIN {printf "%d", t * 1000 / dt}')

header "LAMMPS ReaxFF MD: $JOB"
log "Data:       $DATA"
log "ReaxFF:     $REAXFF"
log "Temperature: ${TEMP} K"
log "Time:       ${SIM_TIME} ps (${NSTEPS} steps × ${DT} fs)"
log "Job:        $JOB"

# ── Generate LAMMPS input ──
INPUT="${JOB_DIR}/in.${JOB}"
log "Generating input: $INPUT"

TDAMP_VAL=$(awk -v td=${TDAMP} 'BEGIN{printf "%.1f", td}')
cat > "$INPUT" << EOF
# ReaxFF MD — ${JOB}
# Temperature: ${TEMP} K, Time: ${SIM_TIME} ps

units           real
atom_style      full

read_data       ${DATA}

# ── ReaxFF Force Field ──
pair_style      reaxff NULL
pair_coeff      * * ${REAXFF} C H O N

# ── Charge equilibration ──
fix             qeq all qeq/reaxff 1 0.0 10.0 1e-6 reaxff

# ── Initial velocities ──
velocity        all create ${TEMP} 12345

# ── NVT ensemble ──
fix             nvt all nvt temp ${TEMP} ${TEMP} $TDAMP_VAL

# ── Timestep ──
timestep        ${DT}

# ── Output ──
thermo          ${DUMP_FREQ}
thermo_style    custom step temp press pe ke etotal vol

# Trajectory dump (atom coords + element + charge)
dump            traj all custom ${DUMP_FREQ} ${JOB}.lammpstrj id type xu yu zu q element

# Species tracking (ReaxFF)
fix             spec all reaxff/species 1 1 ${SPECIES_FREQ} ${JOB}.species
fix             bonds all reaxff/bonds ${SPECIES_FREQ} ${JOB}.bonds

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
log "Command: $LMP -in in.$JOB"
echo ""

$LMP -in "in.$JOB" 2>&1 | tail -5

if [[ -f "${JOB}.species" ]]; then
    log "Species file: ${JOB_DIR}/${JOB}.species"
fi
if [[ -f "${JOB}.lammpstrj" ]]; then
    log "Trajectory:    ${JOB_DIR}/${JOB}.lammpstrj"
fi

echo ""
log "Done."
