"""Semantic **α** via SimCSE embeddings + HDBSCAN, semantic voting (SV), and weighted stability.

Enabled when :class:`~aegean.types.AegeanConfig`.``semantic_equivalence`` has ``enabled=True``.
Requires optional install: ``pip install 'multi-agentic-bft[semantic]'`` (``numpy``, ``hdbscan``,
``sentence-transformers``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .decision_engine import DecisionStepResult
from .logutil import get_aegean_logger
from .types import SemanticEquivalenceConfig

_log = get_aegean_logger("semantic_equivalence")


def _sort_key(x: Any) -> tuple[str, str]:
    return (str(type(x).__name__), str(x))


def extract_conclusion(output: Any) -> str:
    """Best-effort final-answer string for clustering / SV (adapters may normalize further)."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output.strip()
    if isinstance(output, dict):
        for k in ("final_answer", "answer", "conclusion", "output"):
            if k in output and output[k] is not None:
                return str(output[k]).strip()
        return str(output).strip()
    return str(output).strip()


class SimCSEEmbedder:
    """Lazy Hugging Face Sentence-Transformer (SimCSE checkpoint)."""

    __slots__ = ("_model", "_model_name")

    def __init__(self, model_name: str) -> None:
        self._model_name = str(model_name)
        self._model = None

    def encode_conclusions(self, texts: Sequence[str]) -> Any:
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - exercised when extras missing
            raise ImportError(
                "Semantic equivalence requires optional dependencies. "
                "Install with: pip install 'multi-agentic-bft[semantic]'"
            ) from e
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        emb = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(emb, dtype=np.float64)


def _effective_hdbscan_mcs(alpha: int, n_accepts: int, override: int | None) -> int:
    if n_accepts <= 0:
        return 2
    if override is None:
        return min(max(2, int(alpha)), int(n_accepts))
    return min(max(2, int(override)), int(n_accepts))


def _l2_normalize_rows(mat: Any) -> Any:
    import numpy as np

    x = np.asarray(mat, dtype=np.float64)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return x / norms


def _sv_scores_for_dominant(norm_sub: Any) -> Any:
    """Mean cosine sim to other dominant points (SV); |C|=1 → [1.0]."""
    import numpy as np

    sim = norm_sub @ norm_sub.T
    d = int(sim.shape[0])
    if d == 1:
        return np.array([1.0], dtype=np.float64)
    np.fill_diagonal(sim, 0.0)
    return sim.sum(axis=1) / float(d - 1)


def _hdbscan_labels(emb_norm: Any, mcs: int, min_samples: int | None) -> Any:
    import hdbscan
    import numpy as np

    x = np.asarray(emb_norm, dtype=np.float64)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=int(mcs),
        min_samples=min_samples,
        metric="euclidean",
        allow_single_cluster=True,
    )
    return np.asarray(clusterer.fit_predict(x), dtype=np.int64)


def _dominant_label(labels: Any) -> int | None:
    """Largest non-noise cluster; tie-break smaller label id."""
    import numpy as np

    lab = np.asarray(labels, dtype=np.int64)
    best: int | None = None
    best_count = -1
    for L in sorted(set(lab.tolist())):
        if L == -1:
            continue
        c = int((lab == L).sum())
        if c > best_count:
            best_count = c
            best = int(L)
        elif c == best_count and best is not None and int(L) < best:
            best = int(L)
    return best


def _semantic_prev_gate(
    dominant_idx: list[int],
    conclusions: list[str],
    emb_norm: Any,
    prev_conclusions: list[str],
    encode_fn: Callable[[list[str]], Any] | None,
    embedder: SimCSEEmbedder,
    r_similarity_threshold: float,
) -> list[int]:
    """Return indices (within dominant_idx) whose conclusion is semantically close to any
    item in R̄_prev.  Falls back to exact-match inclusion so the gate is never stricter
    than the legacy mode.

    Uses cosine similarity on L2-normalised SimCSE embeddings.  Any dominant candidate
    that has max-sim ≥ ``r_similarity_threshold`` against the previous-round conclusion
    set is considered eligible.
    """
    import numpy as np

    # Fast path: exact match always qualifies (preserves original semantics exactly).
    prev_set = set(prev_conclusions)
    exact_eligible = {i for i in dominant_idx if conclusions[i] in prev_set}

    if not prev_conclusions:
        return list(exact_eligible)

    dom_texts = [conclusions[i] for i in dominant_idx]
    all_texts = dom_texts + prev_conclusions
    if encode_fn is not None:
        all_emb = np.asarray(encode_fn(all_texts), dtype=np.float64)
    else:
        all_emb = np.asarray(embedder.encode_conclusions(all_texts), dtype=np.float64)

    all_norm = _l2_normalize_rows(all_emb)
    n_dom = len(dominant_idx)
    dom_norm = all_norm[:n_dom]
    prev_norm = all_norm[n_dom:]

    # sim[i, j] = cosine(dom_i, prev_j)
    sim = dom_norm @ prev_norm.T
    max_sim = sim.max(axis=1) if sim.ndim == 2 and sim.shape[1] > 0 else np.zeros(n_dom)

    sem_eligible = {dominant_idx[i] for i in range(n_dom) if float(max_sim[i]) >= r_similarity_threshold}
    return sorted(exact_eligible | sem_eligible)


