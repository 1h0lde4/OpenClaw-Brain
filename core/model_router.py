"""
core/model_router.py — The maturity gate.
Decides whether to call the external model, the module's own model, or both.
Tracks maturity scores and triggers stage promotions.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import config
from .privacy import privacy


SHADOW_PROMOTE_THRESHOLD   = 0.85   # score needed to go shadow → native
SHADOW_PROMOTE_MIN_QUERIES = 500    # minimum queries at shadow stage
REGRESSION_THRESHOLD       = 0.70   # score below this triggers rollback
REGRESSION_WINDOW          = 100    # number of queries to watch


@dataclass
class RouteResult:
    answer: str
    source: str          # "external" | "shadow" | "native"
    shadow_answer: Optional[str] = None
    similarity: Optional[float] = None
    latency_ms: int = 0


class ModelRouter:
    def __init__(self):
        self._recent_scores: dict[str, list[float]] = {}

    async def route(self, module_name: str, subtask: str, context) -> RouteResult:
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")

        t0 = time.monotonic()

        if stage == "bootstrap":
            answer = await self._call_external(module_name, subtask, context)
            self._record_training_pair(module_name, subtask, answer)
            self._increment_query_count(module_name)
            return RouteResult(
                answer=answer, source="external",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        elif stage == "shadow":
            # Run both models in parallel
            ext_answer, own_answer = await asyncio.gather(
                self._call_external(module_name, subtask, context),
                self._call_own_model(module_name, subtask, context),
            )

            similarity = _cosine_sim_text(ext_answer, own_answer)
            self._update_maturity(module_name, similarity)
            self._record_training_pair(module_name, subtask, ext_answer)
            self._increment_query_count(module_name)
            self._maybe_promote(module_name)

            return RouteResult(
                answer=ext_answer, source="shadow",
                shadow_answer=own_answer, similarity=round(similarity, 4),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        else:  # native
            answer = await self._call_own_model(module_name, subtask, context)
            score = await self._spot_check(module_name, subtask, answer)
            if score is not None:
                self._update_maturity(module_name, score)
                self._maybe_rollback(module_name)
            self._increment_query_count(module_name)
            return RouteResult(
                answer=answer, source="native",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

    async def _call_external(self, module_name: str, subtask: str, context) -> str:
        state      = config.get_module_state(module_name)
        model_name = state.get("bootstrap_model", "mistral")
        host       = config.get("global.ollama_host") or "http://localhost:11434"

        ctx_str = context.format_for_prompt(5) if context else ""
        prompt  = f"{ctx_str}\n\nUser: {subtask}\nAssistant:"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model_name, "prompt": prompt, "stream": False},
                )
                return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[External model error: {e}]"

    async def _call_own_model(self, module_name: str, subtask: str, context) -> str:
        """Call the module's own fine-tuned model via Ollama (loaded as custom model)."""
        state      = config.get_module_state(module_name)
        own_model  = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        host       = config.get("global.ollama_host") or "http://localhost:11434"

        ctx_str = context.format_for_prompt(5) if context else ""
        prompt  = f"{ctx_str}\n\nUser: {subtask}\nAssistant:"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": own_model, "prompt": prompt, "stream": False},
                )
                return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[Own model error: {e}]"

    async def _spot_check(self, module_name: str, subtask: str, own_answer: str) -> Optional[float]:
        """Occasionally compare own model against external — 1-in-20 queries."""
        import random
        if random.random() > 0.05:
            return None
        ext_answer = await self._call_external(module_name, subtask, None)
        return _cosine_sim_text(own_answer, ext_answer)

    def _record_training_pair(self, module_name: str, query: str, answer: str):
        if not privacy.can_save_training():
            return
        import json
        from pathlib import Path
        out = Path(__file__).parent.parent / "data" / "raw" / module_name
        out.mkdir(parents=True, exist_ok=True)
        pair = {"query": query, "answer": answer, "timestamp": time.time()}
        filename = f"{uuid.uuid4()}.json"
        (out / filename).write_text(
            json.dumps(pair, ensure_ascii=False)
        )

    def _increment_query_count(self, module_name: str):
        state = config.get_module_state(module_name)
        config.set_module_state(module_name, "query_count", state.get("query_count", 0) + 1)

    def _update_maturity(self, module_name: str, score: float):
        scores = self._recent_scores.setdefault(module_name, [])
        scores.append(score)
        if len(scores) > REGRESSION_WINDOW:
            scores.pop(0)
        avg = sum(scores) / len(scores)
        config.set_module_state(module_name, "maturity_score", round(avg, 4))

    def _maybe_promote(self, module_name: str):
        state  = config.get_module_state(module_name)
        stage  = state.get("stage", "bootstrap")
        score  = state.get("maturity_score", 0.0)
        qcount = state.get("query_count", 0)

        if stage == "bootstrap" and qcount >= 1000:
            config.set_module_state(module_name, "stage", "shadow")

        elif stage == "shadow":
            scores = self._recent_scores.get(module_name, [])
            if (len(scores) >= SHADOW_PROMOTE_MIN_QUERIES
                    and score >= SHADOW_PROMOTE_THRESHOLD):
                config.set_module_state(module_name, "stage", "native")

    def _maybe_rollback(self, module_name: str):
        scores = self._recent_scores.get(module_name, [])
        if len(scores) < REGRESSION_WINDOW:
            return
        avg = sum(scores[-REGRESSION_WINDOW:]) / REGRESSION_WINDOW
        if avg < REGRESSION_THRESHOLD:
            config.set_module_state(module_name, "stage", "shadow")
            self._recent_scores[module_name] = []

    def get_maturity_score(self, module_name: str) -> float:
        return float(config.get_module_state(module_name).get("maturity_score", 0.0))


def _cosine_sim_text(a: str, b: str) -> float:
    """Fast word-overlap cosine similarity — no model needed for scoring."""
    if not a or not b:
        return 0.0
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / ((len(set_a) * len(set_b)) ** 0.5)


model_router = ModelRouter()
