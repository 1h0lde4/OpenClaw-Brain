"""
core/classifier.py — Assigns module labels + confidence scores.
Step 1: fast keyword match (free, < 1 ms).
Step 2: if ambiguous, zero-shot LLM prompt.
Step 3: if still below threshold → fan-out or ask user.
"""
import asyncio
import json
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import config
from .parser import ParsedQuery


@dataclass
class Label:
    module: str       # "coding" | "web_search" | "knowledge" | "system_ctrl" | custom
    confidence: float # 0.0 – 1.0
    subtask: str      # the slice of the query this label owns


async def label(parsed: ParsedQuery, context) -> list[Label]:
    """
    Returns a list of Labels sorted by confidence descending.
    Multiple labels = multi-module dispatch.
    """
    module_names = config.all_module_names()
    scores: dict[str, float] = {}

    # ── Step 1: keyword match ───────────────────────────────────
    for mod in module_names:
        kws = config.get_module_keywords(mod) or []
        hits = sum(1 for kw in kws if kw.lower() in parsed.raw.lower())
        if hits:
            base_score = min(0.4 + hits * 0.15, 0.85)
            # boost if used recently
            boost = context.boost_module(mod)
            scores[mod] = min(base_score + boost, 1.0)

    # ── Step 2: LLM disambiguation if ambiguous ─────────────────
    threshold = float(config.get("global.confidence_floor") or 0.6)
    if not scores or max(scores.values()) < threshold:
        llm_scores = await _llm_classify(parsed.raw, module_names)
        for mod, score in llm_scores.items():
            scores[mod] = max(scores.get(mod, 0.0), score)

    # ── Build label list ─────────────────────────────────────────
    labels = []
    for mod, score in scores.items():
        if score >= threshold:
            labels.append(Label(
                module=mod,
                confidence=round(score, 3),
                subtask=parsed.raw,   # full query per module; decomposer refines this
            ))

    labels.sort(key=lambda l: l.confidence, reverse=True)

    # ── Fallback: knowledge module if nothing matched ────────────
    if not labels:
        labels.append(Label(module="knowledge", confidence=0.5, subtask=parsed.raw))

    return labels


async def _llm_classify(query: str, module_names: list[str]) -> dict[str, float]:
    """Zero-shot classification via local Ollama."""
    ollama_host = config.get("global.ollama_host") or "http://localhost:11434"
    prompt = (
        f"You are a router. Given the user query below, output a JSON object "
        f"mapping each of these module names to a confidence score 0.0-1.0:\n"
        f"Modules: {module_names}\n"
        f"Query: {query}\n"
        f"Respond ONLY with valid JSON, e.g.: "
        f'{{"{module_names[0]}": 0.9, "{module_names[1]}": 0.1}}'
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ollama_host}/api/generate",
                json={"model": "mistral", "prompt": prompt, "stream": False},
            )
            text = resp.json().get("response", "{}")
            # Extract JSON from response
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
    except Exception:
        pass
    return {}
