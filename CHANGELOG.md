# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `ty` type checking, wheel-content verification in CI, PyPI Trusted Publishing release
  workflow, contributor and issue/PR templates.

### Changed

- `tests/conftest.py` now resolves the Hermes ABC by putting a real stub **package**
  (`tests/stubs/agent/`) on `sys.path` instead of synthesising a `ModuleType` at runtime, so
  static analysis can resolve it.
- Dropped the unused `pytest-asyncio` dev dependency.

## [0.1.0] - 2026-09-15

### Added

- `OllamaWebSearchProvider`: backs Hermes' built-in `web_search` and `web_extract` tools with
  Ollama's hosted `/api/web_search` and `/api/web_fetch` endpoints.
- Dual install: pip/uv entry point (`hermes_agent.plugins`) or directory plugin.
- `OLLAMA_WEB_BASE_URL` override for proxies and self-hosted gateways.
- `hermes tools` picker row via `get_setup_schema()`.

### Fixed

- **Search results are budgeted.** Ollama returns full page content per result (~10k chars
  each) and Hermes applies its char budget to `web_extract` only, so a `limit=5` search pushed
  ~50k chars into context. Results are now trimmed to `OLLAMA_SEARCH_SNIPPET_CHARS`
  (default 1200) on a word boundary — measured 7.5k chars for the same live query.
- Empty titles (returned for raw `.md` URLs) fall back to a `host — path-tail` label instead of
  rendering blank to the model.

[Unreleased]: https://github.com/edgar971/hermes-ollama-web/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/edgar971/hermes-ollama-web/releases/tag/v0.1.0
