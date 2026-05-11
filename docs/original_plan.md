---
name: Paper Focused Aegean Plan
overview: "Canonical Python work lives in `code-projects/multi-agentic-bft/aegean/` (checklist Slices 1–9 done through 2026-05). Core fail-stop P0 is implemented in-process: R=N−f, Soln→Refm+α/β engine, NewTermAck recovery, Refm round/set guards, RV→Vote election simulation. Left: explicit leader/commit invariants + certificates (P1), proof-heavy tests, `round_timeout_ms`/`confidence_threshold` wiring, election stall→next-term behavior, networked RPC for election, adversarial RefmSet integration tests, P2 benchmarks/inference reduction. TypeScript `nexus-agents` remains non-canonical unless ported."
todos:
  - id: p0-refinement-loop
    content: "Task→Soln quorum (Round 0) then RefmSet/Refm loop — DONE: aegean/protocol.py + tests."
    status: completed
  - id: p0-alpha-beta-engine
    content: "Stateful α/β engine (R̄_prev gate, overturn, on_new_term) — DONE: aegean/decision_engine.py + tests."
    status: completed
  - id: p0-term-recovery
    content: "NewTermAck recovery, RV/Vote types + simulate_leader_election — DONE in-library + coordinator; NEWTERM/RV/Vote over RPC still TODO (see p1-election-rpc)."
    status: completed
  - id: p0-leader-participation
    content: "All experts (incl. leader) run Soln and Refm tasks — DONE: protocol loops all experts."
    status: completed
  - id: p0-f-bound-validation
    content: "f bound + R=N−f everywhere — DONE: validate_failstop_fault_bound, calculate_quorum_size."
    status: completed
  - id: p0-prev-round-output-rule
    content: "Engine outputs only from previous R̄ — DONE: DecisionEngine.step(r_bar_prev=...)."
    status: completed
  - id: p0-round-reset-on-newterm
    content: "After recovery, first Refm uses round_num=1 — DONE: protocol + recovery tests."
    status: completed
  - id: p0-beta-reset-on-newterm
    content: "Reset β on new term — DONE: engine.on_new_term."
    status: completed
  - id: p0-beta-reset-on-candidate-overturn
    content: "Overturn→stability 1 — DONE: decision_engine."
    status: completed
  - id: p0-refmset-update-guard
    content: "incoming round >= local — DONE: refm_set_update_allowed + PerAgentRefmRoundTrack in protocol."
    status: completed
  - id: p0-refm-round-match-filter
    content: "Refm tasks must match leader round — DONE: refm_task_matches_round before execute."
    status: completed
  - id: p0-no-round0-after-recovery
    content: "Skip Round 0 when recovery provides non-bottom R̄ — DONE: protocol recovery branch."
    status: completed
  - id: p0-newtermack-bottom-fallback
    content: "All-bottom acks → fresh Soln — DONE: recovery_acks_all_bottom path."
    status: completed
  - id: p0-leader-self-included-in-quorum
    content: "Leader counts in quorum — DONE: all experts in vote collection + dedupe-by-agent."
    status: completed
  - id: p0-leader-only-output-invariant
    content: "TODO: Explicit leader-attributed commit + test at-most-one commit per refinement round (Lemma 1); align with p1-commit-semantics."
    status: pending
  - id: p0-one-vote-per-term
    content: "At-most-one Vote per term — DONE: LocalElectionState.record_vote; re-verify under RPC."
    status: completed
  - id: p0-candidate-self-vote
    content: "Candidate included in RV/Vote simulation quorum — DONE: simulate_leader_election."
    status: completed
  - id: p0-requestvote-higher-term-guard
    content: "Strictly higher term for RV grant — DONE: request_vote_granted / grant_request_vote."
    status: completed
  - id: p0-output-from-refmset-only
    content: "Commit only from refinement-set members — DONE: engine membership gate."
    status: completed
  - id: p0-round0-quorum-rule
    content: "Same R for Round 0 Soln and Refm — DONE: evaluate_quorum_status paths."
    status: completed
  - id: p1-election-rpc
    content: "Networked RequestVote/Vote (optional NewTerm) transport — simulation only today; wire for multi-process/agents."
    status: pending
  - id: p1-refmset-adversarial-tests
    content: "Integration tests: multi-term persisted RefmSet state, adversarial/stale delivery order beyond unit tests."
    status: pending
  - id: p1-proof-invariant-tests
    content: "Expand Lemma 1/2/3-style invariant tests (monotonicity, validity, termination under harness assumptions)."
    status: pending
  - id: p1-runtime-controls
    content: "Wire round_timeout_ms and confidence_threshold; decision-primary loop vs max_rounds backstop; precise fail-stop termination reasons."
    status: pending
  - id: p1-election-timeout-next-term
    content: "Election no-progress: timeout, increment term, retry RV/Vote (paper Section 5.2 style)."
    status: pending
  - id: p1-commit-semantics
    content: "Commit certificates / phase records + monotonicity guard for replay."
    status: pending
  - id: p2-inference-reduction
    content: "Early termination, parallel dispatch, skip rounds once α+β satisfied (production orchestration)."
    status: pending
  - id: p2-benchmarks
    content: "Paper-aligned benchmark harness vs fixed-round majority baseline."
    status: pending
