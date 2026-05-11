# Aegean paper implementation — checklist

Working target: **paper-faithful fail-stop Aegean** in `aegean/` (`R = N − f`, refinement loop, term recovery, etc.). Source plan: *Paper Focused Aegean Plan* (P0–P2).

---

## Done

### Slice 1 — Types, quorum math, logging scaffold
- **`aegean/types.py`**: Module doc for **round numbering** (round 0 = Soln bootstrap; first RefmSet round = 1; NewTerm resets to 1). Paper **fail-stop** checks: `validate_failstop_fault_bound`, `max_failstop_faults_allowed`, **`calculate_quorum_size` → `R = N − f`** (replaces legacy `⌈(N+f+1)/2⌉`). `AegeanConfig.byzantine_tolerance` documented as paper **`f`**.
- **`aegean/logutil.py`**: `configure_aegean_file_logging`, `get_aegean_logger`, `aegean_log`; default file **`logs/aegean.log`** under package project root; **`logs/.gitignore`** for `*.log`.
- **`pyproject.toml`**: Setuptools **`packages.find.include = ["aegean*"]`** so `logs/` is not treated as a package.
- **Tests**: `tests/test_aegean_paper_config.py` (bounds, **R** parity, logging smoke); quorum helper/protocol tests updated for **`R = N − f`**.

### Slice 2 — Protocol startup (paper `f` / `N`, not `3f+1`)
- **`aegean/protocol.py`**: Removed **`max(3, 3f+1)`** minimum agent count. Startup uses **`validate_failstop_fault_bound(len(experts), f)`**; on failure returns `{"ok": False, "error": str(exc)}`. Logs **INFO** with `session_id`, **N**, **f**, **R** at run start; **WARNING** on validation failure. **`configure_aegean_file_logging()`** called from protocol **`__init__`** (deduped per log path in `logutil`).
- **Tests**: `test_rejects_failstop_f_above_paper_limit` (`test_aegean_protocol.py`); Byzantine e2e: **`test_rejects_when_f_exceeds_paper_failstop_bound`**, **`test_three_agents_f_one_is_allowed_under_paper_bound`** (replaces legacy “3 agents + f=1 must fail” expectation).

### Slice 3 — Quorum helpers (unique agents, same `R`)
- **`aegean/helpers_utils.py`**: **`dedupe_votes_by_agent_last_wins`** — one tally slot per `agent_id` (later vote wins); duplicate ids logged at **WARNING** on **`aegean.quorum`**. **`evaluate_quorum_status`** tallies on deduped votes so duplicate entries cannot inflate accepts toward **`R`**. Same **`calculate_quorum_size(N,f)`** path for every call (round-0 Soln and future Refm phases).
- **`aegean/__init__.py`**: Re-exports **`dedupe_votes_by_agent_last_wins`**.
- **Tests** (`test_aegean_helpers_utils.py`): dedupe / last-wins, duplicate accept not double-counted, leader accept in tally, same **`required`** across repeated helper calls.

---

### Slice 4 — Task routing & scripted agent (no LLM)
- **`aegean/task_routing.py`**: **`aegean_task_phase`** / **`refinement_context`** read **`context["aegean"]`**. **`build_soln_task`** tags round‑0 Soln work; **`build_refm_task`** builds Refm prompts with **`refinement_set`**, **`term_num`**, **`round_num`**.
- **`aegean/mocks/scripted_agent.py`**: **`ScriptedAegeanAgent`** mock implementation that branches on phase (fixed values or callables).
- **`aegean/__init__.py`**: Re-exports routing helpers + **`ScriptedAegeanAgent`**.
- **Tests**: `tests/test_aegean_task_routing.py`.

### Slice 5 — Decision engine (α / β, **R̄_prev** gate, term & overturn)
- **`aegean/decision_engine.py`**: **`DecisionEngine`** with **`alpha_same`** / **`beta_same`** (default equality). **`step(r_bar_prev= R̄_i, current_round_outputs=…)`** only admits candidates **∈ R̄_prev** with an α-quorum cluster; **β** consecutive stability; overturn sets **`stability` → 1**; no α support → **`stability` 0**, no candidate; **`on_new_term`** clears β state. **`cluster_by_alpha_equivalence`** exposed for tests.
- **Tests**: `tests/test_decision_engine.py` (Figure 5–style fast path + overturn, Lemma 2 membership, **`β=1`**, custom α).

### Slice 6 — Single-term paper coordinator (Soln quorum → Refm + engine)
- **`aegean/types.py`**: **`AegeanConfig.alpha`**, **`AegeanConfig.beta`** (defaults **2**).
- **`aegean/protocol.py`**: **`execute`** runs **round 0 Soln** then **Refm** iterations with **`DecisionEngine`**; **`term_num`** is **1** for normal runs or the recovered term when runtime **`config["new_term_ack_provider"]`** yields non-bottom acks; **`build_refm_task`** uses that **`term_num`**.
- **`tests/aegean_test_utils.MockAgent`**: **`refm_output`**, branches on **`aegean_task_phase`**.
- **Tests**: protocol, quorum, multiround, leader, byzantine suites updated for Soln/Refm + shared **R̄** values so α/β can commit.

