# Platonic Navigator – Heavy Agent Repo (MVP)

> A self-modifying, self-auditing software stack that treats *software stacks themselves* as objects to navigate, rewrite, and test.

This repository is an MVP for a **Platonic Navigator** implemented as a **heavy agent**:

* A **software stack that traverses into other software stacks**, including itself.
* Each concrete repository state is treated as an **instance** of a higher‑order, Platonic representation of “what this repo could be”.
* A recursive, self‑aware control hierarchy uses generative models, tests, and explicit rules to:

  * explore possible configurations,
  * correct errors and regressions,
  * revert bad mutations,
  * test better strategies,
  * and accumulate historical data about past behaviors and lessons.

The repo is therefore both:

1. **The world being navigated** (toolboxes, tests, structs, templates, drafters, auditors), and
2. **The machinery that does the navigating** (LLM tooling, test runner, future control loop).

---

## Heavy vs. Light Agents

Most current “agent” frameworks implement what this project calls a **light agent**:

* A mostly fixed internal graph (prompt → tools → model calls).
* It takes an input, runs its chain, and returns an output.
* It may call tools or sub‑agents, but its own implementation is not the main object of optimization.

This repository implements a **heavy agent**:

* The agent’s **own implementation is the primary thing being optimized**.
* Internal structure (scripts, prompts, tests, templates, file layout) is an actively edited surface.
* The system is designed to:

  * ingest new repositories,
  * integrate them as capabilities,
  * and continuously **rewrite its own stack** to stay coherent with its rules.

A light agent sits *on top of* a fixed stack.
This repo is the stack that changes itself.

---

## Core Concepts

### Platonic Space of Stacks

The “Platonic Navigator” idea:

* Each *type* of artifact in the repo (toolbox, test plan, auditor, drafter, struct, template) has:

  * a **struct** describing the ideal constraints and fields,
  * and (eventually) a bundle of **prompts** describing how to generate or modify instances.
* Together, these define a **Platonic form** for that artifact type.
* The concrete `.py`, `.json`, `.md`, and `.html` files in the repo are **instances** of those forms.

The heavy agent navigates a **space of possible repos** by:

1. Auditing how far the current instance deviates from its struct.
2. Drafting changes that move it closer to the Platonic description.
3. Running tests to see whether behavior improved or regressed.
4. Keeping timelines and reports so future iterations can learn from history.

### Rules, Checks, and Drafts

The stack is organized around three logical roles:

1. **Rules** – What “good” looks like.
2. **Checks (Auditors)** – What is currently wrong or improvable.
3. **Drafts (Drafters)** – How to change the repo.

These roles are implemented through structs, templates, code modules, and prompts.

#### Rules

