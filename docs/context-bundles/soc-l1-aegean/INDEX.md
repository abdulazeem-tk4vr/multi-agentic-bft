# Context bundles: SOC L1 automation × Aegean consensus

**Location:** `docs/context-bundles/soc-l1-aegean/`  
**Code reference:** `code-projects/multi-agentic-bft/` (`AegeanProtocol`, `DecisionEngine`, `task_routing`)

## Reading order

1. **`bundle-a-aegean-protocol.md`** — How the library actually runs (quorum, R̄, α/β, commit).
2. **`bundle-e-sas-mechanism.md`** — SAS for semantic `alpha_same` (reasoning), exact structured fields, α+β commit stack, SBERT options.
3. **`bundle-b-soc-primer.md`** — SOC vocabulary (SIEM vs SOAR, what analysts do).
4. **`bundle-c-integration-mapping.md`** — How to plug alerts/agents into Aegean-shaped tasks.
5. **`bundle-d-l1-scope-evaluation.md`** — L1 as alert-queue worker, scope, and evaluation design.

**Meta:** `SOC-PLAN.md` describes how these bundles are split and maintained. **`PLAN-OF-ACTION.md`** is the sequenced roadmap (validate → SAS → SOC).

## One-line thesis

Use **Wazuh (or similar)** for **detection**; use **multi-agent deliberation with a quorum + stability commit** (Aegean) for **post-alert L1 triage**, with **SAS-augmented `alpha_same`** on reasoning and **exact** structured verdict/action — compare to rule-based active response on labeled data.
