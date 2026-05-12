#!/bin/bash
# ============================================================
# gromacs-metadynamics.sh — GROMACS + PLUMED Metadynamics  |  MOTUS v0.0.1
# ============================================================
# Two modes:
#   MD:  gromacs-metadynamics.sh <job_dir> --meta-md [OPTS]
#   Ana: gromacs-metadynamics.sh <job_dir> --analyze [OPTS]
#
# Metadynamics via PLUMED (built into GROMACS 2020+):
#   - Well-tempered metadynamics
#   - CV: DISTANCE, TORSION, RMSD, GYRATION, COORDINATION
#   - Output: HILLS, COLVAR files
#
# Options:
#   -t, --time <ps>         Sim time (default: 2000)
#   -i, --interval <ps>     Record interval (default: 1)
#   --height <kcal>         Gaussian height (default: 1.0 kJ/mol ≈ 0.24 kcal)
#   --mt-interval <ps>      Deposition stride (default: 1.0 ps)
#   --biasfactor <N>        Well-tempered bias factor (default: 10)
#   --cv-dist <a1 a2>       Distance CV (atom indices)
#   --cv-torsion <a1 a2 a3 a4>  Torsion CV
#   --cv-rmsd <ref.pdb>     RMSD CV to reference
#   --cv-gyration <group>   Radius of gyration CV
#   --temp <K>              Temperature (default: 300)
#   --plot                  Generate analysis plots
#   --fig-only              Re-plot only
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() { head -28 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

# ── Find GROMACS ──
GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found."

# ── Defaults ──
SIM_TIME=2000; REC_INTERVAL=1; TEMP=300; PRESSURE=1.01325
MT_HEIGHT=1.0; MT_INTERVAL=1.0; MT_BIASFACTOR=10
MODE=""; JOB_DIR=""; CV_DIST=(); CV_TORSION=(); CV_RMSD=""; CV_GYRATION=""
USE_GPU=1; DO_PLOT=0; FIG_ONLY=0
DO_PLOT=0; FIG_ONLY=0

# ── Parse ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -t|--time)       SIM_TIME="$2"; shift 2 ;;
        -i|--interval)   REC_INTERVAL="$2"; shift 2 ;;
        -T|--temp)       TEMP="$2"; shift 2 ;;
        --height)        MT_HEIGHT="$2"; shift 2 ;;
        --mt-interval)   MT_INTERVAL="$2"; shift 2 ;;
        --biasfactor)    MT_BIASFACTOR="$2"; shift 2 ;;
        --cv-dist)       CV_DIST=($2 $3); shift 3 ;;
        --cv-torsion)    CV_TORSION=($2 $3 $4 $5); shift 5 ;;
        --cv-rmsd)       CV_RMSD="$2"; shift 2 ;;
        --cv-gyration)   CV_GYRATION="$2"; shift 2 ;;
        --gpu)           USE_GPU=1; shift ;;
        --no-gpu)        USE_GPU=0; shift ;;
        --meta-md)       MODE="md"; shift ;;
        --analyze)       MODE="analyze"; shift ;;
        --plot)          DO_PLOT=1; shift ;;
        --fig-only)      FIG_ONLY=1; DO_PLOT=1; shift ;;
        --gmx)           GMX="$2"; shift 2 ;;
        *)               JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory."
[[ -z "$MODE" ]] && error "Specify --meta-md or --analyze"
[[ ! -d "$JOB_DIR" ]] && error "Directory not found: $JOB_DIR"

JOB_DIR=$(realpath "$JOB_DIR")
JOB_NAME=$(basename "$JOB_DIR")
cd "$JOB_DIR"
unset OMP_NUM_THREADS 2>/dev/null || true

