"""Make ``agent.web_search_provider`` importable so the provider's ABC resolves.

The provider subclasses a Hermes ABC, but a Hermes checkout shouldn't be required to run
unit tests. Resolution order:

1. **Real Hermes** at ``$HERMES_REPO`` (default ``~/.hermes/hermes-agent``) when it imports
   cleanly — the contract is then verified against actual Hermes code.
2. **``tests/stubs/``** otherwise (CI, contributors without Hermes installed).

The stub is a real package on disk rather than a synthesised ``ModuleType``, so static
analysis (``ty``) resolves it the same way the interpreter does.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_STUBS_DIR = Path(__file__).parent / "stubs"


def _hermes_repo() -> Path | None:
    """Path to a Hermes checkout containing the real ABC, or ``None``."""
    candidates = (
        os.environ.get("HERMES_REPO", ""),
        str(Path.home() / ".hermes" / "hermes-agent"),
    )
    for candidate in candidates:
        if candidate and (Path(candidate) / "agent" / "web_search_provider.py").is_file():
            return Path(candidate)
    return None


def _drop_agent_modules() -> None:
    """Forget a partially imported ``agent`` package so the stub import starts clean."""
    for name in [m for m in sys.modules if m == "agent" or m.startswith("agent.")]:
        del sys.modules[name]


def _install_abc_source() -> str:
    """Put the real ABC (preferred) or the stub on ``sys.path``; return which was used."""
    repo = _hermes_repo()
    if repo is not None:
        sys.path.insert(0, str(repo))
        try:
            import agent.web_search_provider  # noqa: F401  (the import IS the probe)

            return f"hermes:{repo}"
        except Exception:  # heavy optional Hermes deps missing — fall back to the stub
            sys.path.remove(str(repo))
            _drop_agent_modules()
    sys.path.insert(0, str(_STUBS_DIR))
    return f"stub:{_STUBS_DIR}"


#: Which ABC the suite is running against — surfaced by ``test_abc_source_is_reported``.
ABC_SOURCE = _install_abc_source()
