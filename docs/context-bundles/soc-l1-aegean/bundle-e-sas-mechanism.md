# Bundle E — SAS mechanism (semantic agreement for α clustering)

**SAS** here means **Semantic Agreement Similarity**: a scoring function (typically cosine similarity between embeddings) applied to **free-form reasoning text** so that paraphrases can count as the **same** underlying position for **α** clustering, without requiring byte-identical strings.

**Problem it solves:** Default `==` in `DecisionEngine` treats *“block the source IP immediately”* and *“isolate the offending IP address”* as different outputs. For LLM agents, that hides **genuine consensus**. SAS is intended for the **reasoning** field; structured fields stay **exact**.

---

## Where SAS fits (`alpha_same`)

Agents should return **structured** outputs (controlled vocabulary / schema), e.g.:

- `verdict` — e.g. true positive / false positive (exact match)
- `proposed_action` — e.g. block / dismiss / escalate (exact match)
- `reasoning` — free-form explanation (SAS)

**Sketch:**

```python
def alpha_same(output_a, output_b, *, sas_fn, threshold: float) -> bool:
    similarity = sas_fn(output_a["reasoning"], output_b["reasoning"])
    return (
        output_a["verdict"] == output_b["verdict"]
        and output_a["proposed_action"] == output_b["proposed_action"]
        and similarity >= threshold
    )
```

- **Do not** run SAS on `verdict` / `proposed_action` — those should be **exact** so actions stay auditable and machine-checkable.
- **Do** run SAS on **reasoning** (or comparable narrative fields) where paraphrase is expected.

**β (`beta_same`):** Often keep **exact** comparison on the **chosen structured decision** (verdict + action, or a canonical JSON key subset) so “stability across rounds” means the **same committed decision class**, not cosine drift of prose. Project can experiment with SAS on reasoning for β only if the research question demands it; default recommendation is **structured β**, **SAS-assisted α**.

---

## Refined commit picture (design stack)

Treat final commit as satisfying **all** of:

1. **Semantic agreement on reasoning** — pairwise (or cluster-internal) SAS ≥ tuned threshold where `alpha_same` requires it.
2. **α quorum** — enough agents in the same equivalence class (per `DecisionEngine` clustering).
3. **β stability** — the **eligible** winning value stays stable for β consecutive refinement rounds (mitigates one-round herding / sycophancy).

**None of these alone** is intended to be sufficient: similarity-only commit without α/β would be weak; α without SAS misses paraphrase consensus; β reduces “lucky one-round agreement.”

---

## Implementation options (*practical*)

| Approach | Notes |
|----------|--------|
| **Sentence-BERT** (`sentence-transformers`) | Local, common default: `all-MiniLM-L6-v2` (fast); `all-mpnet-base-v2` if more accuracy needed. Cosine similarity between single-vector encodings of reasoning strings. |
| **BERTScore** | `bert-score` package; F1-style similarity on tokens/embeddings. |
| **Hosted embeddings** | OpenAI etc. — cost/latency tradeoff; good for experiments. |

**PoC default:** `SentenceTransformer('all-MiniLM-L6-v2')` + cosine similarity; expose **threshold** as a hyperparameter (e.g. sweep 0.75–0.90 against labeled data).

---

## Research / evaluation hooks

- **Ablation:** `alpha_same` with **exact match** (full output or reasoning string) vs **SAS-augmented** `alpha_same` (structured exact + SAS on reasoning).
- **Metrics:** rounds to commit, final decision accuracy vs ground truth (e.g. BOTS), false convergence rate.
- **Calibration:** threshold sensitivity analysis is an empirical contribution — task-specific optimum is not assumed (e.g. no fixed “90%” without tuning).

---

## Relation to literature-style framing (*conversation notes*)

External writeups often stress: **semantic similarity and aggregation** help when strings differ but meaning aligns; **multi-round** protocols add **stability** requirements so single-round similarity spikes do not trivially commit. This bundle aligns SAS with that pattern while keeping **Aegean’s α + β** as the backbone. Cite primary sources explicitly in any formal writeup.

---

## Code touchpoint

Wire SAS into **`DecisionEngine(..., alpha_same=...)`** in `code-projects/multi-agentic-bft` once agent outputs are structured dicts (or normalize to dicts in an adapter layer). See `bundle-a-aegean-protocol.md` for base protocol behavior.
