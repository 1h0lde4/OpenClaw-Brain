"""
modules/web_search/module.py — Web search expert module.
Fetches live results, injects them into KB, then generates an answer.
Uses SearXNG (self-hosted) or falls back to direct HTTP fetch.
"""
import time
import httpx
import trafilatura
from modules.base import BaseModule, ModuleResult
from core.config import config


class Module(BaseModule):
    name = "web_search"

    async def run(self, task: str, context) -> ModuleResult:
        t0 = time.monotonic()

        # 1. Fetch live results
        live_chunks = await self._fetch_live(task)

        # 2. Ingest fresh chunks into KB immediately
        if live_chunks:
            meta = [
                {"timestamp": time.time(), "quality_score": 0.75,
                 "source_type": "query", "source_url": "live"}
                for _ in live_chunks
            ]
            self.ingest(live_chunks, meta)

        # 3. Retrieve from KB (now includes fresh content)
        kb_chunks = self.retrieve(task, k=5)

        prompt = self._build_prompt(task, kb_chunks or live_chunks, context)
        answer = await self._call_external_raw(prompt)
        self.save_training_pair(task, answer)
        return ModuleResult(
            answer=answer,
            source="external",
            chunks_used=kb_chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def run_own(self, task: str, context) -> ModuleResult:
        t0        = time.monotonic()
        kb_chunks = self.retrieve(task, k=5)
        prompt    = self._build_prompt(task, kb_chunks, context)
        answer    = await self._call_own_raw(prompt)
        return ModuleResult(
            answer=answer, source="native",
            chunks_used=kb_chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def _fetch_live(self, query: str) -> list[str]:
        """Fetch top web results and extract text."""
        chunks = []
        try:
            # Try SearXNG first (self-hosted, configurable)
            searxng = config.get("global.searxng_url") or ""
            if searxng:
                urls = await self._searxng_urls(query, searxng)
            else:
                # Fallback: use DuckDuckGo HTML (no API key needed)
                urls = await self._ddg_urls(query)

            async with httpx.AsyncClient(timeout=15.0) as client:
                for url in urls[:3]:
                    try:
                        resp = await client.get(url, follow_redirects=True)
                        text = trafilatura.extract(resp.text)
                        if text and len(text) > 100:
                            # Chunk at ~300 tokens
                            for chunk in _rough_chunk(text, 300):
                                chunks.append(chunk)
                    except Exception:
                        continue
        except Exception:
            pass
        return chunks[:15]  # Cap at 15 chunks per query

    async def _searxng_urls(self, query: str, base: str) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base}/search",
                params={"q": query, "format": "json", "engines": "google,bing"},
            )
            results = resp.json().get("results", [])
            return [r["url"] for r in results[:5] if "url" in r]

    async def _ddg_urls(self, query: str) -> list[str]:
        """DuckDuckGo HTML scrape — no API key required."""
        import re
        async with httpx.AsyncClient(timeout=10.0, headers={
            "User-Agent": "Mozilla/5.0 (compatible; OpenClaw/1.0)"
        }) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            urls = re.findall(r'href="(https?://[^"&]+)"', resp.text)
            # Filter out DDG internal links
            return [u for u in urls if "duckduckgo.com" not in u][:5]

    def _build_prompt(self, task: str, chunks: list, context) -> str:
        ctx_str = context.format_for_prompt(3) if context else ""
        kb_str  = "\n\n".join(chunks) if chunks else "No web results found."
        return (
            f"You are a helpful assistant with access to current web information.\n"
            f"{ctx_str}\n\n"
            f"Web search results:\n{kb_str}\n\n"
            f"Query: {task}\n\n"
            f"Answer based on the search results above:"
        )

    async def _call_external_raw(self, prompt: str) -> str:
        state = config.get_module_state(self.name)
        model = state.get("bootstrap_model", "mistral")
        host  = config.get("global.ollama_host") or "http://localhost:11434"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[Web search module error: {e}]"

    async def _call_own_raw(self, prompt: str) -> str:
        state = config.get_module_state(self.name)
        model = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        host  = config.get("global.ollama_host") or "http://localhost:11434"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[Web search own-model error: {e}]"


def _rough_chunk(text: str, max_tokens: int = 300) -> list[str]:
    words    = text.split()
    chunks   = []
    current  = []
    for word in words:
        current.append(word)
        if len(current) >= max_tokens:
            chunks.append(" ".join(current))
            current = current[-50:]  # 50-token overlap
    if current:
        chunks.append(" ".join(current))
    return chunks