isProject: false
---

# Aegean Paper-Focused Implementation Plan

## Goal
Implement a paper-faithful Aegean protocol in `multi-agentic-bft` with correct refinement semantics, stability-based finalization, leader-change recovery, and consensus-aware inference reduction.

## Live status (Cursor todos + repo checklist)

- **Shipped work is tracked in:** [checklist.md](c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\checklist.md) (**Slices 1–9** as of 2026-05).
- **This file’s YAML `todos` (front matter)** is the Cursor task list: set `status: completed` for items implemented in `aegean/`; `status: pending` is what is still open (P1/P2 and one P0 gap: explicit leader-only commit path).
- **Still open (summary):** `p0-leader-only-output-invariant`, `p1-election-rpc`, `p1-refmset-adversarial-tests`, `p1-proof-invariant-tests`, `p1-runtime-controls`, `p1-election-timeout-next-term`, `p1-commit-semantics`, `p2-inference-reduction`, `p2-benchmarks`.

## Paper Reference
- Primary source: [c:\Relevant\OMSCS\AI_8903\code-projects\2512.20184v1.pdf](c:\Relevant\OMSCS\AI_8903\code-projects\2512.20184v1.pdf)
- Title: Reaching Agreement Among Reasoning LLM Agents
- This plan's protocol semantics, term/recovery rules, decision engine behavior, and evaluation criteria are derived from this paper.

## Scope (Paper Only)
- In scope: protocol semantics and execution model from the paper (`RefmSet/Refm`, `alpha`, `beta`, term-based recovery, early cancellation).
- Out of scope: SOC-specific schemas/connectors, ticketing integrations, domain-specific policy gates.
- Current execution scope: production API providers only; local serving-engine internals are deferred.

## Canonical codebase (implementation target)
- **Source of truth for paper semantics:** `multi-agentic-bft` (`aegean/`). P0–P2 protocol work lands here unless the team explicitly rescopes.
- **Not canonical unless explicitly ported:** `nexus-agents` TypeScript Aegean (`aegean-protocol.ts` and related helpers/tests) — same label, but today it is a simplified leader-propose / vote loop, not Algorithm 1. Porting it would be a separate, deliberate effort.

## Migrating from the current Python baseline
The repo’s pre-refactor Aegean shim optimizes for a **Byzantine-style sizing habit**, not the paper’s fail-stop ensemble story. When implementing P0, **replace** rather than blend:
- Remove or rewrite startup gates such as **`min_agents = max(3, 3f + 1)`** in favor of the paper model: **`N`** configured agents with **`f ≤ ⌈(N − 1)/2⌉`** fail-stop failures (validate `f` against `N`, not a separate 3f+1 minimum).
- Replace **`calculate_quorum_size` = ⌈(N + f + 1) / 2⌉** with the paper’s single quorum size **`R = N − f`** for **both** Round 0 Soln collection and every Refm quorum. One formula everywhere so Round 0 cannot drift from refinement rounds.

## Fail-stop vs Byzantine-style quorum (nuance — keep for future context)
**Neither formula is intrinsically “wrong”; they answer different questions.** The bug risk is **mixing** paper Aegean (fail-stop) with helpers named for Byzantine-quorum intuition.