def run_semantic_decision_step(
    *,
    accepted: Sequence[tuple[str, Any]],
    r_bar_prev: Sequence[Any],
    alpha: int,
    n_experts: int,
    sem_cfg: SemanticEquivalenceConfig,
    embedder: SimCSEEmbedder,
    encode_fn: Callable[[list[str]], Any] | None,
    tracker: SemanticStabilityTracker,
) -> tuple[DecisionStepResult, list[str], bool, float]:
    """One refinement round: cluster → SV → **R̄_prev** gate → weighted stability update.

    Returns ``(decision, round_dissent, skip_round, increment_applied)``.

    The R̄_prev gate is evaluated semantically (SimCSE cosine similarity ≥
    ``sem_cfg.r_bar_similarity_threshold``, default 0.80) so that LLM paraphrases
    across refinement rounds are still recognised as the same value in circulation.
    Exact-string matches always qualify regardless of threshold.
    """
    import numpy as np

    acc = list(accepted)
    if not acc:
        res = tracker.apply_round(skip=True, eligible=None, sum_sv_dominant=0.0)
        return res, [], True, 0.0

    conclusions = [extract_conclusion(out) for _, out in acc]
    prev_conclusions = [extract_conclusion(o) for o in r_bar_prev]

    if encode_fn is not None:
        emb = np.asarray(encode_fn(list(conclusions)), dtype=np.float64)
    else:
        emb = np.asarray(embedder.encode_conclusions(conclusions), dtype=np.float64)

    emb_norm = _l2_normalize_rows(emb)
    n_acc = len(acc)
    if n_acc <= 1:
        labels = np.zeros(max(1, n_acc), dtype=np.int64)
    else:
        mcs = _effective_hdbscan_mcs(alpha, n_acc, sem_cfg.hdbscan_min_cluster_size)
        labels = _hdbscan_labels(emb_norm, mcs, sem_cfg.hdbscan_min_samples)

    if bool((labels == -1).all()):
        dominant_idx = list(range(n_acc))
        dominant_label_val: int | None = None
    else:
        dom_lab = _dominant_label(labels)
        dominant_label_val = dom_lab
        if dom_lab is None:
            dominant_idx = list(range(n_acc))
        else:
            dominant_idx = [i for i in range(n_acc) if int(labels[i]) == int(dom_lab)]

    all_conclusions = list(conclusions)

    def _skip_all_dissent() -> tuple[DecisionStepResult, list[str], bool, float]:
        res = tracker.apply_round(skip=True, eligible=None, sum_sv_dominant=0.0)
        dedup: list[str] = []
        seen: set[str] = set()
        for s in all_conclusions:
            if s and s not in seen:
                seen.add(s)
                dedup.append(s)
        return res, dedup, True, 0.0

    if len(dominant_idx) < int(alpha):
        return _skip_all_dissent()

    sub = emb_norm[np.array(dominant_idx, dtype=np.intp)]
    sv_vec = _sv_scores_for_dominant(sub)
    sum_sv = float(sv_vec.sum())

    r_sim_thr = float(getattr(sem_cfg, "r_bar_similarity_threshold", 0.80))
    eligible_global_idx = _semantic_prev_gate(
        dominant_idx,
        conclusions,
        emb_norm,
        prev_conclusions,
        encode_fn,
        embedder,
        r_sim_thr,
    )

    eligible_cands: list[tuple[float, Any]] = []
    dom_row = {gi: row_k for row_k, gi in enumerate(dominant_idx)}
    for gi in eligible_global_idx:
        row_k = dom_row.get(gi)
        if row_k is None:
            continue
        eligible_cands.append((float(sv_vec[row_k]), acc[gi][1]))

    if not eligible_cands:
        return _skip_all_dissent()

    winner_out = sorted(eligible_cands, key=lambda t: (-t[0], _sort_key(t[1])))[0][1]
    win_conc = extract_conclusion(winner_out)

    dissent_set: list[str] = []
    seen_d: set[str] = set()

    def _add_dissent(s: str) -> None:
        if not s or s == win_conc:
            return
        if s not in seen_d:
            seen_d.add(s)
            dissent_set.append(s)

    discard_noise = bool(sem_cfg.discard_noise_from_dissent) and int(n_experts) >= int(
        sem_cfg.min_agents_to_discard_noise
    )

    for L in sorted(set(labels.tolist())):
        if L == -1:
            continue
        if dominant_label_val is not None and int(L) == int(dominant_label_val):
            continue
        idxs = [i for i in range(n_acc) if int(labels[i]) == int(L)]
        if not idxs:
            continue
        first_i = min(idxs)
        _add_dissent(conclusions[first_i])

    if not discard_noise:
        for i in range(n_acc):
            if int(labels[i]) == -1:
                _add_dissent(conclusions[i])

    inc = sum_sv / float(max(1, int(n_experts)))
    res = tracker.apply_round(skip=False, eligible=winner_out, sum_sv_dominant=sum_sv)
    return res, dissent_set, False, inc


