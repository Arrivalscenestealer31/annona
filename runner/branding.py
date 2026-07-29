"""Project identity, in one place.

The open-source project is called **Dogana** — Italian for *customs*. It is the
post at the border: everything crossing is declared, checked against the rules,
and either cleared or held, and a stamped record survives the crossing.

That is not decoration. It is the product, and it gives the whole system one
coherent vocabulary:

===============  ============================================================
Term             What it names
===============  ============================================================
**declaration**  what a step states it is about to send outward
**clearance**    the gate's decision on a tool call or an egress
**manifest**     the trace: an ordered, verifiable record of every crossing
**held**         a call the policy refused
**green lane**   a path pre-cleared as low-sensitivity, no inspection needed
===============  ============================================================

Keeping the strings here rather than scattering them means renaming the project
is one edit, and means the CLI, the UI and the docs cannot drift apart on what
this thing is called.

The Python package stays :mod:`runner` and the primary command stays ``akaion``
for now; ``dogana`` is installed as an equal alias. See
``docs/adr/0004-name-the-project-dogana.md`` for why the rename stops there.
"""

from __future__ import annotations

__all__ = [
    "DESCRIPTION",
    "DOCS_URL",
    "LICENSE",
    "NAME",
    "PRONUNCIATION",
    "REPO_URL",
    "TAGLINE",
    "VENDOR",
    "banner_subtitle",
]

NAME = "Dogana"
"""The project name. Italian for *customs*."""

PRONUNCIATION = "doh-GAH-nah"

TAGLINE = "Nothing crosses undeclared."

DESCRIPTION = (
    "The perimeter for AI agents. Dogana runs agent plans inside your "
    "infrastructure and keeps a record of what left it."
)

VENDOR = "Akaion AI Lab"

REPO_URL = "https://github.com/Akaion-repos/akaion-app-runner"
DOCS_URL = "https://akaion-repos.github.io/akaion-app-runner/"

LICENSE = "Apache-2.0"


def banner_subtitle(local_only: bool = True) -> str:
    """One line for the CLI banner, honest about the current mode.

    The border is only meaningful if you can see which side you are on, so the
    banner says it every time rather than hiding it behind a status command.
    """
    posture = "local only" if local_only else "cloud connected"
    return f"{NAME} — {TAGLINE}  [{posture}]"
