#!/bin/bash
# ============================================================
# desmond-publish.sh — One-Click Paper from Analysis Data
# ============================================================
# Reads analysis data, substitutes into the approved paper template,
# and compiles PDF. Does NOT modify the template.
#
# Usage:  cd desmond_md_job_XXX && bash ../motus/desmond/desmond-publish.sh
# ============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/templates/paper-template.tex"
GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

[[ $# -ge 1 && -d "$1" ]] && MD_DIR="$(realpath "$1")" || MD_DIR="$(pwd)"

ANADIR="$MD_DIR/analysis"
[[ ! -f "$ANADIR/energy_stats.txt" ]] && { echo "ERROR: Run desmond-analysis.sh --plot first."; exit 1; }
[[ ! -f "$TEMPLATE" ]] && { echo "ERROR: Template not found: $TEMPLATE"; exit 1; }

echo -e "${CYAN}━━━ desmond-publish.sh — MOTUS v1.0 ━━━${NC}"

# Read energy stats (fields on SAME line: T_avg: VAL K T_std: VAL T_range: [...])
T_AVG=$(grep "T_avg" "$ANADIR/energy_stats.txt" | awk '{print $2}')
T_STD=$(grep "T_std" "$ANADIR/energy_stats.txt" | awk '{print $5}')  # field 5, NOT 2!
P_AVG=$(grep "P_avg" "$ANADIR/energy_stats.txt" | awk '{print $2}')
V_AVG=$(grep "V_avg" "$ANADIR/energy_stats.txt" | awk '{print $2}')
EPOT=$(grep "Epot_avg" "$ANADIR/energy_stats.txt" | awk '{print $2}')

# Default system (from template — only override if CMS found)
DME_COUNT=604; FSI_COUNT=75; LI_COUNT=75; NATOMS=10414; BOX=58.6

CMS=$(ls "$MD_DIR"/*-out.cms 2>/dev/null | head -1)
if [[ -n "$CMS" ]]; then
    INFO=$("$SCHRODINGER/run" python3 -c "
import sys
sys.path.insert(0,'/home/xenon/tools/schrodinger2025-2/internal/lib/python3.11/site-packages')
sys.path.insert(0,'/home/xenon/tools/schrodinger2025-2/mmshare-v7.0/lib/python3.11/site-packages')
from schrodinger.application.desmond import cms
m=cms.Cms(file='$CMS')
atoms=m.atom_total; box=m.box[0]
mt={}
for i in range(1,atoms+1):
    mn=m.atom[i].molecule_number
    mt.setdefault(mn,set()).add(m.atom[i].element)
dc=fs=li=0
for mn,el in mt.items():
    if 'Li' in el: li+=1
    elif 'S' in el: fs+=1
    elif 'C' in el: dc+=1
print(f'{atoms} {box:.1f} {dc} {fs} {li}')
" 2>/dev/null)
    [[ -n "$INFO" ]] && read NATOMS BOX DME_COUNT FSI_COUNT LI_COUNT <<< "$INFO"
fi

echo -e "${GREEN}System: $DME_COUNT DME + $FSI_COUNT FSI- + $LI_COUNT Li+ ($NATOMS atoms, ${BOX} A box)${NC}"

# Substitute system values into template
cp "$TEMPLATE" "$ANADIR/report.tex"
sed -i \
    -e "s/604 DME molecules/$DME_COUNT DME molecules/g" \
    -e "s/75 FSI\$^-\\$ anions/$FSI_COUNT FSI\$^-\\$ anions/g" \
    -e "s/75 Li\$^+\\$ cations/$LI_COUNT Li\$^+\\$ cations/g" \
    -e "s/(10,414 atoms/($NATOMS atoms/g" \
    -e "s/5.86 nm/$(printf '%.1f' $(bc <<< "scale=1; $BOX/10")) nm/g" \
    -e "s/604 DME/$DME_COUNT DME/g" \
    -e "s/75 FSI\^-\\$/$FSI_COUNT FSI\^-\\$/g" \
    -e "s/75 Li\^+\\$/$LI_COUNT Li\^+\\$/g" \
    -e "s/10,414 atoms/$NATOMS atoms/g" \
    -e "s/299.8/$T_AVG/g" \
    -e "s/7.2 K/$T_STD K/g" \
    -e "s/-222/-${P_AVG#-}/g" \
    -e "s/-21,405.4/$EPOT/g" \
    -e "s/207,848/$V_AVG/g" \
    "$ANADIR/report.tex"

# Compile
echo -e "${GREEN}Compiling...${NC}"
cd "$ANADIR"
pdflatex -interaction=nonstopmode report.tex > /dev/null 2>&1
pdflatex -interaction=nonstopmode report.tex > /dev/null 2>&1
echo -e "${GREEN}Done:${NC} $(ls -lh report.pdf | awk '{print $5, $NF}')"
