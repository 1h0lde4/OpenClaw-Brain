#!/usr/bin/env bash
# setup.sh — First-time setup script for OpenClaw
# Run once after cloning the repo.
# Usage: bash setup.sh

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

# 1. Python version check
PY=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
MAJOR=$(echo "$PY" | cut -d. -f1)
MINOR=$(echo "$PY" | cut -d. -f2)
if [[ "$MAJOR" -lt 3 || ( "$MAJOR" -eq 3 && "$MINOR" -lt 11 ) ]]; then
    err "Python 3.11+ required. Found: $PY"
fi
ok "Python $PY ✓"

# 2. Virtual environment
if [[ ! -d ".venv" ]]; then
    ok "Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
ok "Virtual environment activated"

# 3. Install dependencies
ok "Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
ok "Core dependencies installed"

# 4. spaCy model
ok "Downloading spaCy language model..."
python -m spacy download en_core_web_sm --quiet
ok "spaCy model ready"

# 5. Optional: training deps
echo ""
read -rp "Install training dependencies (PyTorch + LoRA, ~3GB)? [y/N] " TRAIN
if [[ "$TRAIN" =~ ^[Yy]$ ]]; then
    pip install -r requirements.txt --quiet
    pip install ".[training]" --quiet
    ok "Training dependencies installed"
else
    warn "Skipping training deps — modules will use external models only"
fi

# 6. Optional: voice deps
read -rp "Install voice input dependencies (Whisper + pyttsx3)? [y/N] " VOICE
if [[ "$VOICE" =~ ^[Yy]$ ]]; then
    pip install ".[voice]" --quiet
    ok "Voice dependencies installed"
fi

# 7. Check Ollama
echo ""
if command -v ollama &>/dev/null; then
    ok "Ollama found: $(ollama --version 2>/dev/null || echo 'installed')"
    # Check if at least one model is pulled
    if ollama list 2>/dev/null | grep -q "mistral\|codestral\|llama"; then
        ok "Ollama model(s) found ✓"
    else
        warn "No Ollama models found. Pulling mistral (this will take a while)..."
        ollama pull mistral
        ok "mistral model ready"
    fi
else
    warn "Ollama not installed. OpenClaw needs Ollama for bootstrap stage."
    warn "Install from: https://ollama.ai"
    warn "Then run: ollama pull mistral && ollama pull codestral"
fi

# 8. Create data directories
mkdir -p data/raw data/chunks data/evals
ok "Data directories ready"

# 9. Ensure __init__.py files exist
for d in core modules modules/coding modules/web_search modules/knowledge modules/system_ctrl modules/_template learning interface; do
    touch "$d/__init__.py" 2>/dev/null || true
done
ok "Package init files ready"

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
