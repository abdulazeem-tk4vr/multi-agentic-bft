# References — Aegean semantic equivalence layer

This file maps the **semantic equivalence design** (SimCSE + HDBSCAN + semantic voting + weighted stability) to the code in [`aegean/semantic_equivalence.py`](../aegean/semantic_equivalence.py) and [`aegean/protocol.py`](../aegean/protocol.py). When `AegeanConfig.semantic_equivalence` is `None` or `enabled=False`, the run uses the legacy **exact-match** α/β engine (`DecisionEngine` with `==` on outputs).

## Design steps vs implementation

| Step | Design | Implementation |
|------|--------|----------------|
| **1 — Conclusion** | Strip reasoning; keep a **final answer** string; later steps use conclusions only. | `extract_conclusion()`; SimCSE / `semantic_encode_fn` encodes **conclusions** only, not full raw traces. |
| **2 — Embed** | SimCSE locally (Gao et al., 2021). | `SimCSEEmbedder.encode_conclusions` or injected `session_cfg["semantic_encode_fn"]` (`Callable[[list[str]], ndarray]]`) for tests/offline embeddings. |
| **3 — Cluster** | HDBSCAN (Malzer & Baum, 2020); `min_cluster_size` tied to **α** (clamped to accept count, minimum 2); dominant / minority / noise. | `_effective_hdbscan_mcs`; `_hdbscan_labels` with `allow_single_cluster=True`; `n≤1` accepts skip HDBSCAN and use a single trivial cluster (HDBSCAN requires `min_cluster_size≥2`). |
| **3b — All-noise fallback** | If every label is `-1`, treat all accepts as one pseudo-cluster so refinement can continue. | `(labels == -1).all()` branch sets `dominant_idx = range(n)`. |
| **4 — α quorum / skip** | If `len(dominant) < α`: skip the decision update; route all conclusions as dissent. | `len(dominant_idx) < alpha` → `skip_round=True`, `SemanticStabilityTracker.apply_round(skip=True)` (no score/candidate mutation), `round_dissent` = deduped all conclusions. |
| **4b — R̄_prev gate** | Admissible SV winner must appear in prior refinement set (paper safety). | Eligible outputs restricted to `o in set(r_bar_prev)` before picking max SV; if none → same skip path as (4). |
| **5 — SV** | \(SV(i)=\frac{1}{|C|-1}\sum_{j\neq i}\mathrm{sim}(a_i,a_j)\); highest among **R̄_prev**-eligible wins (Jiang et al., 2026). | `_sv_scores_for_dominant`; **\(|C|=1\)** → `SV=1.0` (no divide-by-zero). Tie-break: higher SV, then `_sort_key(output)` lexicographic. |
| **6 — Share back** | Dominant winner as **reference**; minority + noise as **dissent** (MSR / FDI analog; Ishii & Feng, 2022; Pasqualetti et al., 2010; Ruan et al., 2025). | `build_refm_task(..., reference_answer=...)` adds an explicit **Semantic reference** block on non-skip rounds with an eligible candidate. `dissenting_context` lists minority-cluster reps + HDBSCAN noise conclusions (see noise policy below). |
| **7 — Weighted stability** | Reset score to `0.0` on candidate change, then add `sum(SV)/N` atomically; finalize when `≥ stability_score_threshold` (Zhang et al., 2021; Ruan et al., 2025). | `SemanticStabilityTracker.apply_round`; `DecisionStepResult.stability_score`; integer `stability` is `0` on skip else `1` for traces (granular signal is the float score). |
| **7b — Term boundaries** | β-like state does not cross **term**. | `SemanticStabilityTracker.on_new_term(term_num)` mirrors `DecisionEngine.on_new_term`. |
| **8 — Tmax fallback** | Structured `no_consensus` when ending without commit under `max_rounds` / `timeout`. | `SemanticSessionAccumulator.to_no_consensus_payload` → `AegeanResult.semantic_no_consensus` (`status`, `rounds_completed`, `candidate`, `confidence`, `cluster_results`, `minority_signals`, last-round diagnostics). |

### Noise policy (small vs large ensembles)

| `SemanticEquivalenceConfig` | Default | Role |
|------------------------------|---------|------|
| `discard_noise_from_dissent` | `False` | When `False`, HDBSCAN noise (`-1`) conclusions are included in dissent (valuable for **N < 10**). |
| `min_agents_to_discard_noise` | `10` | If `discard_noise_from_dissent` is `True` **and** `N ≥` this value, noise rows are omitted from dissent. |

**Norm-based σ filtering (Yeo & Lee, 2025)** is **not** implemented in this release; outliers are handled via HDBSCAN labels, dissent routing, and the all-noise fallback. The citation remains relevant for optional future work.

### Parameters (defaults)

| Parameter | Code / default | Note |
|-----------|----------------|------|
| **α** | `AegeanConfig.alpha` (default **2**) | Minimum dominant-cluster size to run SV + stability update. |
| **Stability threshold** | `SemanticEquivalenceConfig.stability_score_threshold` (default **2.0**) | Weighted horizon replacing integer **β** for semantic mode. |
| **HDBSCAN `min_cluster_size`** | `hdbscan_min_cluster_size: None` | **`None`** → `min(max(2, α), len(accepts))`. Set an `int` to override. |
| **Tmax** | `AegeanConfig.max_rounds` | Same as legacy path. |

**Latency:** SimCSE “~20ms on CPU” is order-of-magnitude design guidance; not asserted in unit tests.

**Dependencies:** `pip install 'multi-agentic-bft[semantic]'` — `numpy`, `hdbscan`, `sentence-transformers`. Dev tests add `hdbscan` via `[dev]`. Tests set `session_cfg["semantic_encode_fn"]` to avoid HF downloads.

### Hugging Face models (SimCSE)

| Model | Approx. size | Notes |
|-------|----------------|------|
| `princeton-nlp/sup-simcse-bert-base-uncased` | ~110MB | Default; good latency on CPU. |
| `princeton-nlp/sup-simcse-roberta-large` | ~355MB | Higher quality / cost. |

Both are MIT-licensed checkpoints usable from `sentence-transformers`.

## Bibliography

- Gao, T., Yao, X., & Chen, D. (2021). SimCSE: Simple Contrastive Learning of Sentence Embeddings. *EMNLP*.

- Ishii, H., & Feng, S. (2022). Multi-agent consensus under adversarial attacks. *Annual Reviews in Control*.

- Jiang, J., et al. (2026). Semantic Voting. *ICLR 2026*. (Confirm final proceedings metadata when citing.)

- Malzer, C., & Baum, M. (2020). HDBSCAN: Hierarchical density based clustering of skewed and high dimensional data. *IEEE SSCI*.

- Pasqualetti, F., Bicchi, A., & Bullo, F. (2010). Consensus in Unreliable Networks. *IEEE Transactions on Automatic Control*.

- Ruan, Y., et al. (2025). Reaching Agreement Among Reasoning LLM Agents. *arXiv:2512.20184*.

- Yeo, D., & Lee, J. (2025). Norm-Based Outlier Filtering for Federated Learning. *IEEE Access*. (Optional future normalization — not implemented in this release.)

- Zhang, H., et al. (2021). Mixed aggregation functions for outliers detection. *Journal of Intelligent & Fuzzy Systems*.
