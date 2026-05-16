#!/usr/bin/env bash
# =============================================================================
# MOTUS Installer — one-command setup for any Linux server
# =============================================================================
# This script bootstraps MOTUS from a fresh git clone:
#   1. Creates the ~/.motus/ config directory
#   2. Writes an .env template for your DeepSeek API key
#   3. Installs the Python package (pip install)
#   4. Detects installed MD engines (GROMACS, LAMMPS, Desmond)
#
# Usage:
#   git clone https://github.com/X-Hydrogen/motus.git
#   cd motus
#   bash install.sh
#
# Then edit ~/.motus/.env to add your API key and you're ready:
#   motus "Study methane hydrate formation at 260K and 200 bar"
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOTUS_DIR="${HOME}/.motus"
ENV_FILE="${MOTUS_DIR}/.env"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        🧬  MOTUS Installer  —  v1.0.0                        ║"
echo "║        Autonomous Molecular Dynamics Scientist               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ---- Step 1: Config directory ----
echo "━━━ Step 1/4: Config directory ━━━"
mkdir -p "${MOTUS_DIR}"
echo "   ✓ ${MOTUS_DIR}"

# ---- Step 2: API key template ----
echo ""
echo "━━━ Step 2/4: API key configuration ━━━"
if [ -f "${ENV_FILE}" ]; then
    echo "   ⚠  ${ENV_FILE} already exists — skipping."
    echo "   → Edit it to set your DeepSeek API key: nano ${ENV_FILE}"
else
    cat > "${ENV_FILE}" << 'EOF'
# MOTUS DeepSeek API key
# Get your key at: https://platform.deepseek.com/api_keys
MOTUS_DEEPSEEK_KEY=sk-your-key-here
EOF
    echo "   ✓ Created ${ENV_FILE}"
    echo ""
    echo "   ╔════════════════════════════════════════════════════════════╗"
    echo "   ║  IMPORTANT:  Set your API key before using MOTUS!         ║"
    echo "   ║                                                           ║"
    echo "   ║    nano ~/.motus/.env                                     ║"
    echo "   ║                                                           ║"
    echo "   ║  Replace 'sk-your-key-here' with your real key from:      ║"
    echo "   ║  https://platform.deepseek.com/api_keys                   ║"
    echo "   ╚════════════════════════════════════════════════════════════╝"
fi

# ---- Step 3: Python package ----
echo ""
echo "━━━ Step 3/4: Python package ━━━"

# Determine Python
PYTHON=""
for py in python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        PYVER=$("$py" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "0")
        MAJOR=$(echo "$PYVER" | cut -d. -f1)
        MINOR=$(echo "$PYVER" | cut -d. -f2)
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$py"
            break
        fi
    fi
done

if [ -z "${PYTHON}" ]; then
    echo "   ✗ Python ≥3.10 not found. Please install it first."
    exit 1
fi
echo "   Python: ${PYTHON} ($(${PYTHON} --version))"

# Install in development mode so scripts, templates, etc. stay accessible
AGENT_DIR="${SCRIPT_DIR}/agent"
if [ -f "${AGENT_DIR}/pyproject.toml" ]; then
    ${PYTHON} -m pip install -e "${AGENT_DIR}" --quiet 2>&1 | tail -3 || {
        echo "   ✗ pip install failed. Try: pip install -e ${AGENT_DIR}"
        exit 1
    }
    echo "   ✓ motus-agent installed (editable mode)"
else
    echo "   ✗ agent/pyproject.toml not found — are you in the motus repo root?"
    exit 1
fi

# Verify CLI works
if command -v motus &>/dev/null; then
    echo "   ✓ motus CLI registered"
else
    echo "   ⚠  'motus' not on PATH — you may need to add ~/.local/bin to your PATH"
    echo "   → export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ---- Step 4: MD engines ----
echo ""
echo "━━━ Step 4/4: MD engine detection ━━━"

engines_found=0

# GROMACS
if command -v gmx &>/dev/null || command -v gmx_mpi &>/dev/null; then
    echo "   ✓ GROMACS"
    engines_found=$((engines_found + 1))
else
    echo "   ✗ GROMACS not found on PATH (optional)"
fi

# LAMMPS
if command -v lmp &>/dev/null || command -v lmp_mpi &>/dev/null || command -v lmp_serial &>/dev/null; then
    echo "   ✓ LAMMPS"
    engines_found=$((engines_found + 1))
else
    echo "   ✗ LAMMPS not found on PATH (optional)"
fi

# Desmond (Schrödinger)
if [ -n "${SCHRODINGER:-}" ] && [ -f "${SCHRODINGER}/utilities/multisim" ]; then
    echo "   ✓ Desmond (Schrödinger)"
    engines_found=$((engines_found + 1))
else
    echo "   ✗ Desmond / Schrödinger not detected (optional)"
    echo "     → export SCHRODINGER=/path/to/schrodinger"
fi

# VMD
if command -v vmd &>/dev/null; then
    echo "   ✓ VMD (for system rendering)"
fi

# ---- Done ----
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           ✅  MOTUS installation complete!                   ║"
echo "║                                                              ║"
echo "║  Engines detected: ${engines_found}/3                                  ║"
echo "║  Config:           ~/.motus/.env                              ║"
echo "║                                                              ║"
echo "║  Next steps:                                                 ║"
echo "║    1. Set your API key:  nano ~/.motus/.env                  ║"
echo "║    2. Run your first simulation:                             ║"
echo "║       motus \"Study methane hydrate formation\"               ║"
echo "║    3. Or start the web interface:                            ║"
echo "║       motus-web --host 0.0.0.0                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