| Aspect | **Aegean paper (§5.1, fail-stop)** | **Legacy `multi-agentic-bft` shim habit** |
|--------|-----------------------------------|-------------------------------------------|
| Failure model | At most **`f`** fail-stop agents; **`f ≤ ⌈(N − 1)/2⌉`** | Implicit **Byzantine-style** deployment sizing (**`3f + 1`** replicas) and quorum scaling |
| Meaning of **`f`** | Upper bound on **crashes / stop responding** | Same symbol often used in code as **`byzantine_tolerance`** — evokes **Byzantine** bounds, not paper semantics |
| Quorum **`R`** | **One** threshold: **`R = N − f`** for Soln and Refm (plan convention aligned with paper ensemble + fail-stop) | **`⌈(N + f + 1) / 2⌉`** — familiar from **Byzantine quorum** analyses (grows stricter vs plain majority for many `(N,f)` pairs) |
| Minimum **`N`** | **`N ≥ 3`** is enough for small ensembles with **`f`** satisfying the paper bound | **`max(3, 3f + 1)`** enforces **classic 3f+1 layout**, which is **stronger** than the paper’s minimum |

**Concrete disagreement:** for **`N = 5`**, **`f = 2`** (allowed fail-stop bound in the paper’s ⌈(N−1)/2⌉ sense): paper-path **`R = N − f = 3`**; legacy helper **`⌈(5 + 2 + 1) / 2⌉ = 4`**. Same inputs, **different quorums** — hence different liveness (“do we have quorum yet?”) and different tests vs the PDF.

**Why this matters:** you can implement messages and rounds correctly yet **silently diverge** from the paper if **`f`** still drives **`⌈(N+f+1)/2⌉`** or **`3f+1`** gates. Treat **`R = N − f`** and **`f ≤ ⌈(N−1)/2⌉`** as the **single coherent package** for this plan.

**Future Byzantine extension:** if you later add **malicious** agents, you need **explicit** separate assumptions (e.g. **`n ≥ 3f + 1`**, **`2f + 1`** quorums), **not** reuse the paper’s **`R = N − f`** without re-deriving safety. Until then, keep **`byzantine_failure`** termination labels **reserved** (see P1 todos) and avoid implying Byzantine guarantees from fail-stop **`f`**.

## Round numbering: Algorithm 1 vs §5.2 prose
The PDF mixes Algorithm 1 (initialize **`round-num ← 0`**, then the main loop increments) with prose/Figure 4 that assigns **`round-num = 1`** to the first **`RefmSet`** after a Soln quorum. **Pick one internal convention, document it beside the state machine, and use it in tests/logs:**
- **Recommended mapping:** Treat **Soln quorum formation** as **bootstrap phase round 0**. The **first** leader broadcast **`⟨RefmSet, term-num, round-num, R̄⟩`** after Soln uses **`round-num = 1`** (matches §5.2 narrative). Advance **`round-num`** each refinement iteration per Algorithm 1 thereafter (until decision or term change).
- **Recovery:** After **`NewTerm`**, paper sets **`round-num ← 1`** before the first **`RefmSet`** in the new term — keep consistent with the chosen convention above.
- Ensures **`R_bar_prev` / round `i` vs `i + 1`** in the decision engine and the “output only from previous refinement set” rule stay aligned with stored round indices.

## Baseline Code Areas
- Core protocol loop: [c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\aegean\protocol.py](c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\aegean\protocol.py)
- Types/state model: [c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\aegean\types.py](c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\aegean\types.py)
- Helpers/quorum logic: [c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\aegean\helpers_utils.py](c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\aegean\helpers_utils.py)
- Existing tests: [c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\tests](c:\Relevant\OMSCS\AI_8903\code-projects\multi-agentic-bft\tests)

## Paper Section -> Implementation Mapping
- `§4.1 Problem Formulation` -> encode protocol-level guarantees and assumptions in state/types and tests:
  - refinement termination, validity, monotonicity,
  - fail-stop + partial synchrony assumptions in test fixtures.
  - Refinement monotonicity allows **multiple committed outputs over real time** across rounds/terms; **at most one commit per leader per refinement round** (Lemma 1). Do not conflate “one per round” with “only one ever.”
- `§4.2 Agent Operational Semantics` -> implement agent reasoning interface contracts:
  - task-input reasoning (`R(task)`),
  - refinement-input reasoning (`R(R_bar)`),
  - context/state transition handling.
- `§4.3 Semantics Validation` -> document and test reliance on refinement assumption:
  - weaker/stronger-agent behavior expectations,
  - non-decreasing quality-oriented refinement checks.
