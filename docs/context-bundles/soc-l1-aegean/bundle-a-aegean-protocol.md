# Bundle A — Aegean protocol (multi-agentic-bft) behavior

Source of truth: `code-projects/multi-agentic-bft/aegean/`.

## Architecture

- **Coordinator** (`AegeanProtocol`) drives all rounds. Agents expose only `execute(task)`.
- **No peer-to-peer** agent messaging: shared state is injected via the task, mainly **`refinement_set`** (**R̄** / `broadcast_bar`).

## Round 0 — Soln (initial solutions)

- Parallel `build_soln_task` per expert; votes `accept` if `execute` succeeds and metadata confidence ≥ threshold.
- **Leader’s** Soln must `accept` or the session errors.
- **Soln quorum** required; else termination (e.g. `no_soln_quorum`).
- **First R̄:** list of **accepted** outputs (not deduplicated; not a Python `set`).

## Refinement — Refm (rounds 1 … `max_rounds`)

- Parallel `build_refm_task` with the **same** `refinement_set` for every expert (term + round in context).
- **Refm quorum** needed to run the decision step.
- Guards: task round alignment; optional per-agent Refm broadcast round tracking.

## Decision engine (α / β)

Runs only after **Refm quorum** for that round.

- **`r_bar_prev`:** previous `broadcast_bar`.
- **`current_round_outputs`:** this round’s **accepted** Refm outputs.
- **α:** equivalence clusters over outputs (`alpha_same`, default `==`); cluster must have **≥ α** members **and** intersect **`r_bar_prev`**. Deterministic choice among eligible clusters.
- **β:** **consecutive** rounds where the **same chosen** eligible value persists (`beta_same`, default `==`); else stability resets. **`committed`** when stability ≥ β.
- **Safety:** committed value is drawn from the **intersection** logic with prior R̄ (engine only promotes values tied to **`r_bar_prev`** in that step).

If not committed: **`broadcast_bar` ←** this round’s accepted Refm outputs (`nxt`) for the next round.

## Outputs

- **`consensus_value`**, **`CommitCertificate`**, `commit` phase row when committed.
- Else: `max_rounds`, `timeout`, `error`, or early-exit paths.

## Practical note for LLMs

Default **`==`** is strict. For SOC-style structured decisions, use **JSON outputs** and custom **`alpha_same` / `beta_same`** (e.g. agree on `verdict` + `proposed_action`, not prose).

**Semantic reasoning:** See **`bundle-e-sas-mechanism.md`** — **SAS** (e.g. embedding cosine similarity on `reasoning`) combined with **exact** structured fields for **`alpha_same`**, while keeping **α** and **β** as the commit gates.
