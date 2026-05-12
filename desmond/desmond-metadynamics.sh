#!/bin/bash
# ============================================================
# desmond-metadynamics.sh — Desmond Metadynamics Pipeline  |  MOTUS v0.0.1
# ============================================================
# Two modes:
#   MD Mode:   desmond-metadynamics.sh <setup_folder> --meta-md [OPTIONS]
#   Analysis:  desmond-metadynamics.sh <md_job_folder> --analyze [OPTIONS]
#
# MD options:
#   -t, --time <ps>        Simulation time (default: 2000)
#   -i, --interval <ps>    Recording interval (default: 1)
#   --height <kcal>        Gaussian height (default: 0.03)
#   --mt-interval <ps>     Deposition interval (default: 0.09)
#   --mt-first <ps>        First deposition time (default: 0.0)
#   --ktemp <kcal>         Well-tempered kT (<0 = standard, default: -1)
#   --cv-dist <a1 a2>      Distance CV (2 atom indices)
#   --cv-dihedral <a1..a4> Dihedral CV (4 atom indices)
#   --cv-angle <a1..a3>    Angle CV (3 atom indices)
#   --cv-rmsd <a1 a2 ...>  RMSD CV to initial structure (4+ atoms)
#   --cv-rgyr <a1 a2 ...>  Radius of gyration CV (2+ atoms)
#   --cv-zdist <a1 a2 ...> Z-distance CV (1+ atoms)
#   --cv-name <name>       Custom CV name tag
#
# Analysis options:
#   --plot              Generate publication figures after analysis
#   --fig-only          Skip analysis, re-plot only
#   --plot-type <type>  Specific plot: meta_cv|meta_height|meta_fes|all
#
# Examples:
#   # Run metadynamics MD
#   desmond-metadynamics.sh desmond_setup_myjob --meta-md \
#       --cv-dist "1 4" --cv-dihedral "34 0 1 3" -t 500 -i 1 --height 0.05
#
#   # Analyze existing metadynamics job
#   desmond-metadynamics.sh desmond_md_job_myjob --analyze --plot
#
#   # Re-plot only
#   desmond-metadynamics.sh desmond_md_job_myjob --analyze --fig-only
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() {
    head -44 "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

# ── Auto-detect Schrödinger installation ──
SCHRODINGER="${SCHRODINGER:-}"
find_schrodinger() {
    if [[ -n "$SCHRODINGER" ]] && [[ -f "$SCHRODINGER/run" ]]; then return 0; fi
    for pattern in /opt/schrodinger* /home/$USER/schrodinger* \
                   /home/$USER/tools/schrodinger* /usr/local/schrodinger* /shared/schrodinger*; do
        for dir in $pattern; do
            if [[ -d "$dir" ]] && [[ -f "$dir/run" ]]; then
                SCHRODINGER="$dir"; return 0
            fi
        done
    done
    return 1
}
find_schrodinger || error "Cannot find Schrödinger installation. Set SCHRODINGER env var."

RUN_SCHROD="$SCHRODINGER/run"
MULTISIM="$SCHRODINGER/utilities/multisim"
JOBCTL="$SCHRODINGER/jobcontrol"

# ── Defaults ──
SIM_TIME=2000; REC_INTERVAL=1; TEMP=300; PRESSURE=1.01325; CUTOFF=5.0; CPU=1; GPU_LIC=16
MT_HEIGHT=0.03; MT_INTERVAL=0.09; MT_FIRST=0.0; MT_KTEMP=-1
MODE=""; FOLDER=""; CV_DIST=(); CV_DIHEDRAL=(); CV_ANGLE=(); CV_RMSD=(); CV_RGYR=(); CV_ZDIST=()
CV_NAME=""; DO_PLOT=0; FIG_ONLY=0; PLOT_TYPE="all"

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -t|--time)       SIM_TIME="$2"; shift 2 ;;
        -i|--interval)   REC_INTERVAL="$2"; shift 2 ;;
        -T|--temperature) TEMP="$2"; shift 2 ;;
        -P|--pressure)   PRESSURE="$2"; shift 2 ;;
        -c|--cutoff)     CUTOFF="$2"; shift 2 ;;
        --cpu)           CPU="$2"; shift 2 ;;
        --gpu-license)   GPU_LIC="$2"; shift 2 ;;
        --height)        MT_HEIGHT="$2"; shift 2 ;;
        --mt-interval)   MT_INTERVAL="$2"; shift 2 ;;
        --mt-first)      MT_FIRST="$2"; shift 2 ;;
        --ktemp)         MT_KTEMP="$2"; shift 2 ;;
        --cv-dist)       CV_DIST=($2); shift 2 ;;
        --cv-dihedral)   CV_DIHEDRAL=($2); shift 2 ;;
        --cv-angle)      CV_ANGLE=($2); shift 2 ;;
        --cv-rmsd)       shift; while [[ $# -gt 0 ]] && [[ ! "$1" =~ ^- ]]; do CV_RMSD+=("$1"); shift; done ;;
        --cv-rgyr)       shift; while [[ $# -gt 0 ]] && [[ ! "$1" =~ ^- ]]; do CV_RGYR+=("$1"); shift; done ;;
        --cv-zdist)      shift; while [[ $# -gt 0 ]] && [[ ! "$1" =~ ^- ]]; do CV_ZDIST+=("$1"); shift; done ;;
        --cv-name)       CV_NAME="$2"; shift 2 ;;
        --meta-md)       MODE="md"; shift ;;
        --analyze)       MODE="analyze"; shift ;;
        --plot)          DO_PLOT=1; shift ;;
        --fig-only)      FIG_ONLY=1; DO_PLOT=1; shift ;;
        --plot-type)     PLOT_TYPE="$2"; shift 2 ;;
        --schrodinger)   SCHRODINGER="$2"; shift 2 ;;
        --output-dir)    OUTPUT_DIR="$2"; shift 2 ;;
        -*)              error "Unknown option: $1" ;;
        *)               FOLDER="$1"; shift ;;
    esac
