# Skills

A skill is a folder with a `SKILL.md`: YAML front matter, then prose that teaches
a model how to do one thing well. The format is
[Anthropic's Agent Skills](https://github.com/anthropics/skills), deliberately
and exactly — an instruction written for Claude works here, and one written here
works there.

Annona adds one field, and it is the only thing that makes this more than a
prompt library:

```yaml
pins: local
```

The moment a model loads a skill declaring it, the working set is raised —
*before* the instruction is handed over — and no later turn of that run can be
placed outside the perimeter, whatever the prompt looks like by then.

A prompt library asks politely at the bottom of the file. A capability system
refuses to place the work anywhere else.

---

## The shipped set

Generic in name, specific in effect. That is not marketing: an instruction that
names a domain gets used only in that domain, and the same "read this image and
tell me what you see, with your limits stated" is the right instruction for a
radiologist, a loss adjuster and a site engineer.

| Skill | What it does | Pins |
|---|---|---|
| `image-report` | reads images, produces observations with measurements where a scale exists, confidence per line, and an always-non-empty *limits* section | local · needs vision |
| `document-triage` | a folder of documents becomes a table: type by evidence rather than filename, identifying fields, and a flag on anything a person must see | local |
| `case-timeline` | a dated chronology with a source per line, undated events kept separate, and contradictions between documents named explicitly | local |
| `bulk-extract` | the same fields across many documents into one CSV; an empty cell means absent and `?` means unreadable, and neither is ever invented | local |
| `evidence-pack` | an answer plus the sources, the steps, the assumptions, and what would change the conclusion | local |
| `redact-and-ask` | restates a question so it can be answered without identifiers, checks the restatement, then applies the answer to the real matter here | — |
| `second-opinion` | answers, then attacks its own answer as an adversary would, and reports where the two disagree and how to settle it | — |

The first five pin the run local, because the material people point them at does
not leave. The last two touch nothing, so they do not — confining a run for no
reason is its own kind of dishonesty.

```bash
annona skills                      # installed · allowed · usable here
annona skills --show image-report  # read the instruction your model is given
```

!!! warning "`image-report` is not a diagnostic device"
    It produces observations for a professional to interpret; the instruction
    tells the model to refuse a diagnosis, a prognosis, a valuation or a finding
    of fault and to hand back the observations instead. Software intended for
    diagnosis is regulated as a medical device, and giving it a neutral name
    does not change that.

---

## Installing somebody else's

```bash
annona skills-install ~/Downloads/pdf     # a folder, or a SKILL.md
annona skills-install pdf                 # or by name, from ~/.claude/skills
```

Anything from `anthropics/skills`, or anything already in your Claude Code
directory, installs unchanged — `scripts/` and `references/` come along whole.

Two things happen on the way in.

**The skill is pinned to the perimeter.** A skill is an instruction your agent
will follow: a supply-chain dependency that happens to be prose. Whoever wrote
the file decides what your agent does with your material. One you did not write
runs inside your walls until you have read it and said otherwise:

```bash
annona skills --show pdf                        # read it first
annona skills-install ~/Downloads/pdf --trust --force   # then unpin it
```

Provenance is written into the front matter (`imported_from`, `imported_at`,
`pinned_reason`) and **the body is copied byte for byte** — silently editing
somebody's instruction would be its own kind of supply-chain problem.

**Installed is not enabled.** The policy still has to name it. Copying a file
into a directory is not a decision about what your agents may do:

```yaml
skills: [image-report, second-opinion, pdf]
```

Skills that bundle `scripts/` are copied whole, and the install says plainly
that those scripts will not run unless the policy allows the `shell` tool, which
by default it does not. The instructions still work; the automation in them does
not.

---

## Writing one

```markdown
---
name: verbale-riunione
description: Turn meeting notes into a formal minute, in the house format.
version: 1
requires: [vision]          # optional: substrate capabilities
tools: [document_reader]    # optional: tools it expects to be allowed
min_context: 16000          # optional
pins: local                 # local | none
---

# Minute of a meeting

1. …
```

Put it in `~/.annona/skills/verbale-riunione/SKILL.md`. A skill there overrides
a shipped one of the same name, which is how a practice encodes its house style
without forking anything.

Only `name` and `description` are required — that is the Anthropic contract, and
it is kept. Everything Annona adds is optional and ignored by a runtime that
does not understand it.

### What the description is for

It is the only thing a model sees before deciding whether to load the skill, so
it has to say **what the skill does and when to use it**, not what it is called.
"Turn meeting notes into a formal minute, in the house format" is useful.
"Meeting helper" is not.

### When to pin

Pin when the skill's *subject matter* is material that must not leave — images
of people or property, client files, medical or personnel records — even when
the instruction itself is generic. The instruction is portable; the material is
not, and the pin is about the second.

Do not pin a skill that only reasons. A run confined for no reason costs quality
and buys nothing, and operators who see that happen start looking for the flag
that turns the perimeter off.

---

## How it behaves at runtime

**Default-deny.** A skill the policy does not name is never offered, and asking
for a disabled skill is answered exactly like asking for one that does not
exist — a model must not be able to enumerate what an operator chose not to
enable.

**Progressive disclosure is a perimeter property.** The catalogue in the tool
description is names and one-line descriptions; bodies arrive only when asked
for. What is in the prompt is in the transcript, and the transcript is what
crosses.

**Bodies are classified.** A skill body enters the transcript like any other
material and passes through the same classifier, so an instruction file carrying
an identifier raises the class of the run rather than arriving unclassified.

**Loading is recorded.** `annona audit` shows which skills a run loaded, which
were refused and why, in the same hash-chained ledger as every placement.

**Requirements are checked before offering.** A skill needing vision is not
offered where no substrate can read an image; one whose tools are denied is not
offered at all. `annona skills` prints the reason for anything blocked, so the
answer to "why isn't it using the skill" is a command rather than an
investigation.
