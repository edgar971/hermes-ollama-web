"""Fail the release when the git tag and ``project.version`` disagree.

A mismatched tag publishes a wheel whose version nobody can correlate to a commit, and PyPI
will not let you re-upload the same version to fix it. Run before ``uv build``.

Usage: ``python scripts/check_version_matches_tag.py v0.1.0``
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # tomllib landed in 3.11; the package floor is 3.10
    import tomli as tomllib

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def project_version() -> str:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <tag>", file=sys.stderr)
        return 2
    tag = argv[1].removeprefix("refs/tags/").removeprefix("v")
    version = project_version()
    if tag != version:
        print(
            f"tag {argv[1]!r} does not match project.version {version!r} — bump pyproject.toml or retag",
            file=sys.stderr,
        )
        return 1
    print(f"tag matches project.version ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
