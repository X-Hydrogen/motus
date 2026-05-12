#!/bin/bash
# ============================================================
# lammps-metadynamics.sh — LAMMPS Metadynamics  |  MOTUS v0.0.1
# ============================================================
# Uses LAMMPS fix colvars (COLVARS package) or manual hill deposition.
# Two modes:
#   MD:  lammps-metadynamics.sh <job_dir> --meta-md
#   Ana: lammps-metadynamics.sh <job_dir> --analyze [--plot]
#
# Options (MD mode):
#   -t, --time <ps>         Sim time (default: 2000)
#   --height <kcal>         Hill height (default: 0.5 kcal/mol)
#   --mt-interval <ps>      Deposition interval (default: 1.0)
#   --biasfactor <N>        Well-tempered bias factor (0 = standard)
#   --cv-dist <i j>         Distance CV (atom indices)
#   --cv-angle <i j k>      Angle CV
#   --cv-dihedral <i j k l> Dihedral CV
#   --gpu                   Use GPU
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() { head -23 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Find LAMMPS ──
LMP="${LMP:-}"
[[ -z "$LMP" ]] && for p in lmp /home/$USER/tools/lammps-*/install/bin/lmp /home/$USER/.local/bin/lmp; do [[ -x "$p" ]] && LMP="$p" && break; done
[[ -z "$LMP" ]] && error "LAMMPS not found."

# ── Defaults ──
SIM_TIME=2000; TEMP=300; PRESSURE=1.01325
MT_HEIGHT=0.5; MT_INTERVAL=1.0; MT_BIAS=0; USE_GPU=1
MODE=""; JOB_DIR=""; CV_DIST=(); CV_ANGLE=(); CV_DIHEDRAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -t|--time)       SIM_TIME="$2"; shift 2 ;;
        --height)        MT_HEIGHT="$2"; shift 2 ;;
        --mt-interval)   MT_INTERVAL="$2"; shift 2 ;;
        --biasfactor)    MT_BIAS="$2"; shift 2 ;;
        -T|--temp)       TEMP="$2"; shift 2 ;;
        --cv-dist)       CV_DIST=($2 $3); shift 3 ;;
        --cv-angle)      CV_ANGLE=($2 $3 $4); shift 4 ;;
        --cv-dihedral)   CV_DIHEDRAL=($2 $3 $4 $5); shift 5 ;;
        --gpu)           USE_GPU=1; shift ;;
        --no-gpu)        USE_GPU=0; shift ;;
        --no-gpu)        USE_GPU=0; shift ;;
        --meta-md)       MODE="md"; shift ;;
        --analyze)       MODE="analyze"; shift ;;
        --plot)          DO_PLOT=1; shift ;;
        --lmp)           LMP="$2"; shift 2 ;;
        *)               JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory."
[[ -z "$MODE" ]] && error "Specify --meta-md or --analyze"
JOB_DIR=$(realpath "$JOB_DIR"); cd "$JOB_DIR"

