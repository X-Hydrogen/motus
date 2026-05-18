#!/bin/bash
# ============================================================================
# desmond-metamd_job-analysis.sh — Standalone Desmond Metadynamics Pipeline
# ============================================================================
# MOTUS v1.0 — Works directly from Windows Maestro output folders.
# Completely independent of desmond-metadynamics.sh.
#
# Usage:
#   # Run MD + auto-analyze (default: CWD if run from inside the job folder)
#   bash desmond-metamd_job-analysis.sh
#   bash desmond-metamd_job-analysis.sh ~/xhy/desmond_metadynamics_job_353-test
#
#   # Analyze only (MD already done, has .kerseq + .cvseq)
#   bash desmond-metamd_job-analysis.sh ~/xhy/desmond_metadynamics_job_353-test --analyze-only
#
#   # Re-plot only (skip analysis, regenerate figures)
#   bash desmond-metamd_job-analysis.sh ~/xhy/desmond_metadynamics_job_353-test --fig-only
#
# What it does:
#   1. Fixes Windows CRLF line endings (.msj, .cfg, .sh)
#   2. Launches Desmond metadynamics MD via multisim
#   3. Monitors: equilibration stages + production progress bar (ns/day)
#   4. After completion: auto-analyzes .kerseq + .cvseq via Schrödinger Python
#   5. Generates 4 publication-quality figures:
#      - meta_cv_time:    CV evolution over simulation time
#      - meta_height:     Gaussian height decay (well-tempered)
#      - meta_fes_1d/2d: Free energy surface
#      - meta_summary:    Dashboard
# ============================================================================

set -euo pipefail

# ── Colors ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

usage() {
    head -28 "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

# ── Script directory (for finding desmond_plot.py, meta_gen.py) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
META_GEN="${SCRIPT_DIR}/functions/meta_gen.py"
PLOT_SCRIPT="${SCRIPT_DIR}/functions/desmond_plot.py"

# ── Auto-detect Schrödinger installation ──
SCHRODINGER="${SCHRODINGER:-}"
find_schrodinger() {
    if [[ -n "$SCHRODINGER" ]] && [[ -f "$SCHRODINGER/run" ]]; then return 0; fi
    local search_paths=(
        /opt/schrodinger* /home/$USER/schrodinger*
        /home/$USER/tools/schrodinger* /usr/local/schrodinger* /shared/schrodinger*
    )
    for pattern in "${search_paths[@]}"; do
        for dir in $pattern; do
            if [[ -d "$dir" ]] && [[ -f "$dir/run" ]]; then
                SCHRODINGER="$dir"; return 0
            fi
        done
    done
    return 1
}
find_schrodinger || error "Cannot find Schrödinger. Set SCHRODINGER env var."

RUN_SCHROD="$SCHRODINGER/run"
MULTISIM="$SCHRODINGER/utilities/multisim"
JOBCTL="$SCHRODINGER/jobcontrol"

# ── Fix Windows CRLF ──
# ── Safe file finder (handles no-match gracefully with pipefail) ──
safe_find() {
    # Usage: safe_find <dir> <glob> — prints first match or nothing
    shopt -s nullglob
    local files=( "$1"/$2 )
    shopt -u nullglob
    if [[ ${#files[@]} -gt 0 ]]; then
        echo "${files[0]}"
    fi
}

fix_crlf() {
    local f="$1"
    if [[ ! -f "$f" ]]; then return; fi
    if grep -q $'\r' "$f" 2>/dev/null; then
        sed -i 's/\r$//' "$f"
        log "Fixed Windows (CRLF) line endings: $(basename "$f")"
    fi
}

# ── Safe integer from .cfg ──
cfg_int() {
    tr -d '\r' < "$1" | awk -v pattern="$2" -v field="$3" '
        $0 ~ pattern { val=$field; gsub(/[^0-9].*/, "", val); if(val!="") {print val; exit} }
    '
}

# ── Parse args ──
JOB_FOLDER=""
ANALYZE_ONLY=0
FIG_ONLY=0
MODE="full"   # full | analyze | fig
CPU=1
GPU_LICENSE=16

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --analyze-only) ANALYZE_ONLY=1; MODE="analyze"; shift ;;
        --fig-only)     FIG_ONLY=1; MODE="fig"; shift ;;
        --cpu)          CPU="$2"; shift 2 ;;
        --gpu-license)  GPU_LICENSE="$2"; shift 2 ;;
        --schrodinger)  SCHRODINGER="$2"; shift 2 ;;
        -*)             error "Unknown option: $1" ;;
        *)              JOB_FOLDER="$1"; shift ;;
    esac
