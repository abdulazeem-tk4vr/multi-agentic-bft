# Bundle C — Integration: SIEM / Wazuh × Aegean-shaped agents

## Data flow

```text
SIEM detects → alert payload → orchestration → Aegean session (agents) → committed decision (+ optional SOAR execution)
```

## What the SIEM hands off

Structured alert context, e.g. rule id, severity, entities (IP, user, host), timestamps, raw excerpts — **one payload** becomes the **base task** for every expert.

## Agent roles (example mapping)

| Expert id (example) | Role |
|---------------------|------|
| `triage` | Real vs false positive |
| `context` | Asset/user/business context |
| `threat_intel` | IOC enrichment interpretation |
| `response` | Proposed action / escalation |

Each implements `execute(task)` and returns protocol-shaped `value` (output + metadata confidence).

## Aegean ↔ SOC mapping

| Aegean | SOC |
|--------|-----|
| Experts | Specialised agents above |
| `build_soln_task` | Independent assessment of the alert |
| `build_refm_task` | Revise using peer outputs in **R̄** |
| **R̄** / `broadcast_bar` | Shared peer assessments + prior outputs |
| **α** | Enough agents agree on same **structured** decision class |
| **β** | Same winning decision persists across rounds |
| `CommitCertificate` | Audit record (who participated, round, committed fields) |
| `consensus_value` | Final L1 decision + proposed action (as structured object) |

## Wazuh-specific notes (*from discussion*)

- Ships with large **default rule set**; useful as **baseline** for comparison.
- **Active response** = rule-triggered **automated actions** — compare agent **proposal** to this baseline where appropriate.
- Rules live as XML under the server ruleset path in standard installs — useful **context** to attach to agent tasks.

## Leader choice

Map **leader** to the most trusted or **triage-first** agent in PoC; leader Soln failure → treat as **escalate / abort** (matches strict protocol behavior).
