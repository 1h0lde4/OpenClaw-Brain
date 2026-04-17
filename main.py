"""
main.py — OpenClaw Brain V2 entry point.
Startup sequence:
  1. Run schema migrations (safe, never destructive)
  2. Load config
  3. Check Ollama
  4. Initialize modules via registry
  5. Start Orchestrator
  6. Start learning scheduler
  7. Start FastAPI + Brain API v2
  8. Start system tray + voice
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("openclaw")


async def check_ollama() -> bool:
    import httpx
    from core.config import config
    host = config.get("global.ollama_host") or "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{host}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def main():
    print("=" * 55)
    print("  OpenClaw Brain  v2.0.0")
    print("=" * 55)

    # ── Step 1: Migrations ────────────────────────────────────
    log.info("Running schema migrations...")
    try:
        from core.migrator import run_migrations
        run_migrations()
    except Exception as e:
        log.error(f"Migration failed: {e}")
        sys.exit(1)

    # ── Step 2: Config ────────────────────────────────────────
    from core.config import config
    from core.brain_version import brain_version_manager
    log.info(f"Brain version: {brain_version_manager.brain_version} | "
             f"App: {brain_version_manager.app_version} | "
             f"Schema: v{brain_version_manager.schema_version}")

    # ── Step 3: Ollama check ──────────────────────────────────
    log.info("Checking Ollama...")
    if not await check_ollama():
        log.warning("Ollama not reachable — bootstrap/shadow stages will fail "
                    "until Ollama is running at "
                    f"{config.get('global.ollama_host')}")
    else:
        log.info("Ollama OK")

    # ── Step 4: Load modules ──────────────────────────────────
    log.info("Loading modules...")
    from core.module_registry import load_all
    modules = load_all()
    if not modules:
        log.error("No modules loaded. Check modules/ directory.")
        sys.exit(1)
    log.info(f"Loaded {len(modules)} module(s): {list(modules.keys())}")

    # ── Step 5: Orchestrator ──────────────────────────────────
    from core.context import context_memory
    from core.model_router import model_router
    from core.orchestrator import Orchestrator
    orchestrator = Orchestrator(modules, context_memory, model_router)
    log.info("Orchestrator ready")

    # ── Step 6: Scheduler ─────────────────────────────────────
    from learning.scheduler import Scheduler
    scheduler = Scheduler(modules)

    # ── Step 7: Wire API ──────────────────────────────────────
    from interface.api import app, setup as api_setup
    api_setup(orchestrator, scheduler)

    # ── Emit brain.ready event ────────────────────────────────
    from core.event_bus import bus
    await bus.emit("brain.ready", {
        "modules": list(modules.keys()),
        "version": brain_version_manager.brain_version,
    })

    # ── Step 8: System tray ───────────────────────────────────
    try:
        from interface.tray import start as tray_start
        tray_start(orchestrator)
    except Exception as e:
        log.debug(f"Tray not started: {e}")

    # ── Step 9: Voice ─────────────────────────────────────────
    if config.get("global.voice_enabled", False):
        try:
            from interface.voice import start as voice_start
            def _handle_voice(q: str):
                asyncio.create_task(orchestrator.handle(q))
            voice_start(_handle_voice)
        except Exception as e:
            log.debug(f"Voice not started: {e}")

    # ── Step 10: Run server + scheduler ──────────────────────
    port = int(config.get("global.web_ui_port") or 7437)
    log.info(f"Web UI  → http://localhost:{port}")
    log.info(f"API     → http://localhost:{port}/docs")
    log.info(f"Events  → http://localhost:{port}/events")
    log.info(f"Brain   → http://localhost:{port}/brain/v2/status")
    log.info("OpenClaw Brain is ready.\n")

    uv_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level=str(config.get("global.log_level") or "info").lower(),
        loop="asyncio",
    )
    server = uvicorn.Server(uv_config)

    await asyncio.gather(
        server.serve(),
        scheduler.start(),
    )


def _handle_sigterm(sig, frame):
    log.info("Shutting down OpenClaw Brain...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped by user.")
