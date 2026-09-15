"""Hermes plugin entry point — registers the Ollama web search/fetch backend.

Works in both install modes:

* **Directory plugin** — this package directory is linked to
  ``$HERMES_HOME/plugins/web/ollama``; Hermes imports ``__init__.py`` by path.
* **Pip plugin** — installed as ``hermes-ollama-web``, discovered through the
  ``hermes_agent.plugins`` entry point (see ``pyproject.toml``).

The relative import below is what makes one source tree serve both.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["OllamaWebSearchProvider", "register"]

from .provider import OllamaWebSearchProvider


def register(ctx) -> None:
    """Called once at plugin load time."""
    ctx.register_web_search_provider(OllamaWebSearchProvider())
