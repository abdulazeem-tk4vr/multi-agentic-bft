# Bundle D — L1 scope and evaluation design

## L1 as alert queue worker

L1 is essentially an **alert queue worker**. Their entire job is:

### Core tasks

- Monitor the SIEM dashboard for incoming alerts
- Review each alert and decide — real threat or false positive
- Dismiss false positives with a justification note
- Escalate genuine alerts to L2 with a summary
- Follow predefined playbooks for known alert types
- Log every action taken in the ticketing system
- Basic containment on obvious threats — block an IP, disable an account

### What a typical shift looks like

```text
Alert fires
    ↓
Check severity level
    ↓
Look up the source IP / user / asset
    ↓
Compare against known signatures / playbook
    ↓
False positive → dismiss and document
Real alert    → escalate to L2 with notes
```

Repeat this hundreds of times per shift.

### What they don't do

- Deep forensic investigation — that's L2
- Threat hunting — that's L3
- Writing detection rules — that's L3
- Incident response leadership — that's L3

### Why it's automatable

Every single L1 task maps directly to your system:

| L1 task | Your system |
|--------|-------------|
| Monitor alert queue | Wazuh webhook trigger |
| Check source IP | Threat intel agent |
| Look up asset/user | Context agent |
| Compare to playbook | Wazuh rulebook baseline |
| Decide real vs false positive | Agent consensus verdict |
| Dismiss or escalate | Consensus action output |
| Document decision | `CommitCertificate` |

L1 is a decision and documentation job. Your system does both.

---

## Scope: L1 automation only

**In scope**

- Given an **existing** SIEM alert, decide: **true vs false positive**, coarse severity, **auto-dismiss vs escalate**, optional **low-risk** action proposal.
- Run **Aegean** (or compatible) deliberation; emit **`CommitCertificate`** for audit.

**Out of scope (for a tight first contribution)**

- Building a better log correlator than the SIEM.
- Full L2/L3 investigation automation (optional later).

## Baselines

| Layer | Baseline | Treatment |
|-------|----------|-----------|
| Detection | SIEM rules (e.g. Wazuh) | Same for both arms |
| Decision / response proposal | Rulebook / **active response** intent | Agent consensus output |

**Framing:** Wazuh is typically **stronger at fast deterministic detection** on known patterns; the research claim is narrower — **better contextual triage / response choice given the same alerts**, especially ambiguous or noisy cases.

## Datasets (*verify licensing and suitability*)

- **BOTS** (Splunk CTF-style): labeled scenarios — useful for **ground truth** comparisons.
- Other public IDS/SOC datasets (CIC-IDS, Mordor/OTRF, etc.) as needed.

## Metrics

**Triage**

- Precision / recall vs ground truth labels (TP, FP, FN).
- False positive **dismissal** rate where appropriate.

**Deliberation**

- Convergence rate; rounds to commit; timeout rate.
- **Herding proxies:** e.g. diversity of round-0 outputs vs final cluster (design-specific).

**Response** (harder)

- Define a **rubric** for “appropriate response” when labels are thin — methodology contribution.

## Mismatch workflow (rule vs agents)

```text
if baseline_action == agent_committed_action:
    log validated / high agreement
else:
    flag for review; compare both to ground truth when available
```

Use mismatch logs to study **who was right when they disagree** (alert type, novelty, severity).

## Implementation hints

- **Structured outputs:** e.g. `{ verdict, proposed_action, reasoning, confidence }` — **exact** match on `verdict` + `proposed_action`; **SAS** on `reasoning` inside `alpha_same` (see **`bundle-e-sas-mechanism.md`**).
- **Ablations:** exact-match vs SAS `alpha_same`; threshold sweeps — extra evaluation sections.
- **Integration:** webhook or poll → enqueue alert → one Aegean `execute` per alert (PoC).
- **Human gate:** high-impact actions always require approval regardless of consensus.
