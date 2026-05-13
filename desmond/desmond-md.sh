#!/bin/bash
# ============================================================
# desmond-md.sh — Automated Schrödinger Desmond MD Pipeline
# ============================================================
# MOTUS v0.0.1 — See SKILL.md for full usage instructions.
#
# Mode 1 (default): Run from WITHIN a desmond_md_job_XXXXX folder
#   cd ~/xhy/desmond_md_job_urea-hydrolysis
#   bash ../motus/desmond/desmond-md.sh                # Use Maestro settings
#   bash ../motus/desmond/desmond-md.sh -t 5000 -i 2.5 # Optional: override
#
# Mode 2 (--mode 2): Old behavior — from a desmond_setup_XXXXX folder
#   bash motus/desmond/desmond-md.sh --mode 2 ~/xhy/desmond_setup_urea-hydrolysis -t 2000 -i 1
# ============================================================

set -euo pipefail

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Defaults ──
SIM_TIME=-1               # -1 = use .cfg value (no override)
REC_INTERVAL=-1           # -1 = use .cfg value
TEMPERATURE=300           # K
PRESSURE=1.01325          # bar
CUTOFF=5.0                # Å
CPU=1
GPU_LICENSE=16
MODE=1                    # 1 = md_job folder (CWD), 2 = setup folder (old)

# ── Auto-detect Schrödinger installation ──
SCHRODINGER="${SCHRODINGER:-}"
find_schrodinger() {
    if [[ -n "$SCHRODINGER" ]] && [[ -f "$SCHRODINGER/run" ]]; then
        return 0
    fi
    local search_paths=(
        /opt/schrodinger*
        /home/$USER/schrodinger*
        /home/$USER/tools/schrodinger*
        /usr/local/schrodinger*
        /shared/schrodinger*
    )
    for pattern in "${search_paths[@]}"; do
        for dir in $pattern; do
            if [[ -d "$dir" ]] && [[ -f "$dir/run" ]]; then
                SCHRODINGER="$dir"
                return 0
            fi
        done
    done
    return 1
}
if ! find_schrodinger; then
    echo -e "\033[0;31m[ERROR]\033[0m Cannot find Schrödinger installation."
    echo "    Set SCHRODINGER env var or install in /opt/ or ~/tools/"
    exit 1
fi

usage() {
    head -15 "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

log()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()   { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

# ── Fix Windows line endings (auto-detect CRLF) ──
fix_crlf() {
    local f="$1"
    if [[ ! -f "$f" ]]; then return; fi
    if grep -q $'\r' "$f" 2>/dev/null; then
        sed -i 's/\r$//' "$f"
        log "Fixed Windows (CRLF) line endings in $(basename "$f")"
    fi
}

# ── Safe integer from .cfg value (handles \r, decimals) ──
cfg_int() {
    # Extract a numeric value from .cfg, strip \r and decimal, return int
    tr -d '\r' < "$1" | awk -v pattern="$2" -v field="$3" '
        $0 ~ pattern { val=$field; gsub(/[^0-9].*/, "", val); if(val!="") {print val; exit} }
    '
}

# ── Parse args ──
TARGET_FOLDER=""
HAS_POSITIONAL=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)          MODE="$2"; shift 2 ;;
        -t|--time)       SIM_TIME="$2"; shift 2 ;;
        -i|--interval)   REC_INTERVAL="$2"; shift 2 ;;
        -T|--temperature) TEMPERATURE="$2"; shift 2 ;;
        -P|--pressure)   PRESSURE="$2"; shift 2 ;;
        -c|--cutoff)     CUTOFF="$2"; shift 2 ;;
        --cpu)           CPU="$2"; shift 2 ;;
        --gpu-license)   GPU_LICENSE="$2"; shift 2 ;;
        --schrodinger)   SCHRODINGER="$2"; shift 2 ;;
        -h|--help)       usage ;;
        -*)              error "Unknown option: $1" ;;
        *)               TARGET_FOLDER="$1"; HAS_POSITIONAL=1; shift ;;
    esac
done

