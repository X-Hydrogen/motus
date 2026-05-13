#!/bin/bash
# ============================================================
# lammps-reaxff-analysis.sh — ReaxFF Reaction Analysis
# ============================================================
# Usage:
#   lammps-reaxff-analysis.sh <job_dir> [OUTPUT_DIR]
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANA_ENGINE="${SCRIPT_DIR}/functions/reaction_analysis.py"

JOB_DIR="${1:-.}"
ANADIR="${2:-${JOB_DIR}/analysis}"
mkdir -p "$ANADIR"

header "ReaxFF Reaction Analysis"

# Find species and trajectory files
SPECIES=$(ls "$JOB_DIR"/*.species 2>/dev/null | head -1)
TRAJ=$(ls "$JOB_DIR"/*.lammpstrj 2>/dev/null | head -1)

if [[ -n "$SPECIES" ]]; then
    log "Species file: $SPECIES"
    log "Parsing species data..."
    python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}/functions')
from reaction_analysis import parse_reaxff_species
df = parse_reaxff_species('${SPECIES}')
df.to_csv('${ANADIR}/species_timeseries.csv', index=False)
print(f'  Frames: {len(df)}, Species: {len(df.columns)-2}')
" 2>&1 | while read line; do log "  $line"; done
else
    warn "No .species file found — skipping species analysis"
fi

if [[ -n "$TRAJ" ]]; then
    log "Trajectory: $TRAJ"
    log "Computing energy statistics..."
    
    # Extract thermo data from log
    LOG=$(ls "$JOB_DIR"/log.* 2>/dev/null | head -1)
    if [[ -n "$LOG" ]]; then
        python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}/functions')
import pandas as pd, numpy as np

# Parse LAMMPS log for thermo data
lines = open('${LOG}').readlines()
data_start = None
for i, line in enumerate(lines):
    if 'Step' in line and 'Temp' in line:
        data_start = i + 1
        break
if data_start:
    thermo_lines = []
    for line in lines[data_start:]:
        parts = line.strip().split()
        if len(parts) >= 6 and parts[0].isdigit():
            thermo_lines.append(parts[:7])
    if thermo_lines:
        df = pd.DataFrame(thermo_lines, columns=['Step','Temp','Press','PotEng','KinEng','TotEng','Vol'])
        df = df.astype(float)
        df['Time_ps'] = df.index * (float('${JOB_DIR}') and 0.1)  # approximate
        df.to_csv('${ANADIR}/energy_timeseries.csv', index=False)
        print(f'  Thermo frames: {len(df)}')
" 2>&1 | while read line; do log "  $line"; done
    fi
fi

log "Analysis complete. Results in: $ANADIR"
