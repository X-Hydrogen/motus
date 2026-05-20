#!/bin/bash
# ============================================================
# desmond-analysis.sh — Comprehensive Desmond MD Analysis  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   desmond-analysis.sh [md_job_folder] [OPTIONS]
#   (Run from within the folder to auto-detect, or pass the folder as argument)
#
# Options:
#   --plot              Full analysis + generate publication figures (PDF+PNG)
#   --fig-only          Skip analysis, ONLY re-plot from existing CSV data
#   --free-volume       Enable free volume / void analysis (SLOW, ~hours for large systems, off by default)
#   --plot-type <type>  Plot type: energy|hbonds|water_shells|rdf|density|rg|distance|water_res|dipole|freevol|cluster|dashboard|all
#
# The folder must contain:
#   -out.cms (final structure), _trj/ (trajectory), .ene (energy), .log (log)
#
# Automatically runs ALL available Schrödinger analysis tools
# and generates a summary report.
# ============================================================

set -eu

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Auto-detect Schrödinger installation ──
SCHRODINGER="${SCHRODINGER:-}"
find_schrodinger() {
    if [[ -n "$SCHRODINGER" ]] && [[ -f "$SCHRODINGER/run" ]]; then
        return 0
    fi
    # Search common install locations
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
    echo -e "\033[0;31m[✗]\033[0m Cannot find Schrödinger installation."
    echo "    Set SCHRODINGER environment variable or install in /opt/ or ~/tools/"
    exit 1
fi
TIMEOUT=600

# ── Find a working python3 (must have numpy + matplotlib + scipy) ──
# Priority: MOTUS_PYTHON env var → .motus_python_path → conda → system
find_python3() {
    local candidates=()

    # 1. MOTUS_PYTHON environment variable
    if [[ -n "${MOTUS_PYTHON:-}" ]] && [[ -x "$MOTUS_PYTHON" ]]; then
        candidates+=("$MOTUS_PYTHON")
    fi

    # 2. Saved path from setup.sh
    local motus_py_path="$SCRIPT_DIR/.motus_python_path"
    if [[ -f "$motus_py_path" ]]; then
        local saved_py
        saved_py=$(cat "$motus_py_path" 2>/dev/null)
        if [[ -n "$saved_py" ]] && [[ -x "$saved_py" ]]; then
            candidates+=("$saved_py")
        fi
    fi

    # 3. Conda
    candidates+=(
        /home/xenon/miniconda3/bin/python3
        /opt/miniconda3/bin/python3
        "$HOME/miniconda3/bin/python3"
    )

    # 4. Generic conda (search PATH)
    if command -v conda &>/dev/null; then
        local conda_py
        conda_py=$(command -v python3 2>/dev/null || true)
        if [[ -n "$conda_py" ]] && [[ -x "$conda_py" ]]; then
            candidates+=("$conda_py")
        fi
    fi

    # 5. System fallback
    candidates+=(
        /usr/bin/python3
        /bin/python3
    )

    for py in "${candidates[@]}"; do
        if [[ -x "$py" ]] && "$py" -c "import numpy, matplotlib, scipy" 2>/dev/null; then
            echo "$py"
            return 0
        fi
    done
    return 1
}
PYTHON3=$(find_python3)
if [[ -z "$PYTHON3" ]]; then
    echo -e "\033[0;31m[✗]\033[0m No python3 with numpy+matplotlib+scipy found. Install: pip install scipy"
    exit 1
fi

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; }
skip()   { echo -e "${YELLOW}[~]${NC} $* (skipped)"; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }
section(){ echo -e "\n${BOLD}── $* ──${NC}"; }

usage() {
    head -18 "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

# ── Parse args ──
MD_FOLDER=""; ASL1=""; ASL2=""; DO_PLOT=1; FIG_ONLY=0; PLOT_TYPE="all"; DO_FREEVOL=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --asl1) ASL1="$2"; shift 2 ;;
        --asl2) ASL2="$2"; shift 2 ;;
        --schrodinger) SCHRODINGER="$2"; shift 2 ;;
        --plot)   DO_PLOT=1; shift ;;
        --fig-only) FIG_ONLY=1; DO_PLOT=1; shift ;; 
        --plot-type) PLOT_TYPE="$2"; shift 2 ;;
        --free-volume) DO_FREEVOL=1; shift ;;
        *) MD_FOLDER="$1"; shift ;;
    esac
done

# ── Validation ──
[[ -z "$MD_FOLDER" ]] && MD_FOLDER="$PWD"
[[ ! -d "$MD_FOLDER" ]] && error "Folder not found: $MD_FOLDER" && exit 1

MD_DIR=$(realpath "$MD_FOLDER")
MD_NAME=$(basename "$MD_DIR")

# Detect system name
if [[ "$MD_NAME" =~ ^desmond_md_job_(.+)$ ]]; then
    SYSTEM="${BASH_REMATCH[1]}"
else
    SYSTEM="$MD_NAME"
fi