# ── Validate SCHRODINGER ──
[[ ! -d "$SCHRODINGER" ]] && error "SCHRODINGER not found: $SCHRODINGER"
MULTISIM="$SCHRODINGER/utilities/multisim"
[[ ! -x "$MULTISIM" ]] && error "multisim not found: $MULTISIM"

# ═══════════════════════════════════════════════════
# MODE 1: md_job folder (default — auto-detect CWD)
# ═══════════════════════════════════════════════════
if [[ "$MODE" -eq 1 ]]; then
    if [[ "$HAS_POSITIONAL" -eq 0 ]]; then
        TARGET_FOLDER="$PWD"
    fi

    JOB_DIR=$(realpath "$TARGET_FOLDER")
    JOB_NAME=$(basename "$JOB_DIR")

    [[ ! -d "$JOB_DIR" ]] && error "Folder not found: $JOB_DIR"

    # Find .msj (most critical — defines the protocol)
    MSJ_FILE=$(ls "$JOB_DIR"/*.msj 2>/dev/null | head -1)
    [[ -z "$MSJ_FILE" ]] && error "No .msj file found in $JOB_DIR"

    # Find .cfg
    CFG_FILE=$(ls "$JOB_DIR"/*.cfg 2>/dev/null | grep -v '\-out\.cfg$' | grep -v '\-in\.cfg$' | head -1)
    if [[ -z "$CFG_FILE" ]]; then
        CFG_FILE=$(ls "$JOB_DIR"/*.cfg 2>/dev/null | head -1)
    fi
    [[ -z "$CFG_FILE" ]] && error "No .cfg file found in $JOB_DIR"

    # Find .cms (input structure — prefer the main one, not -in or -out)
    CMS_FILE=$(ls "$JOB_DIR"/*.cms 2>/dev/null | grep -v '\-out\.cms$' | grep -v '\-in\.cms$' | head -1)
    if [[ -z "$CMS_FILE" ]]; then
        # Fallback: use any .cms
        CMS_FILE=$(ls "$JOB_DIR"/*.cms 2>/dev/null | head -1)
    fi
    [[ -z "$CMS_FILE" ]] && error "No .cms file found in $JOB_DIR"

    # Auto-fix Windows line endings from Maestro
    fix_crlf "$CFG_FILE"
    fix_crlf "$MSJ_FILE"

    OUTPUT_DIR="$JOB_DIR"

    header "Desmond MD Pipeline (Mode 1: md_job folder)"
    echo -e "  ${BOLD}Job folder:${NC}   $JOB_DIR"
    echo -e "  ${BOLD}Job name:${NC}     $JOB_NAME"
    echo -e "  ${BOLD}CMS:${NC}          $(basename "$CMS_FILE")"
    echo -e "  ${BOLD}MSJ:${NC}          $(basename "$MSJ_FILE")"
    echo -e "  ${BOLD}CFG:${NC}          $(basename "$CFG_FILE")"

    # Warn if previous results exist
    if [[ -f "$JOB_DIR/${JOB_NAME}.ene" ]]; then
        warn "Existing .ene found — this folder already has MD results. Output may be overwritten."
    fi

    # ── Patch .cfg if -t/-i overrides provided ──
    if [[ "$SIM_TIME" -gt 0 ]] || [[ "$(awk -v ri="$REC_INTERVAL" 'BEGIN{print (ri>0)?1:0}')" -eq 1 ]]; then
        # Read original values from .cfg (safe: handles \r and decimals)
        ORIG_TIME=$(cfg_int "$CFG_FILE" '^time = ' 3)
        ORIG_INTERVAL=$(cfg_int "$CFG_FILE" '^trajectory = \{' 3)
        # For trajectory block interval, need to parse inside the block
        ORIG_INTERVAL=$(tr -d '\r' < "$CFG_FILE" | awk '/^trajectory = \{/{found=1} found && /interval =/{val=$3; gsub(/[^0-9].*/,"",val); print val; exit}' )

        TOTAL_PS=${SIM_TIME:-${ORIG_TIME:-2000}}
        [[ "$SIM_TIME" -le 0 ]] && TOTAL_PS="$ORIG_TIME"
        REC_INT=${REC_INTERVAL}
        [[ "$(awk -v ri="$REC_INTERVAL" 'BEGIN{print (ri>0)?1:0}')" -eq 0 ]] && REC_INT="$ORIG_INTERVAL"
        TOTAL_FRAMES=$(( TOTAL_PS / REC_INT ))
        CHKPT_INT=$(( TOTAL_PS / 10 ))
        [[ $CHKPT_INT -lt 50 ]] && CHKPT_INT=50

        log "Patching .cfg: time=${TOTAL_PS}ps, interval=${REC_INT}ps, frames=${TOTAL_FRAMES}, chkpt=${CHKPT_INT}s"

        # Patch time (top-level)
        sed -i "s/^time = .*/time = ${TOTAL_PS}.0/" "$CFG_FILE"

        # Patch trajectory block: interval + frames_per_file
        sed -i "/^trajectory = {/,/^}/{
            s/\(interval = \)[0-9.]\+/\1${REC_INT}.0/
            s/\(frames_per_file = \)[0-9]\+/\1${TOTAL_FRAMES}/
        }" "$CFG_FILE"

        # Patch eneseq block: interval
        sed -i "/^eneseq = {/,/^}/{
            s/\(interval = \)[0-9.]\+/\1${REC_INT}.0/
        }" "$CFG_FILE"

        # Patch checkpt block: interval
        sed -i "/^checkpt = {/,/^}/{
            s/\(interval = \)[0-9.]\+/\1${CHKPT_INT}.0/
        }" "$CFG_FILE"

        # Patch maeff_output block: interval
        sed -i "/^maeff_output = {/,/^}/{
            s/\(interval = \)[0-9.]\+/\1${CHKPT_INT}.0/
        }" "$CFG_FILE"
    else
        # Use .cfg values (safe: handles \r and decimals via cfg_int)
        TOTAL_PS=$(cfg_int "$CFG_FILE" '^time = ' 3)
        REC_INT=$(tr -d '\r' < "$CFG_FILE" | awk '/^trajectory = \{/{found=1} found && /interval =/{val=$3; gsub(/[^0-9].*/,"",val); print val; exit}')
        [[ -z "$TOTAL_PS" ]] && TOTAL_PS=2000
        [[ -z "$REC_INT" ]] && REC_INT=1
        TOTAL_FRAMES=$(( TOTAL_PS / REC_INT ))
        log "Using .cfg settings: time=${TOTAL_PS}ps, interval=${REC_INT}ps, frames=${TOTAL_FRAMES}"
    fi

    echo -e "  ${BOLD}Sim time:${NC}      ${TOTAL_PS} ps (${TOTAL_FRAMES} frames)"
    echo -e "  ${BOLD}Record interval:${NC} ${REC_INT} ps"
    echo -e "  ${BOLD}Schrodinger:${NC}   $SCHRODINGER"

