"""
modules/base.py — Abstract base class every expert module inherits.
The full contract: run, run_own, ingest, retrieve, load_weights, health, save_training_pair.
"""
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import chromadb


@dataclass
class ModuleResult:
    answer: str
    confidence: float = 1.0
    source: str = "external"        # "external" | "shadow" | "native" | "error"
    chunks_used: list = field(default_factory=list)
    latency_ms: int = 0


class BaseModule(ABC):
    name: str = "base"

    def __init__(self):
        self.root: Path = Path(__file__).parent / self.name
        self.root.mkdir(parents=True, exist_ok=True)

        # Weights folders
        for sub in ["weights/active", "weights/previous", "weights/pending"]:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

        # ChromaDB — persistent per-module collection
        db_path = str(self.root / "knowledge.db")
        self._chroma_client = chromadb.PersistentClient(path=db_path)
        self.db = self._get_or_create_collection()

        self._model = None  # Loaded lazily in native stage

    def _get_or_create_collection(self):
        from .embedding_fn import get_embedding_function
        return self._chroma_client.get_or_create_collection(
            name=self.name,
            embedding_function=get_embedding_function(self.name),
        )

    # ── Abstract methods (must be implemented) ─────────────────

    @abstractmethod
    async def run(self, task: str, context) -> ModuleResult:
        """Main entry — uses model_router stage logic."""
        ...

    @abstractmethod
    async def run_own(self, task: str, context) -> ModuleResult:
        """Always use own model regardless of stage."""
        ...

    # ── Shared methods (inherited by all modules) ───────────────

    async def run_routed(self, task: str, context, router) -> "RouteResult":
        """Called by dispatcher — delegates routing to model_router."""
        return await router.route(self.name, task, context)

    def retrieve(self, query: str, k: int = 5) -> list[str]:
        """Semantic search over this module's ChromaDB collection."""
        try:
            results = self.db.query(
                query_texts=[query],
                n_results=min(k, self.db.count()),
                include=["documents", "metadatas"],
            )
            docs      = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            # Apply staleness decay filter
            filtered = []
            now = time.time()
            for doc, meta in zip(docs, metadatas):
                ts = meta.get("timestamp", now) if meta else now
                qs = meta.get("quality_score", 0.5) if meta else 0.5
                age_days = (now - ts) / 86400
                if qs < 0.4:
                    continue
                filtered.append(doc)
            return filtered
        except Exception:
            return []

    def ingest(self, chunks: list[str], metadatas: Optional[list[dict]] = None):
        """Embed and upsert chunks into this module's ChromaDB."""
        if not chunks:
            return
        if metadatas is None:
            metadatas = [{"timestamp": time.time(), "quality_score": 0.7}] * len(chunks)
        ids = [f"{self.name}_{abs(hash(c))}_{int(time.time())}" for c in chunks]
        try:
            self.db.upsert(documents=chunks, metadatas=metadatas, ids=ids)
        except Exception as e:
            print(f"[{self.name}] ingest error: {e}")

    def load_weights(self, path: Path):
        """Hot-swap LoRA adapter — atomic, no downtime."""
        try:
            new_model = self._load_lora(path)
            old_model = self._model
            self._model = new_model
            del old_model
            # Archive: move active → previous, pending → active
            active  = self.root / "weights" / "active"
            prev    = self.root / "weights" / "previous"
            pending = self.root / "weights" / "pending"
            import shutil
            if active.exists() and any(active.iterdir()):
                if prev.exists():
                    shutil.rmtree(prev)
                shutil.copytree(active, prev)
            if pending.exists() and any(pending.iterdir()):
                if active.exists():
                    shutil.rmtree(active)
                shutil.copytree(pending, active)
        except Exception as e:
            print(f"[{self.name}] load_weights error: {e}")

    def _load_lora(self, path: Path):
        """Load LoRA adapter — implemented when native stage is reached."""
        return None

    def save_training_pair(self, query: str, answer: str):
        from core.privacy import privacy
        if not privacy.can_save_training():
            return
        out = Path(__file__).parent.parent / "data" / "raw" / self.name
        out.mkdir(parents=True, exist_ok=True)
        pair = {"query": query, "answer": answer, "timestamp": time.time()}
        fname = out / f"{abs(hash(query + str(time.time())))}.json"
        fname.write_text(json.dumps(pair, ensure_ascii=False))

    def health(self) -> dict:
        from core.config import config
        state = config.get_module_state(self.name)
        try:
            count = self.db.count()
            db_ok = True
        except Exception:
            count = 0
            db_ok = False
        return {
            "name":          self.name,
            "stage":         state.get("stage", "bootstrap"),
            "maturity_score":state.get("maturity_score", 0.0),
            "query_count":   state.get("query_count", 0),
            "db_ok":         db_ok,
            "kb_chunks":     count,
            "model":         state.get("bootstrap_model", "unknown"),
        }

    def _build_prompt(self, task: str, chunks: list[str], context) -> str:
        ctx_str = context.format_for_prompt(5) if context else ""
        kb_str  = "\n\n".join(chunks) if chunks else "No relevant knowledge found."
        return (
            f"Conversation history:\n{ctx_str}\n\n"
            f"Relevant knowledge:\n{kb_str}\n\n"
            f"Task: {task}\n\nResponse:"
        )