- `§5.1 Protocol Overview` -> main coordinator flow in `protocol.py`:
  - term/leader lifecycle,
  - Round 0 Soln bootstrap,
  - iterative RefmSet propagation and previous-round output semantics.
- `§5.2 Protocol Specification (Algorithm 1 + election + decision engine)` -> primary implementation source of truth:
  - message/state transitions (`Task`, `Soln`, `RefmSet`, `Refm`, `RequestVote`, `Vote`, `NewTerm`, `NewTermAck`),
  - leader election guards and tie-break rules,
  - alpha/beta decision logic and round/term reset behavior.
- `§5.3 Correctness Proof` -> invariant test suite in `tests/`:
  - Lemma 1: monotonicity + leader-only/at-most-one-output-per-round,
  - Lemma 2: output validity from refinement sets only,
  - Lemma 3: eventual termination under bounded-delay assumptions.
- `§6.1-§6.3 Aegean-Serve` -> deferred backlog (non-blocking for production-API scope):
  - serving-layer incremental quorum/cancellation primitives,
  - ensemble-aware admission/preemption,
  - scheduler/resource-management hooks.
- `§7.1-§7.4 Experiments` -> benchmark harness requirements:
  - default config (`n=3`, `alpha=2`, `beta=2`, `Tmax=5`),
  - baseline sweep (`MaxRound in {4,5,6}`),
  - metrics (avg latency, P99, token cost, quality/accuracy, overturn behavior),
  - optional: Poisson arrivals over request rate (§7.1) for Figure 7–8 style load replication.

## Implementation Phases

### Phase 1: Protocol Correctness (P0) [Paper: §4.1, §4.2, §5.1, §5.2, §5.3]
- Before editing coordinator code, read **Canonical codebase**, **Migrating from the current Python baseline**, **Fail-stop vs Byzantine-style quorum**, and **Round numbering** (sections above) so quorum sizing and `round-num` stay aligned with §5.2. Add and migrate tests per **Testing strategy** (section after Phase 4) alongside each deliverable.
- Recommended implementation order inside P0:
  - first implement single-term refinement + decision engine semantics (Figure 5 fast/slow paths),
  - then add term election/recovery machinery (`RequestVote`/`Vote`/`NewTerm`/`NewTermAck`).
- **Implementation slices (merge milestones):** Ship each slice as one logical PR (or tight commit series): **code + tests** per **Testing strategy**. Finish slice *n* before starting *n*+1 to avoid debugging election and refinement at once.
  1. **Types + config** — Validate `f ≤ ⌈(N−1)/2⌉`, single quorum **`R = N − f`**, round-number convention documented in module/state (Soln bootstrap vs first `RefmSet` = 1). Tests: invalid `f`, `R` parity for Round 0 vs Refm.
  2. **Quorum helpers** — Unique-agent counting, **leader self-included**, same **`R`** for Soln and Refm, timeout/missing agent slots. Tests: duplicate-id rejection, leader counts toward **`R`**.
  3. **Mock agent / task routing** — Deterministic agents dispatch **`task` → Soln**, **`RefmSet` / `R̄` → Refm** (no live LLM). Tests: scripted outputs for Figure 5 scenarios.
  4. **Decision engine module** — Stateful α (within-round) / β (across-round), **`R̄_prev`**, output **only** from previous round’s set when evaluating round **`i+1`**, no synthesis, no-α → bottom + stability reset, overturn + new-term reset rules. Tests: Lemma 2-style membership, negative “invented value” case, Figure 5 Case 1/2 transitions **in engine unit tests** (mock **`R̄`** lists).
  5. **Single-term coordinator** — Algorithm 1 inner loop only: Round 0 Soln quorum → broadcast `RefmSet` → collect Refm quorum → advance **`R̄`**, call decision engine each round, with **`RefmSet` guard** and **`Refm` round match** on leader. **No election yet.** Tests: end-to-end path with mocks from slice 3; coordinator + engine integration.
  6. **Election + NewTerm recovery** — `RequestVote` / `Vote` / `NewTerm` / `NewTermAck`, tie-break, **`round-num ← 1`**, no Round 0 after recovery except **all-bottom** extension. Tests: one vote per term, higher-term guard, recovery pick, negative cases from **Testing strategy** table.
  7. **P1 runtime (follows slice 6)** — `while r* == ⊥` primary loop, **`max_rounds`** backstop, **`round_timeout_ms`**, election timeout → **next term + retry**, fail-stop termination reasons, optional **`confidence_threshold`** gating. Tests: **Runtime / P1** and **Election timeout** rows.