done

# Default: CWD if no folder given
if [[ -z "$JOB_FOLDER" ]]; then
    JOB_FOLDER="$(pwd)"
fi

JOB_FOLDER="$(realpath "$JOB_FOLDER")"
JOB_NAME="$(basename "$JOB_FOLDER")"

[[ ! -d "$JOB_FOLDER" ]] && error "Folder not found: $JOB_FOLDER"

# ═══════════════════════════════════════════════════
# Validate job folder (must look like desmond_metadynamics_job_XXXXX)
# ═══════════════════════════════════════════════════
if [[ ! "$JOB_NAME" =~ ^desmond_metadynamics_job_ ]]; then
    warn "Folder name doesn't match 'desmond_metadynamics_job_XXXXX' pattern."
    warn "Continuing anyway with: $JOB_NAME"
fi

# Find key files (with nullglob-safe patterns)
shopt -s nullglob
_cms_files=( "$JOB_FOLDER"/*.cms )
_cms_main=()
for f in "${_cms_files[@]}"; do
    [[ "$(basename "$f")" =~ -out\.cms$|^-in\.cms$ ]] && continue
    _cms_main+=("$f")
done
CMS_FILE="${_cms_main[0]:-}"
[[ -z "$CMS_FILE" ]] && CMS_FILE="${_cms_files[0]:-}"
[[ -z "$CMS_FILE" ]] && error "No .cms file found in $JOB_FOLDER"

_msj_files=( "$JOB_FOLDER"/*.msj )
MSJ_FILE="${_msj_files[0]:-}"
[[ -z "$MSJ_FILE" ]] && error "No .msj file found in $JOB_FOLDER"

_cfg_files=( "$JOB_FOLDER"/*.cfg )
_cfg_main=()
for f in "${_cfg_files[@]}"; do
    [[ "$(basename "$f")" =~ -out\.cfg$ ]] && continue
    _cfg_main+=("$f")
done
CFG_FILE="${_cfg_main[0]:-}"
[[ -z "$CFG_FILE" ]] && CFG_FILE="${_cfg_files[0]:-}"
[[ -z "$CFG_FILE" ]] && error "No .cfg file found in $JOB_FOLDER"
shopt -u nullglob

# Fix Windows CRLF
fix_crlf "$MSJ_FILE"
fix_crlf "$CFG_FILE"
# Also fix .sh if present
SH_FILE=$(safe_find "$JOB_FOLDER" "*.sh")
[[ -n "$SH_FILE" ]] && fix_crlf "$SH_FILE"

# ── Extract parameters from .cfg ──
SIM_TIME=$(cfg_int "$CFG_FILE" '^time = ' 3)
[[ -z "$SIM_TIME" ]] && SIM_TIME=5000

REC_INT=$(tr -d '\r' < "$CFG_FILE" | awk '/^trajectory = \{/{found=1} found && /interval =/{val=$3; print val; exit}' | tr -d ',' | grep -oP '[0-9.]+')
[[ -z "$REC_INT" ]] && REC_INT=2.5

TEMP=$(tr -d '\r' < "$CFG_FILE" | awk '/temperature = \[/{getline; gsub(/[\[\]]/, ""); val=$1+0; print val; exit}')
[[ -z "$TEMP" ]] || [[ "$TEMP" == "0" ]] && TEMP=300

TOTAL_FRAMES=$(awk -v t="$SIM_TIME" -v i="$REC_INT" 'BEGIN{printf "%.0f", t/i}')

header "Desmond Metadynamics Job — $JOB_NAME"
echo -e "  ${BOLD}Job folder:${NC}     $JOB_FOLDER"
echo -e "  ${BOLD}Input CMS:${NC}     $(basename "$CMS_FILE")"
echo -e "  ${BOLD}Protocol:${NC}      $(basename "$MSJ_FILE")"
echo -e "  ${BOLD}Sim time:${NC}      ${SIM_TIME} ps (${TOTAL_FRAMES} frames)"
echo -e "  ${BOLD}Rec interval:${NC}  ${REC_INT} ps"
echo -e "  ${BOLD}Temperature:${NC}   ${TEMP} K"
echo -e "  ${BOLD}Schrödinger:${NC}  $SCHRODINGER"
echo -e "  ${BOLD}Mode:${NC}          $MODE"
echo ""

# ═══════════════════════════════════════════════════
# Extract CV info from .msj for display
# ═══════════════════════════════════════════════════
CV_INFO=$(grep -A2 'type = ' "$MSJ_FILE" 2>/dev/null | grep -E 'type|atom|width' | head -6)
if [[ -n "$CV_INFO" ]]; then
    echo -e "  ${BOLD}CV definition:${NC}"
    echo "$CV_INFO" | while IFS= read -r line; do
        echo -e "    $(echo "$line" | sed 's/^[[:space:]]*//' | tr -d '\r')"
    done
fi

# ── Detect metadynamics params from .msj ──
MT_HEIGHT=$(grep 'height = ' "$MSJ_FILE" 2>/dev/null | grep -oP '[0-9.]+' | head -1 || echo "0.03")
MT_INTERVAL=$(grep -A15 'meta = {' "$MSJ_FILE" 2>/dev/null | grep 'interval = ' | grep -oP '[0-9.]+' | head -1)
[[ -z "$MT_INTERVAL" ]] && MT_INTERVAL="0.09"
echo -e "  ${BOLD}Meta height:${NC}    ${MT_HEIGHT} kcal/mol"
echo -e "  ${BOLD}Meta interval:${NC}  ${MT_INTERVAL} ps"
echo ""

# ═══════════════════════════════════════════════════
# FIG-ONLY fast path
# ═══════════════════════════════════════════════════
if [[ "$FIG_ONLY" -eq 1 ]]; then
    ANADIR="$JOB_FOLDER/analysis"
    FIGDIR="$ANADIR/figures"
    
    if [[ ! -f "$PLOT_SCRIPT" ]]; then
        error "Plot script not found: $PLOT_SCRIPT"
    fi
    
    header "Metadynamics Figure-Only Mode"
    log "Re-plotting from existing CSV data in $ANADIR ..."
    
    # Run plot script for meta plots
    python3 "$PLOT_SCRIPT" "$ANADIR" --type all 2>&1 | while IFS= read -r line; do
        if [[ "$line" =~ ✓ ]]; then
            log "  $(echo "$line" | sed 's/^[[:space:]]*✓[[:space:]]*//')"
        fi
    done || true
    
    echo ""
    echo -e "${BOLD}── Metadynamics Figures ──${NC}"
    find "$FIGDIR" -name "meta_*" -type f 2>/dev/null | sort | while read f; do
        SIZE=$(du -h "$f" | cut -f1)
        echo -e "  ${GREEN}📄${NC} $(basename "$f") (${SIZE})"
    done
    echo ""
    log "Re-plot complete."
    exit 0
fi

# ═══════════════════════════════════════════════════
# Check if MD already completed (has .ene + .kerseq)
# ═══════════════════════════════════════════════════
ENE_FILE=$(safe_find "$JOB_FOLDER" "*.ene")
KERSEQ=$(safe_find "$JOB_FOLDER" "*.kerseq")
CVSEQ=$(safe_find "$JOB_FOLDER" "*.cvseq")

MD_ALREADY_DONE=0
if [[ -n "$ENE_FILE" ]] && [[ -n "$KERSEQ" ]] && [[ -n "$CVSEQ" ]]; then
    MD_ALREADY_DONE=1
fi

if [[ "$ANALYZE_ONLY" -eq 1 ]]; then
    if [[ "$MD_ALREADY_DONE" -eq 0 ]]; then
        error "No .kerseq/.cvseq found. MD hasn't been run yet. Remove --analyze-only to run MD first."
    fi
    log "MD already completed — skipping to analysis."
fi

# ═══════════════════════════════════════════════════
# LAUNCH MD (if not already done and not analyze-only)
# ═══════════════════════════════════════════════════
if [[ "$MD_ALREADY_DONE" -eq 0 ]] && [[ "$ANALYZE_ONLY" -eq 0 ]]; then
    
    # Check if .msj has meta block
    if ! grep -q 'meta = {' "$MSJ_FILE" 2>/dev/null; then
        warn "No 'meta = {' block detected in .msj — this may not be a metadynamics job."
        warn "Continuing anyway..."
    fi
    
    # Check if .msj has analysis block
    if grep -q 'analysis {' "$MSJ_FILE" 2>/dev/null; then
        log "Analysis block detected in .msj — FES will be auto-computed after MD."
    fi
    
    header "Launching Metadynamics MD"
    log "Job name: $JOB_NAME"
    log "Output dir: $JOB_FOLDER"
    
    cd "$JOB_FOLDER"
    
    # Check for previous run results
    if [[ -f "$JOB_NAME.ene" ]]; then
        warn "Existing .ene found — results may be overwritten."
    fi
    
    PROJ_DIR="$JOB_FOLDER/.proj_tmp"
    mkdir -p "$PROJ_DIR"
    
    START_TIME=$(date +%s)
    
    # Launch multisim
    MULTISIM_OUT=$("$MULTISIM" \
        -JOBNAME "$JOB_NAME" \
        -HOST localhost \
        -maxjob 1 \
        -cpu "$CPU" \
        -m "$(basename "$MSJ_FILE")" \
        -c "$(basename "$CFG_FILE")" \
        -description "Metadynamics MD - ${SIM_TIME}ps" \
        "$(basename "$CMS_FILE")" \
        -mode umbrella \
        -PROJ "$PROJ_DIR" \
        -DISP append \
        -o "${JOB_NAME}-out.cms" \
        -lic "DESMOND_GPGPU:${GPU_LICENSE}" 2>&1)
    
    MULTISIM_EXIT=$?
    echo "$MULTISIM_OUT" | tail -5
    
    # Extract JobId
    JOB_ID=$(echo "$MULTISIM_OUT" | grep -oP 'JobId:\s*\K\S+' | head -1)
    
    if [[ -z "$JOB_ID" ]]; then
        warn "Could not detect JobId. Multisim exit code: $MULTISIM_EXIT"
        EXIT_CODE=$MULTISIM_EXIT
    else
        log "Job ID: $JOB_ID — monitoring progress..."
        EXIT_CODE=0
        
        # Find scratch directory
        SCRATCH_BASE=""
        for base in "$SCHRODINGER/scratch/$USER" "$SCHRODINGER/scratch"; do
            if [[ -d "$base" ]]; then
                SCRATCH_BASE="$base"
                break
            fi
        done
        [[ -z "$SCRATCH_BASE" ]] && SCRATCH_BASE="$SCHRODINGER/scratch/$USER"
        
        # ── Poll with stage + progress monitoring ──
        MULTISIM_LOG="${JOB_FOLDER}/${JOB_NAME}_multisim.log"
        TIMEOUT=$(( SIM_TIME / 10 + 600 ))
        POLL_INTERVAL=5
        ELAPSED_WAIT=0
        LAST_STAGE_LINE=""
        LAST_PROGRESS=""
        EQUIL_DONE=0
        
        while true; do
            # ── Show equilibration stages ──
            if [[ -f "$MULTISIM_LOG" ]] && [[ "$EQUIL_DONE" -eq 0 ]]; then
                STAGE_LINE=$(grep -E '^Stage [0-9]|completed\.|failed\.|running' "$MULTISIM_LOG" 2>/dev/null | tail -3) || true
                if [[ -n "$STAGE_LINE" ]] && [[ "$STAGE_LINE" != "$LAST_STAGE_LINE" ]]; then
                    echo -e "  ${CYAN}$(echo "$STAGE_LINE" | tail -1)${NC}"
                    LAST_STAGE_LINE="$STAGE_LINE"
                fi
                # Check if we've moved past equilibration (stage output that mentions 'meta')
                if echo "$STAGE_LINE" | grep -q 'meta'; then
                    EQUIL_DONE=1
                fi
            fi
            
            # ── Production progress bar (metadynamics stage) ──
            SCRATCH_LOG="$SCRATCH_BASE/${JOB_NAME}/${JOB_NAME}.log"
            if [[ ! -f "$SCRATCH_LOG" ]]; then
                SCRATCH_LOG=$(ls -t "$SCRATCH_BASE/${JOB_NAME}."*"/${JOB_NAME}.log" 2>/dev/null | head -1) || true
            fi
            
            if [[ -f "$SCRATCH_LOG" ]]; then
                PROGRESS_LINE=$(grep 'Chemical time:' "$SCRATCH_LOG" 2>/dev/null | tail -1) || true
                if [[ -n "$PROGRESS_LINE" ]] && [[ "$PROGRESS_LINE" != "$LAST_PROGRESS" ]]; then
                    CHEM_TIME=$(echo "$PROGRESS_LINE" | grep -oP 'Chemical time:\s+\K[0-9.]+' || echo "0")
                    NS_DAY=$(echo "$PROGRESS_LINE" | grep -oP 'ns/day:\s+\K[0-9.]+' || echo "N/A")
                    PCT=$(awk -v t="$CHEM_TIME" -v total="$SIM_TIME" 'BEGIN{printf "%.0f", t/total*100}' 2>/dev/null || echo "0")
                    [[ ${PCT:-0} -gt 100 ]] && PCT=100
                    BAR_LEN=30
                    FILLED=$(( PCT * BAR_LEN / 100 ))
                    EMPTY=$(( BAR_LEN - FILLED ))
                    BAR=$(printf "%${FILLED}s" | tr ' ' '=')$(printf "%${EMPTY}s" | tr ' ' '-')
                    printf "\r  [%s] %3d%% | %s/%s ps | %s ns/day" \
                        "$BAR" "$PCT" "$CHEM_TIME" "$SIM_TIME" "${NS_DAY:-N/A}"
                    LAST_PROGRESS="$PROGRESS_LINE"
                fi
            fi
            
            # ── Check completion ──
            if [[ -x "$JOBCTL" ]]; then
                STATUS=$("$JOBCTL" -list "$JOB_ID" 2>/dev/null | grep "$JOB_ID" | head -1) || true
                if echo "$STATUS" | grep -qE "exited|finished|died|killed|cancelled"; then
                    printf "\n"
                    log "Job finished: $(echo "$STATUS" | awk '{print $2}')"
                    if echo "$STATUS" | grep -qE "died|killed|cancelled"; then
                        EXIT_CODE=1
                    fi
                    break
                fi
                if [[ -z "$STATUS" ]]; then
                    printf "\n"
                    log "Job completed (record cleaned from jobcontrol)"
                    break
                fi
            fi
            
            [[ $ELAPSED_WAIT -ge $TIMEOUT ]] && { printf "\n"; warn "Timeout after ${TIMEOUT}s"; break; }
            sleep $POLL_INTERVAL
            ELAPSED_WAIT=$((ELAPSED_WAIT + POLL_INTERVAL))
        done
    fi
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    printf "\n"
    
    # ── MD Summary ──
    header "MD Summary"
    echo -e "  ${BOLD}Wall time:${NC}  ${ELAPSED}s ($(( ELAPSED / 60 ))m $(( ELAPSED % 60 ))s)"
    echo -e "  ${BOLD}Output dir:${NC} $JOB_FOLDER"
    
    ENE_FILE=$(safe_find "$JOB_FOLDER" "*.ene")
    if [[ -n "$ENE_FILE" ]] && [[ -f "$ENE_FILE" ]]; then
        ENE_ROWS=$(tail -n +11 "$ENE_FILE" 2>/dev/null | wc -l)
        echo -e "  ${BOLD}Energy rows:${NC} $ENE_ROWS"
    fi
    
    KERSEQ=$(safe_find "$JOB_FOLDER" "*.kerseq")
    CVSEQ=$(safe_find "$JOB_FOLDER" "*.cvseq")
    
    if [[ -n "$KERSEQ" ]] && [[ -n "$CVSEQ" ]]; then
        KER_SIZE=$(wc -c < "$KERSEQ" 2>/dev/null || echo "?")
        CV_SIZE=$(wc -c < "$CVSEQ" 2>/dev/null || echo "?")
        echo -e "  ${GREEN}Metadynamics:${NC} ✓ .kerseq (${KER_SIZE} bytes) + .cvseq (${CV_SIZE} bytes)"
        MD_ALREADY_DONE=1
    else
        warn "No .kerseq/.cvseq found — metadynamics may not have run"
    fi
    
    # Show output files
    echo ""
    ls -lh "$JOB_FOLDER"/*.{ene,kerseq,cvseq,log,cpt} 2>/dev/null | awk '{printf "  %-8s %s\n", $5, $NF}'
    
    rm -rf "$PROJ_DIR"
    
    if [[ "$EXIT_CODE" -ne 0 ]]; then
        error "MD job failed (exit code: $EXIT_CODE). Check logs in $JOB_FOLDER"
    fi
    
    echo ""
fi

# ═══════════════════════════════════════════════════
# ANALYSIS: Parse metadynamics output
# ═══════════════════════════════════════════════════

# Re-detect files (in case they were just created by MD)
KERSEQ=$(safe_find "$JOB_FOLDER" "*.kerseq")
CVSEQ=$(safe_find "$JOB_FOLDER" "*.cvseq")
TRJ_DIR=$(safe_find "$JOB_FOLDER" "*_trj")

if [[ -z "$KERSEQ" ]]; then
    warn "No .kerseq file found — skipping metadynamics analysis."
    warn "If MD is still running, wait for it to complete, then run:"
    warn "  $0 $JOB_FOLDER --analyze-only"
    exit 0
fi

ANADIR="$JOB_FOLDER/analysis"
FIGDIR="$ANADIR/figures"
mkdir -p "$ANADIR" "$FIGDIR"

header "Metadynamics Analysis"
log "Kerseq:  $(basename "$KERSEQ")"
log "Cvseq:   $(basename "$CVSEQ")"
if [[ -n "$TRJ_DIR" ]]; then
    log "Traj:    $(basename "$TRJ_DIR")"
fi

# ── Run meta_gen.py via Schrödinger Python ──
if [[ -f "$META_GEN" ]]; then
    log "Running meta_gen.py (CV + kernel parsing + FES)..."
    
    CMS_OUT=$(safe_find "$JOB_FOLDER" "*-out.cms")
    [[ -z "$CMS_OUT" ]] && CMS_OUT="$CMS_FILE"
    [[ -z "$TRJ_DIR" ]] && TRJ_DIR="$JOB_FOLDER"
    
    cd "$ANADIR"
    
    # Use Schrödinger's Python for CMS/Desmond package access
    META_OUT=$("$RUN_SCHROD" python3 "$META_GEN" "$CMS_OUT" "$TRJ_DIR" "$ANADIR" 2>&1)
    META_EXIT=$?
    
    echo "$META_OUT" | while IFS= read -r line; do
        if [[ "$line" =~ ^✓ ]]; then
            log "  $(echo "$line" | sed 's/^✓[[:space:]]*//')"
        elif [[ -n "$line" ]] && [[ ! "$line" =~ ^[[:space:]]*$ ]]; then
            echo -e "  ${CYAN}$line${NC}"
        fi
    done
    
    if [[ $META_EXIT -ne 0 ]]; then
        warn "meta_gen.py exited with code $META_EXIT"
    fi
    
    # Count generated CSVs
    N_CSV=$(find "$ANADIR" -maxdepth 1 -name "meta_*.csv" | wc -l)
    log "Generated $N_CSV metadynamics CSV file(s)"
    
    # Show summary
    if [[ -f "$ANADIR/meta_summary.txt" ]]; then
        echo ""
        echo -e "${BOLD}── Metadynamics Summary ──${NC}"
        cat "$ANADIR/meta_summary.txt"
    fi
    
else
    warn "meta_gen.py not found at $META_GEN"
    warn "Skipping CV/kernel parsing. Only FES from Desmond's analysis block (if any) will be available."
fi

# ── Generate plots ──
if [[ -f "$PLOT_SCRIPT" ]]; then
    header "Generating Metadynamics Figures"
    
    python3 "$PLOT_SCRIPT" "$ANADIR" --type all 2>&1 | while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*✓ ]]; then
            log "  $(echo "$line" | sed 's/^[[:space:]]*✓[[:space:]]*//')"
        elif [[ "$line" =~ ^── ]]; then
            echo -e "  ${BOLD}$line${NC}"
        fi
    done || true
    
    # ── Figure summary ──
    echo ""
    echo -e "${BOLD}── Metadynamics Figures ──${NC}"
    for f in $(find "$FIGDIR" -name "meta_*.pdf" -o -name "meta_*.png" 2>/dev/null | sort); do
        SIZE=$(du -h "$f" | cut -f1)
        EXT="${f##*.}"
        case "$EXT" in
            pdf) echo -e "  📄 ${BOLD}$(basename "$f")${NC} (${SIZE})" ;;
            png) echo -e "  🖼  $(basename "$f") (${SIZE})" ;;
        esac
    done
    
    N_PDF=$(find "$FIGDIR" -name "meta_*.pdf" 2>/dev/null | wc -l)
    N_PNG=$(find "$FIGDIR" -name "meta_*.png" 2>/dev/null | wc -l)
    
    if [[ $N_PDF -gt 0 ]] || [[ $N_PNG -gt 0 ]]; then
        echo ""
        echo -e "  ${CYAN}Directory:${NC} $FIGDIR/"
        log "Generated: $N_PDF PDF(s) + $N_PNG PNG(s)"
    else
        warn "No metadynamics figures generated. Check if meta_*.csv files exist in $ANADIR"
    fi
else
    warn "Plot script not found at $PLOT_SCRIPT"
fi

# ═══════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ✅  Metadynamics pipeline complete!${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Job folder:${NC}   $JOB_FOLDER"
echo -e "  ${BOLD}Analysis:${NC}     $ANADIR/"
echo -e "  ${BOLD}Figures:${NC}     $FIGDIR/"
echo ""
echo -e "  ${CYAN}Next steps:${NC}"
echo -e "    • View FES:      evince $FIGDIR/meta_fes_1d.pdf"
echo -e "    • Re-plot only:  $0 $JOB_FOLDER --fig-only"
echo -e "    • Full analysis: $0 $JOB_FOLDER --analyze-only"
echo ""
