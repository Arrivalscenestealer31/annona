"""L1 — redactors: adapters that find identifiers and replace them.

The perimeter decides *whether* a redacted payload may cross. These decide
*what* an identifier is, which is a model's job rather than a policy's.

Shipped: :class:`~runner.capability.redactors.rizzo_pii.RizzoPiiRedactor`, an
adapter for `rizzo-pii <https://github.com/Rizzo-AI-Academy/rizzo-pii>`_ — MIT,
0.3B, CPU-only, 22 Italian categories including codice fiscale, partita IVA and
cadastral identifiers.
"""

from runner.capability.redactors.rizzo_pii import DEFAULT_LABEL_CLASSES, RizzoPiiRedactor

__all__ = ["DEFAULT_LABEL_CLASSES", "RizzoPiiRedactor"]
