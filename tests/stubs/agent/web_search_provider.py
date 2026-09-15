"""Stub mirroring the parts of Hermes' ``WebSearchProvider`` ABC this plugin uses.

Kept deliberately small: it declares only the members the provider overrides or calls.
The real contract lives in Hermes at ``agent/web_search_provider.py``; when that repo is
importable, ``tests/conftest.py`` prefers it so the suite tests against real code and this
file is never imported.
"""

from __future__ import annotations

import abc
import os
from typing import Any


def get_provider_env(name: str) -> str:
    """Stub of Hermes' config-aware env lookup (real one also reads ``~/.hermes/.env``)."""
    return (os.getenv(name, "") or "").strip()


class WebSearchProvider(abc.ABC):
    """Abstract web search/extract backend."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable id used in ``web.*_backend`` config."""

    @property
    def display_name(self) -> str:
        return self.name

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Cheap, no-network availability gate."""

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def is_keyless_available(self) -> bool:
        return False

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        raise NotImplementedError

    def extract(self, urls: list[str], **kwargs: Any) -> Any:
        raise NotImplementedError

    def get_setup_schema(self) -> dict[str, Any]:
        return {"name": self.display_name, "badge": "", "tag": "", "env_vars": []}
