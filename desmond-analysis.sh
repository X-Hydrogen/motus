#!/bin/bash
# ============================================================
# desmond-analysis.sh — Comprehensive Desmond MD Analysis  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   desmond-analysis.sh <md_job_folder> [OPTIONS]
#
# Options:
#   --plot              Full analysis + generate publication figures (PDF+PNG)
#   --fig-only          Skip analysis, ONLY re-plot from existing CSV data
#   --plot-type <type>  Plot type: energy|hbonds|water_shells|contacts|rmsd|rmsf|dashboard|all
#
# The folder must contain:
#   -out.cms (final structure), _trj/ (trajectory), .ene (energy), .log (log)
#
# Automatically runs ALL available Schrödinger analysis tools
# and generates a summary report.
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCHRODINGER="${SCHRODINGER:-/home/xenon/tools/schrodinger2025-2}"
TIMEOUT=600

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
MD_FOLDER=""; ASL1=""; ASL2=""; DO_PLOT=0; FIG_ONLY=0; PLOT_TYPE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --asl1) ASL1="$2"; shift 2 ;;
        --asl2) ASL2="$2"; shift 2 ;;
        --schrodinger) SCHRODINGER="$2"; shift 2 ;;
        --plot)   DO_PLOT=1; shift ;;
        --fig-only) FIG_ONLY=1; DO_PLOT=1; shift ;; 
        --plot-type) PLOT_TYPE="$2"; shift 2 ;;
        *) MD_FOLDER="$1"; shift ;;
    esac
done

# ── Validation ──
[[ -z "$MD_FOLDER" ]] && error "No MD folder provided.\nUsage: $0 <desmond_md_job_XXXXX>" && exit 1
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

    PLOT_SCRIPT="$SCRIPT_DIR/desmond_plot.py"
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
    SIMA_SCRIPT="$SCRIPT_DIR/sima_plot.py"
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
        time=$1; etot=$2; epot=$3; ekin=$4; press=$7; vol=$8; temp=$9
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
    tail -n +11 "$ENE" | awk '{printf "%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.3f\n", $1,$2,$3,$4,$7,$8,$9}' >> "$ANADIR/energy_timeseries.csv"
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
# ANALYSIS 4: Solute-Water Distance & Contacts
# ============================================================
header "4. Solute-Water Shell Analysis (Free vs Bound)"
cd "$ANADIR"

