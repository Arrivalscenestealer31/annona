"""L1 — inference adapters.

Each module here implements :class:`runner.kernel.ports.InferenceBackend` for one
provider or runtime: translate a request out, translate an answer back, hold no
state, decide nothing.

Provider SDKs are imported *only* in this package. ``.importlinter`` enforces
that, which is what turns "the loop is provider-agnostic" into a checked fact.

Shipped in Phase 0:

============  =========  ====================================================
Backend       Local      Notes
============  =========  ====================================================
``echo``      yes        Scripted, offline. Tests and ``make demo``.
``ollama``    **yes**    A real local model, native tool calling (tier 1).
``anthropic`` no         Messages API with native tool use.
``akaion``    no         Control-plane proxy. Sends the whole transcript.
============  =========  ====================================================

``ollama`` is the first backend where ``is_local`` is ``True`` *and* a model is
doing the work. Phase 2 continues with ``llamacpp`` and ``vllm``, which add
grammar-constrained decoding (tier 2).
"""

from runner.capability.backends.akaion import AkaionBackend
from runner.capability.backends.anthropic import AnthropicBackend
from runner.capability.backends.echo import EchoBackend, script_from_config
from runner.capability.backends.ollama import OllamaBackend

__all__ = [
    "AkaionBackend",
    "AnthropicBackend",
    "EchoBackend",
    "OllamaBackend",
    "script_from_config",
]
