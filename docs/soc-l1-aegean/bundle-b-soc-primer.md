# Bundle B — SOC primer (conversation distill)

*Operational definitions only; verify vendor-specific details independently.*

## SOC (Security Operations Centre)

Central function: **monitor → detect → triage → respond → report** across logs, endpoints, network, cloud.

## SIEM (Security Information and Event Management)

- **Ingests** and **normalises** logs/events.
- **Correlates** (rules, searches) to raise **alerts**.
- **Stores** data for investigation and compliance.

## SOAR (Security Orchestration, Automation and Response)

- **Downstream of detection:** playbooks **act** on alerts (tickets, containment, enrichment APIs).
- Automation quality depends on **encoded playbooks** and maintenance.

## Where tooling sits vs agents

- **SIEM:** primarily **detection** and alert creation.
- **Agent system (this design):** primarily **post-alert** — triage, enrichment reasoning, response **proposal**, audit trail — not replacing high-throughput log correlation.

## Analyst tiers (typical)

| Tier | Focus |
|------|--------|
| **L1** | High-volume triage: real vs false positive, severity bucket, route or auto-close |
| **L2** | Deeper investigation, correlation, incident validation |
| **L3** | Hunt, major IR, new detection content |

**Current scope (project):** automate **L1**-class decisions with consensus; escalate on low confidence, mismatch, or policy.

## Evolution notes (*conversation / industry direction*)

Trends cited in discussion: AI-assisted triage, XDR-style unification, more automation — treat as background, not implementation requirements.
