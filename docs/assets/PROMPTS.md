# Brand assets: how each one was made

Every image in this repository is reproducible from the prompt or the source
below. Nothing here is decoration nobody can regenerate — a logo whose prompt
was lost is a logo you cannot iterate on.

---

## Choosing the tool before writing the prompt

This is the part that saves an afternoon. The three jobs look similar and need
different tools.

| You want | Use | Why |
|---|---|---|
| A **character** (mascot, avatar, hero art) | `nano_banana_pro` on Higgsfield | Image models are excellent at this and nothing else competes on time-to-first-good-result. |
| A **diagram whose labels must be correct** | **Excalidraw** or Mermaid | An image model draws *a picture of* a diagram. It will misspell a label eventually, and you cannot fix one word without regenerating the whole thing. |
| A **diagram for a landing page**, look over precision | `nano_banana_pro`, then verify every word | Good enough when the text is four short labels, and it is the look people associate with a friendly open-source project. |
| An **explainer video** | **Remotion** | Code-driven, so the numbers are the real numbers and a rerun after a product change costs nothing. Akaion already runs it. |
| **Atmosphere** — a hero clip, social b-roll | Veo 3.1 | Beautiful motion, no control over text. Never put a label in it. |

**The rule that matters:** never ship a diagram from an image model without
reading every word in it out loud. Models render *plausible* text — `RESTRICED`,
`MODELO FRONTIER`, a repeated arrow label — and the errors are invisible to
whoever wrote the prompt because they read what they meant.

Practical division of labour, and what this project does:

- **Mermaid** in `docs/design/hld.md` — eight diagrams, versioned with the code,
  render on GitHub and in the docs site. These are the *true* ones.
- **An illustrated one** for the landing page and for a slide, generated below.
  It carries four labels and a mascot, which is the ceiling of what an image
  model should be trusted with.

---

## The mascot

`annona-mascot.png` — generated with `nano_banana_pro` (1:1), then background
removed with the same provider's `remove_background`, then resized to 512 px.

```text
3D rendered cute chibi mascot character logo: a friendly Roman praetorian guard
standing centered, glossy Pixar-style rendering, big expressive eyes, warm
smile, wearing a burnished bronze legionary helmet with a deep red horsehair
crest and a verdigris-patinated cuirass with subtle gold trim, holding a small
round shield engraved with a golden wheat sheaf in one hand and a rolled sealed
scroll in the other, a small terracotta amphora spilling golden grain at his
feet, soft studio lighting with a subtle teal rim light, clean solid dark
background, centered composition, highly detailed, appealing toy-like
proportions, brand mascot illustration
```

Why those objects: the **wheat sheaf** is the annona, the **sealed scroll** is
the ledger, the **amphora** is the supply. The verdigris armour is the accent
colour used across the docs (`#1F6F68`). Ask for a *dark solid background* even
when you want transparency — a cut-out from a clean background is far better
than one from a busy scene.

---

## The "how it works" illustration

Template. Replace the bracketed parts; keep the structure, because the structure
is what makes the model place things predictably.

```text
Hand-drawn whiteboard-style technical infographic, black marker on off-white
paper, clean and friendly, minimal text. Title at top in hand-lettered capitals:
"[TITLE, 2-4 WORDS]".

LEFT COLUMN: [two documents, one with a red padlock labelled "[LABEL 1]", one
plain labelled "[LABEL 2]"].

CENTER: a rounded rectangle box with a soft teal border containing [the mascot,
described in one sentence]. Under the box, hand-lettered: "[PRODUCT]" and
smaller beneath it "[three verbs separated by dots]".

RIGHT COLUMN: three destination boxes stacked vertically, labelled "[DEST 1]",
"[DEST 2]", "[DEST 3]".

ARROWS: a thick green arrow from [source] into the box, then to [allowed
destination]. A red dashed arrow from the box toward [forbidden destination],
crossed with a large red X and a small hand-lettered tag reading "[REFUSAL
WORD]". A separate green arrow from [other source] through the box to [other
destination] with a green check mark.

BOTTOM STRIP: [one visual element] with the hand-lettered caption "[CAPTION]".

Style: excalidraw / notebook sketch aesthetic, slightly wobbly lines, generous
white space, only the words listed above, no other text, no paragraphs, no
watermark, no logos.
```

Five rules learned the expensive way:

1. **Name the layout in capitals** (`LEFT COLUMN`, `CENTER`, `ARROWS`). Models
   follow positional instructions far better than they follow prose.
2. **Cap every label at three words.** Long strings are where the spelling goes.
3. **Say "only the words listed above"** or the model will invent captions, and
   the invented ones are always the ones that end up wrong.
4. **Ask for generous white space.** Crowded sketches read as noise at the size a
   landing page uses.
5. **Use 16:9** for anything going above the fold on a page or into a slide.

### Verification checklist before shipping one

- [ ] every word matches what you asked for, character by character
- [ ] the arrows point the way the product actually behaves
- [ ] nothing implies a guarantee the code does not make
- [ ] no invented vendor logo (a model will draw an approximate one, and that is
      somebody else's trademark, approximately)

---

## What to use for a video

**Remotion**, not a video model, for anything explaining the product: it is React
that renders frames, so the numbers on screen are read from the same place the
README reads them, and a rerun after a change costs a build. Akaion already has
`akaion-app-remotion`.

A generative video model — Veo 3.1, or Higgsfield's catalogue — earns its place
in exactly one role: a few seconds of atmosphere behind a title card. The moment
a label has to be legible, it is the wrong tool, and no amount of prompting
changes that.
