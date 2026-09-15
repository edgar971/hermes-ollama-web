## What changed

<!-- One or two sentences. Why, not just what. -->

## How I verified it

<!-- Real commands and real output. "Should work" isn't verification. -->

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run ty check`
- [ ] `uv run pytest`
- [ ] Exercised against a real Hermes install (say so if you didn't — that's fine, just be explicit)

## What I did NOT verify

<!-- Be honest here. It's more useful than a clean-looking checklist. -->

## Notes

- [ ] If the Hermes ABC surface changed, `tests/stubs/agent/web_search_provider.py` is updated to match
- [ ] New behaviour has a test that fails without the change
- [ ] No secrets, API keys, or private vault/item names in the diff
