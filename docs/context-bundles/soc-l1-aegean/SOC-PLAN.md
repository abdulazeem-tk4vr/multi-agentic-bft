# SOC plan: local context bundles (SOC × Aegean / L1)

## Goal

Preserve **durable, searchable** notes from the SOC workflow discussion and how it connects to **`multi-agentic-bft`** (Aegean-style coordinator), without depending on chat history.

## Bundle layout

| File | Purpose |
|------|---------|
| `INDEX.md` | Start here: links and reading order |
| `PLAN-OF-ACTION.md` | Sequenced roadmap: validate architecture → SAS → SOC L1 workflow |
| `SOC-PLAN.md` | How bundles are split and maintained (this file) |
| `bundle-a-aegean-protocol.md` | Aegean session behavior (Soln, Refm, α/β, commit) |
| `bundle-b-soc-primer.md` | SOC, SIEM, SOAR, analyst tiers (L1–L3) |
| `bundle-c-integration-mapping.md` | Data flow: SIEM → agents → decision; Aegean column ↔ SOC column |
| `bundle-d-l1-scope-evaluation.md` | L1 alert-queue worker definition, scope, Wazuh/BOTS baseline, metrics, mismatch logic |
| `bundle-e-sas-mechanism.md` | SAS (semantic agreement similarity) for `alpha_same`; SBERT/options; α+β commit stack |

## Conventions

- **Facts about this repo** (Aegean) stay aligned with `code-projects/multi-agentic-bft` source.
- **Product / market claims** (e.g. what vendors ship) are labeled *conversation notes* — verify before citing academically.
- When extending: add a new `bundle-*.md` or a dated addendum; bump `INDEX.md`.

## Maintenance

- After implementation milestones, add a short **Changelog** section to `INDEX.md` (date + what changed).
- Prefer updating an existing bundle over duplicating content across files.
