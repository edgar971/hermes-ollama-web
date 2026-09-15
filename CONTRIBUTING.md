# Contributing

Thanks for helping out. This is a small, single-purpose package: an Ollama backend for
Hermes' `web_search` / `web_extract` tools. Changes that keep it small are the good kind.

## Setup

```bash
git clone https://github.com/edgar971/hermes-ollama-web
cd hermes-ollama-web
uv sync --all-groups
```

You do **not** need Hermes installed to develop or test — see [The ABC](#the-abc-and-why-tests-work-without-hermes).

## The three gates

CI runs exactly these. Run them before pushing:

```bash
uv run ruff check .          # lint
uv run ruff format .         # format (CI uses --check --diff)
uv run ty check              # types
uv run pytest                # tests
```

## The ABC, and why tests work without Hermes

The provider subclasses `agent.web_search_provider.WebSearchProvider`, which lives in the
Hermes *application*, not in a pip package — so it can't be a dependency. `tests/conftest.py`
resolves it in two steps:

1. The real ABC from `$HERMES_REPO` (default `~/.hermes/hermes-agent`) when importable.
   Contributors with Hermes installed test against real Hermes code.
2. Otherwise `tests/stubs/agent/web_search_provider.py`, a hand-maintained mirror. CI uses this.

`ty` is pointed at the stub via `[tool.ty.environment] extra-paths`.

**If you touch the ABC surface, update the stub.** A stub that drifts from Hermes means green
tests and a broken plugin — the failure mode this layout is most exposed to.

## Testing rules

- **No network in tests.** Mock the Ollama API with `respx`. A test that needs a real API key
  won't run in CI and won't be accepted.
- Test the **envelope**, not the internals. The contract with Hermes is the exact response
  shape (see the response-shape section in the [provider plugin docs][abc-docs]); assert on it.
- Every bug fix gets a test that fails before the fix. If a test can't fail, it isn't a guard.

## Verifying against a real Hermes

Unit tests prove the mapping; they don't prove Hermes routes to you. To check end to end:

```bash
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python -e .
hermes plugins enable web-ollama
hermes config set web.backend ollama
hermes chat -q 'Use web_search to find the Ollama web search docs.'
```

When testing routing, disable `web.keyless_fallback` and `web.keyless_rescue` first —
otherwise a failure in this provider is silently served by Hermes' keyless ring and looks
like success.

## Style

- `ruff format` decides formatting. Don't hand-align anything.
- **Comment the non-obvious, not the obvious.** Explain *why* a constraint exists (a vendor
  cap, a Hermes contract, a bug worked around); don't narrate what the code plainly does.
- Type annotations on public functions. `from __future__ import annotations` is already on.
- Keep `is_available()` cheap and network-free — Hermes calls it on every `hermes tools` paint.

## Commits & PRs

- One concern per commit; [Conventional Commits](https://www.conventionalcommits.org/) subjects
  (`feat:`, `fix:`, `docs:`, `ci:`, `test:`, `chore:`).
- Explain *why* in the body when the change isn't self-evident.
- PRs: say what you changed, how you verified it, and what you did **not** verify.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Releasing (maintainers)

1. Bump `version` in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Tag `vX.Y.Z` and push it.

`release.yml` re-runs every gate, asserts the tag matches `project.version`, and publishes via
PyPI Trusted Publishing (no stored token). A tag that disagrees with `pyproject.toml` fails
before upload.

[abc-docs]: https://hermes-agent.nousresearch.com/docs/developer-guide/web-search-provider-plugin
