"""L2 — placement: where a step is allowed to run, and what crosses.

- :mod:`runner.placement.registry` — substrates and their observed health
- :mod:`runner.placement.engine` — the placement decision itself
- :mod:`runner.placement.router` — the backend decorator that enforces it
"""

from runner.placement.engine import PlacementDecisionEngine
from runner.placement.registry import Health, SubstrateRegistry, http_prober
from runner.placement.router import RoutingBackend

__all__ = [
    "Health",
    "PlacementDecisionEngine",
    "RoutingBackend",
    "SubstrateRegistry",
    "http_prober",
]
