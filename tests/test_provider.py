"""Contract tests: Ollama HTTP payloads -> the Hermes web-provider response envelope."""

from __future__ import annotations

import httpx
import pytest
import respx

from conftest import ABC_SOURCE
from hermes_ollama_web import OllamaWebSearchProvider, register

SEARCH_URL = "https://ollama.com/api/web_search"
FETCH_URL = "https://ollama.com/api/web_fetch"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.delenv("OLLAMA_WEB_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_SEARCH_SNIPPET_CHARS", raising=False)
    return OllamaWebSearchProvider()


def test_identity_and_capabilities(provider):
    assert provider.name == "ollama"
    assert provider.display_name == "Ollama Web Search"
    assert provider.supports_search() is True
    assert provider.supports_extract() is True
    assert provider.is_available() is True


def test_provider_satisfies_the_abc_contract(provider):
    """Instantiating at all proves every abstract member is implemented.

    Locally this runs against the REAL Hermes ABC (see conftest); CI uses the stub.
    """
    from agent.web_search_provider import WebSearchProvider

    assert isinstance(provider, WebSearchProvider)
    assert ABC_SOURCE.startswith(("hermes:", "stub:"))


def test_is_available_false_without_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert OllamaWebSearchProvider().is_available() is False


def test_register_wires_into_ctx():
    registered = []

    class Ctx:
        def register_web_search_provider(self, instance):
            registered.append(instance)

    register(Ctx())
    assert len(registered) == 1
    assert registered[0].name == "ollama"


@respx.mock
def test_search_maps_to_envelope(provider):
    route = respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Ollama", "url": "https://ollama.com/", "content": "Cloud models..."},
                    {"title": "Guide", "url": "https://example.com/g", "content": "How to..."},
                ]
            },
        )
    )
    result = provider.search("what is ollama?", limit=2)

    assert route.called
    request_body = route.calls[0].request
    assert request_body.headers["authorization"] == "Bearer test-key"
    assert result == {
        "success": True,
        "data": {
            "web": [
                {
                    "title": "Ollama",
                    "url": "https://ollama.com/",
                    "description": "Cloud models...",
                    "position": 1,
                },
                {
                    "title": "Guide",
                    "url": "https://example.com/g",
                    "description": "How to...",
                    "position": 2,
                },
            ]
        },
    }


@respx.mock
def test_search_clamps_limit_to_server_cap(provider):
    route = respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))
    provider.search("q", limit=50)
    import json

    assert json.loads(route.calls[0].request.content)["max_results"] == 10


@respx.mock
def test_search_http_error_returns_failure_envelope(provider):
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(401, text="unauthorized"))
    result = provider.search("q")
    assert result["success"] is False
    assert "401" in result["error"]


def test_search_without_key_returns_failure_envelope(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    result = OllamaWebSearchProvider().search("q")
    assert result["success"] is False
    assert "OLLAMA_API_KEY" in result["error"]


@respx.mock
def test_extract_maps_documents(provider):
    respx.post(FETCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "Ollama",
                "content": "# Ollama\nhello",
                "links": ["https://ollama.com/models"],
            },
        )
    )
    docs = provider.extract(["https://ollama.com"], format="markdown")

    assert len(docs) == 1
    doc = docs[0]
    assert doc["url"] == "https://ollama.com"
    assert doc["title"] == "Ollama"
    assert doc["content"] == "# Ollama\nhello"
    assert doc["raw_content"] == doc["content"]
    assert doc["metadata"]["sourceURL"] == "https://ollama.com"
    assert doc["metadata"]["links"] == ["https://ollama.com/models"]
    assert "error" not in doc


@respx.mock
def test_extract_per_url_failure_is_isolated(provider):
    respx.post(FETCH_URL).mock(
        side_effect=[
            httpx.Response(200, json={"title": "OK", "content": "body"}),
            httpx.Response(500, text="boom"),
        ]
    )
    docs = provider.extract(["https://a.example", "https://b.example"])

    assert docs[0]["content"] == "body"
    assert "error" not in docs[0]
    assert docs[1]["error"]
    assert docs[1]["content"] == ""


@respx.mock
def test_base_url_override(monkeypatch, provider):
    monkeypatch.setenv("OLLAMA_WEB_BASE_URL", "http://localhost:11500/")
    route = respx.post("http://localhost:11500/api/web_search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    provider.search("q")
    assert route.called


@respx.mock
def test_search_trims_long_content_to_snippet_budget(provider):
    """Ollama returns full page content per result; unbudgeted that floods context."""
    body = "word " * 4000  # 20k chars
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json={"results": [{"title": "T", "url": "https://e.example", "content": body}]}
        )
    )
    hit = provider.search("q", limit=1)["data"]["web"][0]

    assert len(hit["description"]) < 1400
    assert hit["description"].endswith("[truncated — use web_extract for the full page]")


@respx.mock
def test_snippet_budget_env_override_disables_trimming(monkeypatch, provider):
    monkeypatch.setenv("OLLAMA_SEARCH_SNIPPET_CHARS", "0")
    body = "word " * 4000
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json={"results": [{"title": "T", "url": "https://e.example", "content": body}]}
        )
    )
    assert provider.search("q", limit=1)["data"]["web"][0]["description"] == body


@respx.mock
def test_short_content_is_not_trimmed(provider):
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json={"results": [{"title": "T", "url": "https://e.example", "content": "short"}]}
        )
    )
    assert provider.search("q", limit=1)["data"]["web"][0]["description"] == "short"


@respx.mock
def test_empty_title_falls_back_to_url_label(provider):
    """Observed live: raw .md URLs come back with title="" — an empty title looks broken."""
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "", "url": "https://docs.ollama.com/capabilities/web-search.md", "content": "c"}
                ]
            },
        )
    )
    assert provider.search("q", limit=1)["data"]["web"][0]["title"] == ("docs.ollama.com — web-search.md")


def test_setup_schema_shape(provider):
    schema = provider.get_setup_schema()
    assert schema["name"] == "Ollama Web Search"
    assert [entry["key"] for entry in schema["env_vars"]] == ["OLLAMA_API_KEY"]
