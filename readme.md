# Heavy Agent (Working Title)

A self-modifying, self-auditing software stack that uses generative AI to iteratively rewrite, test, and reorganize itself while integrating new capabilities.

The core idea: instead of building a fixed “agent” that just applies tools to user prompts, this repository implements a **heavy agent**—a system that traverses a **possibility space of its own implementations**. It treats the entire repo as something to be audited, refactored, and evolved over time.

---

## Motivation

Most “agent” frameworks today are **light agents**:

- They take an input (goal, query, task).
- They have a more or less fixed internal structure (a chain or graph of tool calls, prompts, and models).
- They produce an output without fundamentally changing themselves.

This project is aimed at a different class of system:

- The agent must **change itself** in order to get better at what it’s doing.
- Internal structure, scripts, prompts, tests, and docs are all subject to revision.
- The system should be able to **ingest new codebases** (e.g., a calculator app), integrate them, and reshape its own stack while keeping clear boundaries and constraints.

The result is a “heavy” agent: more moving parts, more internal reflection, and an iterative evolution of the repository itself.

---

## Core Concepts

### Heavy vs. Light Agents

- **Light Agent**
  - Fixed structure + tools.
  - Input → run chain/graph → output.
  - Can be composed hierarchically (LangChain-style flows, agent graphs, etc.), but the composition itself is mostly static.

- **Heavy Agent**
  - The system’s **own implementation is the object of optimization**.
  - Input can include:
    - New goals.
    - New constraints/rules.
    - New external repositories to ingest.
  - The agent:
    - Audits its current state.
    - Drafts changes to itself.
    - Applies and re-audits until it reaches a rule-satisfied state (or a user-defined stopping condition).

This repo is about implementing that heavy-agent pattern in a concrete, usable way.

---

## Architecture

At a high level, the system is built around three logical roles:

1. **Rules (Structure / Constraints)**
2. **Checks (Auditors / Reviewers)**
3. **Drafts (Drafters / Editors)**

On top of that, the repository includes:

- **Templates** – Standardized prompt and file templates for drafts and audits.
- **Testing** – Automated tests that validate behavior and catch regressions.
- **Toolboxes (Utilities)** – Small, reusable utilities shared across the stack.

### 1. Rules

Rules describe what “good” looks like:

- Structural conventions for the repository.
- Style and organization constraints.
- Behavioral or domain-specific constraints.
- Meta-rules about how often and how far the system is allowed to change itself.

These are written to be machine-interpretable, so auditors can apply them systematically.

### 2. Checks (Auditors)

Checks are scripts/processes that:

- Inspect the current repository:
  - File layout.
  - Code quality.
  - Adherence to conventions.
  - Presence/quality of tests, docs, templates, etc.
- Compare what they see against the **rules**.
- Emit **findings**:
  - Violations.
  - Warnings.
  - Opportunities for simplification or abstraction.

Conceptually, this is **relational auditing**: internal components reflect on the rest of the system and its hierarchy, not just on isolated files.

### 3. Drafts (Drafters)

Drafts are the mechanism for change:

- Take auditor findings as input.
- Use generative models to propose:
  - New or refactored code.
  - New tests.
  - Updated documentation.
  - Reorganized modules and interfaces.
- Produce concrete changes (patches, new files, etc.) for the repo.

As long as checks keep surfacing rule violations, drafts keep generating work. When checks no longer find any violations, drafts have nothing left to do and the system reaches a stable state (relative to the current rules and inputs).

---

## System Behavior

The heavy agent cycles through:

1. **Audit Phase**
   - Run checks/auditors over the current repository.
   - Collect all rule violations and improvement suggestions.

2. **Drafting Phase**
   - For each finding (or batch of findings), spawn drafters.
   - Generate proposed changes: code, tests, docs, or structural edits.
   - Apply changes (potentially with human approval, depending on configuration).

3. **Testing Phase**
   - Run the test suite and any additional validation steps.
   - Feed failures back into the auditing/drafting loop as new findings.

4. **Convergence / Continuation**
   - If all checks pass, and tests are green:
     - Either treat this as a **stable state** and stop.
     - Or accept new prompts/rules/repos and continue iterating.
   - If checks or tests fail, loop back to Drafting.

Over time, this creates a sequence of repository “states” as the heavy agent evolves itself.

---

## Example: Ingesting a New Capability

A conceptual example (details depend on actual implementation):

1. You point the heavy agent at an external repo, e.g. a simple **calculator** application.
2. You prompt the system via the “head” script:
   - “Ingest this calculator repo and integrate it as a capability. Then restructure yourself so that:
     - The calculator functionality is accessible as a tool.
     - The overall repo still satisfies all existing rules.”
3. The heavy agent:
   - Pulls the calculator files into its own repo.
   - Runs auditors against the new combined state.
   - Uses drafters to:
     - Wrap the calculator as a proper module/tool.
     - Add tests and docs.
     - Clean up any structural or style violations.
4. When all checks pass and tests are green, the system settles into a new state:
   - Same core heavy-agent stack.
   - Expanded capabilities (now includes a calculator tool).
   - Still able to iterate further in the future.

---

## Design Principles

- **Abstraction over duplication**  
  Instead of attaching tiny auditors/drafters to every individual script, the system prefers shared, higher-order modules that capture common patterns. This keeps complexity manageable and makes the whole stack easier to reason about and audit.

- **Minimal description, maximal leverage**  
  Aim to express the constraints and structure of the system with as few, well-chosen descriptions as possible, while still allowing rich behavior and growth.

- **Indefinite extensibility**  
  The defining property of a “heavy agent” here is not just that it can change once, but that it can keep iterating into new states of itself while remaining coherent and rule-constrained.

---

## Status

This project is under active development and the terminology and structure are still evolving. “Heavy agent” is a working label for this pattern; the naming and module layout may change as the design stabilizes.

Expect breaking changes, experiments, and refactors as the self-auditing and drafting mechanisms become more robust.

---

## Getting Started

> Note: This section is intentionally high-level. Fill in concrete commands and file paths as the implementation stabilizes.

1. **Clone the repository**

   ```bash
   git clone <REPO_URL>
   cd <REPO_NAME>