# ═══════════════════════════════════════════════════
# MODE 2: setup folder (old behavior)
# ═══════════════════════════════════════════════════
elif [[ "$MODE" -eq 2 ]]; then
    [[ "$HAS_POSITIONAL" -eq 0 ]] && error "Mode 2 requires a desmond_setup_XXXXX folder as argument.\nUsage: $0 --mode 2 <desmond_setup_XXXXX> [OPTIONS]"

    SETUP_DIR=$(realpath "$TARGET_FOLDER")
    SETUP_NAME=$(basename "$SETUP_DIR")
    [[ ! -d "$SETUP_DIR" ]] && error "Setup folder not found: $SETUP_DIR"

    # Extract system name from "desmond_setup_XXXXX"
    if [[ "$SETUP_NAME" =~ ^desmond_setup_(.+)$ ]]; then
        SYSTEM="${BASH_REMATCH[1]}"
    else
        error "Setup folder must be named 'desmond_setup_XXXXX'\nGot: $SETUP_NAME"
    fi

    JOB_NAME="desmond_md_job_${SYSTEM}"

    # Find output CMS from setup
    CMS_INPUT=$(ls "$SETUP_DIR/${SETUP_NAME}-out.cms" 2>/dev/null || echo "")
    [[ -z "$CMS_INPUT" ]] && error "No output CMS found in setup folder.\nExpected: $SETUP_DIR/${SETUP_NAME}-out.cms"

    # Determine output directory
    OUTPUT_DIR="$(dirname "$SETUP_DIR")/${JOB_NAME}"
    mkdir -p "$OUTPUT_DIR"

    [[ "$SIM_TIME" -le 0 ]] && SIM_TIME=2000
    [[ "$(awk -v ri="$REC_INTERVAL" 'BEGIN{print (ri>0)?1:0}')" -eq 0 ]] && REC_INTERVAL=1
    TOTAL_PS="$SIM_TIME"
    REC_INT="$REC_INTERVAL"
    TOTAL_FRAMES=$(( TOTAL_PS / REC_INT ))
    CHKPT_INT=$(( TOTAL_PS / 10 ))
    [[ $CHKPT_INT -lt 50 ]] && CHKPT_INT=50

    header "Desmond MD Pipeline (Mode 2: setup folder)"
    echo -e "  ${BOLD}System:${NC}        $SYSTEM"
    echo -e "  ${BOLD}Setup folder:${NC}  $SETUP_DIR"
    echo -e "  ${BOLD}Output folder:${NC} $OUTPUT_DIR"
    echo -e "  ${BOLD}Sim time:${NC}      ${TOTAL_PS} ps (${TOTAL_FRAMES} frames)"
    echo -e "  ${BOLD}Record interval:${NC} ${REC_INT} ps"
    echo -e "  ${BOLD}Temperature:${NC}   ${TEMPERATURE} K"
    echo -e "  ${BOLD}Schrodinger:${NC}   $SCHRODINGER"

    # ── Copy CMS input ──
    log "Copying system from setup..."
    cp "$CMS_INPUT" "$OUTPUT_DIR/${JOB_NAME}-in.cms"
    cp "$CMS_INPUT" "$OUTPUT_DIR/${JOB_NAME}.cms"

    # ── Generate .msj (equilibration protocol) ──
    log "Generating $JOB_NAME.msj..."
    cat > "$OUTPUT_DIR/${JOB_NAME}.msj" << MSJEOF