# trajectory_asl_monitor uses WITHIN operator which CMS ASL doesn't support.
# Multi-shell water analysis via Python: 1st shell (<3.5Å), 2nd shell (3.5-5Å), free (>5Å)
log "Counting water shells: bound (<3.5Å) + 2nd shell (3.5-5Å) + free (>5Å)..."
PYOUT=$($SCHRODINGER/run python3 -c "
from schrodinger.application.desmond.packages import traj, topo
import csv

cms_file = '$CMS'
trj_dir = '$TRJ'

shells = [
    ('Bound_1st',   0.0,  3.5,  'tightly bound, <3.5A'),
    ('Second',      3.5,  5.0,  '2nd shell, 3.5-5.0A'),
    ('Free',        5.0, 1e10,  'free/bulk, >5.0A'),
]

msys, cms = topo.read_cms(cms_file)
tr = traj.read_traj(trj_dir)

solute_aids = cms.select_atom('solute')
water_aids = cms.select_atom('water')
water_oxygens = [(a, cms.atom[a]) for a in water_aids if cms.atom[a].element == 'O']

total_water = len(water_oxygens)

output = open('solute_water_shells.csv', 'w')
writer = csv.writer(output)
shell_names = [s[0] for s in shells]
writer.writerow(['Frame', 'Time_ps', 'Total_Water'] + shell_names)

n_frames = len(tr)
stride = max(1, n_frames // 500)  # sample ~500 frames max
for fi in range(0, n_frames, stride):
    frame = tr[fi]
    if fi % (stride * 100) == 0 or fi == 0:
        print(f'  Frame {fi}/{n_frames}...', flush=True)
    allpos = frame.pos()
    box = frame.box

    counts = [0] * len(shells)
    for wid, watom in water_oxygens:
        wp = allpos[wid]
        # find min distance from this water O to any solute atom
        min_d2 = float('inf')
        for sid in solute_aids:
            sp = allpos[sid]
            dx, dy, dz = wp[0]-sp[0], wp[1]-sp[1], wp[2]-sp[2]
            dx -= box[0][0] * round(dx / box[0][0])
            dy -= box[1][1] * round(dy / box[1][1])
            dz -= box[2][2] * round(dz / box[2][2])
            d2 = dx*dx + dy*dy + dz*dz
            if d2 < min_d2:
                min_d2 = d2
        d = min_d2**0.5
        # classify into shell
        for si, (name, lo, hi, desc) in enumerate(shells):
            if lo <= d < hi:
                counts[si] += 1
                break

    writer.writerow([fi+1, f'{frame.time:.3f}', total_water] + counts)

output.close()
print(f'DONE: {n_frames} frames processed (stride={stride})')
" 2>&1)
RC=$?
if [[ $RC -eq 0 ]] && [[ -f solute_water_shells.csv ]]; then
    NROWS=$(tail -n +2 solute_water_shells.csv 2>/dev/null | wc -l)
    if [[ $NROWS -gt 0 ]]; then
        # Statistics
        BOUND_AVG=$(tail -n +2 solute_water_shells.csv | awk -F',' '{sum+=$4; n++} END {printf "%.1f", sum/n}')
        SECOND_AVG=$(tail -n +2 solute_water_shells.csv | awk -F',' '{sum+=$5; n++} END {printf "%.1f", sum/n}')
        FREE_AVG=$(tail -n +2 solute_water_shells.csv | awk -F',' '{sum+=$6; n++} END {printf "%.1f", sum/n}')
        TOTAL_W=$(head -2 solute_water_shells.csv | tail -1 | awk -F',' '{print $3}')

        log "  Total water:          ${TOTAL_W}"
        log "  Bound (1st, <3.5Å):   ${BOUND_AVG:-N/A}  avg"
        log "  2nd shell (3.5-5.0Å): ${SECOND_AVG:-N/A}  avg"
        log "  Free (>5.0Å):         ${FREE_AVG:-N/A}  avg"
        log "  Bound fraction:       $(awk -v b=$BOUND_AVG -v t=$TOTAL_W 'BEGIN {printf \"%.1f%%\", b/t*100}')"

        report "── Solute-Water Shell Analysis ──"
        report "  Total water molecules: ${TOTAL_W}"
        report "  Bound  (<3.5 Å):     ${BOUND_AVG:-N/A} avg"
        report "  2nd shell (3.5-5.0): ${SECOND_AVG:-N/A} avg"
        report "  Free   (>5.0 Å):     ${FREE_AVG:-N/A} avg"
        report "  Bound fraction:      $(awk -v b=$BOUND_AVG -v t=$TOTAL_W 'BEGIN {printf \"%.1f%%\", b/t*100}')"
    fi
else
    warn "Water shell analysis skipped or failed"
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

# 6d: Simulation Interactions Diagram generation (auto-detect ligand)
SIMA_GEN_SCRIPT="$SCRIPT_DIR/sima_gen.py"
if [[ -f "$SIMA_GEN_SCRIPT" ]]; then
    log "Running Simulation Interactions Diagram generation..."
    # For non-protein: auto-detect largest molecule as ligand
    # For protein systems: skip ligand auto-detect (use --mol to specify)
    SIMA_GEN_OUT=$($RUN_SCHROD python3 "$SIMA_GEN_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        ${HAS_PROTEIN:+--mol 2} \
        --stride 5 --max-frames 1000 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$SIMA_GEN_OUT" | while IFS= read -r line; do
            log "  $line"
        done
        # Auto-run plotting on generated .dat files
        if [[ -f "$ANADIR/L_Torsions.dat" ]]; then
            log "  → Generating SIMA figures..."
            SIMA_PLOT_SCRIPT="$SCRIPT_DIR/sima_plot.py"
            if [[ -f "$SIMA_PLOT_SCRIPT" ]]; then
                python3 "$SIMA_PLOT_SCRIPT" "$ANADIR" --type all 2>&1 | \
                    grep '✓' | while IFS= read -r line; do
                    log "    $line"
                done
            fi
        fi
        report "── Simulation Interactions Diagram ──"
        report "  .dat files generated + plotted"
    else
        warn "SIMA generation failed (non-critical)"
    fi
else
    skip "SIMA generation (sima_gen.py not found)"
fi

report_sep

# ============================================================
# ANALYSIS 7: Radial Distribution Function (RDF)
# ============================================================
header "7. Radial Distribution Function (RDF)"
cd "$ANADIR"

RDF_SCRIPT="$SCRIPT_DIR/rdf_gen.py"
if [[ -f "$RDF_SCRIPT" ]]; then
    log "Computing element-pair, molecular, and water-shell RDFs..."
    RDF_OUT=$($RUN_SCHROD python3 "$RDF_SCRIPT" \
        "$CMS" "$TRJ" "$ANADIR" \
        --stride 10 --max-frames 500 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "$RDF_OUT" | while IFS= read -r line; do
            log "  $line"
        done
        NRDF=$(find "$ANADIR" -maxdepth 1 -name "rdf_*.csv" 2>/dev/null | wc -l)
        log "  Generated $NRDF RDF CSV files"

        # Auto-plot RDFs
        if [[ $NRDF -gt 0 ]]; then
            log "  → Generating RDF figures..."
            python3 "$SCRIPT_DIR/desmond_plot.py" "$ANADIR" --type rdf 2>&1 | \
                grep '✓\|──' | while IFS= read -r line; do
                log "    $line"
            done
        fi
        report "── RDF Analysis ──"
        report "  RDF CSV files: $NRDF"
    else
        warn "RDF computation failed (non-critical)"
    fi
else
    skip "RDF analysis (rdf_gen.py not found)"
fi
report_sep

# ============================================================
# ANALYSIS 8: Publication-quality Plotting (if --plot)
# ============================================================
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "8. Generating Publication Figures"
    cd "$ANADIR"

    PLOT_SCRIPT="$SCRIPT_DIR/desmond_plot.py"
    if [[ ! -f "$PLOT_SCRIPT" ]]; then
        error "desmond_plot.py not found at $PLOT_SCRIPT"
    else
        log "Running plot generation (type: $PLOT_TYPE)..."
        PLOT_LOG=$(mktemp)
        PYPLOT_OUT=$(python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" 2>&1)
        echo "$PYPLOT_OUT" | while IFS= read -r line; do
            log "  $line"
        done

        # Count generated figures
        NPDF=$(find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | wc -l)
        NPNG=$(find "$ANADIR/figures" -name "*.png" 2>/dev/null | wc -l)
        log "Generated: $NPDF PDFs + $NPNG PNGs"
    fi
    report_sep
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
