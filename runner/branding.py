"""Project identity, in one place.

The open-source project is called **Annona**, after the *cura annonae* — the
office that kept Rome fed. It decided where grain was sourced, which route it
took, which granary held it and who received it, and it kept the record. It
existed for one reason: a republic cannot outsource what it cannot live without.

Compute is now that input, so this is the product. Every step is sourced, routed,
executed and recorded under an authority the customer owns — and the decision the
architecture turns on is the same one the prefect faced: *does the cargo travel,
or is it handled here?*

===============  ============================================================
Term             What it names
===============  ============================================================
**placement**    where a step runs: local GPU, private cluster, frontier API
**declaration**  what a step states it is about to do and send
**clearance**    the decision on a tool call, an egress, or a placement
**held**         a call, or a placement, the policy refused
**manifest**     what a step is permitted to carry across
**ledger**       the ordered, hash-chained record of every decision
**green lane**   a path pre-cleared as low-sensitivity, no inspection needed
**prefect**      the component that issues clearances — *praefectus annonae*
**horreum**      the local store: vault and ledger, on the customer's disk
**ration**       a user's or an org's quota of remote capacity
**brief**        the locally produced, cleared summary that may cross in place
                 of the raw material
===============  ============================================================

Keeping the strings here rather than scattering them means renaming the project
is one edit, and means the CLI, the UI and the docs cannot drift apart on what
this thing is called. That design paid for itself twice, in ADR 0005.

The Python package stays :mod:`runner`; ``annona`` is the primary command, with
``dogana`` and ``akaion`` kept as aliases. See
``docs/adr/0005-name-the-project-annona.md``.
"""

from __future__ import annotations

__all__ = [
    "CATEGORY",
    "DESCRIPTION",
    "DOCS_URL",
    "LICENSE",
    "NAME",
    "ORIGIN",
    "PRONUNCIATION",
    "REPO_URL",
    "TAGLINE",
    "VENDOR",
    "banner_subtitle",
]

NAME = "Annona"
"""The project name. Rome's grain administration: sourcing, routing, record."""

PRONUNCIATION = "an-NO-na"

TAGLINE = "Where it runs is a decision."

CATEGORY = "sovereign execution kernel"

DESCRIPTION = (
    "The sovereign execution kernel for AI agents. Annona decides where each "
    "step runs — your GPU, your cluster, or a frontier API — enforces the "
    "decision, and records it."
)

ORIGIN = (
    "Rome ran its own grain supply because a republic cannot outsource what it "
    "cannot live without."
)

VENDOR = "Akaion AI Lab"

REPO_URL = "https://github.com/akaion-ai/annona"
DOCS_URL = "https://akaion-ai.github.io/annona/"

LICENSE = "Apache-2.0"


def banner_subtitle(local_only: bool = True) -> str:
    """One line for the CLI banner, honest about the current mode.

    Sovereignty is only meaningful if you can see which side of the line you are
    on, so the banner says it every time rather than hiding it behind a status
    command.
    """
    posture = "local only" if local_only else "cloud connected"
    return f"{NAME} — {TAGLINE}  [{posture}]"
