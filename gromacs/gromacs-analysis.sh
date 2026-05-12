#!/bin/bash
# ============================================================
# gromacs-analysis.sh — GROMACS MD Post-Processing  |  MOTUS v0.0.1
# ============================================================
# Usage:
#   gromacs-analysis.sh <job_dir> [OPTIONS]
#
# Options:
#   --plot              Generate publication figures (PDF+PNG)
#   --fig-only          Re-plot from existing data only
#   --plot-type <type>  energy|hbonds|rmsd|rdf|rgyr|sasa|density|all
#
# The job directory must contain:
#   prod.xtc (trajectory), prod.gro (structure), prod.edr (energy),
#   topol.top (topology), prod.tpr (optional, for index groups)
# ============================================================

set -uo pipefail  # No -e: stages can fail gracefully with skip()

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
skip()   { echo -e "${YELLOW}[~]${NC} $* (skipped)"; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }
section(){ echo -e "\n${BOLD}── $* ──${NC}"; }

usage() { head -20 "$0" | grep '^#' | sed 's/^# \?//'; exit 0; }

# ── Find GROMACS ──
GMX="${GMX:-}"
[[ -z "$GMX" ]] && command -v gmx &>/dev/null && GMX=gmx
[[ -z "$GMX" ]] && for d in /home/$USER/tools/gromacs-*/bin/gmx; do [[ -x "$d" ]] && GMX="$d" && break; done
[[ -z "$GMX" ]] && error "GROMACS not found. Source GMXRC or set GMX=/path/to/gmx"

# ── Parse args ──
JOB_DIR=""; DO_PLOT=0; FIG_ONLY=0; PLOT_TYPE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        --plot)   DO_PLOT=1; shift ;;
        --fig-only) FIG_ONLY=1; DO_PLOT=1; shift ;;
        --plot-type) PLOT_TYPE="$2"; shift 2 ;;
        --gmx)    GMX="$2"; shift 2 ;;
        *)        JOB_DIR="$1"; shift ;;
    esac
done

[[ -z "$JOB_DIR" ]] && error "No job directory provided."
[[ ! -d "$JOB_DIR" ]] && error "Directory not found: $JOB_DIR"

JOB_DIR=$(realpath "$JOB_DIR")
JOB_NAME=$(basename "$JOB_DIR")
ANADIR="$JOB_DIR/analysis"
mkdir -p "$ANADIR"
REPORT="$ANADIR/analysis_report.txt"
> "$REPORT"

report() { echo "$@" >> "$REPORT"; }

# ── Auto-detect files ──
XTC=$(ls "$JOB_DIR"/prod.xtc 2>/dev/null | head -1)
GRO=$(ls "$JOB_DIR"/prod.gro "$JOB_DIR"/npt.gro 2>/dev/null | head -1)
EDR=$(ls "$JOB_DIR"/prod.edr 2>/dev/null | head -1)
TOP=$(ls "$JOB_DIR"/topol.top 2>/dev/null | head -1)
TPR=$(ls "$JOB_DIR"/prod.tpr 2>/dev/null | head -1)
NDX="$JOB_DIR/index.ndx"

[[ -z "$XTC" ]] && error "No prod.xtc found in $JOB_DIR"
[[ -z "$GRO" ]] && error "No .gro found in $JOB_DIR"

cd "$ANADIR"

# ── FIG-ONLY fast path ──
if [[ "$FIG_ONLY" -eq 1 ]]; then
    header "Figure-Only Mode: $JOB_NAME"
    PLOT_SCRIPT="$SCRIPT_DIR/functions/gromacs_plot.py"
    if [[ -f "$PLOT_SCRIPT" ]]; then
        python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
    else
        warn "gromacs_plot.py not found — skipping"
    fi
    exit 0
fi

header "GROMACS Analysis: $JOB_NAME"

# ==== 1: Energy Analysis ====
header "1. Energy Analysis"
if [[ -n "$EDR" ]]; then
    log "Extracting energy components..."
    # gmx energy expects term names one-per-line, then empty line to finish
    printf "Temperature\nPressure\nPotential\nVolume\nDensity\n\n" | \
        $GMX energy -f "$EDR" -o energy.xvg 2>&1 | tail -5
    
    if [[ -f energy.xvg ]]; then
        # XVG legend order (s0-s4):
        #   Time, Potential(kJ/mol), Temperature(K), Pressure(bar), Volume(nm3), Density(kg/m3)
        grep -v '^[@#]' energy.xvg | awk 'BEGIN{print "Time_ps,Pot_E_kJmol,Temp_K,Pressure_bar,Vol_nm3,Density_kgm3"}
            {printf "%.3f,%.2f,%.2f,%.2f,%.3f,%.2f\n", $1,$2,$3,$4,$5,$6}' > energy_timeseries.csv
        log "  → energy_timeseries.csv"
        
        # Stats: col2=Potential, col3=Temp, col4=Pressure
        awk -F, 'NR>1 {e+=$2; t+=$3; p+=$4; n++} END {
            printf "Frames: %d\nT_avg: %.1f K\nP_avg: %.1f bar\nEpot_avg: %.1f kJ/mol\n", n, t/n, p/n, e/n
        }' energy_timeseries.csv > energy_stats.txt
        cat energy_stats.txt
        report "$(cat energy_stats.txt)"
    fi
else
    skip "No .edr file found"
fi

