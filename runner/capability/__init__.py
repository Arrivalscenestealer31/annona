"""L1 — capabilities: the things an agent can actually do.

Two families live here:

- ``backends/`` — inference adapters, one per provider or local runtime.
- ``tooling`` — adapters that put the existing tool registry and permission
  manager behind the L0 ports.

Everything in this layer implements a port declared in
:mod:`runner.kernel.ports` and is injected by the composition root. Nothing here
imports :mod:`runner.agent`; the loop and the capabilities do not know about each
other, and ``.importlinter`` keeps it that way.

The tools themselves still live in :mod:`runner.tools` and are scheduled to move
under this package during the layout migration — see
``docs/adr/0002-unify-the-agentic-loop.md``.
"""
