"""
core/merger.py — Combines multiple module results into one coherent answer.
Single-module: pass-through.
Multi-module: dedup, rank, weave via LLM call.
"""
import httpx
from .dispatcher import TaskResult
from .config import config


async def merge(results: list[TaskResult], original_query: str) -> str:
    if not results:
        return "I was unable to process your request."

    if len(results) == 1:
        return results[0].result.answer

    # Filter out error results
    valid = [r for r in results if r.result.source != "error"]
    errors = [r for r in results if r.result.source == "error"]

    if not valid:
        return "\n".join(r.result.answer for r in errors)

    if len(valid) == 1:
        return valid[0].result.answer

    # Deduplicate near-identical answers
    unique = _deduplicate([r.result.answer for r in valid])

    # Weave via LLM
    combined = await _weave(unique, original_query)
    if errors:
        combined += "\n\n" + "\n".join(r.result.answer for r in errors)
    return combined


def _deduplicate(answers: list[str]) -> list[str]:
    """Remove answers that are too similar to a previous one."""
    unique = []
    for ans in answers:
        is_dup = any(
            _word_overlap(ans, u) > 0.85
            for u in unique
        )
        if not is_dup:
            unique.append(ans)
    return unique


def _word_overlap(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa), len(sb))


async def _weave(answers: list[str], query: str) -> str:
    """Call local LLM to produce one unified response from N module answers."""
    host  = config.get("global.ollama_host") or "http://localhost:11434"
    parts = "\n\n---\n\n".join(
        f"[Module {i+1}]:\n{ans}" for i, ans in enumerate(answers)
    )
    prompt = (
        f"You received multiple answers to the user query below. "
        f"Combine them into one clear, non-repetitive response.\n\n"
        f"User query: {query}\n\n"
        f"Module answers:\n{parts}\n\n"
        f"Unified response:"
    )
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{host}/api/generate",
                json={"model": "mistral", "prompt": prompt, "stream": False},
            )
            return resp.json().get("response", "").strip()
    except Exception:
        # Fallback: join with newlines
        return "\n\n".join(answers)
