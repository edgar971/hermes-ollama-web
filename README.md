# hermes-ollama-web

[![CI](https://github.com/edgar971/hermes-ollama-web/actions/workflows/ci.yml/badge.svg)](https://github.com/edgar971/hermes-ollama-web/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Checked with ty](https://img.shields.io/badge/types-ty-261230)](https://docs.astral.sh/ty/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Ollama **Web Search** and **Web Fetch** as a native Hermes Agent backend.

It implements the `WebSearchProvider` ABC, so it backs the **built-in `web_search` and
`web_extract` tools** — no extra model-facing tools, no MCP hop, no prompt bloat. Every
Hermes feature that sits on top of the web tools (result caching, character budgeting,
`security.website_blocklist`, SSRF guards, keyless rescue, subagent coalescing) keeps
working unchanged.

| Hermes tool | Ollama endpoint |
| --- | --- |
| `web_search` | `POST https://ollama.com/api/web_search` |
| `web_extract` | `POST https://ollama.com/api/web_fetch` (one call per URL) |

Docs: <https://docs.ollama.com/capabilities/web-search>

## Requirements

- Hermes Agent (any version with web-search provider plugins)
- A free Ollama account + API key: <https://ollama.com/settings/keys>
- `uv` (dev + install), `ruff` (lint), `pytest` (tests)

## Install

### Option A — pip/uv install (recommended, shareable)

Discovered through the `hermes_agent.plugins` entry point, so there is nothing to symlink.
Install it **into the Hermes venv**:

```bash
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python \
  git+https://github.com/edgar971/hermes-ollama-web
hermes plugins enable web-ollama
```

From a local checkout:

```bash
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python -e ~/dev/hermes-ollama-web
hermes plugins enable web-ollama
```

> Entry-point plugins are opt-in (only *bundled* backends auto-load), so the `enable` step is
> required. Verify the venv path with `cat $(which hermes)` — installer layouts use `venv/`,
> some git checkouts use `.venv/`.

### Option B — directory plugin (local hacking)

```bash
mkdir -p "${HERMES_HOME:-$HOME/.hermes}/plugins/web"
ln -sfn ~/dev/hermes-ollama-web/src/hermes_ollama_web \
        "${HERMES_HOME:-$HOME/.hermes}/plugins/web/ollama"
hermes plugins enable web/ollama
```

## Configure

Key goes in `.env` (secrets only); backend selection goes in `config.yaml` via `hermes config set`
— never hand-edit `config.yaml`.

```bash
# ~/.hermes/.env
OLLAMA_API_KEY=<your key>
```

```bash
# use Ollama for both capabilities
hermes config set web.backend ollama

# or per-capability, e.g. Ollama search + Firecrawl extract
hermes config set web.search_backend ollama
hermes config set web.extract_backend firecrawl
```

`hermes tools` → **Web Search & Extract** also lists it (“Ollama Web Search”) and prompts for the key.

Optional knobs:

- `OLLAMA_WEB_BASE_URL` — proxy/gateway base (default `https://ollama.com`)
- `OLLAMA_SEARCH_SNIPPET_CHARS` — per-result search snippet budget (default `1200`, `0` = no trimming)

### 1Password instead of plaintext (optional)

Hermes can resolve the key from 1Password at startup, so it never sits in `.env`:

```bash
hermes secrets onepassword set OLLAMA_API_KEY "op://<Vault>/<Item>/credential"
hermes secrets onepassword sync     # dry-run
```

## Verify

```bash
hermes plugins list | grep -i ollama                       # → web-ollama  enabled
source ~/.hermes/hermes-agent/venv/bin/activate && python -m tools.web_tools   # prints active backend
hermes chat -q 'Use web_search to find the Ollama web search docs, then web_extract that URL.'
```

`hermes setup` shows `✅ Web Search & Extract (ollama)` once selected.

## Behaviour notes

- `max_results` is clamped to **10** (Ollama's server-side cap). Verified server-side honoured:
  `limit=2` → 2 results, `limit=7` → 7. (The official JS SDK sent camelCase `maxResults`, which
  the API silently ignored — [ollama-js#283][js283]. This plugin sends snake_case.)
- **There is an hourly rate limit on the free tier, and hitting it is abrupt.** Measured: 8
  searches succeeded at ~0.9 s each, then every following call returned
  `HTTP 429 "you have reached your web search hourly request limit"` in ~0.2 s. The fast failure
  is the tell — a 429 comes back quicker than a real search. Budget accordingly for agent loops,
  which can burn a dozen searches in one task, and consider keeping a second backend configured
  for `web_search` so a 429 doesn't stall the run.
- **Search results carry full page content, not snippets.** Measured live: ~10k chars *per result*,
  so an untrimmed `limit=5` search is ~50k chars (~13k tokens) of context. Hermes applies its char
  budget to `web_extract` only, never to `web_search`, so this provider trims each result to
  `OLLAMA_SEARCH_SNIPPET_CHARS` (default 1200) on a word boundary and marks the cut. Same query at
  `limit=5`: **~7.4k chars instead of ~50k**. Use `web_extract` when you want a page in full.
- Ollama sometimes returns `title: ""` (seen on raw `.md` URLs); the provider substitutes a
  `host — last-path-segment` label so results never render as blank to the model.
- `web_fetch` takes a single URL, so `web_extract` on N URLs issues N sequential requests;
  a failure on one URL becomes a per-URL `error` entry and never fails the batch.
- Search timeout 30 s, fetch timeout 60 s per URL. Hermes additionally bounds the whole
  extract dispatch with `web.extract_timeout`.
- `format` / `include_raw` / `max_chars` extract kwargs are ignored — Ollama returns markdown-ish
  content only. Truncation and the on-disk full-text spill are handled by Hermes.
- Ollama returns discovered `links` for a fetched page; they are preserved in `metadata.links`.
- Transient `HTTP 502 {"error": "search service error"}` happens; retry before debugging.

### Result quality

Probed across 8 consumer/technical categories (cars, lawn care, cooking, home repair, health,
finance) at `limit=5`: **mean 0.89 s, 4.5/5 unique hosts, zero duplicate or mirrored URLs, zero
blank titles.** Top hits skewed authoritative — `irs.gov` for tax limits, Clemson HGIC and
university extension services for turf, Consumer Reports for vehicles, Springer and Stronger by
Science for sports nutrition.

Technical/docs queries are where it gets noisier: it does content-matching, so it will happily
return both a docs page and that same page's raw `.md` mirror as separate results. If you mainly
search docs, pair a ranked index for search with Ollama for fetch:

```bash
hermes config set web.search_backend brave-free
hermes config set web.extract_backend ollama
```

[js283]: https://github.com/ollama/ollama-js/issues/283

## Development

```bash
uv sync --all-groups
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ty check          # types
uv run pytest            # tests
```

Tests use `respx` to mock the Ollama HTTP API — no network, no key needed. `tests/conftest.py`
imports the **real** `agent.web_search_provider` ABC from `$HERMES_REPO` (default
`~/.hermes/hermes-agent`) when available so the contract is checked against actual Hermes code,
and falls back to `tests/stubs/` in CI.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, and [SECURITY.md](SECURITY.md)
for how the API key is handled.

## Why a provider plugin instead of an MCP server or custom tools

Ollama ships an MCP server example, and you *could* register `ollama_web_search` /
`ollama_web_fetch` as new tools. Both are worse here:

- **MCP** adds a subprocess, a second tool surface, and duplicate tool descriptions the model
  must disambiguate from `web_search`.
- **Custom tools** bypass Hermes' web pipeline: no result cache, no char budget, no blocklist,
  no `hermes tools` integration.

A `WebSearchProvider` swaps only the transport underneath the tools the agent already knows.

## License

MIT