### Slice 7 — Election / NewTerm recovery (library + coordinator hook)
- **`aegean/types.py`**: **`REFM_BOTTOM`**, **`is_refm_bottom`**, **`NewTermAckPayload`**, **`RequestVoteMessage`**, **`VoteMessage`**.
- **`aegean/election.py`**: **`request_vote_granted`**, **`LocalElectionState`** (one vote per term), **`select_recovery_ack`** / **`recovery_acks_all_bottom`**, **`as_refinement_list`**, **`new_term_ack_from_mapping`**, **`refm_set_update_allowed`** (incoming **round-num ≥ local**).
- **`aegean/protocol.py`**: Runtime recovery source is **`config["new_term_ack_provider"]`** (hard-cut, no config `recovery.acks` fallback). Non-bottom acks → **skip Round 0 Soln**, **`term_num`** from winning ack, first Refm uses **`round_num = 1`**; **`build_refm_task`** uses run **`term_num`**. All-bottom/no acks → **fresh Soln**. **`|R̄| < R`** after recovery → **`recovery_insufficient_bar`**, no rounds.
- **`aegean/__init__.py`**: Re-exports recovery / election / **REFM_BOTTOM** symbols.
- **Tests**: `tests/test_election.py`, `tests/test_recovery_protocol.py`.

### Slice 8 — RequestVote quorum gate, Refm round alignment, events (α / β)
- **`aegean/election.py`**: **`request_vote_quorum_reached`** simulates **RequestVote** grants until **R = N − f**, with optional **`initial_local_terms`** (`agent_id → persisted term`) so agents with **local term ≥ candidate term** deny the vote.
- **`aegean/refinement_state.py`**: **`PerAgentRefmRoundTrack`** — per-agent **RefmSet** broadcast round monotonic guard (reject **`incoming < last_accepted`**; same-round replay accepted).
- **`aegean/task_routing.py`**: **`refm_task_matches_round`** — Refm task **`round_num`** vs leader round.
- **`aegean/protocol.py`**: After leader resolution, enforces RequestVote quorum for **`(term_num, leader_id)`**; optional **`config["election_initial_terms"]`** for simulation / persisted terms. Refm collection checks **`refm_task_matches_round`** and **`PerAgentRefmRoundTrack`** before **`execute`**.
- **`aegean/events.py`**: **`emit_protocol_started`** includes **`alphaQuorum`** / **`betaStability`**; config keys use **`.get`** with defaults.
- **Tests**: `tests/test_election.py`, `tests/test_refinement_state.py`, `tests/test_aegean_task_routing.py`, `tests/test_aegean_protocol.py`, `tests/test_aegean_events.py`.

### Slice 9 — RequestVote → Vote election simulation (in-process)
- **`aegean/election.py`**: **`ElectionSimulationResult`**, **`local_election_states_for_experts`**, **`simulate_leader_election`** (RequestVote broadcast → term adoption → per-grantor **Vote**); **`LocalElectionState.grant_request_vote`**. **`request_vote_quorum_reached`** remains a cheap RV-only check (no term adoption / votes).
- **`aegean/protocol.py`**: Pre-flight leader check uses **`simulate_leader_election`** and **`has_vote_quorum`** (aligns coordinator with the full message pass).
- **Tests**: election simulation + **`local_election_states_for_experts`**; Refm track vs **`refm_set_update_allowed`** ordering; protocol error assertion updated for election failure wording.

### Slice 10 — `round_timeout_ms`, `confidence_threshold`, `CommitCertificate`
- **`aegean/types.py`**: **`CommitCertificate`** (term, refinement round, leader, value, **R**, α, β, supporting Refm agent ids). **`AegeanResult.commit_certificate`** optional, set on consensus. Refm rows use ``phase="refinement"`` (legacy ``"voting"`` in type union) with optional **decision** snapshot fields; on **consensus** the coordinator appends a **commit** phase row at the same refinement index carrying the chosen value.
- **`aegean/protocol.py`**: Per-round wall-clock join via **`concurrent.futures.wait`** (**`round_timeout_ms`** applies to the whole Soln collection and each Refm round). **`metadata.confidence`** (default **1.0**) must be ≥ **`confidence_threshold`** for a tally accept; otherwise the slot is excluded from quorum and from **`DecisionEngine`** inputs. Stragglers canceled after the deadline; **`termination_reason`** **`timeout`** when any round hit the wall clock and the run did not finish with **`consensus`** (and was not canceled). On **`consensus`**, the leader records **`CommitCertificate`** from the committing Refm round.
- **`tests/aegean_test_utils.MockAgent`**: optional **`confidence`** in **`metadata`**.
- **`aegean/commit_semantics.py`**: **Replay / monotonicity** — :func:`~aegean.commit_semantics.validate_aegean_result_replay` (phase graph **proposal → refinement[*] → optional commit**, Lemma 2 **R̄** check), :func:`~aegean.commit_semantics.assert_certificate_chain_monotonic` for an append-only certificate log, :func:`~aegean.commit_semantics.commit_certificate_to_mapping` / ``from_mapping`` for JSON-stable audit export.
- **Tests**: **`tests/test_runtime_commit_certificate.py`**, **`tests/test_commit_semantics.py`**.