# ═══════════════════════════════════════════════
# FAST PATH: --fig-only → skip all analysis, just re-plot
# ═══════════════════════════════════════════════
if [[ "$FIG_ONLY" -eq 1 ]]; then
    ANADIR="$MD_DIR/analysis"
    mkdir -p "$ANADIR"

    header "Figure-Only Mode: $SYSTEM"
    log "Skipping analysis — re-plotting from existing CSV data"

    NCSV=$(find "$ANADIR" -maxdepth 1 -name "*.csv" 2>/dev/null | wc -l)
    if [[ $NCSV -eq 0 ]]; then
        error "No CSV files found in $ANADIR/"
        error "Run without --fig-only first to generate analysis data."
        exit 1
    fi
    log "Found $NCSV CSV files in $ANADIR/"

    PLOT_SCRIPT="$SCRIPT_DIR/functions/desmond_plot.py"
    if [[ ! -f "$PLOT_SCRIPT" ]]; then
        error "desmond_plot.py not found at $PLOT_SCRIPT"
        exit 1
    fi

    log "Running plot generation (type: $PLOT_TYPE)..."
    PLOT_LOG=$(mktemp)
    python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" > "$PLOT_LOG" 2>&1
    while IFS= read -r line; do
        log "  $line"
    done < "$PLOT_LOG"
    rm -f "$PLOT_LOG"

    NPDF=$(find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | wc -l)
    NPNG=$(find "$ANADIR/figures" -name "*.png" 2>/dev/null | wc -l)

    # Also process SIMA .dat files if present
    SIMA_SCRIPT="$SCRIPT_DIR/functions/sima_plot.py"
    SIMA_FILES=$(find "$ANADIR" -maxdepth 1 -name "*.dat" 2>/dev/null | wc -l)
    if [[ $SIMA_FILES -gt 0 ]] && [[ -f "$SIMA_SCRIPT" ]]; then
        log "Processing Simulation Interactions Diagram data ($SIMA_FILES .dat files)..."
        python3 "$SIMA_SCRIPT" "$ANADIR" --type all > /dev/null 2>&1
        NSIMA=$(find "$ANADIR/figures" -name "sima_*.pdf" 2>/dev/null | wc -l)
        [[ $NSIMA -gt 0 ]] && log "  Generated $NSIMA SIMA figure(s)"
    fi

    NPDF=$(find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | wc -l)
    NPNG=$(find "$ANADIR/figures" -name "*.png" 2>/dev/null | wc -l)
    log "Generated: $NPDF PDFs + $NPNG PNGs"

    echo ""
    if [[ -d "$ANADIR/figures" ]]; then
        echo -e "${BOLD}── Publication Figures ──${NC}"
        find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | sort | while read f; do
            echo -e "  📄 ${BOLD}$(basename $f)${NC}"
        done
        echo ""
        echo -e "  ${CYAN}Full directory:${NC} $ANADIR/figures/"
    fi
    echo ""
    echo -e "${GREEN}Re-plot complete.${NC}"
    exit 0
fi