- Replace one-shot proposal/vote rounds with paper-style iterative refinement:
  - Distinguish initial Soln collection phase (Round 0) from refinement rounds.
  - `Task -> Soln quorum -> RefmSet(r) broadcast -> Refm quorum -> RefmSet(r+1)`.
  - Round 0 Soln collection is bootstrap-only; after leader recovery in a new term, resume from recovered `RefmSet` (do not rerun Round 0).
- Ensure leader is a full participant (`forall a in A`) in both:
  - Round 0 Soln generation from task input,
  - refinement rounds from prior `RefmSet`.
  - quorum accounting includes leader's own Soln/Refm contribution (unique agents including leader).
- Add decision engine with explicit predicates:
  - `alpha`: within-round quorum over semantically equivalent outputs in one `R_bar` (default methods: exact match and/or embedding similarity).
  - `beta`: across-round candidate persistence over consecutive refinement sets (default methods: exact match and/or LLM-as-judge).
  - Decision engine must be stateful across rounds and retain at least:
    - previous refinement set `R_bar_prev`,
    - candidate key/value,
    - stability counter.
  - Stability reset rules:
    - reset on term change,
    - reset-to-1 on candidate overturn mid-term.
  - No-alpha-support behavior (explicit):
    - if no value reaches `alpha` support in current round, candidate becomes bottom and stability counter resets to 0.
- Introduce term-based leadership and recovery:
  - `RequestVote`, `Vote`, `NewTerm`, `NewTermAck`.
  - New leader reconstructs state from quorum acks using paper tie-break order:
    - highest `term-num`, then highest `round-num` on ties.
  - After selecting recovered state, new leader sets `round-num = 1` for the new term before first broadcast.
  - Recovery fallback when all selected `NewTermAck` states have `RefmSet = bottom`:
    - run fresh Round 0 Soln collection for that term.
  - Election safety rules:
    - each agent casts at most one `Vote` per term,
    - candidate votes for itself,
    - agents grant vote only on strictly higher `term-num` with correct role/term transitions.
- Validate protocol fault-bound invariant at runtime:
  - enforce paper bound `f <= ceil((N-1)/2)` for configured `N`.
  - use one quorum size `R = N - f` consistently for Round 0 Soln and all Refm quorum collection.
- Enforce monotonicity rule:
  - paper rule: engine decides at round `i+1` using newly received evidence but may output only from stored previous refinement set `R_bar_i`.
- Enforce message-order/round integrity:
  - per-agent `RefmSet` update accepted only if incoming `round-num >= local round-num`,
  - leader counts `Refm` quorum only when `refm.round-num == leader.round-num`.
- Enforce leader output invariants:
  - only leader may emit committed protocol output,
  - leader emits at most one committed output per round.
  - (§4.1) Multiple outputs over the full run are allowed when monotonicity holds — each commit is separate in time; serial commits must not violate provenance/monotonicity rules.

### Phase 2: Runtime Enforcement and Safety (P1) [Paper: §4.1 fail-stop/partial synchrony, §5.2 decision engine/election behavior, §5.3 correctness conditions]
- Activate currently declarative controls:
  - make `while r* == bottom` (decision-driven) the primary loop condition.
  - keep `max_rounds` as a safety backstop only (liveness guard), not primary convergence logic.
  - enforce `round_timeout_ms`.
  - leader election (§5.2): if election does not complete before timeout, **increment term** and **retry** leader election (fail-stop / partial synchrony model); align with paper “time out, advance to next term, retry.”
  - enforce `confidence_threshold` for individual output/vote eligibility.
  - emit precise fail-stop termination reasons (`consensus`, `timeout`, `max_rounds`, `error`).
  - keep `byzantine_failure` label as reserved/deferred for future Byzantine-fault extension only.
- Add explicit protocol phases and commit artifacts:
  - phase transitions: proposal/refinement/decision/commit.
  - commit certificate metadata for auditability and replay.
- Monotonicity guard implementation detail:
  - guard by protocol provenance ordering (term/round progression and previous-set output rule), not direct quality oracle comparison.

