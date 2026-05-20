#!/bin/bash
# ============================================================
# MOTUS setup.sh — One-command environment setup
# ============================================================
# Usage:
#   bash setup.sh              # auto-detect conda or fallback to system pip
#   bash setup.sh --no-conda   # skip conda, use system python3 + pip
#   bash setup.sh --fresh      # install miniconda from scratch
#
# This script:
#   1. Detects or installs Miniconda3 (Tsinghua mirrors)
#   2. Configures conda mirror channels
#   3. Installs all Python dependencies (numpy, matplotlib, scipy, …)
#   4. Sets MOTUS_PYTHON env var for the analysis scripts
# ============================================================

set -eu

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; }
header() { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }

CONDA_DIR="${HOME}/miniconda3"
MOTUS_DIR="$(cd "$(dirname "$0")" && pwd)"
USE_CONDA=1
FRESH_INSTALL=0
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-conda) USE_CONDA=0; shift ;;
        --fresh)    FRESH_INSTALL=1; shift ;;
        -h|--help)
            head -20 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *) shift ;;
    esac
done

header "MOTUS Environment Setup"

# ── Step 1: Conda ──
if [[ "$USE_CONDA" -eq 1 ]]; then
    if [[ -x "$CONDA_DIR/bin/conda" ]]; then
        log "Found conda at $CONDA_DIR"
    elif [[ "$FRESH_INSTALL" -eq 1 ]] || [[ ! -x "$CONDA_DIR/bin/conda" ]]; then
        warn "Conda not found. Installing Miniconda3..."
        echo ""
        echo "  This will download ~100 MB and install to $CONDA_DIR"
        echo "  Press Enter to continue, or Ctrl+C to cancel."
        read -r

        INSTALLER="/tmp/Miniconda3-latest-Linux-x86_64.sh"
        if [[ ! -f "$INSTALLER" ]]; then
            log "Downloading Miniconda3..."
            wget -q --show-progress \
                https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
                -O "$INSTALLER"
        fi

        log "Installing Miniconda3 to $CONDA_DIR ..."
        bash "$INSTALLER" -b -p "$CONDA_DIR"
        rm -f "$INSTALLER"

        # Configure Tsinghua mirrors
        log "Configuring Tsinghua mirrors..."
        cat > "$HOME/.condarc" << 'CONDARC_EOF'
channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  msys2: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  bioconda: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  menpo: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch-lts: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  simpleitk: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  deepmodeling: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
CONDARC_EOF

        log "Conda installed. Restart your shell or run:"
        echo  "    source $CONDA_DIR/bin/activate"
        echo  "    conda init bash"
        echo  "  Then re-run: bash setup.sh"
        echo ""
        exit 0
    fi

    # Initialize conda for this script
    source "$CONDA_DIR/etc/profile.d/conda.sh" 2>/dev/null || true
    conda activate base 2>/dev/null || true

    PYTHON_BIN="$CONDA_DIR/bin/python3"
    PIP_BIN="$CONDA_DIR/bin/pip3"
    log "Conda base activated"
else
    PYTHON_BIN="$(which python3 2>/dev/null || echo /usr/bin/python3)"
    PIP_BIN="$(which pip3 2>/dev/null || echo /usr/bin/pip3)"
    warn "Skipping conda — using system python3: $PYTHON_BIN"
fi

# ── Step 2: Upgrade conda packages ──
if [[ "$USE_CONDA" -eq 1 ]]; then
    header "Upgrading conda packages"
    conda upgrade --all -y 2>&1 | tail -3
fi

# ── Step 3: Install Python dependencies ──
header "Installing Python dependencies"
log "Python: $($PYTHON_BIN --version)"
log "Pip:    $($PIP_BIN --version 2>&1 | head -1)"

$PIP_BIN install -r "$MOTUS_DIR/requirements.txt" -i "$PIP_MIRROR" 2>&1 | tail -5

# ── Step 4: Verify ──
header "Verification"
REQUIRED="numpy matplotlib scipy pandas yaml PIL docx"
ALL_OK=1
for mod in $REQUIRED; do
    if $PYTHON_BIN -c "import $mod" 2>/dev/null; then
        log "  $mod ✓"
    else
        warn "  $mod ✗ (missing)"
        ALL_OK=0
    fi
done

# ── Step 5: Write MOTUS_PYTHON env marker ──
echo "$PYTHON_BIN" > "$MOTUS_DIR/.motus_python_path"
log "Python path saved to .motus_python_path"

# ── Done ──
echo ""
if [[ "$ALL_OK" -eq 1 ]]; then
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD}  MOTUS environment ready!${NC}"
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  Python:  ${BOLD}$PYTHON_BIN${NC}"
    echo -e "  MOTUS:   ${BOLD}$MOTUS_DIR${NC}"
    echo ""
    echo "  To use MOTUS scripts, just run them directly:"
    echo "    bash motus/desmond/desmond-analysis_large_system.sh"
    echo "    bash motus/gromacs/gromacs-analysis.sh"
    echo "    bash motus/lammps/lammps-analysis.sh"
else
    error "Some packages missing. Run: $PIP_BIN install -r $MOTUS_DIR/requirements.txt"
fi