done

[[ -z "$FOLDER" ]] && error "No folder provided. Usage: $0 <folder> [--meta-md|--analyze] [OPTIONS]"
[[ -z "$MODE" ]] && error "Specify mode: --meta-md (launch MD) or --analyze (post-process)"
[[ ! -d "$FOLDER" ]] && error "Folder not found: $FOLDER"

FOLDER=$(realpath "$FOLDER")
FOLDER_NAME=$(basename "$FOLDER")

# ── Normalize batch CV arrays (split space-separated single arg into multiple) ──
for arr_name in CV_RMSD CV_RGYR CV_ZDIST; do
    eval "arr=(\"\${${arr_name}[@]}\")"
    if [[ ${#arr[@]} -eq 1 ]] && [[ "${arr[0]}" =~ \  ]]; then
        eval "${arr_name}=(${arr[0]})"
    fi
done

# ═══════════════════════════════════════════════
# MODE: Launch metadynamics MD
# ═══════════════════════════════════════════════
if [[ "$MODE" == "md" ]]; then
    if [[ ! "$FOLDER_NAME" =~ ^desmond_setup_(.+)$ ]]; then
        error "Setup folder must be named 'desmond_setup_XXXXX'. Got: $FOLDER_NAME"
    fi
    SYSTEM="${BASH_REMATCH[1]}"
    JOB_NAME="desmond_md_job_${SYSTEM}"

    # Find input CMS
    CMS_IN=$(ls "$FOLDER/${FOLDER_NAME}-out.cms" 2>/dev/null || echo "")
    [[ -z "$CMS_IN" ]] && error "No output CMS found. Expected: $FOLDER/${FOLDER_NAME}-out.cms"

    OUTPUT_DIR="${OUTPUT_DIR:-$(dirname "$FOLDER")/${JOB_NAME}}"
    mkdir -p "$OUTPUT_DIR"

    # Derived values
    TOTAL_FRAMES=$(( SIM_TIME / REC_INTERVAL ))
    CHKPT_INTERVAL=$(( SIM_TIME / 10 )); [[ $CHKPT_INTERVAL -lt 50 ]] && CHKPT_INTERVAL=50

    header "Desmond Metadynamics MD Pipeline"
    echo -e "  ${BOLD}System:${NC}        $SYSTEM"
    echo -e "  ${BOLD}Setup:${NC}         $FOLDER"
    echo -e "  ${BOLD}Output:${NC}        $OUTPUT_DIR"
    echo -e "  ${BOLD}Sim time:${NC}      ${SIM_TIME} ps (${TOTAL_FRAMES} frames)"
    echo -e "  ${BOLD}Record int:${NC}    ${REC_INTERVAL} ps"
    echo -e "  ${BOLD}Meta height:${NC}   ${MT_HEIGHT} kcal/mol"
    echo -e "  ${BOLD}Meta interval:${NC} ${MT_INTERVAL} ps"
    [[ "$MT_KTEMP" -gt 0 ]] && echo -e "  ${BOLD}Well-tempered:${NC} kT = ${MT_KTEMP} kcal/mol"

    # Copy CMS
    log "Copying system from setup..."
    cp "$CMS_IN" "$OUTPUT_DIR/${JOB_NAME}-in.cms"
    cp "$CMS_IN" "$OUTPUT_DIR/${JOB_NAME}.cms"

    # ── Generate .msj with meta block ──
    log "Generating $JOB_NAME.msj (with metadynamics)..."
    cat > "$OUTPUT_DIR/${JOB_NAME}.msj" << MSJEOF
task {
  task = "desmond:auto"
  set_family = { desmond = { checkpt.write_last_step = no } }
}

simulate {
  title   = "Brownian Dynamics NVT, T = 10 K, restraints on solute heavy atoms, 100ps"
  time    = 100;  timestep = [0.001 0.001 0.003];  temperature = 10.0
  ensemble = { class = "NVT"  method = "Brownie"  brownie = { delta_max = 0.1 } }
  polarization_restraints = full
  restraints.new = [{ name = posre_harm  atoms = solute_heavy_atom  force_constants = 50.0 }]
  eneseq.interval = 0.3
}

simulate {
  title = "NVT, T = 10 K, restraints on solute heavy atoms, 12ps"
  time = 12;  timestep = [0.001 0.001 0.003];  temperature = 10.0
  polarization_restraints = full
  restraints.new = [{ name = posre_harm  atoms = solute_heavy_atom  force_constants = 50.0 }]
  ensemble = { class = NVT  method = Langevin  thermostat.tau = 0.1 }
  randomize_velocity.interval = 1.0;  eneseq.interval = 0.3;  trajectory.center = []
}

simulate {
  title = "NPT, T = 10 K, restraints on solute heavy atoms, 12ps"
  time = 12;  temperature = 10.0
  polarization_restraints = full;  restraints.existing = retain
  ensemble = { class = NPT  method = Langevin  thermostat.tau = 0.1  barostat.tau = 50.0 }
  randomize_velocity.interval = 1.0;  eneseq.interval = 0.3;  trajectory.center = []
}

simulate {
  title = "NPT and restraints on solute heavy atoms, 12ps"
  effect_if = [["@*.*.annealing"] 'annealing = off temperature = "@*.*.temperature[0][0]"']
  time = 12
  polarization_restraints = full;  restraints.existing = retain
  ensemble = { class = NPT  method = Langevin  thermostat.tau = 0.1  barostat.tau = 50.0 }
  randomize_velocity.interval = 1.0;  eneseq.interval = 0.3;  trajectory.center = []
}

simulate {
  title = "NPT and no restraints, 24ps"
  effect_if = [["@*.*.annealing"] 'annealing = off temperature = "@*.*.temperature[0][0]"']
  time = 24
  ensemble = { class = NPT  method = Langevin  thermostat.tau = 0.1  barostat.tau = 2.0 }
  polarization_restraints = decay;  eneseq.interval = 0.3;  trajectory.center = solute
}

simulate {
   meta = {
      height    = ${MT_HEIGHT}
      first     = ${MT_FIRST}
      interval  = ${MT_INTERVAL}
      name      = "${JOB_NAME}.kerseq"
      cv_name   = "${JOB_NAME}.cvseq"
      cv        = [CV_PLACEHOLDER]
   }
   cfg_file = "${JOB_NAME}.cfg"
   jobname  = "\$MAINJOBNAME"
   dir      = ".";  compress = ""
}
MSJEOF

    # ── Build CV list ──
    CV_ENTRIES=""
    # Dist CV (2 atoms, flat list)
    if [[ ${#CV_DIST[@]} -ge 2 ]]; then
        CV_ENTRIES+="         { type = dist  atom = [\"atom.num ${CV_DIST[0]}\" \"atom.num ${CV_DIST[1]}\"]  width = 0.4 }"$'\n'
    fi
    # Dihedral CV (4 atoms, flat list)
    if [[ ${#CV_DIHEDRAL[@]} -ge 4 ]]; then
        CV_ENTRIES+="         { type = dihedral  atom = [\"atom.num ${CV_DIHEDRAL[0]}\" \"atom.num ${CV_DIHEDRAL[1]}\" \"atom.num ${CV_DIHEDRAL[2]}\" \"atom.num ${CV_DIHEDRAL[3]}\"]  width = 0.4 }"$'\n'
    fi
    # Angle CV (3 atoms, flat list)
    if [[ ${#CV_ANGLE[@]} -ge 3 ]]; then
        CV_ENTRIES+="         { type = angle  atom = [\"atom.num ${CV_ANGLE[0]}\" \"atom.num ${CV_ANGLE[1]}\" \"atom.num ${CV_ANGLE[2]}\"]  width = 0.4 }"$'\n'
    fi
    # RMSD CV (4+ atoms, NESTED list: atom = [["atom.num 1" "atom.num 2" ...]])
    if [[ ${#CV_RMSD[@]} -ge 4 ]]; then
        RMSD_ATOMS=$(printf '\"atom.num %s\" ' "${CV_RMSD[@]}")
        CV_ENTRIES+="         { type = rmsd  atom = [[${RMSD_ATOMS}]]  width = 0.4 }"$'\n'
    fi
    # Rgyr CV (2+ atoms, nested list)
    if [[ ${#CV_RGYR[@]} -ge 2 ]]; then
        RGYR_ATOMS=$(printf '\"atom.num %s\" ' "${CV_RGYR[@]}")
        CV_ENTRIES+="         { type = rgyr  atom = [[${RGYR_ATOMS}]]  width = 0.5 }"$'\n'
    fi
    # Zdist CV (1+ atoms, nested list)
    if [[ ${#CV_ZDIST[@]} -ge 1 ]]; then
        ZDIST_ATOMS=$(printf '\"atom.num %s\" ' "${CV_ZDIST[@]}")
        CV_ENTRIES+="         { type = zdist  atom = [[${ZDIST_ATOMS}]]  width = 0.5 }"$'\n'
    fi

    # Auto-detect CVs if none specified
    if [[ -z "$CV_ENTRIES" ]]; then
        warn "No CV specified — auto-detecting from system..."
        # Let Python inspect the system
        AUTO_CV=$($RUN_SCHROD python3 -c "
import sys
sys.path.insert(0, '$SCHRODINGER/internal/lib/python3.11/site-packages')
from schrodinger.application.desmond import cms
m = cms.Cms(file='$CMS_IN')
# Find largest non-water molecule (solute)
mol_atoms = {}
for i in range(1, m.atom_total+1):
    mn = m.atom[i].molecule_number if hasattr(m.atom[i], 'molecule_number') else 0
    if mn not in mol_atoms: mol_atoms[mn] = []
    if m.atom[i].element != 'H': mol_atoms[mn].append(i)

# Sort by heavy atom count
sorted_mols = sorted(mol_atoms.items(), key=lambda x: -len(x[1]))
print(f'NMOLS={len(sorted_mols)}')
for mn, atoms in sorted_mols[:5]:
    elems = set(m.atom[a].element for a in atoms)
    print(f'MOL_{mn} NATOMS={len(atoms)} ELEMS={\",\".join(sorted(elems))} ATOMS={\",\".join(str(a) for a in atoms[:10])}')
" 2>&1)
        echo "$AUTO_CV" | while IFS= read -r line; do log "  $line"; done
        
        warn "Auto-detection not yet implemented — please specify CVs manually with --cv-dist, --cv-dihedral, etc."
        warn "Example: --cv-dihedral \"35 1 2 4\" for urea HN-C-N-H dihedral"
        error "No CV definitions provided."
    fi

    # Write CV entries to temp file, then inject into .msj
    echo "$CV_ENTRIES" > "$OUTPUT_DIR/.cv_entries.tmp"
    python3 -c "
with open('$OUTPUT_DIR/${JOB_NAME}.msj', 'r') as f:
    content = f.read()
with open('$OUTPUT_DIR/.cv_entries.tmp', 'r') as f:
    cv_text = f.read().rstrip()
content = content.replace('[CV_PLACEHOLDER]', '\\n' + cv_text)
with open('$OUTPUT_DIR/${JOB_NAME}.msj', 'w') as f:
    f.write(content)
"
    rm -f "$OUTPUT_DIR/.cv_entries.tmp"
    log "  CV definitions:"
    echo "$CV_ENTRIES" | while IFS= read -r line; do [[ -n "$line" ]] && log "    $line"; done

    # ── Generate .cfg ──
    log "Generating $JOB_NAME.cfg..."
    cat > "$OUTPUT_DIR/${JOB_NAME}.cfg" << CFGEOF
annealing = false
backend = {}
bigger_rclone = false;  box = ?;  bulk_properties = false
checkpt = { first = 0.0  interval = ${CHKPT_INTERVAL}.0  name = "\$JOBNAME.cpt"  write_last_step = true }
cpu = ${CPU};  cutoff_radius = ${CUTOFF}
dipole_moment = false;  ebias_force = false;  elapsed_time = 0.0;  energy_group = false
eneseq = { first = 0.0  interval = ${REC_INTERVAL}.0  name = "\$JOBNAME\$[_replica\$REPLICA\$].ene" }
ensemble = { barostat = { tau = 2.0 }  class = NPT  method = MTK  thermostat = { tau = 1.0 } }
gaussian_force = false;  glue = solute;  lambda_dynamics = false
maeff_output = { center_atoms = solute  first = 0.0  interval = ${CHKPT_INTERVAL}.0
   name = "\$JOBNAME\$[_replica\$REPLICA\$]-out.cms"  periodicfix = true
   trjdir = "\$JOBNAME\$[_replica\$REPLICA\$]_trj" }
meta = off;  meta_file = ?;  msd = false
polarization_restraints = none;  pressure = [${PRESSURE} isotropic ];  pressure_tensor = false
randomize_velocity = { first = 0.0  interval = inf  seed = 2007  temperature = "@*.temperature" }
restrain = none;  restraints = { existing = ignore  new = [] }
rnemd = false
simbox = { first = 0.0  interval = 1.2  name = "\$JOBNAME\$[_replica\$REPLICA\$]_simbox.dat" }
spatial_temperature = false;  surface_tension = 0.0;  taper = false
temperature = [[${TEMP}.0 0 ]];  time = ${SIM_TIME}.0;  timestep = [0.002 0.002 0.006]
trajectory = { center = []  first = 0.0  format = dtr  frames_per_file = ${TOTAL_FRAMES}
   interval = ${REC_INTERVAL}.0  name = "\$JOBNAME\$[_replica\$REPLICA\$]_trj"
   periodicfix = true  write_last_step = true  write_last_vel = false  write_velocity = false }
wall_force = false
CFGEOF

    # ── Launch ──
    header "Launching Metadynamics MD"
    log "Job: $JOB_NAME"
    
    PROJ_DIR="$OUTPUT_DIR/.proj_tmp"; mkdir -p "$PROJ_DIR"
    cd "$OUTPUT_DIR"
    
    START_TIME=$(date +%s)
    MULTISIM_OUT=$("$MULTISIM" -JOBNAME "$JOB_NAME" -HOST localhost -maxjob 1 -cpu "$CPU" \
        -m "${JOB_NAME}.msj" -c "${JOB_NAME}.cfg" \
        -description "Metadynamics MD - ${SIM_TIME}ps" \
        "${JOB_NAME}.cms" -mode umbrella -PROJ "$PROJ_DIR" -DISP append \
        -o "${JOB_NAME}-out.cms" -lic "DESMOND_GPGPU:${GPU_LIC}" 2>&1)
    MULTISIM_EXIT=$?
    
    JOB_ID=$(echo "$MULTISIM_OUT" | grep -oP 'JobId:\s*\K\S+' | head -1)
    if [[ -z "$JOB_ID" ]]; then
        warn "Could not detect JobId. Exit code: $MULTISIM_EXIT"
    else
        log "Job ID: $JOB_ID — monitoring..."
        if [[ -x "$JOBCTL" ]]; then
            TIMEOUT=$((SIM_TIME / 10 + 600))
            ELAPSED=0
            while true; do
                STATUS=$("$JOBCTL" -list "$JOB_ID" 2>/dev/null | grep "$JOB_ID" | head -1)
                if echo "$STATUS" | grep -qE "exited|finished|died|killed|cancelled"; then
                    log "Job finished: $STATUS"; break
                fi
                [[ -z "$STATUS" ]] && { log "Job completed (record cleaned)"; break; }
                [[ $ELAPSED -ge $TIMEOUT ]] && { warn "Timeout after ${TIMEOUT}s"; break; }
                sleep 10; ELAPSED=$((ELAPSED + 10))
            done
        else
            log "Waiting for output files..."; sleep 30
        fi
    fi
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    echo ""
    header "MD Summary"
    echo -e "  ${BOLD}Wall time:${NC}  ${ELAPSED}s"
    echo -e "  ${BOLD}Output dir:${NC} $OUTPUT_DIR"
    [[ -f "${JOB_NAME}.ene" ]] && echo -e "  ${BOLD}Energy rows:${NC} $(tail -n +11 ${JOB_NAME}.ene | wc -l)"
    [[ -f "${JOB_NAME}.log" ]] && echo -e "  ${BOLD}Speed:${NC}      $(grep 'Total rate' ${JOB_NAME}.log | tail -1 | awk '{print $5}') ns/day"
    
    # Check for metadynamics output
    if [[ -f "${JOB_NAME}.kerseq" ]] && [[ -f "${JOB_NAME}.cvseq" ]]; then
        echo -e "  ${GREEN}Metadynamics: ✓ .kerseq + .cvseq generated${NC}"
    else
        warn "No .kerseq/.cvseq found — metadynamics may not have run"
    fi
    
    rm -rf "$PROJ_DIR"
    echo ""
    ls -lh "$OUTPUT_DIR"/*.{cpt,ene,log,kerseq,cvseq} 2>/dev/null | awk '{printf "  %-8s %s\n", $5, $NF}'
    exit $MULTISIM_EXIT

fi

# ═══════════════════════════════════════════════
# MODE: Analyze metadynamics outputs
# ═══════════════════════════════════════════════
if [[ "$MODE" == "analyze" ]]; then
    MD_DIR="$FOLDER"
    MD_NAME=$(basename "$MD_DIR")
    
    # Detect files
    CMS=$(ls "$MD_DIR"/*-out.cms 2>/dev/null | head -1)
    TRJ=$(ls -d "$MD_DIR"/*_trj 2>/dev/null | head -1)
    KERSEQ=$(ls "$MD_DIR"/*.kerseq 2>/dev/null | head -1)
    CVSEQ=$(ls "$MD_DIR"/*.cvseq 2>/dev/null | head -1)
    
    [[ -z "$KERSEQ" ]] && error "No .kerseq file found in $MD_DIR. Not a metadynamics job?"
    
    ANADIR="$MD_DIR/analysis"
    mkdir -p "$ANADIR"
    
    META_GEN="$SCRIPT_DIR/functions/meta_gen.py"
    PLOT_SCRIPT="$SCRIPT_DIR/functions/desmond_plot.py"
    
    # ── FIG-ONLY fast path ──
    if [[ "$FIG_ONLY" -eq 1 ]]; then
        header "Metadynamics Figure-Only: $MD_NAME"
        log "Re-plotting from existing CSV data..."
        
        [[ ! -f "$META_GEN" ]] && error "meta_gen.py not found at $META_GEN"
        [[ ! -f "$PLOT_SCRIPT" ]] && error "desmond_plot.py not found at $PLOT_SCRIPT"
        
            python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" 2>&1 | grep '✓' | while IFS= read -r line; do
                log "  $(echo "$line" | sed 's/^[[:space:]]*✓[[:space:]]*//')"
            done || true
        
        echo ""
        ls -lh "$ANADIR/figures"/meta_*.{pdf,png} 2>/dev/null | awk '{printf "  %-8s %s\n", $5, $NF}'
        echo -e "\n${GREEN}Re-plot complete.${NC}"
        exit 0
    fi
    
    # ── Full analysis ──
    header "Metadynamics Analysis: $MD_NAME"
    log "MD folder: $MD_DIR"
    log "Analysis dir: $ANADIR"
    
    if [[ -z "$CMS" ]] || [[ -z "$TRJ" ]]; then
        warn "Missing CMS or trajectory — some analyses may be limited"
    fi
    
    cd "$ANADIR"
    
    # Run meta_gen.py
    if [[ -f "$META_GEN" ]] && [[ -n "$CMS" ]] && [[ -n "$TRJ" ]]; then
        log "Parsing kernel and CV sequences..."
        META_OUT=$($RUN_SCHROD python3 "$META_GEN" "$CMS" "$TRJ" "$ANADIR" 2>&1)
        if [[ $? -eq 0 ]]; then
            echo "$META_OUT" | while IFS= read -r line; do
                [[ -n "$line" ]] && log "  $line"
            done
            NMETA=$(find "$ANADIR" -maxdepth 1 -name "meta_*.csv" | wc -l)
            log "Generated $NMETA metadynamics CSV file(s)"
            
            # Show summary
            if [[ -f "$ANADIR/meta_summary.txt" ]]; then
                echo ""
                cat "$ANADIR/meta_summary.txt"
            fi
        else
            warn "meta_gen.py failed"
        fi
    elif [[ ! -f "$META_GEN" ]]; then
        warn "meta_gen.py not found at $META_GEN"
    fi
    
    # ── Plot if requested ──
    if [[ "$DO_PLOT" -eq 1 ]] && [[ -f "$PLOT_SCRIPT" ]]; then
        header "Generating Metadynamics Figures"
        python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" 2>&1 | while IFS= read -r line; do
            [[ "$line" =~ ^\ *✓ ]] && log "  $line" || [[ "$line" =~ ^── ]] && echo -e "  ${BOLD}$line${NC}"
        done
        
        NPDF=$(find "$ANADIR/figures" -name "meta_*.pdf" 2>/dev/null | wc -l)
        NPNG=$(find "$ANADIR/figures" -name "meta_*.png" 2>/dev/null | wc -l)
        echo ""
        echo -e "${BOLD}── Metadynamics Figures ──${NC}"
        find "$ANADIR/figures" -name "meta_*.pdf" 2>/dev/null | sort | while read f; do
            echo -e "  📄 ${BOLD}$(basename $f)${NC}"
        done
        echo -e "  ${CYAN}Directory:${NC} $ANADIR/figures/"
        log "Generated: $NPDF PDFs + $NPNG PNGs"
    fi
    
    echo ""
    log "Analysis complete."
    exit 0
fi