### Phase 3: Production API Cost and Latency Reduction (P2) [Paper: §5.2 decision-driven termination, §7.2 and §7.4 efficiency outcomes]
- Optimize only what is controllable at production API level:
  - early termination once `alpha` equivalent and `beta` stable,
  - parallel dispatch of agents per round,
  - skip launching next round when decision engine already finalized.
- API cancellation note: cancellation is best-effort for wall-clock latency control and orchestration progress; it does not guarantee provider-side compute/token reclaim.
- Treat these as orchestration-level controls (not serving-engine internals).

### Backlog: Serving Layer Optimizations (Deferred) [Paper: §6.1-§6.3 Aegean-Serve]
- Defer low-level serving-engine optimizations until after production API path is stable.
- Backlog items:
  - aggressive in-flight straggler cancellation with infrastructure-level resource reclamation,
  - token-streaming quorum evaluation at serving layer,
  - collective admission controls,
  - ensemble-aware preemption with alpha-survivorship checks,
  - KV cache reservation hints and eager memory reclaim directives.
- Near-term approach (production APIs): use API-capability-aware fallbacks (streaming when available, completion-based incremental quorum otherwise).

### Phase 4: Paper-Focused Validation (P2) [Paper: §5.3 proofs, §7.1-§7.4 experimental setup/results]
- Build benchmark harness against fixed-round majority baseline.
- Use paper default evaluation configuration unless a test explicitly overrides it:
  - `n=3`, `alpha=2`, `beta=2`, `Tmax=5`.
- Report at least:
  - latency (avg, P99),
  - token usage,
  - output quality/accuracy,
  - overturn rate and stability progression.
- Run controlled parameter sweeps for `N`, `alpha`, `beta`.
- For direct paper comparability, include fixed-round majority baseline sweep with `MaxRound in {4, 5, 6}`.
- **Optional §7.1 parity:** Poisson arrivals over request rate (as in the paper’s load experiments) — not required for first harness; add when reproducing Figure 7–8 style congestion results.
- Add proof-aligned invariant tests (must pass independently of benchmark metrics):
  - monotonicity (Lemma 1-style),
  - refinement validity (Lemma 2-style, output drawn from valid refinement sets),
  - refinement termination (Lemma 3-style under healthy partial synchrony assumptions in test harness).
  - Include explicit fixtures for partial synchrony assumptions: bounded message delay, bounded reasoning time, and at most `f` failures.

## Testing strategy (cover all new code)

**Goal:** Every behavior introduced for paper Aegean has **automated tests** at the right layer (unit → coordinator integration → proof-style). Tests should fail when **`f` / quorum / round-num** regress to legacy Byzantine-style assumptions.

### Principles
- **Co-locate coverage with features:** New modules (`decision_engine`, message handlers, election state, etc.) land with tests in the same PR/commit series as the implementation; avoid merging protocol logic without assertions.
- **Deterministic first:** Prefer pure-function tests for quorum math, tie-breaks, guards (`incoming round-num >= local`), and decision-engine transitions; use **mock agents** with scripted outputs (no live LLM) for `protocol.py` flows.
- **Migrate or delete legacy tests** that encode the old shim: **`3f+1` minimum agents**, **`⌈(N+f+1)/2⌉`** expectations, leader-only proposal + `vote-` task-id mocks **unless** updated to Soln/Refm/RefmSet semantics.
- **Coverage tooling (recommended):** Add `pytest-cov` (or equivalent) to `dev` dependencies and run on CI over `aegean/` + `tests/` with a stated threshold once the new suite stabilizes (avoid chasing percentages before types stabilize).

### Related repos (optional inspiration — not canonical)
Use these for **layout, harness ideas, or dataset shape** only. **Paper + this plan** remain the source of truth for `f`, `R = N − f`, and message semantics; do not copy conflicting quorum or decision rules without reconciling them.

