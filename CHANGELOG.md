# Changelog

## [2.0.0] — 2025

### New features
- **Brain API v2** (`/brain/v2/*`) — versioned, stable API contract with OpenAPI docs
- **Event bus** (`core/event_bus.py`) — pub/sub system for real-time brain events
- **Streaming responses** (`/query` with `stream: true`, `/events` SSE)
- **Knowledge distillation** (`learning/distiller.py`) — use teacher LLMs to generate synthetic training data on specific topics
- **Gap detection** (`learning/gap_detector.py`) — automatically detects knowledge weaknesses and queues targeted distillation
- **Brain versioning** (`core/brain_version.py`) — separate version tracking for brain state vs app code
- **Schema migrations** (`core/migrator.py`) — safe, automatic schema upgrades on every startup
- **Brain export/import** (`core/brain_export.py`) — portable `.ocbrain` bundles for sharing trained modules
- **Distillation + gap detection scheduler loops** — runs every 12h and 6h respectively
- **pip installable from GitHub** — `pip install git+https://github.com/YOUR_USERNAME/openclaw.git`
- **apt repo on GitHub Pages** — `sudo apt install openclaw` after adding repo
- **winget + brew + AUR** — native package manager support on all platforms

### Improvements
- `main.py` — migration check runs before anything else starts
- `scheduler.py` — adds distillation and gap detection loops
- `interface/api.py` — adds Brain API v2 router, SSE event stream, distill/export/import endpoints
- `install.sh` — unified installer with graceful pip fallback on all platforms
- `pyproject.toml` — GitHub URLs, dynamic version from version.txt, all extras defined
- `README.md` — full installation docs, API reference, module maturity model

### Bug fixes (from V1 review)
- `evaluator.py` — was calling `asyncio.run()` inside an async context (deadlock risk)
- `model_router.py` — privacy guard was imported inside method on every call
- `finetuner.py` — `__import__("datetime")` hack replaced with proper import
- `context.py` — dataclass with mutable defaults replaced with plain class

## [1.0.0] — initial release
- Core orchestrator (parser, classifier, decomposer, dispatcher, merger)
- 4 expert modules (coding, web_search, knowledge, system_ctrl)
- Custom module system with factory + registry
- LoRA fine-tuning pipeline (Unsloth/QLoRA)
- Web crawler + ChromaDB knowledge store
- Cross-platform packaging (deb, rpm, arch, exe, pkg)
- System tray, voice input, CLI