# ═══════════════════════════════════════════════
# MODE: Launch metadynamics MD
# ═══════════════════════════════════════════════
if [[ "$MODE" == "md" ]]; then
    GRO=$(ls system.gro *.gro 2>/dev/null | head -1)
    TOP=$(ls topol.top *.top 2>/dev/null | head -1)
    [[ -z "$GRO" ]] && error "No .gro found"
    [[ -z "$TOP" ]] && error "No .top found"
    
    # Check PLUMED support
    if ! $GMX mdrun -h 2>&1 | grep plumed > /dev/null; then
        error "GROMACS compiled without PLUMED support. Rebuild with -DGMX_EXTERNAL_PLUMED=ON"
    fi
    
    TOTAL_PS=$SIM_TIME
    NSTEPS=$((SIM_TIME * 500))
    NSTXOUT=$((REC_INTERVAL * 500))
    
    header "GROMACS + PLUMED Metadynamics: $JOB_NAME"
    log "Sim time: ${TOTAL_PS} ps, height: ${MT_HEIGHT} kJ/mol, biasfactor: ${MT_BIASFACTOR}"
    
    # ── Build PLUMED input via Python helper ──
    log "Generating plumed.dat..."
    PLUMED_GEN="$SCRIPT_DIR/functions/gromacs_meta_gen.py"
    PLUMED_ARGS="--height ${MT_HEIGHT} --interval ${MT_INTERVAL} --biasfactor ${MT_BIASFACTOR} --temp ${TEMP}"
    [[ ${#CV_DIST[@]} -ge 2 ]] && PLUMED_ARGS+=" --dist ${CV_DIST[0]} ${CV_DIST[1]}"
    [[ ${#CV_TORSION[@]} -ge 4 ]] && PLUMED_ARGS+=" --torsion ${CV_TORSION[0]} ${CV_TORSION[1]} ${CV_TORSION[2]} ${CV_TORSION[3]}"
    [[ -n "$CV_GYRATION" ]] && PLUMED_ARGS+=" --gyration ${CV_GYRATION}"
    
    python3 "$PLUMED_GEN" $PLUMED_ARGS -o plumed.dat || {
        error "Failed to generate plumed.dat -- check CV definitions"
    }
    grep "^# CVs:" plumed.dat | sed "s/# CVs: /  PLUMED /"
    
    # ── Run MD with PLUMED ──
    header "Launching Metadynamics MD"
    
    # EM
    log "Energy minimization..."
    cat > _em.mdp << 'EOMDP'
integrator  = steep
nsteps      = 5000
emtol       = 100.0
nstxout     = 100
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
EOMDP
    $GMX grompp -f _em.mdp -c "$GRO" -p "$TOP" -o em.tpr -maxwarn 10 -po em_out.mdp 2>&1 | tail -1
    $GMX mdrun -deffnm em -ntmpi 1 -ntomp 4 2>&1 | tail -1
    
    # Production with PLUMED
    log "Production NPT with PLUMED..."
    cat > _prod.mdp << PRODDP
integrator    = md
nsteps        = ${NSTEPS}
dt            = 0.002
nstxout-compressed = ${NSTXOUT}
nstenergy     = ${NSTXOUT}
nstlog        = ${NSTXOUT}
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
pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau-p         = 2.0
ref-p         = ${PRESSURE}
compressibility = 4.5e-5
gen-vel       = yes
gen-temp      = ${TEMP}
PRODDP
    
    START=$(date +%s)
    # Set PLUMED_KERNEL if not already set
    if [[ -z "${PLUMED_KERNEL:-}" ]]; then
        for klib in /home/$USER/tools/plumed/lib/libplumedKernel.so                      /usr/lib/libplumedKernel.so                      $(find /home/$USER/tools -name "libplumedKernel.so" 2>/dev/null | head -1); do
            if [[ -f "$klib" ]]; then
                export PLUMED_KERNEL="$klib"
                log "  PLUMED kernel: $klib"
                break
            fi
        done
    fi
    if [[ -z "${PLUMED_KERNEL:-}" ]]; then
        warn "PLUMED_KERNEL not found — metadynamics may fail. Install PLUMED first."
    fi
    
    GPU_OPTS=""
    if [[ "$USE_GPU" -eq 1 ]] && nvidia-smi &>/dev/null 2>&1; then
        GPU_OPTS="-nb gpu -pme gpu -bonded gpu"
    fi
    $GMX grompp -f _prod.mdp -c em.gro -p "$TOP" -o prod.tpr -maxwarn 10 -po prod_out.mdp 2>&1 | tail -1
    $GMX mdrun -deffnm prod -plumed plumed.dat $GPU_OPTS -ntmpi 1 -ntomp 4 2>&1 | tail -5
    END=$(date +%s)
    
    echo ""
    header "Metadynamics Complete"
    echo -e "  Wall time: $((END-START))s"
    ls -lh HILLS COLVAR 2>/dev/null && log "Metadynamics outputs: HILLS + COLVAR"
    rm -f _em.mdp _prod.mdp
    exit 0
fi

# ═══════════════════════════════════════════════
# MODE: Analyze metadynamics outputs
# ═══════════════════════════════════════════════
if [[ "$MODE" == "analyze" ]]; then
    ANADIR="$JOB_DIR/analysis"
    mkdir -p "$ANADIR"
    
    HILLS="$JOB_DIR/HILLS"
    COLVAR="$JOB_DIR/COLVAR"
    
    [[ ! -f "$HILLS" ]] && error "No HILLS file found. Run metadynamics first."
    
    header "PLUMED Metadynamics Analysis: $JOB_NAME"
    
    cd "$ANADIR"
    
    # ── Parse COLVAR → CSV ──
    if [[ -f "$COLVAR" ]]; then
        log "Parsing COLVAR..."
        # PLUMED COLVAR format: #! FIELDS time cv1 cv2 ... bias
        # Data columns: time, cv1, cv2, ...
        NCV=$(head -1 "$COLVAR" | awk '{print NF-3}')  # header: "#! FIELDS time cv1..." => NF-3 = ncv
        [[ $NCV -lt 1 ]] && NCV=1
        # Generate CSV with header
        (echo -n "Time_ps"; for i in $(seq 1 $NCV); do echo -n ",CV${i}"; done; echo) > meta_cv_time.csv
        awk -v ncv=$NCV '!/^#/{printf "%.3f",$1; for(i=2;i<=ncv+1;i++) printf ",%.4f",$i; print ""}' \
            "$COLVAR" >> meta_cv_time.csv
        log "  → meta_cv_time.csv ($(wc -l < meta_cv_time.csv) frames)"
    fi
    
    # ── Reconstruct FES from HILLS using PLUMED sum_hills ──
    log "Reconstructing Free Energy Surface from HILLS..."
    if command -v plumed &>/dev/null; then
        # Use plumed sum_hills
        plumed sum_hills --hills "$HILLS" --outfile fes.dat --mintozero 2>&1 | tail -2
        if [[ -f fes.dat ]]; then
            awk '!/^#/{print $1","$2}' fes.dat > meta_fes_1d.csv
            log "  → meta_fes_1d.csv"
        fi
    else
        # Manual FES reconstruction from HILLS (simplified)
        log "  plumed CLI not found — using Python fallback..."
        python3 -c "
import numpy as np
data = np.loadtxt('$HILLS', comments='#')
if data.ndim == 2 and data.shape[1] >= 4:
    # time, cv, height, sigma
    cv = data[:,1]; h = data[:,2]; s = data[:,3]
    # Build histogram of weighted CV values as crude FES
    bins = np.linspace(cv.min(), cv.max(), 100)
    hist, edges = np.histogram(cv, bins=bins, weights=h)
    centers = (edges[:-1] + edges[1:]) / 2
    with open('meta_fes_1d.csv', 'w') as f:
        f.write('CV,Free_Energy_kJmol\n')
        for c, v in zip(centers, hist):
            f.write(f'{c:.4f},{v:.4f}\n')
    print(f'  → meta_fes_1d.csv ({len(centers)} bins)')
"
    fi
    
    # ── Plot ──
    if [[ "$DO_PLOT" -eq 1 ]]; then
        PLOT_SCRIPT="$SCRIPT_DIR/functions/gromacs_plot.py"
        if [[ -f "$PLOT_SCRIPT" ]]; then
            python3 "$PLOT_SCRIPT" "$ANADIR" --type meta 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
        fi
    fi
    
    log "Analysis complete."
    exit 0
fi