# Desmond standard NPT relaxation protocol
# Auto-generated by desmond-md.sh
# All times in ps, energy in kcal/mol
task {
  task = "desmond:auto"
  set_family = {
    desmond = {
      checkpt.write_last_step = no
    }
  }
}

simulate {
  title       = "Brownian Dynamics NVT, T = 10 K, small timesteps, and restraints on solute heavy atoms, 100ps"
  annealing   = off
  time        = 100
  timestep    = [0.001 0.001 0.003 ]
  temperature = 10.0
  ensemble = {
    class  = "NVT"
    method = "Brownie"
    brownie = {
      delta_max = 0.1
    }
  }
  polarization_restraints = full
  restraints.new = [
    {
      name            = posre_harm
      atoms           = solute_heavy_atom
      force_constants = 50.0
    }
  ]
  eneseq.interval = 0.3
}

simulate {
  title                   = "NVT, T = 10 K, small timesteps, and restraints on solute heavy atoms, 12ps"
  annealing               = off
  time                    = 12
  timestep                = [0.001 0.001 0.003]
  temperature             = 10.0
  polarization_restraints = full
  restraints.new = [
    {
      name            = posre_harm
      atoms           = solute_heavy_atom
      force_constants = 50.0
    }
  ]
  ensemble = {
    class          = NVT
    method         = Langevin
    thermostat.tau = 0.1
  }
  randomize_velocity.interval = 1.0
  eneseq.interval             = 0.3
  trajectory.center           = []
}

simulate {
  title                   = "NPT, T = 10 K, and restraints on solute heavy atoms, 12ps"
  annealing               = off
  time                    = 12
  temperature             = 10.0
  polarization_restraints = full
  restraints.existing     = retain
  ensemble = {
    class          = NPT
    method         = Langevin
    thermostat.tau = 0.1
    barostat  .tau = 50.0
  }
  randomize_velocity.interval = 1.0
  eneseq.interval             = 0.3
  trajectory.center           = []
}