Rules live primarily in **STRUCTS/**:

* Structural conventions for each file type.
* Requirements on functions, headers, logging, tests, and prompts.
* In some cases, explicit instructions for coverage, error handling, and edge‑case behavior.

Structs are written as machine‑readable JSON so they can be applied automatically.

#### Checks (Auditors)

Auditors are scripts that:

* Walk parts of the repo.
* Load the relevant struct for each file type.
* Compare actual files to their Platonic description.
* Emit structured findings (violations, warnings, suggestions).

Right now most auditor modules are stubs; the struct files and templates define what they **should** become.

#### Drafts (Drafters)

Drafters are responsible for change:

* They take:

  * struct definitions,
  * templates,
  * prompts,
  * and (eventually) auditor findings,
* then use LLMs to propose:

  * new files,
  * refactors,
  * test cases,
  * doc updates,
  * or structural reorganizations.

Most drafter modules are also currently stubs; the `drafter_toolbox.py` and struct/prompt design show how they’re intended to operate.

---

## High‑Level Behavior

In its intended steady state, the heavy agent runs a loop:

1. **Audit Phase**

   * Run auditors over the repo.
   * Compare each artifact to its struct.
   * Collect a set of rule violations and improvement opportunities.

2. **Drafting Phase**

   * For each finding, invoke the appropriate drafter.
   * Generate proposed code / tests / docs / structural edits.
   * Apply changes (either automatically or subject to human review).

3. **Testing Phase**

   * Use the `test_toolbox` and JSON test plans to run the relevant tests.
   * Capture results plus a detailed execution **timeline**.

4. **Convergence / Continuation**

   * If all checks pass and tests are green, the system is locally stable relative to current rules.
   * If not, the new failures become fresh findings, and the loop continues.
   * New prompts, new rules, or new target repos can be introduced to continue evolving the stack.

Over time this produces a sequence of repository states: a trajectory through the Platonic space of possible implementations.

---

## Repository Layout

Top‑level structure (from the current MVP):

```text
.
├── AUDITORS/        # Auditor modules + their tests
├── DRAFTERS/        # Drafter modules
├── STRUCTS/         # Platonic definitions (rules + prompts) for each file type
├── TEMPLATES/       # Canonical minimal instances of each file type
└── TOOLBOXES/       # Shared utilities, testing infra, and LLM glue
```

### STRUCTS/

Core struct files:

* `STRUCTS/struct.json`
  Generic struct for struct files themselves.

* `STRUCTS/audit_struct.json`
  Platonic rules for auditor modules (naming, structure, exposed functions, logging, test layout, etc.).

* `STRUCTS/draft_struct.json`
  Rules for drafter modules: how they expose entrypoints, how they consume structs/prompts, what they must log and test.

* `STRUCTS/template_struct.json`
  Rules for template files (Python vs JSON vs Markdown, required markers, etc.).

* `STRUCTS/test_struct.json`
  Rules for test plans and test case bundles (`test_plan.json`, `*_tests.json`), in terms of fields, coverage semantics, and expected relationships.

* `STRUCTS/toolbox_struct.json`
  Rules for `*_toolbox.py` modules: single `TypeToolbox` class, header conventions, function header comments, and configuration hooks.

Struct prompts:

* `STRUCTS/prompts/` contains per‑struct prompt sets intended for LLM‑driven drafting and modification.
* Currently the most populated folder is:

  * `STRUCTS/prompts/test_struct/` – prompts for generating test plans, test cases, logic descriptions, and support files for new modules.
* Other struct prompt directories exist as placeholders (`audit_struct`, `draft_struct`, `struct`, `template_struct`, `toolbox_struct`) and will be filled as the system matures.

These structs and prompts are the **Platonic description layer** for the stack.

### TEMPLATES/

Canonical minimal examples for each file type:

* `TEMPLATES/auditor_template.py` – skeleton for auditor modules.
* `TEMPLATES/drafter_template.py` – skeleton for drafter modules.
* `TEMPLATES/toolbox_template.py` – skeleton for toolbox modules (`TypeToolbox` class, header pattern, function layout).
* `TEMPLATES/struct_template.json` – canonical struct file shape.
* `TEMPLATES/test_plan_template.json` – canonical `test_plan.json`.
* `TEMPLATES/test_case_template.json` – canonical `*_tests.json`.
* `TEMPLATES/test_logic_template.md` – narrative description format for test logic.

Templates are the “minimum viable instances” that structs talk about and auditors enforce.

### TOOLBOXES/

Shared utilities, LLM integration, and testing backbone.

Core modules:

* `TOOLBOXES/file_io_toolbox.py`

  * File and JSON I/O helpers.
  * Safe read/write/append operations.
  * Validation routines for JSON content.
  * Used heavily by the test infrastructure.

* `TOOLBOXES/logging_toolbox.py`

  * Centralized logging with line‑wrap/line‑break support.
  * Helpers for consistent log formatting across modules.

* `TOOLBOXES/test_toolbox.py`

  * Generalized test runner for **JSON‑described test plans**.
  * Key ideas:

    * A `test_plan.json` defines a set of test cases, each referencing `*_tests.json` logic bundles.
    * The toolbox dynamically imports scripts and functions, resolves parameters, and executes call chains.
    * Results and execution traces are recorded as:

      * structured **test reports** (per suite / per case),
      * and detailed **timelines** of events for post‑hoc inspection.

* `TOOLBOXES/llm_toolbox.py`

  * Wrapper for LLM providers (OpenAI, Google Gemini, etc.).
  * Tracks token usage and cost.
  * Encapsulates model configuration and context‑window limits for drafters and auditors.

* `TOOLBOXES/drafter_toolbox.py`

  * Early “meta‑drafter” that:

    * Reads struct JSON and associated prompts.
    * Builds rich prompt contexts from repo state.
    * Orchestrates multi‑step LLM calls to create or modify files.
  * This is a prototype of how future drafter modules will be driven.

* `TOOLBOXES/system_trace_toolbox.py`

  * Utilities for hashing and recording execution traces.
  * Enables comparison between runs and detection of behavioral drift in the heavy agent’s own tools.

Support assets:

* `TOOLBOXES/timeline_viewer.html`

  * A Tailwind‑based viewer to visualize test timelines and reports in the browser.

Configuration files:

* `TOOLBOXES/file_io_toolbox.json`
* `TOOLBOXES/logging_toolbox.json`
* `TOOLBOXES/test_toolbox.json`

These hold configuration/metadata for their respective toolboxes.

Toolbox tests:

```text
TOOLBOXES/tests/
  ├── auditor_toolbox/        # (placeholder)
  ├── drafter_toolbox/        # (placeholder)
  ├── file_io_toolbox/        # concrete tests + fixtures + LLM-gen history
  ├── llm_toolbox/            # (placeholder)
  ├── logging_toolbox/        # JSON-defined tests
  ├── templates/              # HTML dashboard template(s)
  ├── test_toolbox/           # deep tests for the test runner itself
  └── test_reviewer.py        # Flask dashboard for browsing test results
```

Notable folders:

* `TOOLBOXES/tests/file_io_toolbox/`

  * Includes `test_plan.json` and rich sets of `*_tests.json` files covering:

    * JSON round‑trip read/write,
    * validation edge cases,
    * file‑system behavior (non‑existent, empty, no‑permission files, etc.).
  * Includes historical LLM prompt/response logs under timestamped subfolders documenting how tests were drafted.

* `TOOLBOXES/tests/logging_toolbox/`

  * `test_plan.json` plus multiple `logging_*_tests.json` covering init, line‑wrap, linebreaks, and core methods.

* `TOOLBOXES/tests/test_toolbox/`

  * `test_plan.json` plus multiple test case bundles for:

    * `load_files`,
    * `prepare_functions`,
    * `resolve_params`,
    * `validate_files`,
    * input‑validation edge cases.
  * Also includes fixture files like `script_test.py`, `sample_data.csv`, `dummy_input_for_resolve.json`, etc.

* `TOOLBOXES/tests/file_io_toolbox/test_reviewer.py`

  * A specialized Flask viewer focused on the file‑IO test suite.

The test infrastructure is the primary **objective feedback channel** for the heavy agent.

### DRAFTERS/

`DRAFTERS/` currently contains placeholder modules:

* `auditor_drafter.py`
* `drafter_drafter.py`
* `struct_drafter.py`
* `template_drafter.py`
* `test_drafter.py`
* `toolbox_drafter.py`

They exist so that:

* struct and template rules have concrete targets,
* and future iterations can overwrite these files using `drafter_toolbox` + LLMs.

Intended responsibilities:

* Take in:

  * relevant struct(s),
  * template(s),
  * prompts,
  * and (eventually) auditor findings.
* Generate:

  * new modules (e.g., a new toolbox or auditor),
  * migrations (e.g., updating modules to a new struct version),
  * and the corresponding test plans + test cases.

### AUDITORS/

`AUDITORS/` mirrors `DRAFTERS/`:

* `auditor_auditor.py`
* `drafter_auditor.py`
* `struct_auditor.py`
* `template_auditor.py`
* `test_auditor.py`
* `toolbox_auditor.py`
* `AUDITORS/logs/`
* `AUDITORS/tests/`
  with subfolders for each auditor type (currently placeholders).

Intended responsibilities:

* Load each file type in the repo.
* Compare implementation to the relevant struct and template.
* Emit structured findings that can be fed to drafters and test plans.
* Log their own behavior for later inspection.

---

## Example: Stack Traversing Another Stack

A conceptual flow for ingesting a new capability (e.g., a basic calculator repo):

1. **User prompt**

   > “Ingest this calculator repo and integrate it as a capability.
   > Constrain it to your existing struct rules and expose it as a tool.
   > Keep your overall structure consistent and fully tested.”

2. **Heavy agent steps**

   * Use `file_io_toolbox` to import the target repo into a dedicated subdirectory or module.
   * Run relevant auditors:

     * check naming,
     * detect missing tests,
     * flag structural inconsistencies with existing rules.
   * Invoke drafters to:

     * wrap calculator functions into a standardized toolbox/module,
     * create `test_plan.json` and `*_tests.json` for calculator behaviors using `test_struct` prompts,
     * generate docs or README entries for the new capability.

3. **Test and reconcile**

   * Run `test_toolbox` on both existing and new test plans.
   * Use test failures to drive a second wave of drafting.
   * When tests are green and auditors are satisfied, commit this repo state as a new stable point in the heavy agent’s trajectory.

The key point: the agent did not just *call* the calculator; it **reshaped itself** to absorb the calculator cleanly.

---

## Design Principles

* **Heavy first, light later**
  This repo is the heavy agent’s core. Light agents (task‑specific flows) will be layered on top of a stable, self‑auditing base.

* **Abstraction over duplication**
  Shared functionality (I/O, logging, test orchestration, LLM integration) is centralized in toolboxes.
  Structs and templates encode patterns once rather than copying conventions everywhere.

* **Minimal description, maximal leverage**
  Prefer a small number of precise struct + prompt descriptions that can generate a wide variety of consistent artifacts.

* **Indefinite extensibility**
  The essential feature of a heavy agent here is its capacity to continue iterating into new capabilities and internal structures while staying governed by explicit rules and tests.

---

## Dependencies

The repo targets **Python 3.10+**.

Third‑party packages currently used:

* `openai` – LLM API access (via `llm_toolbox.py`).
* `google-generativeai` – Gemini API access (via `llm_toolbox.py`).
* `tiktoken` – Token counting and context estimation (via `llm_toolbox.py`).
* `networkx` – Experimental graph utilities in `drafter_toolbox.py`.
* `flask` – Test report dashboards (`TOOLBOXES/tests/test_reviewer.py` and variants).

Install (example):

```bash
pip install openai google-generativeai tiktoken networkx flask
```

A dedicated `requirements.txt` can be added once the dependency set stabilizes.

Most core toolbox tests can run without LLM credentials as long as LLM‑dependent paths are not exercised.

---

## Running Tests

### 1. Running a toolbox test plan programmatically

Example: run the `file_io_toolbox` test plan.

```python
from pathlib import Path
from TOOLBOXES import test_toolbox

plan = Path("TOOLBOXES/tests/file_io_toolbox/test_plan.json")
runner = test_toolbox.TestToolbox(str(plan))

# Run all cases in the plan
report = runner.execute_test_plan()

# Or run a specific test case by ID (if supported by the version you’re using)
# report = runner.execute_test_plan("json_validation_tests")

print(report.get("summary", report))
```

This will:

* Execute all tests defined in the plan.
* Use `logging_toolbox` for structured logging.
* Emit JSON reports and timelines into the same folder as the plan.

### 2. Browsing reports via Flask dashboard

From the repo root:

```bash
cd TOOLBOXES/tests
python test_reviewer.py
```

Then open the printed URL (typically `http://127.0.0.1:5000/`) in your browser.

You can:

* Browse test plans and individual cases.
* Inspect reports and timelines.
* Compare runs over time.

A specialized version exists under `TOOLBOXES/tests/file_io_toolbox/test_reviewer.py` for that suite.

---

## Getting Started (High‑Level)

1. **Clone the repo**

   ```bash
   git clone <REPO_URL>
   cd <REPO_NAME>
   ```

2. **Set up Python environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt  # when available
   ```

   Or install the dependencies listed above directly.

3. **Configure LLM access**

   * Set environment variables or config files for:

     * OpenAI keys and models.
     * Gemini keys and models.
   * Optionally configure pricing tables and model aliases in `llm_toolbox.py`.

4. **Run an initial test sweep**

   * Start with toolbox tests, e.g.:

     ```bash
     python -m TOOLBOXES.tests.test_toolbox_entrypoint   # replace with actual entrypoint once defined
     ```

   * Or invoke `TestToolbox` programmatically as shown above.

5. **Begin experimental heavy‑agent loops**

   * Implement a small orchestrator script (e.g., `navigator.py`) that:

     * loads structs,
     * runs preliminary auditors,
     * calls `drafter_toolbox` to propose a small refactor,
     * runs the relevant tests,
     * and logs results.
   * Iterate from there.

Because this is an MVP, the heavy‑agent loop itself is not yet a single, polished script—what you have is the **scaffolding** and **feedback channels** needed to build it.

---

## Roadmap (Sketch)

* **Short term**

  * Fill out missing struct prompt sets (`audit_struct`, `draft_struct`, `toolbox_struct`, etc.).
  * Implement first serious versions of:

    * `*_drafter.py` modules,
    * `*_auditor.py` modules,
    * and their corresponding tests.
  * Stabilize `TestToolbox` API and add CLI entrypoints.

* **Medium term**

  * Implement a top‑level **navigator** loop that:

    * discovers applicable structs and prompts,
    * runs auditors,
    * schedules drafting work,
    * manages test execution and timeline recording,
    * and decides when to accept or revert changes.
  * Add visualization tools for:

    * dependency graphs,
    * audit results,
    * and evolution of the repo over time.

* **Long term**

  * Support ingesting arbitrary external repos as “candidate stacks” to traverse and absorb.
  * Host multiple **light agents** atop the heavy agent core, each with:

    * its own prompt interface,
    * tool orchestration,
    * and safety/constraint profile.
  * Make it straightforward to spin up new heavy‑agent instances with different rule sets for different domains.

---

## License

TBD.
