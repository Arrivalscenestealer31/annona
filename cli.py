#!/usr/bin/env python3
"""Frozen-bundle entry point.

PyInstaller builds from this file (see ``runner.spec``), so it has to exist at the
repository root. The CLI itself lives in :mod:`runner.cli` — the same module the
``akaion`` console script installs.

Until Phase 0 this file held a *second copy* of the CLI, 972 lines of it, and the
two had drifted: the copy installed by ``pip`` was missing the ``note``, ``sync``
and ``cloud`` commands the README documents, and six shared commands had different
options and different service-URL resolution. Users got a different program
depending on whether they installed the wheel or the ``.dmg``. There is now one
CLI, and this shim.
"""

from runner.cli import app

__all__ = ["app"]

if __name__ == "__main__":
    app()
