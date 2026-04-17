#!/usr/bin/env bash
# setup.sh — First-time setup script for OpenClaw
# Usage:
#   bash setup.sh
# Optional (non-interactive):
#   TRAIN=y VOICE=n bash setup.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[setup]${NC} $*"; }
err()  { echo -e "${RED}[setup]${NC} $*"; exit 1; }

echo ""
echo "  ╔═══════════════════════════════╗"
echo "  ║   OpenClaw First-Time Setup   ║"
echo "  ╚═══════════════════════════════╝"
echo ""

# 0. Check prerequisites
command -v python3 >/dev/null || err "python3 is not installed"
command -v pip >/dev/null || warn "pip not found globally (will rely on venv)"

# Optional but recommended
if ! command -v node >/dev/null; then
    warn "Node.js not installed (recommended for full OpenClaw ecosystem)"
fi

# 1. Python version check (robust)
PY=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJOR=$(echo "$PY" | cut -d. -f1)
MINOR=$(echo "$PY" | cut -d. -f2)

if [[ "$MAJOR" -lt 3 || ( "$MAJOR" -eq 3 && "$MINOR" -lt 11 ) ]]; then
    err "Python 3.11+ required. Found: $PY"
fi
ok "Python $PY ✓"

# 2. Virtual environment
if [[ ! -d ".venv" ]]; then
    ok "Creating virtual environment..."
    python3 -m venv .venv || err "Failed to create virtual environment"
fi

if [[ ! -f ".venv/bin/activate" ]]; then
    err "Virtualenv activation script not found"
fi

# shellcheck disable=SC1091
source .venv/bin/activate
ok "Virtual environment activated"

# 3. Install core dependencies
ok "Installing core dependencies (this may take a few minutes)..."
python -m pip install --upgrade pip --quiet 2>/tmp/pip_upgrade.err || {
    err "Failed to upgrade pip. $(cat /tmp/pip_upgrade.err)"
}
pip install -r requirements.txt --quiet 2>/tmp/req_install.err || {
    err "Failed to install requirements. $(cat /tmp/req_install.err)"
}
ok "Core dependencies installed"

# 3b. Install the project itself (includes all core deps from pyproject.toml)
ok "Installing OpenClaw Brain package..."
pip install -e . --quiet 2>/tmp/pkg_install.err || {
    err "Failed to install OpenClaw Brain package. $(cat /tmp/pkg_install.err)"
}
ok "OpenClaw Brain installed"

# 4. spaCy model
ok "Downloading spaCy language model..."
python -m spacy download en_core_web_sm --quiet 2>/tmp/spacy.err || {
    err "spaCy model download failed. $(cat /tmp/spacy.err)"
}
ok "spaCy model ready"

# 5. Optional: training deps
echo ""
TRAIN=${TRAIN:-}
if [[ -z "$TRAIN" ]]; then
    read -rp "Install training dependencies (PyTorch + LoRA, ~3GB)? [y/N] " TRAIN
fi

if [[ "$TRAIN" =~ ^[Yy]$ ]]; then
    ok "Installing training dependencies..."
    pip install "openclaw-brain[training]" --quiet 2>/tmp/training.err || {
        err "Training dependencies installation failed. $(cat /tmp/training.err)"
    }
    ok "Training dependencies installed"
else
    warn "Skipping training deps — modules will use external models only"
fi

# 6. Optional: voice deps
VOICE=${VOICE:-}
if [[ -z "$VOICE" ]]; then
    read -rp "Install voice input dependencies (Whisper + pyttsx3)? [y/N] " VOICE
fi

if [[ "$VOICE" =~ ^[Yy]$ ]]; then
    ok "Installing voice dependencies..."
    pip install "openclaw-brain[voice]" --quiet 2>/tmp/voice.err || {
        err "Voice dependencies installation failed. $(cat /tmp/voice.err)"
    }
    ok "Voice dependencies installed"
else
    warn "Skipping voice dependencies"
fi

# 7. Check Ollama
echo ""
if command -v ollama >/dev/null; then
    ok "Ollama found: $(ollama --version 2>/dev/null || echo 'installed')"

    if ollama list 2>/dev/null | grep -E '(^|\s)(mistral|codestral|llama)' >/dev/null; then
        ok "Ollama model(s) found ✓"
    else
        warn "No Ollama models found. Pulling mistral (this may take a while)..."
        if ! ollama pull mistral 2>/tmp/ollama.err; then
            err "Failed to pull mistral model. $(cat /tmp/ollama.err)"
        fi
        ok "mistral model ready"
    fi
else
    warn "Ollama not installed. Required for local LLM execution."
    warn "Install from: https://ollama.ai"
    warn "Then run: ollama pull mistral && ollama pull codestral"
fi

# 8. Create data directories
mkdir -p data/raw data/chunks data/evals || err "Failed to create data directories"
ok "Data directories ready"

# 9. Ensure Python package structure
for d in core modules modules/coding modules/web_search modules/knowledge modules/system_ctrl modules/_template learning interface; do
    mkdir -p "$d" || err "Failed to create directory: $d"
    touch "$d/__init__.py" || err "Failed to create __init__.py in: $d"
done
ok "Package structure ready"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   Setup complete!                     ║"
echo "  ║                                       ║"
echo "  ║   Start OpenClaw:                     ║"
echo "  ║     source .venv/bin/activate         ║"
echo "  ║     python main.py                    ║"
echo "  ║                                       ║"
echo "  ║   Web UI: http://localhost:7437       ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""