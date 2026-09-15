"""Minimal stand-in for Hermes' ``agent`` package.

Only exists so the test suite (and ``ty``) can resolve ``agent.web_search_provider``
without a full Hermes install. ``tests/conftest.py`` puts this directory on
``sys.path`` **only** when the real Hermes repo isn't importable.
"""
