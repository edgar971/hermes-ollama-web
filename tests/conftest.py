"""Test bootstrap: make ``agent.web_search_provider`` importable without a Hermes checkout.

The provider subclasses a Hermes ABC. In CI (and on machines where Hermes lives elsewhere)
we don't want a full Hermes install just to unit-test HTTP mapping, so:

1. If ``HERMES_REPO`` (or the default install path) has the real module, use it — the
   contract is then verified against real Hermes code.
2. Otherwise register a minimal stand-in with the same surface.
"""

from __future__ import annotations

import abc
import os
import sys
import types
from pathlib import Path


def _real_hermes_repo() -> Path | None:
    candidates = [os.environ.get("HERMES_REPO", ""), str(Path.home() / ".hermes" / "hermes-agent")]
    for candidate in candidates:
        if candidate and (Path(candidate) / "agent" / "web_search_provider.py").exists():
            return Path(candidate)
    return None


def _install_stub() -> None:
    agent_pkg = sys.modules.get("agent")
    if agent_pkg is None:
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = []  # namespace-ish
        sys.modules["agent"] = agent_pkg

    module = types.ModuleType("agent.web_search_provider")

    def get_provider_env(name: str) -> str:
        return (os.getenv(name, "") or "").strip()

    class WebSearchProvider(abc.ABC):
        @property
        @abc.abstractmethod
        def name(self) -> str: ...

        @property
        def display_name(self) -> str:
            return self.name

        @abc.abstractmethod
        def is_available(self) -> bool: ...

        def supports_search(self) -> bool:
            return True

        def supports_extract(self) -> bool:
            return False

        def is_keyless_available(self) -> bool:
            return False

        def get_setup_schema(self) -> dict:
            return {"name": self.display_name, "badge": "", "tag": "", "env_vars": []}

    module.get_provider_env = get_provider_env
    module.WebSearchProvider = WebSearchProvider
    sys.modules["agent.web_search_provider"] = module
    agent_pkg.web_search_provider = module


repo = _real_hermes_repo()
if repo is not None:
    sys.path.insert(0, str(repo))
    try:
        import agent.web_search_provider  # noqa: F401
    except Exception:  # noqa: BLE001 — heavy optional deps missing; fall back
        sys.path.remove(str(repo))
        for stale in [m for m in sys.modules if m == "agent" or m.startswith("agent.")]:
            del sys.modules[stale]
        _install_stub()
else:
    _install_stub()
