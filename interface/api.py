"""
interface/api.py — FastAPI server. V2: adds Brain API v2, streaming,
event bus integration, export/import endpoints.
"""
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import config
from core.event_bus import bus
from core.orchestrator import Orchestrator
from core.module_factory import create as factory_create

app = FastAPI(
    title="OpenClaw Brain",
    version="2.0.0",
    description="OpenClaw Brain API — local self-learning AI assistant",
)

_orchestrator: Optional[Orchestrator] = None
_scheduler = None
_orchestrator_ref = {}   # shared ref for brain_api router

WEB_DIR = Path(__file__).parent / "web"


def setup(orchestrator: Orchestrator, scheduler):
    global _orchestrator, _scheduler
    _orchestrator = orchestrator
    _scheduler    = scheduler
    _orchestrator_ref["orchestrator"] = orchestrator

    # Register Brain API v2 routes
    from core.brain_api import register as register_brain_api
    register_brain_api(app, _orchestrator_ref)

    # Wire event bus → broadcast to connected SSE clients
    bus.on("module.promoted",      _log_event)
    bus.on("learning.train_done",  _log_event)
    bus.on("learning.distill_done",_log_event)
    bus.on("learning.gap_detected",_log_event)


def _log_event(payload: dict):
    import logging
    logging.getLogger("openclaw").info(f"[event] {payload.get('_event')}: {payload}")


# ── Request/Response models ──────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    module: Optional[str] = None
    stream: bool = False

class QueryResponse(BaseModel):
    answer: str
    modules_used: list[str] = []

class NewModuleRequest(BaseModel):
    name: str
    desc: str
    model: str
    keywords: list[str]
    sources: list[str]

class DistillRequest(BaseModel):
    module_name: str
    topic: str
    num_pairs: int = 50

class ExportRequest(BaseModel):
    module_name: str

class ImportRequest(BaseModel):
    bundle_path: str
    overwrite: bool = False


# ── Core routes ───────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if _orchestrator is None:
        raise HTTPException(503, "Brain not ready")
    if req.stream:
        from core.brain_api import _stream_query
        return StreamingResponse(
            _stream_query(_orchestrator, req.query),
            media_type="text/event-stream",
        )
    answer = await _orchestrator.handle(req.query)
    return QueryResponse(answer=answer)


@app.get("/status")
async def status():
    if _orchestrator is None:
        return {"status": "starting"}
    from core.brain_version import brain_version_manager
    return {
        "status":        "ok",
        "modules":       _orchestrator.status(),
        "brain_version": brain_version_manager.brain_version,
        "app_version":   brain_version_manager.app_version,
    }


@app.get("/modules")
async def list_modules():
    if _orchestrator is None:
        raise HTTPException(503, "Not ready")
    return {
        name: mod.health()
        for name, mod in _orchestrator.modules.items()
    }


@app.post("/modules/new")
async def new_module(req: NewModuleRequest):
    try:
        path = factory_create(req.name, req.desc, req.model, req.keywords, req.sources)
        from core.module_registry import reload_module
        reload_module(req.name, _orchestrator.modules)
        await bus.emit("module.created", {"module": req.name})
        return {"status": "created", "path": str(path)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/train/{module_name}")
async def train_module(module_name: str):
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not running")
    if module_name not in _orchestrator.modules:
        raise HTTPException(404, f"Module '{module_name}' not found")
    result = await _scheduler.trigger_module(module_name)
    return {"result": result}


@app.post("/distill")
async def distill(req: DistillRequest):
    if req.module_name not in _orchestrator.modules:
        raise HTTPException(404, f"Module '{req.module_name}' not found")
    from learning.distiller import distill_topic
    n = await distill_topic(req.module_name, req.topic, req.num_pairs)
    return {"status": "done", "pairs_generated": n}


@app.post("/export")
async def export_module(req: ExportRequest):
    from core.brain_export import export_module
    try:
        path = export_module(req.module_name)
        return {"status": "exported", "path": str(path)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/import")
async def import_module(req: ImportRequest):
    from core.brain_export import import_module
    try:
        name = import_module(Path(req.bundle_path), overwrite=req.overwrite)
        reload_module(name, _orchestrator.modules) if _orchestrator else None
        return {"status": "imported", "module": name}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/config")
async def get_config():
    return config._settings


@app.put("/config")
async def set_config(updates: dict):
    for key, value in updates.items():
        config.set(key, value)
    return {"status": "updated"}


@app.get("/updates")
async def check_updates():
    from interface.updater import check
    return check().__dict__


@app.post("/update/install")
async def install_update():
    from interface.updater import check, install
    info = check()
    if not info.available:
        return {"status": "already_up_to_date"}
    asyncio.create_task(_do_install(info.version))
    return {"status": "installing", "version": info.version}


async def _do_install(version: str):
    from interface.updater import install
    install(version)


@app.post("/rollback")
async def rollback():
    from interface.updater import rollback as do_rollback
    do_rollback()
    return {"status": "rolled_back"}


@app.get("/brain/version")
async def brain_version():
    from core.brain_version import brain_version_manager
    return brain_version_manager.to_dict()


# ── SSE event stream ─────────────────────────────────────────

@app.get("/events")
async def event_stream():
    """
    Server-Sent Events stream — OpenClaw components subscribe here
    to receive real-time brain events without polling.
    """
    import json

    async def _generate():
        queue: asyncio.Queue = asyncio.Queue()

        async def enqueue(payload):
            await queue.put(payload)

        # Subscribe to all events
        from core.event_bus import EVENTS
        for evt in EVENTS:
            bus.on(evt, enqueue)

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"   # prevent connection timeout
        finally:
            for evt in EVENTS:
                bus.off(evt, enqueue)

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── Static Web UI ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    index = WEB_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text())
    return HTMLResponse(
        "<h2>OpenClaw Brain v2 is running.</h2>"
        "<p>Web UI not found. API: <a href='/docs'>/docs</a></p>"
    )


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