### Slice 11 — Networked **RequestVote** / **Vote** RPC (HTTP JSON)
- **`aegean/election_transport.py`**: **`ElectionMessenger`** protocol, **`InProcessElectionMessenger`**, **`run_election_with_messenger`** — shared election pass used by **`simulate_leader_election`** and remote transports.
- **`aegean/election_http.py`**: **`ThreadingHTTPServer`** peers with **`POST /aegean/request_vote`** and **`POST /aegean/vote`** (JSON); **`HttpElectionMessenger`**, **`http_cluster_for_experts`**, **`shutdown_servers`**, **`start_threading_election_server`** (stdlib only).
- **`aegean/protocol.py`**: Optional **`config["election_messenger"]`**; if set, leader election uses RPC (remote **`LocalElectionState`** must match **`election_initial_terms`** semantics).
- **`aegean/__init__.py`**: Re-exports transport + HTTP helpers.
- **Tests**: **`tests/test_election_http.py`**.

### Slice 12 — Adversarial **RefmSet** integration tests
- **`aegean/protocol.py`**: Optional **`config["refm_round_track_init"]`** — map **`agent_id → last_accepted_broadcast_round`** to seed :class:`~aegean.refinement_state.PerAgentRefmRoundTrack` (persisted multi-term / stale-delivery scenarios).
- **`aegean/refinement_state.py`**: Module note for coordinator seeding.
- **Tests**: **`tests/test_adversarial_refm_round_track.py`** (high-water rejects round 1, mixed persistence below **R**, matching seed + β path, recovery + stale tracks).

### Slice 13 — Election stall → next term
- **`aegean/types.py`**: **`AegeanConfig.max_election_attempts`** (default **32**) — cap on distinct **term** values tried for RequestVote/Vote.
- **`aegean/protocol.py`**: On missing Vote quorum, log stall, **`attempt_term += 1`**, retry with same **`election_states`** / **`election_messenger`**; optional per-run **`config["max_election_attempts"]`** override. Resolves **`term_num`** to the winning attempt. Start log includes **`max_election_attempts`**.
- **Tests**: **`tests/test_election_stall_retry.py`** (terms 2→success at 3; exhaust small cap vs high persisted terms).

### Slice 14 — Lemma-style proof / invariant tests
- **Tests**: **`tests/test_proof_invariants.py`** — Lemma 2-style **R̄** validity (**`committed_value ∈`** prior **`Proposal.value`** for the committing refinement round); Lemma 1-style **≤1** **`protocol.iteration` / converged** per successful run; **`CommitCertificate.leader_id`** matches session leader and all recorded rounds; recovery **`leader_id`** / **`term_num`** on certificate; explicit **`termination_reason`** / duration; supporting Refm ids ⊆ experts and **≥ quorum_size_r**.

---

### Slice 15 — P2 benchmarks and inference reduction
- **`aegean/benchmark.py`**: **Fixed-round majority** token proxy (**N×Soln + max_ref_rounds×N×Refm**); :func:`~aegean.benchmark.count_refinement_rounds`; :func:`~aegean.benchmark.inference_reduction_vs_fixed_schedule` / :class:`~aegean.benchmark.InferenceReductionReport` vs analytic upper bound; :func:`~aegean.benchmark.summarize_for_logging`.
- **`aegean/__init__.py`**: Re-exports benchmark helpers.
- **Tests**: **`tests/test_benchmark_inference_reduction.py`**.

---

### Slice 16 — Production adapters (generic HTTP + OpenRouter)
- **`aegean/adapters/http_agent.py`**: **`HttpAgent`** generic remote `POST` adapter (stdlib `urllib`), expects protocol-compatible JSON response shape.
- **`aegean/adapters/openrouter_agent.py`**: **`OpenRouterAgent`** adapter for OpenRouter chat completions with usage-to-`tokens_used` mapping.
- **`aegean/adapters/base.py`**: **`ok_result`** / **`error_result`** helpers for writing custom adapters consistently.
- **`aegean/__init__.py`**: Re-exports adapter classes and helper result builders.
- **Tests**: **`tests/test_adapters.py`**.

---

## How to verify

```bash
cd code-projects/multi-agentic-bft
py -3 -m pip install -e ".[dev]"
py -3 -m pytest tests -q
```

Log output (when a protocol instance is created): **`logs/aegean.log`** at repo root of `multi-agentic-bft`.