# ==== 2: H-Bond Analysis ====
header "2. H-Bond Analysis"
if [[ -n "$TPR" ]]; then
    log "Computing hydrogen bonds (System-System)..."
    if printf "System\nSystem\n" | $GMX hbond -f "$XTC" -s "$TPR" -num hbonds.xvg 2>&1 | tail -3; then
        if [[ -f hbonds.xvg ]]; then
            grep -v '^[@#]' hbonds.xvg | awk 'BEGIN{print "Time_ps,HBonds"}{print $1","$2}' > hbonds.csv
            AVG=$(awk -F, 'NR>1{s+=$2;n++}END{printf "%.1f",s/n}' hbonds.csv)
            log "  → hbonds.csv (avg: $AVG bonds/frame)"
            report "H-Bonds avg: $AVG / frame"
        fi
    else
        skip "H-bond analysis failed (may need custom index groups)"
    fi
else
    skip "No .tpr for H-bond analysis"
fi

# ==== 3: RMSD ====
header "3. RMSD Analysis"
log "Computing RMSD (System group)..."
# Use "System" for both fit and calc — works for any system
if printf "System\nSystem\n" | $GMX rms -f "$XTC" -s "$GRO" -o rmsd.xvg 2>&1 | tail -3; then
    if [[ -f rmsd.xvg ]]; then
        grep -v '^[@#]' rmsd.xvg | awk 'BEGIN{print "Time_ps,RMSD_nm"}{print $1","$2*10}' > rmsd.csv
        AVG=$(awk -F, 'NR>1{s+=$2;n++}END{printf "%.2f",s/n}' rmsd.csv)
        log "  → rmsd.csv (avg: ${AVG} Å)"
        report "RMSD avg: ${AVG} Å"
    fi
else
    skip "RMSD failed (try custom index groups)"
fi

# ==== 4: RDF ====
header "4. Radial Distribution Function"
log "Computing RDF (all-atom pairs)..."
# Try OW-OW for water, fallback to System-System
if printf "OW\nOW\n" | $GMX rdf -f "$XTC" -s "$GRO" -o rdf.xvg -bin 0.005 2>&1 | tail -3; then
    :
else
    # Fallback: whole system RDF
    printf "System\nSystem\n" | $GMX rdf -f "$XTC" -s "$GRO" -o rdf.xvg -bin 0.005 2>&1 | tail -3
fi
if [[ -f rdf.xvg ]]; then
    grep -v '^[@#]' rdf.xvg | awk 'BEGIN{print "r_nm,g_r"}{print $1","$2}' > rdf.csv
    log "  → rdf.csv"
fi

# ==== 5: Radius of Gyration ====
header "5. Radius of Gyration"
log "Computing Rg..."
echo "System" | $GMX gyrate -f "$XTC" -s "$GRO" -o gyrate.xvg 2>&1 | tail -3
if [[ -f gyrate.xvg ]]; then
    grep -v '^[@#]' gyrate.xvg | awk 'BEGIN{print "Time_ps,Rg_nm,RgX_nm,RgY_nm,RgZ_nm"}
        {print $1","$2","$3","$4","$5}' > gyrate.csv
    AVG=$(awk -F, 'NR>1{s+=$2;n++}END{printf "%.3f",s/n}' gyrate.csv)
    log "  → gyrate.csv (avg Rg: ${AVG} nm)"
    report "Rg avg: ${AVG} nm"
fi

# ==== 6: SASA ====
header "6. Solvent Accessible Surface Area"
if [[ -n "$TPR" ]]; then
    log "Computing SASA..."
    echo "System" | $GMX sasa -f "$XTC" -s "$TPR" -o sasa.xvg 2>&1 | tail -3
    if [[ -f sasa.xvg ]]; then
        grep -v '^[@#]' sasa.xvg | awk 'BEGIN{print "Time_ps,Area_nm2"}{print $1","$2}' > sasa.csv
        log "  → sasa.csv"
    fi
else
    skip "No .tpr for SASA"
fi

# ==== 7: Density Profile ====
header "7. Density Profile (Z-axis)"
log "Computing density along Z..."
echo "System" | $GMX density -f "$XTC" -s "$GRO" -o density_z.xvg -sl 50 -d Z 2>&1 | tail -3
if [[ -f density_z.xvg ]]; then
    grep -v '^[@#]' density_z.xvg | awk 'BEGIN{print "Z_nm,Density_kgm3"}{print $1","$2}' > density_z.csv
    log "  → density_z.csv"
fi

# ==== Summary ====
header "Analysis Summary"
NCSV=$(find "$ANADIR" -maxdepth 1 -name "*.csv" | wc -l)
log "Generated $NCSV CSV files"
report "Total CSV files: $NCSV"

# ── Plotting ──
if [[ "$DO_PLOT" -eq 1 ]]; then
    header "Generating Figures"
    PLOT_SCRIPT="$SCRIPT_DIR/functions/gromacs_plot.py"
    if [[ -f "$PLOT_SCRIPT" ]]; then
        python3 "$PLOT_SCRIPT" "$ANADIR" --type "$PLOT_TYPE" 2>&1 | grep '✓' | while read l; do log "  $l"; done || true
        NPDF=$(find "$ANADIR/figures" -name "*.pdf" 2>/dev/null | wc -l)
        log "Generated: $NPDF figures"
    fi
fi

echo ""
log "Analysis complete. Results in $ANADIR/"
