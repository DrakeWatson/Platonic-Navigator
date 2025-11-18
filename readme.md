# The Harbor

> The Harbor is the minimal architecture an honest agent eventually constructs once it accepts the axiom **Existence Knows Information**. It is a recursive scaffold—from metaphysics through institutional design—that keeps knowledge, preference, and cooperation coherent under pressure.

## Structure

The Harbor is organized into the following key components:

- **FRAME** — Immutable logical scaffolding. If it changes, every dependent layer is re-audited.
- **CONTEXT** — Domain-specific instantiations (e.g. civic tech, pedagogy, hardware design).
- **TONE** — Raw dialogs, critiques, and narrative attempts. Source material for continuous mining.
- **STRUCTURE** — The seeds of the repo. If these are changed, the rest of the repo will be audited, drafted, and then updated to align with the change.
- **SCRIPTS** — Mechanical helpers for maintaining The Harbor's architecture.

## Scripts

### Tone Organizer

The `tone_organizer.py` script processes conversation data and creates properly formatted markdown files in the appropriate TONE folders (FRAME, CONTEXT, USER, or RAW).

Usage:
```
python SCRIPTS/organizers/tone_organizer.py path/to/conversations.json
```

Options:
- `--dry-run`: Validate the JSON structure without creating any files
- `--verbose`, `-v`: Enable verbose output

See [tone_organizer_guide.md](SCRIPTS/organizers/tone_organizer_guide.md) for detailed information on preparing conversation data.

## Core Philosophy

The Harbor builds from the single axiom "Existence Knows Information" to create a complete framework for understanding agency, ethics, and institutional design. It is a structurally-coherent philosophical and operational framework that translates epistemic honesty into actionable structures, delineating how information becomes function, function becomes action, and how collections of actions scale into ethically stable societies.

For more information, see [what_is_the_harbor.md](FRAME/what_is_the_harbor.md).

## Core Objectives
- **Recursive Self-Improvement:** Use The Harbor to perfect The Harbor.
- **Philosophical Integrity:** Every structure must emerge from necessity, not preference.
- **Technical Precision:** Code, documentation, and automation must reflect clarity, minimalism, and purpose.
- **Proliferation:** Enable scalable translation of core concepts across perspectives and platforms.

## Guiding Principles
- Honesty. Value. Strength.
- Containment → Knowing → Instantiation.
- No performative output. Only necessary, generative structures.

---

## Folder Purpose Map

| **Folder**           | **Purpose**                |
|----------------------|----------------------------|
| `FRAME`              | What The Harbor is         |
| `CONTEXT`            | How it adapts              |
| `TONE`               | How it behaves             |
| `PROLIFERATION`      | How it grows               |
| `OPERATIONS`         | How it governs itself      |
| `VISUALS`            | How it's understood        |
| `UTILITIES`          | How it interfaces          |
| `ARCHIVED`           | Where it began & failed    |
| `WELCOME_ENTER_HERE` | Where outsiders land       |

> *Each folder embodies a function within The Harbor's recursive architecture. This map is not decorative—it is operational. Every addition must respect the role defined here, ensuring cohesion between purpose and structure.*