simulate {
  title                   = "NPT and restraints on solute heavy atoms, 12ps"
  effect_if               = [["@*.*.annealing"] 'annealing = off temperature = "@*.*.temperature[0][0]"']
  time                    = 12
  polarization_restraints = full
  restraints.existing     = retain
  ensemble = {
    class          = NPT
    method         = Langevin
    thermostat.tau = 0.1
    barostat  .tau = 50.0
  }
  randomize_velocity.interval = 1.0
  eneseq.interval             = 0.3
  trajectory.center           = []
}

simulate {
  title     = "NPT and no restraints, 24ps"
  effect_if = [["@*.*.annealing"] 'annealing = off temperature = "@*.*.temperature[0][0]"']
  time      = 24
  ensemble = {
    class          = NPT
    method         = Langevin
    thermostat.tau = 0.1
    barostat  .tau = 2.0
  }
  polarization_restraints = decay
  eneseq.interval         = 0.3
  trajectory.center       = solute
}

simulate {
   cfg_file = "${JOB_NAME}.cfg"
   jobname  = "\$MAINJOBNAME"
   dir      = "."
   compress = ""
}
MSJEOF

    # ── Generate .cfg (production run) ──
    log "Generating $JOB_NAME.cfg..."
    cat > "$OUTPUT_DIR/${JOB_NAME}.cfg" << CFGEOF
annealing = false
backend = {
}
bigger_rclone = false
box = ?
bulk_properties = false
checkpt = {
   first = 0.0
   interval = ${CHKPT_INT}.0
   name = "\$JOBNAME.cpt"
   write_last_step = true
}
cpu = ${CPU}
cutoff_radius = ${CUTOFF}
dipole_moment = false
ebias_force = false
elapsed_time = 0.0
energy_group = false
eneseq = {
   first = 0.0
   interval = ${REC_INT}.0
   name = "\$JOBNAME\$[_replica\$REPLICA\$].ene"
}
ensemble = {
   barostat = {
      tau = 2.0
   }
   class = NPT
   method = MTK
   thermostat = {
      tau = 1.0
   }
}
gaussian_force = false
glue = solute
lambda_dynamics = false
maeff_output = {
   center_atoms = solute
   first = 0.0
   interval = ${CHKPT_INT}.0
   name = "\$JOBNAME\$[_replica\$REPLICA\$]-out.cms"
   periodicfix = true
   trjdir = "\$JOBNAME\$[_replica\$REPLICA\$]_trj"
}
meta = false
meta_file = ?
msd = false
polarization_restraints = none
pressure = [${PRESSURE} isotropic ]
pressure_tensor = false
randomize_velocity = {
   first = 0.0
   interval = inf
   seed = 2007
   temperature = "@*.temperature"
}
restrain = none
restraints = {
   existing = ignore
   new = []
}
rnemd = false
simbox = {
   first = 0.0
   interval = 1.2
   name = "\$JOBNAME\$[_replica\$REPLICA\$]_simbox.dat"
}
spatial_temperature = false
surface_tension = 0.0
taper = false
temperature = [
   [${TEMPERATURE}.0 0 ]
]
time = ${TOTAL_PS}.0
timestep = [0.002 0.002 0.006 ]
trajectory = {
   center = []
   first = 0.0
   format = dtr
   frames_per_file = ${TOTAL_FRAMES}
   interval = ${REC_INT}.0
   name = "\$JOBNAME\$[_replica\$REPLICA\$]_trj"
   periodicfix = true
   write_last_step = true
   write_last_vel = false
   write_velocity = false
}
wall_force = false
CFGEOF

    CMS_FILE="$OUTPUT_DIR/${JOB_NAME}.cms"
    MSJ_FILE="$OUTPUT_DIR/${JOB_NAME}.msj"
    CFG_FILE="$OUTPUT_DIR/${JOB_NAME}.cfg"

else
    error "Invalid mode: $MODE. Use 1 (md_job folder, default) or 2 (setup folder)."
fi

# ═══════════════════════════════════════════════════
# COMMON: Launch Desmond MD via multisim
# ═══════════════════════════════════════════════════

# ── Create tmp project dir ──
PROJ_DIR="$OUTPUT_DIR/.proj_tmp"
mkdir -p "$PROJ_DIR"

