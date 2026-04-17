<div align="center">

# ⚙ OpenClaw Brain

**Local, self-learning AI brain for OpenClaw.**  
Modular expert models that start on Ollama and gradually train their own weights — until they run fully independently.

[![Version](https://img.shields.io/badge/version-2.0.0-1d9e75?style=flat-square)](https://github.com/1h0lde4/OpenClaw-Brain/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/1h0lde4/OpenClaw-Brain/ci.yml?style=flat-square&label=CI)](https://github.com/1h0lde4/OpenClaw-Brain/actions)

</div>

---

## Install

**One-liner (Linux / macOS):**
```bash
curl -fsSL https://raw.githubusercontent.com/1h0lde4/OpenClaw-Brain/main/install.sh | bash
```

**pip from GitHub:**
```bash
pip install git+https://github.com/1h0lde4/OpenClaw-Brain.git
```

**pip specific release:**
```bash
pip install https://github.com/1h0lde4/OpenClaw-Brain/archive/refs/tags/v2.0.0.tar.gz
```

**Clone and run:**
```bash
git clone https://github.com/1h0lde4/OpenClaw-Brain.git
cd OpenClaw-Brain
bash setup.sh          # installs deps + spaCy model + checks Ollama
python main.py
```

**Windows (winget):**
```powershell
winget install OpenClaw.OpenClaw
```

---

## Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| RAM | 8 GB | 16 GB |
| VRAM (training) | 6 GB | 12 GB |
| Disk | 10 GB | 50 GB |
| [Ollama](https://ollama.ai) | required for bootstrap | — |

---

## Quick start

```bash
# 1. Start the brain
python main.py

# 2. Open Web UI
open http://localhost:7437

# 3. CLI query
openclaw "explain how transformers work"

# 4. Check module status
openclaw status
```

---

## Brain API v2

The brain exposes a versioned REST API at `http://localhost:7437`.

| Endpoint | Method | Description |
|---|---|---|
| `/brain/v2/status` | GET | Full brain + module status |
| `/brain/v2/query` | POST | Query the brain (supports `stream: true`) |
| `/brain/v2/version` | GET | Brain + app version info |
| `/query` | POST | Simple query endpoint |
| `/query/stream` | GET | SSE token streaming |
| `/events` | GET | SSE event bus stream |
| `/modules` | GET | List all modules |
| `/modules/new` | POST | Create custom module |
| `/train/{name}` | POST | Manual training trigger |
| `/distill` | POST | Knowledge distillation |
| `/export` | POST | Export module as .ocbrain |
| `/import` | POST | Import .ocbrain bundle |
| `/docs` | GET | Auto-generated OpenAPI docs |

---

## Module maturity model

Each module goes through 3 stages automatically:

```
Bootstrap ──(1000 queries)──► Shadow ──(score ≥ 0.85)──► Native
  Uses Ollama                Both run,              Own model only
  Collects pairs             own model scored       Ollama dropped
```

---

## Adding custom modules

```bash
# CLI wizard
openclaw new-module

# Or via Web UI → Modules → + Add custom module
```

Custom modules follow the same maturity path. Export and share them:

```bash
# Export
POST /export  {"module_name": "my_finance_module"}

# Import on another machine
POST /import  {"bundle_path": "my_finance_module_20250610.ocbrain"}
```

---

## Knowledge distillation

Instead of waiting for organic query pairs, seed a module instantly:

```bash
POST /distill
{
  "module_name": "knowledge",
  "topic": "transformer architecture",
  "num_pairs": 50
}
```

The brain uses a teacher LLM to generate rich Q&A pairs, scores them, and immediately starts training.

---

## Update

```bash
# Check for updates
openclaw update

# Or via package manager
sudo apt upgrade openclaw        # Debian/Ubuntu
sudo dnf upgrade openclaw        # Fedora
yay -Syu openclaw                # Arch
brew upgrade --cask openclaw     # macOS
winget upgrade OpenClaw.OpenClaw # Windows

# Roll back if needed
openclaw rollback
```

---

## Project structure

```
openclaw/
├── core/          Orchestrator, classifier, router, migrator, brain API
├── modules/       Expert modules (coding, web_search, knowledge, system_ctrl)
├── learning/      Crawler, cleaner, trainer, finetuner, distiller, gap detector
├── interface/     FastAPI, Web UI, CLI, tray, voice, updater
├── config/        settings.toml, sources.toml, models.toml
├── data/          Context DB, raw pairs, chunks, evals, .ocbrain exports
├── tests/         Full test suite
└── install/       Cross-platform build scripts
```

---

## Contributing

```bash
git clone https://github.com/1h0lde4/openclaw.git
cd openclaw
pip install -e ".[dev]"
pytest tests/
```

---

## License

MIT — see [LICENSE](LICENSE)
