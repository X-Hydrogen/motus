#!/bin/bash
# ============================================================================
# desmond-model-md.sh — Automated Desmond Modeling Pipeline v2.0
# ============================================================================
# Converts a Packmol-built PDB into a Desmond-ready .cms file.
#
# Pipeline (verified working):
#   1. Packmol → packed.pdb (raw, no residue renaming needed)
#   2. pdbconvert → Maestro .mae
#   3. multisim (build_geometry + S-OPLS) → Desmond .cms
#
# CRITICAL RULES:
#   - Use RAW packed.pdb (NOT fixed_for_schrodinger.pdb — breaks multisim)
#   - ALWAYS use S-OPLS force field (OPLS4 triggers mmlewis bug)
#   - MUST include build_geometry stage with explicit box size
#   - Box size auto-detected from packmol.inp (default: 6.0 nm)
#
# Verified: LiFSI/DME system — 604 DME + 75 FSI⁻ + 75 Li⁺, 10414 atoms
#   Schrödinger 2025-2 (Linux) — ~46s total (build_geometry: 23s, ff: 22s)
#   Schrödinger 2025-1 (Windows) — also confirmed working
#
# Usage:
#   desmond-model-md.sh <project_dir> [output_name]
#
# Dependencies:
#   Schrödinger at /home/xenon/tools/schrodinger2025-2
#   Packmol-built PDB (packed.pdb or system.pdb) + packmol.inp
# ============================================================================

set -euo pipefail

SCRIPT_DIR="/home/xenon/xhy/motus"
SCHRODINGER="/home/xenon/tools/schrodinger2025-2"

# ── Args ──────────────────────────────────────────────────────────────────
PROJECT_DIR="${1:-$(pwd)}"
PROJECT_DIR="$(realpath "$PROJECT_DIR")"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
OUTPUT_NAME="${2:-desmond_model}"

echo "══════════════════════════════════════════════════"
echo "  DESMOND MODELING PIPELINE v2.0"
echo "  Project: $PROJECT_NAME"
echo "  Output:  ${OUTPUT_NAME}-out.cms"
echo "  Force field: S-OPLS"
echo "══════════════════════════════════════════════════"

cd "$PROJECT_DIR"

# ── Step 1: Verify input ──────────────────────────────────────────────────
SOURCE_PDB="${PROJECT_DIR}/packed.pdb"
if [[ ! -f "$SOURCE_PDB" ]]; then
    SOURCE_PDB="${PROJECT_DIR}/system.pdb"
fi
if [[ ! -f "$SOURCE_PDB" ]]; then
    echo "❌ No packed.pdb or system.pdb found in $PROJECT_DIR"
    echo "   Run MOTUS build_system or create packmol.inp first."
    exit 1
fi
echo ""
echo "═══ Step 1/3: Input ═══"
NATOMS=$(grep -c '^ATOM\|^HETATM' "$SOURCE_PDB" 2>/dev/null || echo 0)
echo "  ✓ $SOURCE_PDB: $NATOMS atoms"

# ── Step 2: PDB → Maestro .mae ────────────────────────────────────────────
echo ""
echo "═══ Step 2/3: PDB → Maestro (.mae) ═══"
MAE_FILE="${PROJECT_DIR}/${OUTPUT_NAME}.mae"

export SCHRODINGER="$SCHRODINGER"
export PATH="$SCHRODINGER:$SCHRODINGER/utilities:$PATH"

"$SCHRODINGER"/utilities/pdbconvert \
    -ipdb "$SOURCE_PDB" \
    -omae "$MAE_FILE" 2>&1 | tail -3

if [[ -f "$MAE_FILE" ]]; then
    SIZE=$(du -h "$MAE_FILE" | cut -f1)
    echo "  ✓ Maestro file: $MAE_FILE ($SIZE)"
else
    echo "  ❌ pdbconvert failed"
    exit 1
fi

# ── Step 3: System setup → .cms (build_geometry + S-OPLS) ─────────────────
echo ""
echo "═══ Step 3/3: Desmond system setup (.cms) ═══"

# Detect box size from packmol.inp
BOX_NM=6.0
PACKMOL_INP="${PROJECT_DIR}/packmol.inp"
if [[ -f "$PACKMOL_INP" ]]; then
    BOX_ANGSTROM=$(grep 'inside box' "$PACKMOL_INP" | head -1 | awk '{print $NF}')
    if [[ -n "$BOX_ANGSTROM" ]]; then
        BOX_NM=$(python3 -c "print($BOX_ANGSTROM/10.0)")
    fi
fi
BOX_ANGSTROM=$(python3 -c "print(f'{float($BOX_NM)*10:.1f}')")
echo "  Box: ${BOX_NM} nm = ${BOX_ANGSTROM} Å orthorhombic"

# Create .msj — build_geometry + S-OPLS (CRITICAL: both required!)
MSJ_FILE="${PROJECT_DIR}/${OUTPUT_NAME}.msj"
cat > "$MSJ_FILE" << MSJEOF
task {
  task = "desmond:auto"
}

build_geometry {
  box = {
     shape = orthorhombic
     size = [${BOX_ANGSTROM} ${BOX_ANGSTROM} ${BOX_ANGSTROM} ]
     size_type = absolute
  }
  neutralize_system = false
  override_forcefield = S-OPLS
  rezero_system = false
  solvate_system = false
}

assign_forcefield {
  forcefield = S-OPLS
}
MSJEOF

CMS_FILE="${PROJECT_DIR}/${OUTPUT_NAME}-out.cms"

echo "  Running multisim (build_geometry + S-OPLS, ~46s)..."
"$SCHRODINGER"/utilities/multisim \
    -JOBNAME "${OUTPUT_NAME}" \
    -m "$MSJ_FILE" \
    -o "$CMS_FILE" \
    "$MAE_FILE" 2>&1

# Wait for job (build_geometry + forcefield ~46s, timeout 240s)
echo "  Waiting..."
for i in $(seq 1 120); do
    sleep 2
    if "$SCHRODINGER"/jobcontrol -list 2>&1 | grep -q "no active jobs"; then
        break
    fi
done

# ── Results ────────────────────────────────────────────────────────────────
echo ""
if [[ -f "$CMS_FILE" ]]; then
    CMS_SIZE=$(du -h "$CMS_FILE" | cut -f1)
    echo "══════════════════════════════════════════════════"
    echo "  ✅ DESMOND MODEL READY"
    echo "  Output:  $CMS_FILE ($CMS_SIZE)"
    echo "  Atoms:   $NATOMS"
    echo "  Box:     ${BOX_NM} nm (${BOX_ANGSTROM} Å)"
    echo "  FF:      S-OPLS"
    echo ""
    echo "  To run MD:  desmond-md.sh $PROJECT_DIR"
    echo "══════════════════════════════════════════════════"
    echo ""
    echo "MEDIA:$CMS_FILE"
else
    LOG="${PROJECT_DIR}/${OUTPUT_NAME}_multisim.log"
    if [[ -f "$LOG" ]]; then
        echo "  ❌ .cms not generated. Log summary:"
        grep -E 'completed|failed|FATAL|Error' "$LOG" | tail -5
    else
        echo "  ❌ multisim failed"
    fi
    exit 1
fi