# Find required files
CMS=$(ls "$MD_DIR"/*-out.cms 2>/dev/null | head -1)
TRJ=$(ls -d "$MD_DIR"/*_trj 2>/dev/null | head -1)
ENE=$(ls "$MD_DIR"/*.ene 2>/dev/null | head -1)
LOG=$(ls "$MD_DIR"/*.log 2>/dev/null | grep -v multisim | head -1)
CFG=$(ls "$MD_DIR"/*.cfg 2>/dev/null | grep -v cpt | grep -v out | head -1)
MSJ=$(ls "$MD_DIR"/*.msj 2>/dev/null | head -1)
JOBNAME=$(basename "$MD_DIR")
[[ -z "$CFG" ]] && CFG=$(ls "$MD_DIR"/*.cfg 2>/dev/null | grep -v out | head -1)

[[ -z "$CMS" ]] && error "No -out.cms found in $MD_DIR" && exit 1
[[ -z "$TRJ" ]] && error "No _trj/ found in $MD_DIR" && exit 1
[[ -z "$ENE" ]] && warn "No .ene found — energy analysis will be skipped"
[[ -z "$LOG" ]] && warn "No .log found — simulation summary will be limited"

# Create analysis directory
ANADIR="$MD_DIR/analysis"
mkdir -p "$ANADIR"
REPORT="$ANADIR/analysis_report.txt"
> "$REPORT"

RUN_SCHROD="$SCHRODINGER/run"

# ═══════════════════════════════════════════════
# NORMAL PATH: Full analysis pipeline
# ═══════════════════════════════════════════════

report() { echo "$@" >> "$REPORT"; }
report_sep() { echo "──────────────────────────────────────────────" >> "$REPORT"; }

header "Desmond Analysis: $SYSTEM"
log "MD folder: $MD_DIR"
log "Output dir: $ANADIR"

# ── Discover system composition ──
section "System Inspection"
log "Inspecting system composition..."
INSPECT_OUT=$($SCHRODINGER/run python3 -c "
import schrodinger.structure as st
s = list(st.StructureReader('$CMS'))
for i, m in enumerate(s):
    atoms = m.atom_total
    waters = m.atom_total - len([a for a in m.atom if a.element != 'H' and a.element != 'O'])
    chains = set(a.chain for a in m.atom)
    print(f'M{i}: {m.title[:60]}, atoms={atoms}, chains={chains}')
" 2>&1) || true

echo "$INSPECT_OUT" | while IFS= read -r line; do
    log "  $line"
    report "  $line"
done

# ── Auto-detect ASL ──
# ASL values WITHOUT shell quotes (Schrödinger tools handle their own parsing)
HAS_PROTEIN=0
if echo "$INSPECT_OUT" | grep -qi "protein"; then
    HAS_PROTEIN=1
fi

if [[ -z "$ASL1" ]]; then
    if [[ "$HAS_PROTEIN" -eq 1 ]]; then
        ASL1="protein"
    else
        ASL1="solute"
    fi
fi
if [[ -z "$ASL2" ]]; then
    if [[ "$HAS_PROTEIN" -eq 1 ]]; then
        ASL2="ligand"
    else
        ASL2="water"
    fi
fi

log "ASL1 (group 1): $ASL1"
log "ASL2 (group 2): $ASL2"
report "ASL1: $ASL1"
report "ASL2: $ASL2"

# ============================================================
# ANALYSIS 1: Simulation Summary (from log + ene)
# ============================================================
header "1. Simulation Summary"
cd "$ANADIR"

if [[ -n "$LOG" ]]; then
    log "Extracting simulation parameters..."
    
    START_TIME=$(grep "start time:" "$LOG" | tail -1 | sed 's/.*start time: //')
    STOP_TIME=$(grep "stop time:" "$LOG" | tail -1 | sed 's/.*stop time: //')
    DURATION=$(grep "duration:" "$LOG" | tail -1 | sed 's/.*duration: //')
    TOTAL_RATE=$(grep "Total rate" "$LOG" | tail -1 | awk '{print $5}')
    GPU=$(grep "name.*=" "$LOG" | grep -i "geforce\|nvidia\|rtx" | head -1 | grep -oP '= \K.*' | tr -d ' ')
    
    report "── Simulation Summary ──"
    report "Start:     $START_TIME"
    report "End:       $STOP_TIME" 
    report "Duration:  $DURATION"
    report "GPU:       $GPU"
    report "Speed:     ${TOTAL_RATE:-N/A} ns/day"
    report_sep
    
    log "  Time:  $DURATION"
    log "  Speed: ${TOTAL_RATE:-N/A} ns/day"
    log "  GPU:   $GPU"
fi

# ============================================================
# ANALYSIS 2: Energy Analysis (from .ene file)
# ============================================================
header "2. Energy Analysis"
if [[ -n "$ENE" ]]; then
    log "Parsing energy file..."
    
    # Extract data (skip 10 header lines)
    tail -n +11 "$ENE" | awk '{
        time=$1; etot=$2; epot=$3; ekin=$4; press=$8; vol=$9; temp=$10
        n++; sum_t+=temp; sum_p+=press; sum_v+=vol; sum_e+=etot; sum_ep+=epot
        sum_t2+=temp*temp; sum_p2+=press*press
        
        if (NR==1) { t_min=temp; t_max=temp; p_min=press; p_max=press }
        if (temp<t_min) t_min=temp
        if (temp>t_max) t_max=temp
        if (press<p_min) p_min=press
        if (press>p_max) p_max=press
    } END {
        avg_t=sum_t/n; avg_p=sum_p/n; avg_v=sum_v/n
        std_t=sqrt(sum_t2/n - avg_t*avg_t)
        std_p=sqrt(sum_p2/n - avg_p*avg_p)
        printf "Frames: %d\n", n
        printf "T_avg: %.1f K  T_std: %.1f  T_range: [%.0f, %.0f]\n", avg_t, std_t, t_min, t_max
        printf "P_avg: %.0f bar  P_std: %.0f  P_range: [%.0f, %.0f]\n", avg_p, std_p, p_min, p_max
        printf "V_avg: %.1f A^3\n", avg_v
        printf "Epot_avg: %.1f kcal/mol\n", sum_ep/n
    }' > "$ANADIR/energy_stats.txt" 2>/dev/null
    
    if [[ -s "$ANADIR/energy_stats.txt" ]]; then
        while IFS= read -r line; do
            log "  $line"
            report "$line"
        done < "$ANADIR/energy_stats.txt"
    fi
    
    # Generate energy time-series CSV for further plotting
    log "Generating energy CSV..."
    echo "Time_ps,Total_E_kcal,Pot_E_kcal,Kin_E_kcal,Pressure_bar,Vol_A3,Temp_K" > "$ANADIR/energy_timeseries.csv"
    tail -n +11 "$ENE" | awk '{printf "%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.3f\n", $1,$2,$3,$4,$8,$9,$10}' >> "$ANADIR/energy_timeseries.csv"
    log "  → energy_timeseries.csv ($(wc -l < "$ANADIR/energy_timeseries.csv") rows)"
else
    skip "No .ene file found"
fi
report_sep

# ============================================================
# ANALYSIS 3: Hydrogen Bond Analysis
# ============================================================
header "3. Hydrogen Bond Analysis"
cd "$ANADIR"

log "Running trajectory_analyze_hbonds..."
if $RUN_SCHROD trajectory_analyze_hbonds.py "$CMS" hbonds_all.csv "'all'" 2>/dev/null; then
    NFRAMES=$(tail -n +2 hbonds_all.csv | wc -l)
    HB_AVG=$(tail -n +2 hbonds_all.csv | awk -F',' '{sum+=$2; n++} END {printf "%.1f", sum/n}')
    HB_MIN=$(tail -n +2 hbonds_all.csv | awk -F',' 'NR==1{m=$2}{if($2<m)m=$2} END{print m}')
    HB_MAX=$(tail -n +2 hbonds_all.csv | awk -F',' 'NR==1{M=$2}{if($2>M)M=$2} END{print M}')
    
    log "  Frames:     $NFRAMES"
    log "  Avg H-bonds: ${HB_AVG}"
    log "  Range:       [${HB_MIN}, ${HB_MAX}]"
    
    report "── H-Bond Analysis ──"
    report "  Frames analyzed: $NFRAMES"
    report "  Average H-bonds: ${HB_AVG}"
    report "  Range: [${HB_MIN}, ${HB_MAX}]"
    
    # Also do solute-only H-bonds
    if [[ "$HAS_PROTEIN" -eq 0 ]]; then
        log "Running solute-only H-bond analysis..."
        $RUN_SCHROD trajectory_analyze_hbonds.py "$CMS" hbonds_solute.csv "solute" 2>/dev/null || true
        if [[ -f hbonds_solute.csv ]]; then
            HB_S_AVG=$(tail -n +2 hbonds_solute.csv | awk -F',' '{sum+=$2; n++} END {printf "%.1f", sum/n}')
            log "  Solute H-bonds avg: ${HB_S_AVG}"
            report "  Solute H-bonds avg: ${HB_S_AVG}"
        fi
    fi
else
    warn "H-bond analysis failed"
fi
report_sep

# ============================================================
# ANALYSIS 4: Solute-Water Distance & Contacts — Vectorized
# ============================================================
# Uses fully vectorized numpy broadcasting instead of O(water×solute)
# Python loops. 100-1000× faster for large systems.
# ============================================================
header "4. Solute-Water Shell Analysis (Vectorized)"
cd "$ANADIR"

WATERSHELL_FAST="$SCRIPT_DIR/functions/water_shell_fast.py"
if [[ -f "$WATERSHELL_FAST" ]]; then
    log "Using vectorized water shell classification..."
    WATERSHELL_OUT=$($RUN_SCHROD python3 "$WATERSHELL_FAST" \
        "$CMS" "$TRJ" "$ANADIR" \
        --stride 10 --max-frames 500 2>&1)
    echo "$WATERSHELL_OUT" | grep -E 'Water|Solute|DONE|Bound|Second|Free|✓' | while IFS= read -r line; do
        log "  $line"
    done
    
    if [[ -f solute_water_shells.csv ]]; then
        BOUND_AVG=$(tail -n +2 solute_water_shells.csv | awk -F',' '{sum+=$4; n++} END {printf "%.1f", sum/n}')
        SECOND_AVG=$(tail -n +2 solute_water_shells.csv | awk -F',' '{sum+=$5; n++} END {printf "%.1f", sum/n}')
        FREE_AVG=$(tail -n +2 solute_water_shells.csv | awk -F',' '{sum+=$6; n++} END {printf "%.1f", sum/n}')
        TOTAL_W=$(head -2 solute_water_shells.csv | tail -1 | awk -F',' '{print $3}')
        report "── Solute-Water Shell Analysis (Vectorized) ──"
        report "  Total water: ${TOTAL_W}"
        report "  Bound (<3.5):  ${BOUND_AVG:-N/A} avg"
        report "  2nd shell:     ${SECOND_AVG:-N/A} avg"
        report "  Free (>5.0):   ${FREE_AVG:-N/A} avg"
    fi
else
    warn "water_shell_fast.py not found — using legacy inline Python (slow)"
    # [legacy inline Python code preserved as fallback in original script]
fi
report_sep

# ============================================================
# ANALYSIS 5: Full Geometric Analysis (EAF pipeline, protein-only)
# ============================================================
header "5. Structure & RMSD Analysis (event_analysis + analyze_simulation)"
cd "$ANADIR"

# event_analysis + analyze_simulation are designed for protein systems.
# For pure small-molecule / solvent systems, use targeted trajectory analysis instead.
if [[ "$HAS_PROTEIN" -eq 1 ]]; then
    log "Step 5a: Generating event analysis file..."
    EAF_PREFIX="full_analysis"
    EAF_IN="${EAF_PREFIX}-in.eaf"

    if $RUN_SCHROD event_analysis.py analyze \
        -p "$ASL1" -l "$ASL2" -o "$EAF_PREFIX" "$CMS" 2>/dev/null; then
        if [[ -f "$EAF_IN" ]]; then
            log "  → $EAF_IN generated"
            log "Step 5b: Running frame-by-frame analysis (this may take a while)..."
            if $RUN_SCHROD analyze_simulation.py \
                -WAIT -LOCAL \
                ${CFG:+-sim-cfg "$CFG"} \
                "$CMS" "$TRJ" "$EAF_PREFIX" "$EAF_IN" 2>/dev/null; then
                log "  ✓ Full trajectory analysis complete"
                report "── Full Geometric Analysis ──"
                report "  EAF analysis: complete"
                find "$ANADIR" -name "${EAF_PREFIX}*" -type f ! -name "*.json" 2>/dev/null | while read f; do
                    log "    → $(basename $f)"
                done
            else
                warn "analyze_simulation returned non-zero"
                report "  analyze_simulation: completed with warnings"
            fi
        fi
    else
        warn "event_analysis failed"
        report "  event_analysis: failed (check ASL expressions)"
    fi
else
    skip "event_analysis (requires protein)"
    report "  event_analysis: skipped (non-protein system)"
    
    # Fallback: solute-only RMSD via trajectory_bfactors 
    # (bfactors also protein-only, so skip here too; use manual ASL RMSD if needed)
fi
report_sep

# ============================================================
# ANALYSIS 6: Advanced Tools (if applicable)
# ============================================================
header "6. Advanced Analysis"

cd "$ANADIR"

# 6a: Dihedral analysis (if residues present)
log "Checking for dihedral analysis..."
if [[ "$HAS_PROTEIN" -gt 0 ]]; then
    log "Running trajectory_dihedral (backbone)..."
    $RUN_SCHROD trajectory_dihedral.py \
        -c "$CMS" -r "1-999" -dihedrals backbone \
        -output_csv dihedral_backbone.csv 2>/dev/null && \
        log "  → dihedral_backbone.csv" || \
        warn "  Dihedral analysis failed"
else
    skip "Dihedral analysis (no protein residues)"
fi

# 6b: B-factor analysis (protein-only)
if [[ "$HAS_PROTEIN" -eq 1 ]]; then
    log "Running B-factor analysis..."
    if $RUN_SCHROD trajectory_bfactors.py -asl "protein" -csv "$CMS" bfactors_protein.csv 2>/dev/null; then
        log "  → bfactors_protein.csv"
        if [[ -f bfactors_protein.csv ]]; then
            BF_N=$(tail -n +2 bfactors_protein.csv | wc -l)
            BF_AVG=$(tail -n +2 bfactors_protein.csv | awk -F',' '{sum+=$3; n++} END {printf "%.2f", sum/n}')
            log "  Residues: $BF_N, Avg RMSF: ${BF_AVG}"
            report "── B-Factor / RMSF Analysis ──"
            report "  Residues: $BF_N"
            report "  Avg RMSF: ${BF_AVG} Å"
        fi
    else
        warn "B-factor analysis failed"
    fi
else
    skip "B-factor analysis (requires protein)"
    report "  B-factor analysis: skipped (non-protein system)"
fi

# 6c: Protein-protein interaction (if multiple chains)
if [[ "$HAS_PROTEIN" -gt 0 ]]; then
    log "Running protein interaction analysis..."
    $RUN_SCHROD analyze_trajectory_ppi.py \
        "$CMS" ppi_analysis.csv "protein" "protein" 2>/dev/null && \
        log "  → ppi_analysis.csv" || \
        warn "  PPI analysis failed"
else
    skip "Protein interaction analysis (no protein)"
fi

# 6d: Simulation Interactions Diagram — Schrödinger native SIMA (two-step EAF pipeline)
header "6d. Simulation Interactions Diagram (Schrödinger SIMA)"

# Auto-detect largest non-water molecule for ligand designation
LIGAND_ASL=$($RUN_SCHROD python3 -c "
import schrodinger.structure as st
max_atoms, best_mol = 0, 'mol. 1'
for i, s in enumerate(st.StructureReader('$CMS')):
    # Skip water boxes (they have many O atoms and are titled 'TIP3P' or 'water')
    is_water = 'tip3p' in s.title.lower() or 'water' in s.title.lower() or 'spc' in s.title.lower()
    if not is_water and s.atom_total > max_atoms:
        max_atoms = s.atom_total
        best_mol = f'mol. {i+1}'
print(best_mol)
" 2>&1)

log "  Detected ligand: $LIGAND_ASL"

# Step 1: event_analysis.py → generate .eaf
EAF_PREFIX="$ANADIR/sima_eaf"
log "Step 1: event_analysis.py analyze..."
# Suppress X11 forwarding (headless server)
unset DISPLAY 2>/dev/null || true
$RUN_SCHROD python3 "$SCHRODINGER/mmshare-v7.0/python/scripts/event_analysis.py" analyze \
    -prot "none" -lig "$LIGAND_ASL" -o "$EAF_PREFIX" \
    "$CMS" 2>&1 | tail -1

EAF_IN="${EAF_PREFIX}-in.eaf"
EAF_OUT="${EAF_PREFIX}-out.eaf"

if [[ -f "$EAF_IN" ]]; then
    log "  → ${EAF_PREFIX}-in.eaf generated"
    
    # Step 2: analyze_simulation.py with EAF
    log "Step 2: analyze_simulation.py..."
    unset DISPLAY 2>/dev/null || true
    SIMA_LOG=$(mktemp)
    if $RUN_SCHROD python3 "$SCHRODINGER/internal/bin/analyze_simulation.py" \
        -WAIT -LOCAL \
        ${CFG:+-sim-cfg "$CFG"} \
        "$CMS" "$TRJ" "$EAF_PREFIX" "$EAF_IN" > "$SIMA_LOG" 2>&1; then
        tail -3 "$SIMA_LOG" | while IFS= read -r l; do log "  $l"; done
    else
        warn "SIMA analysis failed:"
        tail -3 "$SIMA_LOG" | while IFS= read -r l; do warn "  $l"; done
    fi
    rm -f "$SIMA_LOG"
    
    # Find the actual output file (may be EAF_PREFIX without .eaf extension)
    EAF_FILE="$EAF_OUT"
    [[ ! -f "$EAF_FILE" ]] && EAF_FILE="$EAF_PREFIX"
    [[ ! -f "$EAF_FILE" ]] && EAF_FILE="${EAF_PREFIX}-out"
    
    if [[ -f "$EAF_FILE" ]]; then
        log "SIMA results: $(du -h "$EAF_FILE" | cut -f1)"
        
        # Ensure .eaf extension for downstream report generation
        EAF_REPORT_FILE="${EAF_PREFIX}.eaf"
        if [[ "$EAF_FILE" != "$EAF_REPORT_FILE" ]]; then
            cp "$EAF_FILE" "$EAF_REPORT_FILE"
        fi
        
        # Extract data
        DATA_DIR="$ANADIR/data"
        mkdir -p "$DATA_DIR"
        EXTRACTOR="$SCRIPT_DIR/functions/extract_sima.py"
        if [[ -f "$EXTRACTOR" ]]; then
            python3 "$EXTRACTOR" "$EAF_FILE" "$DATA_DIR"
            NCSV=$(find "$DATA_DIR" -name "*.csv" 2>/dev/null | wc -l)
            log "  → Extracted $NCSV CSV + .dat files to $DATA_DIR/"
        else
            warn "extract_sima.py not found"
        fi
        
        # Plot SIMA figures (properties dashboard + torsion radar/heatmap)
        SIMA_PLOT_SCRIPT="$SCRIPT_DIR/functions/sima_plot.py"
        if [[ -f "$SIMA_PLOT_SCRIPT" ]]; then
            python3 "$SIMA_PLOT_SCRIPT" "$DATA_DIR" --type all 2>&1 | grep '✓' | while IFS= read -r l; do log "  $l"; done
        fi
        report "── Simulation Interactions Diagram ──"
        report "  Schrödinger SIMA: L-Properties + L_Torsions .dat generated"
    else
        warn "SIMA output file not found"
    fi
else
    warn "event_analysis.py failed — no .eaf generated"
fi

report_sep

# ============================================================
# ANALYSIS 7: Radial Distribution Function (RDF) — VMD Fast Path
# ============================================================
# For large systems (>5000 atoms), use VMD's multi-threaded C
# measure gofr (100-1000× faster than pure Python O(N²)).
# VMD natively reads Desmond .cms + .dtr via dtrplugin.so.
# ============================================================
header "7. Radial Distribution Function (RDF) — VMD Accelerated"
cd "$ANADIR"

VMD_RDF_SCRIPT="$SCRIPT_DIR/functions/vmd_rdf.tcl"
if command -v vmd &>/dev/null && [[ -f "$VMD_RDF_SCRIPT" ]]; then
    log "VMD detected — using multi-threaded measure gofr (12 CPUs)"
    log "Loading system: $(basename "$CMS") + $(basename "$TRJ")"

    VMD_LOG=$(mktemp)
    if vmd -dispdev text -e "$VMD_RDF_SCRIPT" -args \
        "$CMS" "$TRJ" "$ANADIR" 10 > "$VMD_LOG" 2>&1; then
        
        # Parse VMD output for logging
        grep '📊\|Atoms\|Frames\|Elements\|✓\|✅' "$VMD_LOG" | while IFS= read -r line; do
            log "  $line"
        done
        
        NRDF=$(find "$ANADIR" -maxdepth 1 -name "rdf_element_*.csv" 2>/dev/null | wc -l)
        log "  Generated $NRDF RDF CSV files"
        report "── RDF Analysis (VMD Accelerated) ──"
        report "  Element-pair RDFs: $NRDF (via VMD measure gofr)"
        
        # Auto-plot RDFs
        if [[ $NRDF -gt 0 ]]; then
            log "  → Generating RDF figures..."
            python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type rdf 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
    else
        warn "VMD RDF failed — falling back to Python rdf_gen.py"
        grep -i 'error\|fatal' "$VMD_LOG" | head -3 | while IFS= read -r line; do
            warn "  $line"
        done
        
        # Fallback to Python RDF
        RDF_SCRIPT="$SCRIPT_DIR/functions/rdf_gen.py"
        if [[ -f "$RDF_SCRIPT" ]]; then
            log "Computing RDF via Python (slower, single-threaded)..."
            RDF_OUT=$($RUN_SCHROD python3 "$RDF_SCRIPT" \
                "$CMS" "$TRJ" "$ANADIR" \
                --stride 10 --max-frames 500 2>&1)
            echo "$RDF_OUT" | while IFS= read -r line; do
                log "  $line"
            done
        fi
    fi
    rm -f "$VMD_LOG"
elif command -v vmd &>/dev/null; then
    warn "VMD found but vmd_rdf.tcl missing — using Python"
    RDF_SCRIPT="$SCRIPT_DIR/functions/rdf_gen.py"
    [[ -f "$RDF_SCRIPT" ]] && $RUN_SCHROD python3 "$RDF_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" --stride 10 --max-frames 500 2>&1 | \
        while IFS= read -r line; do log "  $line"; done
else
    warn "VMD not found — using Python rdf_gen.py (will be slow for large systems)"
    RDF_SCRIPT="$SCRIPT_DIR/functions/rdf_gen.py"
    if [[ -f "$RDF_SCRIPT" ]]; then
        $RUN_SCHROD python3 "$RDF_SCRIPT" \
            "$CMS" "$TRJ" "$ANADIR" --stride 10 --max-frames 500 2>&1 | \
            while IFS= read -r line; do log "  $line"; done
    else
        skip "RDF analysis (neither VMD nor rdf_gen.py available)"
    fi
fi
report_sep

# ============================================================
# ANALYSIS 8: Density Cross-Section Analysis
# ============================================================
header "8. Density Cross-Section Analysis"
cd "$ANADIR"

DENSITY_SCRIPT="$SCRIPT_DIR/functions/density_gen.py"
if [[ -f "$DENSITY_SCRIPT" ]]; then
    log "Computing 1D + 2D density profiles (water, solute, all)..."
    DENSITY_OUT=$($RUN_SCHROD python3 "$DENSITY_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        --bins 80 --stride 10 --max-frames 400 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$DENSITY_OUT" | grep '✓' | while IFS= read -r line; do
            log "  $line"
        done
        NDENS=$(find "$ANADIR" -maxdepth 1 -name "density_*.csv" 2>/dev/null | wc -l)
        log "  Generated $NDENS density CSV files"
        if [[ $NDENS -gt 0 ]]; then
            log "  → Generating density figures..."
            python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type density 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
        report "── Density Cross-Section ──"
        report "  CSV files: $NDENS"
    else
        warn "Density computation failed (non-critical)"
    fi
else
    skip "Density analysis (density_gen.py not found)"
fi
report_sep

# ============================================================
# ANALYSIS 9: Radius of Gyration (Rg)
# ============================================================
header "9. Radius of Gyration"
cd "$ANADIR"

RG_SCRIPT="$SCRIPT_DIR/functions/rg_gen.py"
if [[ -f "$RG_SCRIPT" ]]; then
    log "Computing radius of gyration for solute molecules..."
    RG_OUT=$($RUN_SCHROD python3 "$RG_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        --stride 10 --max-frames 400 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$RG_OUT" | grep '✓' | while IFS= read -r line; do
            log "  $line"
        done
        NRG=$(find "$ANADIR" -maxdepth 1 -name "rg_*.csv" 2>/dev/null | wc -l)
        log "  Generated $NRG Rg CSV file(s)"
        if [[ $NRG -gt 0 ]]; then
            log "  → Generating Rg figures..."
            python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type rg 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
        report "── Radius of Gyration ──"
        report "  Rg files: $NRG"
    else
        warn "Rg computation failed (non-critical)"
    fi
else
    skip "Rg analysis (rg_gen.py not found)"
fi
report_sep

# ============================================================
# ANALYSIS 10: Distance Monitoring
# ============================================================
header "10. Distance Monitoring"
cd "$ANADIR"

DIST_SCRIPT="$SCRIPT_DIR/functions/dist_gen.py"
if [[ -f "$DIST_SCRIPT" ]]; then
    log "Auto-detecting key inter-molecular distances..."
    DIST_OUT=$($RUN_SCHROD python3 "$DIST_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        --auto --stride 10 --max-frames 400 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$DIST_OUT" | grep '✓' | while IFS= read -r line; do
            log "  $line"
        done
        NDIST=$(find "$ANADIR" -maxdepth 1 -name "distance_*.csv" 2>/dev/null | wc -l)
        log "  Monitored $NDIST distance pairs"
        if [[ $NDIST -gt 0 ]]; then
            log "  → Generating distance figure..."
            python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type distance 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
        report "── Distance Monitoring ──"
        report "  Pairs monitored: $NDIST"
    else
        warn "Distance monitoring failed (non-critical)"
    fi
else
    skip "Distance monitoring (dist_gen.py not found)"
fi
report_sep

# ============================================================
# ANALYSIS 11: Water Residence Time — Vectorized
# ============================================================
# Uses fully vectorized numpy for survival correlation computation.
# Replaces O(water×frames×lag²) → O(τ_max × frames × water) in numpy C.
# ============================================================
header "11. Water Residence Time (Vectorized)"
cd "$ANADIR"

WATERRES_FAST="$SCRIPT_DIR/functions/water_res_fast.py"
if [[ -f "$WATERRES_FAST" ]]; then
    log "Using vectorized water residence time computation..."
    WATERRES_OUT=$($RUN_SCHROD python3 "$WATERRES_FAST" \
        "$CMS" "$TRJ" "$ANADIR" \
        --cutoff 3.5 --stride 10 --max-frames 400 2>&1)
    echo "$WATERRES_OUT" | grep -E 'Water|Frames|Residence|Avg|Exchange|✓|DONE' | while IFS= read -r line; do
        log "  $line"
    done
    
    if [[ -f "$ANADIR/water_residence_survival.csv" ]]; then
        log "  → Generating residence time figure..."
        python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type water_res 2>&1 | \
            grep '✓\\|──' | while IFS= read -r line; do
            log "    $line"
        done
    fi
    report "── Water Residence Time (Vectorized) ──"
    report "  See water_residence_survival.csv"
else
    warn "water_res_fast.py not found — using legacy Python (may be slow)"
    WATERRES_SCRIPT="$SCRIPT_DIR/functions/water_res_gen.py"
    if [[ -f "$WATERRES_SCRIPT" ]]; then
        $RUN_SCHROD python3 "$WATERRES_SCRIPT" \
            "$CMS" "$TRJ" "$ANADIR" \
            --cutoff 3.5 --stride 10 --max-frames 400 2>&1 | \
            while IFS= read -r line; do log "  $line"; done
    else
        skip "Water residence (neither fast nor legacy script found)"
    fi
fi
report_sep

# ============================================================
# ANALYSIS 12: Conformational Clustering + PCA
# ============================================================
header "12. Conformational Clustering"
cd "$ANADIR"

CLUSTER_SCRIPT="$SCRIPT_DIR/functions/cluster_gen.py"
if [[ -f "$CLUSTER_SCRIPT" ]]; then
    log "Performing hierarchical RMSD clustering + PCA projection..."
    CLUSTER_OUT=$($RUN_SCHROD python3 "$CLUSTER_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        --n-clusters 5 --stride 10 --max-frames 300 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$CLUSTER_OUT" | grep -E '✓|Cluster [0-9]|PC1=' | while IFS= read -r line; do
            log "  $line"
        done
        if [[ -f "$ANADIR/cluster_assignments.csv" ]]; then
            log "  → Generating clustering figures..."
            python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type cluster 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
        report "── Conformational Clustering ──"
        report "  See cluster_assignments.csv + cluster_pca.csv"
    else
        warn "Clustering failed (non-critical)"
    fi
else
    skip "Clustering (cluster_gen.py not found)"
fi
report_sep

# ============================================================
# ANALYSIS 13: Dipole Moment
# ============================================================
header "13. Molecular Dipole Moment"
cd "$ANADIR"

DIPOLE_SCRIPT="$SCRIPT_DIR/functions/dipole_gen.py"
if [[ -f "$DIPOLE_SCRIPT" ]]; then
    log "Computing molecular dipole moments..."
    DIPOLE_OUT=$($RUN_SCHROD python3 "$DIPOLE_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        --stride 10 --max-frames 400 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$DIPOLE_OUT" | grep -E '✓|Total dipole|Solute molecules' | while IFS= read -r line; do
            log "  $line"
        done
        NDIPOLE=$(find "$ANADIR" -maxdepth 1 -name "dipole_*.csv" 2>/dev/null | wc -l)
        log "  Generated $NDIPOLE dipole CSV file(s)"
        if [[ $NDIPOLE -gt 0 ]]; then
            log "  → Generating dipole figures..."
            python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type dipole 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
        report "── Dipole Moment ──"
        report "  CSV files: $NDIPOLE"
    else
        warn "Dipole computation failed (non-critical)"
    fi
else
    skip "Dipole analysis (dipole_gen.py not found)"
fi
report_sep

# ============================================================
# ANALYSIS 14: Free Volume
# ============================================================
header "14. Free Volume Analysis"
cd "$ANADIR"

if [[ $DO_FREEVOL -eq 1 ]]; then
    FREEVOL_SCRIPT="$SCRIPT_DIR/functions/freevol_gen.py"
    if [[ -f "$FREEVOL_SCRIPT" ]]; then
        log "Computing free volume / void space..."
        FREEVOL_OUT=$($RUN_SCHROD python3 "$FREEVOL_SCRIPT" \
            "$CMS" "$TRJ" "$ANADIR" \
            --stride 50 --max-frames 40 --probe 1.4 --grid 1.0 2>&1)
        if [[ $? -eq 0 ]]; then
            echo "$FREEVOL_OUT" | grep -E '✓|Free volume|FFV' | while IFS= read -r line; do
                log "  $line"
            done
            if [[ -f "$ANADIR/free_volume.csv" ]]; then
                log "  → Generating free volume figure..."
                python3 "$SCRIPT_DIR/functions/desmond_plot.py" "$ANADIR" --type freevol 2>&1 | \
                    grep '✓\|──' | while IFS= read -r line; do
                    log "    $line"
                done
            fi
            report "── Free Volume ──"
            report "  See free_volume.csv"
        else
            warn "Free volume computation failed (non-critical)"
        fi
    else
        skip "Free volume (freevol_gen.py not found)"
    fi
else
    skip "Free volume (use --free-volume to enable)"
fi
report_sep || true

# ============================================================
# ANALYSIS 15: Publication-quality Plotting (always)
# ============================================================
header "15. Generating Publication Figures"
cd "$ANADIR"

PLOT_SCRIPT="$SCRIPT_DIR/functions/desmond_plot.py"
if [[ ! -f "$PLOT_SCRIPT" ]]; then
    error "desmond_plot.py not found at $PLOT_SCRIPT"
else
    log "Running plot generation (type: $PLOT_TYPE)..."
    PLOT_LOG=$(mktemp)
    set +e
    python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" >"$PLOT_LOG" 2>&1
    PLOT_EXIT=$?
    set -e
    if [[ $PLOT_EXIT -ne 0 ]]; then
        warn "Plot generation FAILED (exit code: $PLOT_EXIT)"
        warn "Full log: $PLOT_LOG"
        cat "$PLOT_LOG" | while IFS= read -r line; do
            warn "  $line"
        done
    else
        cat "$PLOT_LOG" | while IFS= read -r line; do
            log "  $line"
        done
    fi
    rm -f "$PLOT_LOG"

    # Count generated figures
    NPDF=$(find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | wc -l)
    NPNG=$(find "$ANADIR/figures" -name "*.png" 2>/dev/null | wc -l)
    log "Generated: $NPDF PDFs + $NPNG PNGs"
fi
report_sep

# ============================================================
# ANALYSIS 16: Schrödinger SIMA Report PDF
# ============================================================
SIMA_REPORT_PDF="$ANADIR/data/${MD_NAME}_sima.pdf"
if [[ -f "$EAF_REPORT_FILE" ]]; then
    header "16. SIMA Report (Schrödinger Official)"
    cd "$ANADIR"
    log "Generating Schrödinger Simulation Interactions Diagram report..."
    unset DISPLAY 2>/dev/null || true
    if $RUN_SCHROD python3 "$SCHRODINGER/mmshare-v7.0/python/scripts/event_analysis.py" report \
        "$EAF_REPORT_FILE" -pdf "$SIMA_REPORT_PDF" 2>/dev/null; then
        if [[ -f "$SIMA_REPORT_PDF" ]]; then
            log "  ✓ $(basename "$SIMA_REPORT_PDF") ($(du -h "$SIMA_REPORT_PDF" | cut -f1))"
            report "── SIMA Report (Schrödinger) ──"
            report "  See data/${MD_NAME}_sima.pdf"
        fi
    else
        warn "SIMA report PDF generation failed (non-critical)"
    fi
    report_sep || true
else
    skip "SIMA report (no .eaf file found)"
fi

# ============================================================
# FINAL: Generate Report
# ============================================================
header "Analysis Complete"

# Copy report to main MD dir for easy access
cp "$REPORT" "$MD_DIR/analysis_report.txt" 2>/dev/null || true

# Count generated files
NFILES=$(find "$ANADIR" -type f ! -name "*.json" ! -name "*.eaf" 2>/dev/null | wc -l)

echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Analysis Complete: $SYSTEM${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Output directory:${NC} $ANADIR"
echo -e "  ${BOLD}Files generated:${NC}  $NFILES"
echo -e "  ${BOLD}Report:${NC}           $ANADIR/analysis_report.txt"
echo ""

echo "── Output Files ──"
find "$ANADIR" -maxdepth 1 -type f ! -name "*.json" ! -name "*.eaf" 2>/dev/null | sort | while read f; do
    SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
    if [[ $SIZE -gt 0 ]]; then
        printf "  %-8s %s\n" "$(numfmt --to=iec $SIZE 2>/dev/null || echo ${SIZE}B)" "$(basename $f)"
    fi
done

# Show figures if generated
if [[ "$DO_PLOT" -eq 1 ]] && [[ -d "$ANADIR/figures" ]]; then
    echo ""
    echo -e "${BOLD}── Publication Figures ──${NC}"
    find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | sort | while read f; do
        echo -e "  📄 ${BOLD}$(basename $f)${NC}"
    done
    echo ""
    echo -e "  ${CYAN}Full directory:${NC} $ANADIR/figures/"
fi

echo ""
echo -e "${CYAN}── Analysis Report ──${NC}"
cat "$REPORT"

echo ""
echo -e "${GREEN}Analysis complete. All results in: $ANADIR${NC}"
