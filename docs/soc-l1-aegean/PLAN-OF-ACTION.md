# Plan of action — architecture validation → SAS → SOC workflow

Ordered roadmap for `multi-agentic-bft` (Aegean) and the SOC L1 line of work described in this folder.

---

## Phase 1 — Prove the existing architecture works

**Goal:** Confidence that the current coordinator, quorum logic, refinement loop, and decision engine behave as intended before layering new mechanisms.

**Suggested work**

- Run the full **`multi-agentic-bft`** test suite (`pytest`) on a clean environment; fix any drift or env assumptions.
- Exercise **happy paths** with existing mocks (`aegean.mocks`): Soln quorum → at least one Refm round → **commit** when α/β and `max_rounds` allow (see `tests/test_aegean_*`).
- Spot-check **failure paths**: no Soln quorum, leader Soln failure, Refm quorum loss, `max_rounds` without commit, optional recovery / `refm_round_track_init` scenarios if relevant.
- Record **one** minimal "smoke" command sequence in a short note (or CI job) so regressions are obvious.

**Exit criteria**

- Tests green; at least one scripted e2e path from Phase 1 you can re-run after Phase 2 changes.

---

## Phase 2 — Add the SAS mechanism

**Goal:** Introduce **SAS (Semantic Agreement Similarity)** so `alpha_same` can treat **paraphrased reasoning** as agreement while keeping **verdict** and **proposed_action** **exact**. Full spec: **`bundle-e-sas-mechanism.md`**.

**Definition:** SAS scores similarity of **free-form reasoning** (e.g. cosine similarity on sentence embeddings). It plugs into **`alpha_same`**; it does **not** replace **α quorum** or **β stability** — commit is **SAS (within α clusters) + α + β** together, not similarity alone.

**Suggested work**

- Enforce **structured agent outputs** (`verdict`, `proposed_action`, `reasoning`, …) in adapters; document schema.
- Implement SAS backend (start with **`sentence-transformers`** + `all-MiniLM-L6-v2`, tunable cosine threshold); optional upgrade to `all-mpnet-base-v2` or BERTScore / API embeddings.
- Pass custom **`alpha_same`** (and typically **structured** **`beta_same`**) into **`DecisionEngine`**; keep **`r_bar_prev`** / Lemma-style gates unchanged unless the paper design says otherwise.
- Run **ablations:** exact-match `alpha_same` vs SAS-augmented; threshold sweeps; record rounds-to-commit and accuracy vs ground truth.
- Add **unit / integration tests** (embedding mock or small fixed vectors) so CI does not require heavy models unless opted in.

**Exit criteria**

- SAS documented (`bundle-e`), implemented behind a clear API, tested; Phase 1 smoke still passes or is explicitly updated.

---

## Phase 3 — SOC workflow (L1)

**Goal:** End-to-end **post-alert** flow: SIEM alert in → agents + Aegean (+ SAS if applicable) → structured L1 decision and audit trail.

**Suggested work**

- **Ingress:** webhook or poller (e.g. Wazuh → FastAPI or similar) producing a **canonical alert payload** and session id.
- **Agents:** `execute(task)` adapters with **structured outputs** (e.g. `verdict`, `proposed_action`, `confidence`) and custom equivalence for α/β if needed (see `bundle-d-l1-scope-evaluation.md`).
- **Orchestration:** one Aegean `execute` per alert (or batched where safe); map **leader** and **experts** per `bundle-c-integration-mapping.md`.
- **Baselines:** log **rulebook / active-response** intent alongside **consensus** for mismatch analysis (`bundle-d`).
- **Safety:** human gate for high-impact actions regardless of consensus.

**Exit criteria**

- Demo path: **synthetic or recorded alert** → committed or explicit non-commit outcome → `CommitCertificate` (or full `AegeanResult`) persisted; optional comparison row vs baseline.

---

## Sequencing

```text
Phase 1 (validate)  →  Phase 2 (SAS)  →  Phase 3 (SOC L1)
```

Do **not** start Phase 3 until Phase 1 is green. Phase 2 can be stubbed behind feature flags if you need parallel exploration, but avoid shipping SOC workflow without a clear SAS contract.

---

## References in this folder

| Doc | Use |
|-----|-----|
| `SOC-PLAN.md` | Bundle layout and maintenance |
| `bundle-a-aegean-protocol.md` | Protocol semantics |
| `bundle-c-integration-mapping.md` | SIEM → agents mapping |
| `bundle-d-l1-scope-evaluation.md` | L1 tasks, metrics, evaluation |
| `bundle-e-sas-mechanism.md` | SAS / semantic `alpha_same`, tooling, ablations |

**Code:** `code-projects/multi-agentic-bft/`
