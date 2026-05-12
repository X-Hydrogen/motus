#!/bin/bash
# ============================================================
# gromacs-md.sh — Automated GROMACS MD Pipeline  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-md.sh <job_dir> [OPTIONS]
#
# The job directory must contain:
#   system.gro (or .pdb) + topol.top + npt.mdp (or use auto-generated defaults)
#
# Options:
#   -t, --time <ps>        Simulation time (default: 2000)
#   -i, --interval <ps>    Recording interval (default: 1)
#   -T, --temperature <K>  Temperature (default: 300)
#   -P, --pressure <bar>   Pressure (default: 1.01325)
#   --ntomp <N>            OpenMP threads (default: 4)
#   --gpu                  Use GPU (default: auto-detect)
#   --no-gpu               Force CPU-only
#   --clean                Remove backup files after completion
#
# Workflow: EM → NVT → NPT → Production
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() { head -24 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

# ── Auto-detect GROMACS ──
GMX="${GMX:-}"
find_gromacs() {
    if [[ -n "$GMX" ]] && command -v "$GMX" &>/dev/null; then return 0; fi
    # Try sourced GMXRC
    if command -v gmx &>/dev/null; then GMX=gmx; return 0; fi
    # Try common installs
    for d in /home/$USER/tools/gromacs-*/bin/gmx /usr/local/gromacs/bin/gmx; do
        if [[ -x "$d" ]]; then GMX="$d"; return 0; fi
    done
    return 1
}
find_gromacs || error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Defaults ──
SIM_TIME=2000; REC_INTERVAL=1; TEMP=300; PRESSURE=1.01325
NTOMP=4; USE_GPU=1; DO_CLEAN=0

# ── Parse args ──
JOB_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -t|--time)       SIM_TIME="$2"; shift 2 ;;
        -i|--interval)   REC_INTERVAL="$2"; shift 2 ;;
        -T|--temperature) TEMP="$2"; shift 2 ;;
        -P|--pressure)   PRESSURE="$2"; shift 2 ;;
        --ntomp)         NTOMP="$2"; shift 2 ;;
        --gpu)           USE_GPU=1; shift ;;
        --no-gpu)        USE_GPU=0; shift ;;
        --clean)         DO_CLEAN=1; shift ;;
        --gmx)           GMX="$2"; shift 2 ;;
        *)               JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory provided."
[[ ! -d "$JOB_DIR" ]] && error "Directory not found: $JOB_DIR"

JOB_DIR=$(realpath "$JOB_DIR")
JOB_NAME=$(basename "$JOB_DIR")
cd "$JOB_DIR"

# ── Auto-detect input files ──
GRO=$(ls system.gro *.gro 2>/dev/null | head -1)
TOP=$(ls topol.top *.top 2>/dev/null | head -1)
[[ -z "$GRO" ]] && error "No .gro file found in $JOB_DIR"
[[ -z "$TOP" ]] && error "No .top file found in $JOB_DIR"

# ── Detect GPU ──
GPU_OPTS=""
if [[ "$USE_GPU" -eq 1 ]]; then
    if nvidia-smi &>/dev/null 2>&1; then
        GPU_OPTS="-nb gpu -pme gpu -bonded gpu -update gpu"
        log "GPU detected — using GPU acceleration"
    else
        warn "No GPU detected, falling back to CPU"
    fi
fi

# OMP warning workaround
unset OMP_NUM_THREADS 2>/dev/null || true

# Derived values
TOTAL_PS=$SIM_TIME
NSTEPS=$(( SIM_TIME * 500 ))  # 2 fs timestep → 500 steps/ps
NSTXOUT=$(( REC_INTERVAL * 500 ))

header "GROMACS MD Pipeline: $JOB_NAME"
echo -e "  ${BOLD}Input:${NC}    $GRO + $TOP"
echo -e "  ${BOLD}Sim time:${NC}  ${TOTAL_PS} ps (${NSTEPS} steps)"
echo -e "  ${BOLD}Interval:${NC}  ${REC_INTERVAL} ps"
echo -e "  ${BOLD}Temp:${NC}      ${TEMP} K"
echo -e "  ${BOLD}GPU:${NC}       $([[ -n "$GPU_OPTS" ]] && echo "yes" || echo "no")"

# ── Step 1: Energy Minimization ──
header "Step 1/4: Energy Minimization"
log "Running steepest descent EM..."
cat > _em.mdp << EOMDP
integrator  = steep
nsteps      = 5000
emtol       = 100.0
nstxout     = 100
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
EOMDP