| Location | What to borrow | Caveat |
|----------|----------------|--------|
| [aegean-consensus/tests/README.md](c:\Relevant\OMSCS\AI_8903\code-projects\aegean-consensus\tests\README.md) | Documented **pytest** layout (`unit/`, `integration/`, `e2e/`, `fixtures/`), `pytest --cov`, async coordinator example snippets | The `tests/` tree may be **scaffold-only** (no test modules checked in yet). Prefer this README for **directory conventions** and **run commands**. |
| [aegean-consensus/src/aegean/core/](c:\Relevant\OMSCS\AI_8903\code-projects\aegean-consensus\src\aegean\core\) (`decision_engine.py`, `models.py`, `agent.py`) | **Naming** (`DecisionEngine`, `Solution`, stability counter), separation of coordinator vs engine | Implementation details (e.g. how α vs `quorum_size` is defined) may **differ** from this plan — **diff before porting** any logic. |
| [nexus-agents/test-fixtures/](c:\Relevant\OMSCS\AI_8903\code-projects\nexus-agents\test-fixtures) (e.g. `atbench-smoke.jsonl`) | **Line-oriented or smoke** benchmark inputs if you add an external eval runner alongside pytest | Not Aegean protocol fixtures; use for **bench wiring** only. |
| [nexus-agents/testing/datasets/](c:\Relevant\OMSCS\AI_8903\code-projects\nexus-agents\testing\datasets) (e.g. `pr-review-sample.json`) | **Curated JSON** pattern: versioned dataset, entries with metadata, repeatable scenarios | Content is **PR-review / agent eval**, not consensus rounds — reuse the **schema discipline** (provenance, methodology field) for golden protocol traces if useful. |

### By codebase area (what to add)

| Area | Test focus |
|------|----------------|
| **`types.py` / config** | **`f ≤ ⌈(N−1)/2⌉`** rejection; **`R = N − f`**; invalid configs; new dataclasses (`Soln`, `Refm`, `RefmSet` payloads, term/round fields) serialize/reconstruct safely where relevant. |
| **Quorum helpers** | Unique-agent counting including **leader self-contribution**; **`R`** identical for Round 0 Soln and Refm rounds; straggler/timeout slots excluded consistently. |
| **Per-agent state** | **RefmSet update guard** (`incoming round-num >= local`); local **`refmset`** / **`round-num`** after each message type. |
| **Leader aggregation** | **Refm quorum only when `refm.round-num == leader.round-num`**; stale or duplicate agents handled without double-counting. |
| **Decision engine** | **α** equivalence bucketing within one **`R̄`**; **β** consecutive-round stability (**Figure 5 Case 1:** stable candidate across rounds; **Case 2:** overturn resets counter per plan); **output drawn only from previous round’s refinement set** when acting on round **`i+1`** evidence; **no synthesis**; **bottom / no-α** resets stability as specified; **β reset on new term** and **on candidate overturn**. |
| **Election / recovery** | **RequestVote** only on strictly higher term; **at most one Vote per term per agent**; **candidate self-vote**; **NewTermAck** tie-break (**term**, then **round**); **`round-num ← 1`** after recovery before first **RefmSet**; **no Round 0 after recovery** except **all-bottom fallback**. |
| **`protocol.py` coordinator** | End-to-end single-term: Task → Soln quorum → RefmSet/Refm loop until decision or max-round backstop; **Figure 5 Case 1 (fast path):** stable majority for two consecutive rounds with `β=2`; **Figure 5 Case 2 (slow path):** overturn resets stability counter then finalizes after two consecutive rounds on new candidate; leader-change scenario with deterministic mocks. |
| **Events / telemetry** | If event payloads change for new phases, extend **`test_aegean_events.py`** (or successor) so topics/payloads stay stable for downstream consumers. |
| **Runtime / P1 controls** | **`while r* == ⊥` vs `max_rounds`:** decision path terminates before backstop when engine returns; backstop fires when engine never finalizes; **`round_timeout_ms`** marks non-responding agents and still respects **`R = N − f`** where applicable; **`confidence_threshold`** excludes low-confidence votes/slots from α bucketing; termination reasons limited to fail-stop set (`consensus`, `timeout`, `max_rounds`, `error`) — no `byzantine_failure` on fail-stop path. |
| **Election timeout (`p1-election-timeout-next-term`)** | Deterministic test: simulated no-quorum / election stall → **term increments** → **retry** RequestVote/Vote until leader or outer abort; no duplicate Vote in same term after successful grant. |
| **Commit semantics (`p1-commit-semantics`)** | Phase transitions (`proposal` / refinement / `decision` / `commit`) and **commit certificate** fields (term, round, chosen value provenance, supporting agent ids) parse/replay; monotonicity guard rejects out-of-order commit if you expose a replay API. |
| **Production API orchestration (`p2-inference-reduction`)** | **`asyncio.gather`** (or equivalent): all agents launched per round; when decision finalizes mid-round, **pending tasks cancelled** or not awaited (no deadlock); next round not started if `r*` already set; cancellation does not corrupt coordinator state. |