header "Launching Desmond MD"
log "Job name: $JOB_NAME"
log "Output dir: $OUTPUT_DIR"

cd "$OUTPUT_DIR"

START_TIME=$(date +%s)

# Capture multisim output to extract JobId
MULTISIM_OUT=$("$MULTISIM" \
    -JOBNAME "$JOB_NAME" \
    -HOST localhost \
    -maxjob 1 \
    -cpu "$CPU" \
    -m "$(basename "$MSJ_FILE")" \
    -c "$(basename "$CFG_FILE")" \
    -description "Molecular Dynamics - ${TOTAL_PS}ps" \
    "$(basename "$CMS_FILE")" \
    -mode umbrella \
    -PROJ "$PROJ_DIR" \
    -DISP append \
    -o "${JOB_NAME}-out.cms" \
    -lic "DESMOND_GPGPU:${GPU_LICENSE}" 2>&1)

MULTISIM_EXIT=$?
echo "$MULTISIM_OUT" | tail -5

# Extract JobId from multisim output
JOB_ID=$(echo "$MULTISIM_OUT" | grep -oP 'JobId:\s*\K\S+' | head -1)

if [[ -z "$JOB_ID" ]]; then
    warn "Could not detect JobId. Multisim exit code: $MULTISIM_EXIT"
    EXIT_CODE=$MULTISIM_EXIT