$GMX grompp -f _em.mdp -c "$GRO" -p "$TOP" -o em.tpr -maxwarn 10 -po em_out.mdp 2>&1 | tail -3
$GMX mdrun -deffnm em -ntmpi 1 -ntomp "$NTOMP" 2>&1 | tail -3
Epot=$(grep "Potential Energy" em.log 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
log "  E_pot after EM: $Epot"

# ── Step 2: NVT Equilibration ──
header "Step 2/4: NVT Equilibration (100 ps)"
log "Running NVT with position restraints..."
cat > _nvt.mdp << NVTDP
integrator    = md
nsteps        = 50000
dt            = 0.002
nstxout       = 1000
nstvout       = 1000
nstenergy     = 1000
nstlog        = 1000
continuation  = no
constraints   = h-bonds
constraint-algorithm = LINCS
cutoff-scheme = Verlet
coulombtype   = PME
rcoulomb      = 1.0
rvdw          = 1.0
pbc           = xyz
tcoupl        = V-rescale
tc-grps       = System
tau-t         = 0.1
ref-t         = ${TEMP}
pcoupl        = no
gen-vel       = yes
gen-temp      = ${TEMP}
NVTDP

$GMX grompp -f _nvt.mdp -c em.gro -p "$TOP" -o nvt.tpr -maxwarn 10 -po nvt_out.mdp 2>&1 | tail -3
$GMX mdrun -deffnm nvt $GPU_OPTS -ntmpi 1 -ntomp "$NTOMP" 2>&1 | tail -3
log "  NVT complete"

# ── Step 3: NPT Equilibration ──
header "Step 3/4: NPT Equilibration (100 ps)"
log "Running NPT with pressure coupling..."
cat > _npt.mdp << NPTDP
integrator    = md
nsteps        = 50000
dt            = 0.002
nstxout       = 1000
nstvout       = 1000
nstenergy     = 1000
nstlog        = 1000
continuation  = yes
constraints   = h-bonds
constraint-algorithm = LINCS
cutoff-scheme = Verlet
coulombtype   = PME
rcoulomb      = 1.0
rvdw          = 1.0
pbc           = xyz
tcoupl        = V-rescale
tc-grps       = System
tau-t         = 0.1
ref-t         = ${TEMP}
pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau-p         = 2.0
ref-p         = ${PRESSURE}
compressibility = 4.5e-5
NPTDP

$GMX grompp -f _npt.mdp -c nvt.gro -p "$TOP" -o npt.tpr -maxwarn 10 -po npt_out.mdp 2>&1 | tail -3
$GMX mdrun -deffnm npt $GPU_OPTS -ntmpi 1 -ntomp "$NTOMP" 2>&1 | tail -3
log "  NPT complete"

# ── Step 4: Production MD ──
header "Step 4/4: Production MD (${TOTAL_PS} ps)"
log "Running production NPT..."
cat > _prod.mdp << PRODDP
integrator    = md
nsteps        = ${NSTEPS}
dt            = 0.002
nstxout-compressed = ${NSTXOUT}
nstenergy     = ${NSTXOUT}
nstlog        = ${NSTXOUT}
continuation  = yes
constraints   = h-bonds
constraint-algorithm = LINCS
cutoff-scheme = Verlet
coulombtype   = PME
rcoulomb      = 1.0
rvdw          = 1.0
pbc           = xyz
tcoupl        = V-rescale
tc-grps       = System
tau-t         = 0.1
ref-t         = ${TEMP}
pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau-p         = 2.0
ref-p         = ${PRESSURE}
compressibility = 4.5e-5
PRODDP

START_TIME=$(date +%s)
$GMX grompp -f _prod.mdp -c npt.gro -p "$TOP" -o prod.tpr -maxwarn 10 -po prod_out.mdp 2>&1 | tail -3
$GMX mdrun -deffnm prod $GPU_OPTS -ntmpi 1 -ntomp "$NTOMP" 2>&1 | tail -5
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# ── Summary ──
echo ""
header "MD Complete"
echo -e "  ${BOLD}Wall time:${NC}  ${ELAPSED}s"
if [[ -f prod.log ]]; then
    PERF=$(grep "Performance" prod.log | tail -1 | awk '{print $2}')
    echo -e "  ${BOLD}Speed:${NC}      ${PERF:-N/A} ns/day"
fi

# Cleanup
if [[ "$DO_CLEAN" -eq 1 ]]; then
    log "Cleaning intermediate files..."
    rm -f _em.mdp _nvt.mdp _npt.mdp _prod.mdp \#*\#
fi

echo ""
echo -e "${GREEN}Production trajectory → prod.xtc + prod.gro${NC}"
echo -e "${GREEN}Energy data → prod.edr${NC}"
echo -e "${GREEN}Run: gmx energy -f prod.edr -o analysis.xvg${NC}"