### Proof-aligned and regression tests (P1, required before calling P0 “done” for safety-critical paths)
- **Lemma 1-style:** At most one leader commit per refinement round; leader-only commit; ordering respects round/term progression under mocks.
- **Lemma 2-style:** Every emitted committed value is **present in** the legally selected refinement set (previous-round rule + membership).
- **Lemma 3-style / liveness smoke:** Under harness assumptions (bounded delay, no excess failures), run terminates with a decision or explicit **`max_rounds` / timeout** reason — no silent hang.

### Fixtures and mocks
- **Mock agent registry:** Dispatch on task/message kind (`task`, **`soln`**, **`refm`**, election prompts if surfaced as tasks) so integration tests do not depend on string hacks like **`vote-`** prefixes unless that remains the real API.
- **Failure injection:** Optional parametrized tests with **`f`** simulated timeouts/crashes (agents returning errors or missing) to validate quorum thresholds **`R = N − f`** without claiming Byzantine guarantees.
- **Negative / adversarial mocks (fail-stop only):** stale **`RequestVote`** (term ≤ local) must not grant vote; **duplicate agent id** must not double-count toward **`R`**; Refm with **wrong `round-num`** must not enter quorum; **RefmSet** with **lower `round-num` than local** must be ignored.
- **Decision engine negatives:** assert **no committed value** appears that was **not** an element of the legally selected prior **`R̄`** (including if a test double tries to inject a synthesized value).
- **Benchmark / load (Phase 4):** mark slow tests; default CI runs **unit + coordinator** tests; Poisson / high-load harness **opt-in** so PRs stay fast.

### Traceability: todos → tests
- **`p0-*`:** Each P0 item should map to **≥1** test in the table above (or one integration test explicitly listed in the PR until the suite stabilizes).
- **`p1-proof-invariant-tests`:** Lemma 1/2/3 bullets below; strengthen Lemma 2 with **membership** on every code path that emits **`r*`**.
- **`p1-runtime-controls`, `p1-election-timeout-next-term`, `p1-commit-semantics`:** Rows **Runtime / P1 controls**, **Election timeout**, **Commit semantics**.
- **`p2-inference-reduction`:** Row **Production API orchestration**; **`p2-benchmarks`:** Phase 4 harness (separate job from unit tests).

## Required Semantics Clarifications (Implement As Rules)
- Keep quality-oracle proxy inside decision engine only; agents do not consume quality scores directly.
- Keep parameter semantics separate:
  - `alpha` = equivalence-class quorum size,
  - `confidence_threshold` = per-output inclusion gate,
  - `beta` = consecutive-round stability horizon.
- Keep equivalence semantics split by purpose:
  - `alpha` (within-round): exact-match/embedding-based equivalence among values inside one refinement set.
  - `beta` (across-round): exact-match/LLM-as-judge equivalence of candidate across consecutive rounds.
- Keep round semantics explicit:
  - Round 0 = Soln quorum bootstrap from task input.
  - Rounds >= 1 = Refm rounds from prior `RefmSet`.
  - After leader change/recovery in new term: no new Round 0; continue from recovered `RefmSet`.
- Equivalence evaluation methods must be configurable and explicitly include:
  - exact match,
  - embedding similarity threshold,
  - LLM-as-judge.
- Refinement monotonicity (§4.1): the protocol may emit **more than one** committed solution over the lifetime of a run (across rounds/terms); **per refinement round**, the leader commits **at most once** (Lemma 1).

## Deliverables
- Updated protocol/types/helpers implementing paper semantics.
- **Automated tests** covering all new and migrated behavior per **Testing strategy** above (unit, coordinator integration, proof-aligned); legacy tests updated or removed so CI encodes paper **`f`** / **`R`**, not the old shim.
- Benchmark scripts/reports showing inference reduction vs baseline (Phase 4).

## Deviation Notes (Explicit)
- `NewTermAck` all-bottom recovery fallback is an implementation extension for robustness:
  - if quorum recovery yields only `RefmSet = bottom`, run fresh Round 0 Soln bootstrap for that term.
  - when any non-bottom recoverable set exists, follow paper tie-break selection as primary behavior.