else
    log "Job ID: $JOB_ID — waiting for completion..."
    EXIT_CODE=0

    # ── Find scratch directory (varies by server/Schrödinger install) ──
    SCRATCH_BASE=""
    find_scratch() {
        # Try common patterns, return first match containing the job
        for base in "$SCHRODINGER/scratch/$USER" "$SCHRODINGER/scratch"; do
            if [[ -d "$base" ]]; then
                SCRATCH_BASE="$base"
                return 0
            fi
        done
        return 1
    }
    find_scratch || SCRATCH_BASE="$SCHRODINGER/scratch/$USER"

    # ── Poll for completion with stage + progress monitoring ──
    JOBCTL="$SCHRODINGER/jobcontrol"
    MULTISIM_LOG="${OUTPUT_DIR}/${JOB_NAME}_multisim.log"

    if [[ -x "$JOBCTL" ]]; then
        TIMEOUT=$(( TOTAL_PS / 10 + 600 ))
        POLL_INTERVAL=5
        ELAPSED_WAIT=0
        LAST_STAGE_LINE=""
        LAST_PROGRESS=""
        STAGE_SHOWN=0

        while true; do
            # ── Show multisim stage output (equilibration progress) ──
            if [[ -f "$MULTISIM_LOG" ]]; then
                STAGE_LINE=$(grep -E '^Stage [0-9]|completed\.|failed\.|running' "$MULTISIM_LOG" 2>/dev/null | tail -3) || true
                if [[ -n "$STAGE_LINE" ]] && [[ "$STAGE_LINE" != "$LAST_STAGE_LINE" ]]; then
                    echo -e "  ${CYAN}$(echo "$STAGE_LINE" | tail -1)${NC}"
                    LAST_STAGE_LINE="$STAGE_LINE"
                    STAGE_SHOWN=1
                fi
            fi

            # ── Production progress bar ──
            # Log is in scratch: $SCRATCH_BASE/$JOB_NAME/$JOB_NAME.log
            # or sub-stage: $SCRATCH_BASE/$JOB_NAME.N/$JOB_NAME.log
            SCRATCH_LOG="$SCRATCH_BASE/${JOB_NAME}/${JOB_NAME}.log"
            if [[ ! -f "$SCRATCH_LOG" ]]; then
                SCRATCH_LOG=$(ls -t "$SCRATCH_BASE/${JOB_NAME}."*"/${JOB_NAME}.log" 2>/dev/null | head -1) || true
            fi
            if [[ -f "$SCRATCH_LOG" ]]; then
                PROGRESS_LINE=$(grep 'Chemical time:' "$SCRATCH_LOG" 2>/dev/null | tail -1) || true
                if [[ -n "$PROGRESS_LINE" ]] && [[ "$PROGRESS_LINE" != "$LAST_PROGRESS" ]]; then
                    CHEM_TIME=$(echo "$PROGRESS_LINE" | grep -oP 'Chemical time:\s+\K[0-9.]+')
                    NS_DAY=$(echo "$PROGRESS_LINE" | grep -oP 'ns/day:\s+\K[0-9.]+')
                    PCT=$(awk -v t="$CHEM_TIME" -v total="$TOTAL_PS" 'BEGIN{printf "%.0f", t/total*100}')
                    [[ ${PCT:-0} -gt 100 ]] && PCT=100
                    BAR_LEN=30
                    FILLED=$(( PCT * BAR_LEN / 100 ))
                    EMPTY=$(( BAR_LEN - FILLED ))
                    BAR=$(printf "%${FILLED}s" | tr ' ' '=')$(printf "%${EMPTY}s" | tr ' ' '-')
                    printf "\r  [%s] %3d%% | %s/%s ps | %s ns/day" \
                        "$BAR" "$PCT" "$CHEM_TIME" "$TOTAL_PS" "${NS_DAY:-N/A}"
                    LAST_PROGRESS="$PROGRESS_LINE"
                fi
            fi

            # ── Status check ──
            STATUS=$("$JOBCTL" -list "$JOB_ID" 2>/dev/null | grep "$JOB_ID" | head -1)
            if echo "$STATUS" | grep -qE "exited|finished|died|killed|cancelled"; then
                EXIT_LINE=$("$JOBCTL" -list "$JOB_ID" 2>/dev/null | grep "$JOB_ID" | head -1)
                STATUS_WORD=$(echo "$EXIT_LINE" | awk '{print $4}')
                if [[ "$STATUS_WORD" =~ ^(died|killed|cancelled)$ ]]; then
                    EXIT_CODE=1
                    echo ""
                    log "Job $STATUS_WORD — check ${JOB_NAME}_multisim.log for details"
                else
                    EXIT_CODE=0
                    echo ""
                    log "Job finished successfully"
                fi
                break
            fi
            if [[ -z "$STATUS" ]]; then
                echo ""
                log "Job completed (record cleaned)"
                break
            fi
            if [[ $ELAPSED_WAIT -ge $TIMEOUT ]]; then
                echo ""
                warn "Timeout after ${TIMEOUT}s — job may still be running"
                break
            fi
            sleep $POLL_INTERVAL
            ELAPSED_WAIT=$((ELAPSED_WAIT + POLL_INTERVAL))
        done
    else
        log "Waiting for output files to appear..."
        for i in $(seq 1 120); do
            if [[ -f "${JOB_NAME}.ene" ]]; then
                sleep 3
                break
            fi
            sleep 5
        done
    fi
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    header "MD Completed Successfully"
else
    header "MD Failed (exit code: $EXIT_CODE)"
fi

echo -e "  ${BOLD}Wall time:${NC}     ${ELAPSED}s"
echo -e "  ${BOLD}Output dir:${NC}    $OUTPUT_DIR"

# ── Summary ──
ENERGY_FILE="$OUTPUT_DIR/${JOB_NAME}.ene"
LOG_FILE="$OUTPUT_DIR/${JOB_NAME}.log"

if [[ -f "$ENERGY_FILE" ]]; then
    NROWS=$(tail -n +11 "$ENERGY_FILE" | wc -l)
    echo -e "  ${BOLD}Energy rows:${NC}   $NROWS"
fi

if [[ -f "$LOG_FILE" ]]; then
    TOTAL_RATE=$(grep "Total rate" "$LOG_FILE" | tail -1 | awk '{print $5}')
    echo -e "  ${BOLD}Performance:${NC}   ${TOTAL_RATE:-N/A} ns/day"
fi

# Cleanup tmp
rm -rf "$PROJ_DIR"

echo ""
echo -e "${GREEN}Files:${NC}"
ls -lh "$OUTPUT_DIR"/*.{cms,cpt,cfg,msj,ene,log} 2>/dev/null | awk '{printf "  %-8s %s\n", $5, $NF}'

exit $EXIT_CODE
