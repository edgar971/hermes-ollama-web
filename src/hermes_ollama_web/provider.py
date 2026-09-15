"""Ollama Web Search / Web Fetch backend for the Hermes ``web_search`` + ``web_extract`` tools.

Implements the public :class:`agent.web_search_provider.WebSearchProvider` ABC so the
built-in tools route through Ollama's hosted search index — no new model-facing tools.

Endpoints (docs.ollama.com/capabilities/web-search):
    POST https://ollama.com/api/web_search  {"query": str, "max_results": int<=10}
    POST https://ollama.com/api/web_fetch   {"url": str}

Auth: ``OLLAMA_API_KEY`` (free account, https://ollama.com/settings/keys).
Base URL override: ``OLLAMA_WEB_BASE_URL`` (default ``https://ollama.com``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

PROVIDER_NAME = "ollama"
DISPLAY_NAME = "Ollama Web Search"
KEY_ENV = "OLLAMA_API_KEY"
BASE_URL_ENV = "OLLAMA_WEB_BASE_URL"
DEFAULT_BASE_URL = "https://ollama.com"

#: Ollama caps ``max_results`` at 10 server-side.
SEARCH_LIMIT_CAP = 10
SEARCH_TIMEOUT_S = 30.0
FETCH_TIMEOUT_S = 60.0

#: Ollama's ``web_search`` returns FULL page content per result (~10k chars each), not a
#: snippet like index-backed vendors. ``web_search`` has no Hermes-side char budget (only
#: ``web_extract`` does), so an unbudgeted limit=5 search would push ~50k chars into context.
#: Snippets are trimmed on a word boundary; use ``web_extract`` to get a page in full.
#: Override with ``OLLAMA_SEARCH_SNIPPET_CHARS`` (0 disables trimming).
SNIPPET_CHARS_ENV = "OLLAMA_SEARCH_SNIPPET_CHARS"
DEFAULT_SNIPPET_CHARS = 1200


def _env(name: str, default: str = "") -> str:
    """Config-aware env lookup: ``os.environ`` first, then ``~/.hermes/.env``.

    Uses the ABC's helper when present so credentials written through the Hermes config
    layer are visible in gateway/cron/delegate subprocesses, and degrades to ``os.getenv``
    on stripped installs.
    """
    try:
        from agent.web_search_provider import get_provider_env

        value = get_provider_env(name)
    except Exception:  # noqa: BLE001 — config layer is optional here
        value = ""
    return (value or os.getenv(name, "") or default).strip()


def _base_url() -> str:
    return _env(BASE_URL_ENV, DEFAULT_BASE_URL).rstrip("/")


def _snippet_budget() -> int:
    """Per-result content budget for ``search()``; ``0`` means "return it whole"."""
    raw = _env(SNIPPET_CHARS_ENV)
    if not raw:
        return DEFAULT_SNIPPET_CHARS
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("%s=%r is not an integer; using %d", SNIPPET_CHARS_ENV, raw, DEFAULT_SNIPPET_CHARS)
        return DEFAULT_SNIPPET_CHARS


def _snippet(content: str, budget: int) -> str:
    """Trim *content* to *budget* chars on a word boundary, marking the cut."""
    if budget <= 0 or len(content) <= budget:
        return content
    cut = content[:budget]
    space = cut.rfind(" ")
    if space > budget // 2:  # only honour the boundary when it isn't a pathological cut
        cut = cut[:space]
    return f"{cut.rstrip()}… [truncated — use web_extract for the full page]"


def _title_from_url(url: str) -> str:
    """Readable label for a result Ollama returned with no title (host + last path segment)."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = parsed.netloc
    tail = (parsed.path or "").rstrip("/").rsplit("/", 1)[-1]
    if host and tail:
        return f"{host} — {tail}"
    return host or url


def _post(path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST JSON to the Ollama web API. Raises ``ValueError`` with a readable message."""
    import httpx

    api_key = _env(KEY_ENV)
    if not api_key:
        raise ValueError(f"{KEY_ENV} is not set (get a free key at https://ollama.com/settings/keys)")
    try:
        resp = httpx.post(
            f"{_base_url()}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "")[:300]
        raise ValueError(f"Ollama web API HTTP {exc.response.status_code}: {body}") from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"Ollama web API request failed: {exc}") from exc
    except ValueError as exc:  # non-JSON body
        raise ValueError(f"Ollama web API returned a non-JSON response: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Ollama web API returned an unexpected payload shape")
    return data


class OllamaWebSearchProvider(WebSearchProvider):
    """Search + extract backed by Ollama's hosted ``web_search`` / ``web_fetch`` APIs."""

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return DISPLAY_NAME

    def is_available(self) -> bool:
        """Cheap, no-network gate — runs on every ``hermes tools`` paint."""
        return bool(_env(KEY_ENV))

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    # --- capabilities ----------------------------------------------------
    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        try:
            max_results = max(1, min(int(limit), SEARCH_LIMIT_CAP))
        except (TypeError, ValueError):
            max_results = 5
        try:
            data = _post("/api/web_search", {"query": query, "max_results": max_results}, SEARCH_TIMEOUT_S)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        rows = data.get("results") or []
        budget = _snippet_budget()
        web = []
        for index, item in enumerate((row for row in rows[:max_results] if isinstance(row, dict)), start=1):
            url = str(item.get("url") or "")
            # Ollama sometimes returns an empty title (e.g. raw .md URLs). An empty title
            # reads as a broken result to the model, so fall back to the URL's own label.
            title = str(item.get("title") or "").strip() or _title_from_url(url)
            web.append(
                {
                    "title": title,
                    "url": url,
                    "description": _snippet(str(item.get("content") or ""), budget),
                    "position": index,
                }
            )
        logger.info(
            "Ollama web_search %r: %d result(s) (limit=%d, snippet_budget=%d)",
            query,
            len(web),
            max_results,
            budget,
        )
        return {"success": True, "data": {"web": web}}

    def extract(self, urls: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch each URL via ``/api/web_fetch``. Per-URL failures come back as ``error`` entries."""
        del kwargs  # ``format`` / ``include_raw`` / ``max_chars`` are not supported upstream
        results: list[dict[str, Any]] = []
        for url in urls:
            try:
                data = _post("/api/web_fetch", {"url": url}, FETCH_TIMEOUT_S)
            except ValueError as exc:
                results.append({"url": url, "title": "", "content": "", "error": str(exc)})
                continue
            content = str(data.get("content") or "")
            title = str(data.get("title") or "")
            links = [str(link) for link in (data.get("links") or []) if isinstance(link, str)]
            results.append(
                {
                    "url": url,
                    "title": title,
                    "content": content,
                    "raw_content": content,
                    "metadata": {"sourceURL": url, "title": title, "links": links},
                }
            )
        logger.info(
            "Ollama web_fetch: %d URL(s), %d failed", len(results), sum(1 for r in results if r.get("error"))
        )
        return results

    # --- `hermes tools` picker row ---------------------------------------
    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": DISPLAY_NAME,
            "badge": "free",
            "tag": "Search + fetch via Ollama's hosted web API. Free account required.",
            "env_vars": [
                {
                    "key": KEY_ENV,
                    "prompt": "Ollama API key",
                    "url": "https://ollama.com/settings/keys",
                }
            ],
        }