@dataclass
class SemanticStabilityTracker:
    """Weighted stability toward ``stability_score_threshold``; resets on term or candidate flip."""

    stability_score_threshold: float
    n_experts: int
    running_score: float = 0.0
    _tracked: Any | None = field(default=None, repr=False)
    _term_num: int | None = field(default=None, repr=False)

    def on_new_term(self, term_num: int) -> None:
        t = int(term_num)
        if self._term_num is None:
            self._term_num = t
            return
        if t != self._term_num:
            _log.info("semantic stability reset (term %s -> %s)", self._term_num, t)
            self._term_num = t
            self._tracked = None
            self.running_score = 0.0

    def peek_tracked_candidate(self) -> Any | None:
        return self._tracked

    def apply_round(
        self,
        *,
        skip: bool,
        eligible: Any | None,
        sum_sv_dominant: float,
    ) -> DecisionStepResult:
        if skip or eligible is None:
            return DecisionStepResult(
                committed=False,
                value=None,
                stability=0,
                eligible_candidate=None,
                overturned=False,
                stability_score=self.running_score,
            )

        inc = float(sum_sv_dominant) / float(max(1, int(self.n_experts)))
        prev_tracked = self._tracked
        overturned = prev_tracked is not None and prev_tracked != eligible

        if self._tracked != eligible:
            self.running_score = 0.0
            self._tracked = eligible

        self.running_score += inc
        committed = self.running_score >= float(self.stability_score_threshold)
        return DecisionStepResult(
            committed=committed,
            value=eligible if committed else None,
            stability=1,
            eligible_candidate=eligible,
            overturned=overturned,
            stability_score=self.running_score,
        )


@dataclass
class SemanticSessionAccumulator:
    """Diagnostics when semantic mode ends without commit (``max_rounds`` / ``timeout``)."""

    stability_threshold: float
    _cumulative: dict[str, float] = field(default_factory=dict)
    _rounds_won: dict[str, int] = field(default_factory=dict)
    _agents: dict[str, set[str]] = field(default_factory=dict)
    _minority_ordered: list[str] = field(default_factory=list)
    _minority_seen: set[str] = field(default_factory=set)

    def record_round(
        self,
        *,
        accepted: Sequence[tuple[str, Any]],
        skip_round: bool,
        candidate: Any | None,
        increment: float,
        dissent: Sequence[str],
    ) -> None:
        # Only record minority signals from non-skip rounds so the candidate answer
        # (which gets dumped into dissent on skips via _skip_all_dissent) does not
        # misleadingly appear as a minority signal.
        if not skip_round:
            for s in dissent:
                if s and s not in self._minority_seen:
                    self._minority_seen.add(s)
                    self._minority_ordered.append(s)

        if skip_round or candidate is None:
            return

        key = extract_conclusion(candidate)
        self._cumulative[key] = self._cumulative.get(key, 0.0) + float(increment)
        self._rounds_won[key] = self._rounds_won.get(key, 0) + 1
        ag = self._agents.setdefault(key, set())
        for eid, out in accepted:
            if extract_conclusion(out) == key:
                ag.add(str(eid))

    def to_no_consensus_payload(
        self,
        *,
        max_rounds: int,
        last_running_score: float,
        last_tracked: Any | None,
    ) -> dict[str, Any]:
        thr = float(self.stability_threshold)
        max_c = max(self._cumulative.values()) if self._cumulative else 0.0
        confidence = (max_c / thr) if thr > 0 else 0.0

        best_key: str | None = None
        if self._cumulative:
            best_key = max(self._cumulative, key=self._cumulative.get)  # type: ignore[arg-type]
        elif last_tracked is not None:
            bx = extract_conclusion(last_tracked)
            best_key = bx if bx else None

        cluster_results = [
            {
                "answer": k,
                "agents": len(self._agents.get(k, ())),
                "cumulative_score": float(self._cumulative[k]),
                "rounds_dominant": int(self._rounds_won.get(k, 0)),
            }
            for k in sorted(self._cumulative.keys(), key=lambda x: (-self._cumulative[x], x))
        ]

        return {
            "status": "no_consensus",
            "rounds_completed": int(max_rounds),
            "candidate": best_key,
            "confidence": float(confidence),
            "cluster_results": cluster_results,
            "minority_signals": list(self._minority_ordered),
            "last_running_score": float(last_running_score),
            "last_tracked_candidate": extract_conclusion(last_tracked) if last_tracked is not None else None,
        }


def build_semantic_no_consensus_payload(**kwargs: Any) -> dict[str, Any]:
    """Backwards-compatible helper for structured no-consensus export."""
    acc = SemanticSessionAccumulator(stability_threshold=float(kwargs["stability_threshold"]))
    return acc.to_no_consensus_payload(
        max_rounds=int(kwargs["max_rounds"]),
        last_running_score=float(kwargs["last_running_score"]),
        last_tracked=kwargs.get("last_tracked"),
    )