# ═══════════ MD MODE ═══════════
if [[ "$MODE" == "md" ]]; then
    DATA=$(ls system.data 2>/dev/null | head -1)
    [[ -z "$DATA" ]] && error "No system.data found"
    
    GPU_FLAG=""
    [[ "$USE_GPU" -eq 1 ]] && nvidia-smi &>/dev/null 2>&1 && GPU_FLAG="-sf gpu -pk gpu 1"
    
    TIMESTEP=0.5  # fs
    NSTEPS=$(awk -v t=${SIM_TIME} -v dt=${TIMESTEP} 'BEGIN {printf "%d", t * 1000 / dt}')
    DUMP_FREQ=$(awk -v dt=${TIMESTEP} 'BEGIN {printf "%d", 1000 / dt}')  # every 1 ps
    
    header "LAMMPS Metadynamics: $(basename $JOB_DIR)"
    log "Sim: ${SIM_TIME} ps, height: ${MT_HEIGHT} kcal, interval: ${MT_INTERVAL} ps"
    
    # Build CV definitions via Python helper
    COLVARS_GEN="$SCRIPT_DIR/functions/lammps_colvars_gen.py"
    COLVARS_ARGS="--height ${MT_HEIGHT} --interval ${MT_INTERVAL} --timestep ${TIMESTEP} --temp ${TEMP}"
    [[ ${#CV_DIST[@]} -ge 2 ]] && COLVARS_ARGS+=" --dist ${CV_DIST[0]} ${CV_DIST[1]}"
    [[ ${#CV_ANGLE[@]} -ge 3 ]] && COLVARS_ARGS+=" --angle ${CV_ANGLE[0]} ${CV_ANGLE[1]} ${CV_ANGLE[2]}"
    [[ ${#CV_DIHEDRAL[@]} -ge 4 ]] && COLVARS_ARGS+=" --dihedral ${CV_DIHEDRAL[0]} ${CV_DIHEDRAL[1]} ${CV_DIHEDRAL[2]} ${CV_DIHEDRAL[3]}"
    [[ "$MT_BIAS" -gt 0 ]] && COLVARS_ARGS+=" --biasfactor ${MT_BIAS}"
    
    python3 "$COLVARS_GEN" $COLVARS_ARGS -o colvars.meta || {
        error "Failed to generate colvars.meta"
    }
    
    log "Generating LAMMPS metadynamics input..."
    cat > in.meta << LMPEOF
# LAMMPS metadynamics via fix colvars
units           real
atom_style      full
bond_style      harmonic
angle_style     harmonic
dihedral_style  opls
pair_style      lj/cut/coul/long 10.0 10.0
kspace_style    pppm 1e-4
pair_modify     mix geometric

read_data       ${DATA}
neighbor        2.0 bin
velocity        all create ${TEMP}.0 12345

fix             npt all npt temp ${TEMP}.0 ${TEMP}.0 100.0 iso ${PRESSURE} ${PRESSURE} 1000.0

# Colvars metadynamics
fix             meta all colvars colvars.meta

dump            traj all custom ${DUMP_FREQ} prod.lammpstrj id type x y z

thermo          $((DUMP_FREQ * 10))
thermo_style    custom step temp press pe ke etotal
timestep        ${TIMESTEP}
run             ${NSTEPS}
write_data      final.data
LMPEOF

    log "  CVs: defined"
    
    START=$(date +%s)
    $LMP -in in.meta $GPU_FLAG 2>&1 | tee prod.log | grep -E "Step|Temp|colvars|ERROR" | tail -20
    END=$(date +%s)
    
    echo ""; header "Complete ($((END-START))s)"
    ls -lh meta_out.* 2>/dev/null && log "Metadynamics outputs available"
    exit 0
fi

# ═══════════ ANALYZE MODE ═══════════
if [[ "$MODE" == "analyze" ]]; then
    ANADIR="$JOB_DIR/analysis"; mkdir -p "$ANADIR"; cd "$ANADIR"
    
    # Find colvars output
    COLVAR_OUT=$(ls "$JOB_DIR"/meta_out.colvars.traj "$JOB_DIR"/out.colvars.traj 2>/dev/null | head -1) || true
    HILLS=$(ls "$JOB_DIR"/meta_out.hills.traj "$JOB_DIR"/out.hills.traj 2>/dev/null | head -1) || true
    
    if [[ -f "$COLVAR_OUT" ]]; then
        log "Parsing colvars trajectory..."
        grep -v '^#' "$COLVAR_OUT" | awk 'BEGIN{print "Step,CV"}{print $1","$2}' > meta_cv_time.csv
        log "  → meta_cv_time.csv"
    else
        warn "No colvars output found — may need COLVARS-enabled LAMMPS"
    fi
    
    if [[ -n "$HILLS" ]] && [[ -f "$HILLS" ]]; then
        log "Parsing hills..."
        grep -v '^#' "$HILLS" | awk 'BEGIN{print "Step,CV,Height,Sigma"}{print $1","$3","$4","$5}' > meta_hills.csv
        log "  → meta_hills.csv"
    else
        log "  (hills stored in state file — use COLVARS tools for FES reconstruction)"
    fi
    
    log "Analysis complete."
    exit 0
fi
