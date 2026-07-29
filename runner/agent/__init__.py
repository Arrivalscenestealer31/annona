"""L3 — orchestration: the agentic loop and the prompt that drives it.

This layer decides *what happens next*: whether to run tools, whether to
continue, when to stop. It depends only on the ports in
:mod:`runner.kernel.ports`, so it can be pointed at a remote provider, a local
runtime, or a scripted test double without knowing which.

It imports no provider SDK and no adapter. Both are enforced in CI — see
``.importlinter``.
"""

from runner.agent.loop import DEFAULT_MAX_ITERATIONS, AgentLoop, run_agent
from runner.agent.prompt import build_system_prompt

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "AgentLoop",
    "build_system_prompt",
    "run_agent",
]
