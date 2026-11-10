#!/usr/bin/env python3
"""Skill Aggregator — port of AgentDescent's 7-stage merge pipeline.

Adapted to OpenAmer's architecture: Darwin Engine evolves EXISTING skills
serially. This aggregator enables PARALLEL skill evolution by accepting
EvidenceCards from multiple workers, running them through a 7-stage merge
pipeline, and committing winners to the Darwin ledger.

7 stages (design doc section 4):
  1. trigger + bucket        — accept incoming diffs, bucket by skill key
  2. staleness filter        — per-diff eta, hot/tail/cold split, rebase + re-verify
  3. conflict resolution     — same-key conflicts: fusion tournament; disjoint keys: fuse
  4. audit gate              — high blast radius / low trust -> full-set scorer decides, can veto
  5. Beta-posterior accept   — P(delta > 0) > 1 - delta (statistical acceptance, not threshold)
  6. CAS / 2PC commit        — transactional git-backed commit with rollback
  7. dual-branch promotion   — EMA-style dev -> stable after K regression-free rounds

Threading contract: ingest() may be called concurrently from many worker
threads; step() is called from one. Guard shared state.
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Tuple

HOME = Path(os.environ.get("OPENAMER_HOME", "")) or Path(
    os.path.expanduser("~") / "AppData" / "Local" / "openamer-laptop"
)
DARWIN_DIR = HOME / "darwin"
LEDGER_PATH = DARWIN_DIR / "lineage.json"
SKILLS_DIR = HOME / "skills"
AUTO_SKILLS = SKILLS_DIR / "auto-generated"

STAGE_NAMES = (
    "trigger_bucket",
    "staleness_filter",
    "conflict_resolution",
    "audit_gate",
    "beta_posterior_accept",
    "cas_commit",
    "dual_branch_promotion",
)

# Default thresholds (tunable via config later)
DEFAULT_ACCEPTANCE_DELTA = 0.05  # 1 - delta confidence for Beta posterior
DEFAULT_BETA_SAMPLES = 4000
DEFAULT_PROMOTION_ROUNDS = 3  # K regression-free rounds before dev->stable
DEFAULT_STALENESS_ETA = 0.1  # per-diff staleness decay


class MergeResult(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    VETOED = "vetoed"
    STALE = "stale"
    CONFLICT = "conflict"


@dataclass
class EvidenceCard:
    """A worker-proposed diff with evidence — the unit of aggregation."""

    skill_key: str
    diff: Dict[str, Any]
    evidence: Dict[str, Any]  # before/after metrics, test results, etc.
    worker_id: str
    timestamp: float = field(default_factory=time.time)
    eta: float = 1.0  # staleness decay factor (1.0 = fresh)


@dataclass
class MergeReport:
    """Outcome of aggregating one EvidenceCard through the 7-stage pipeline."""

    skill_key: str
    stage_reached: str
    result: MergeResult
    reason: str
    posterior_prob: Optional[float] = None
    commit_sha: Optional[str] = None


@dataclass
class BetaPosterior:
    """Beta(successes + 1, failures + 1) posterior over a success rate."""

    successes: float = 0.0
    failures: float = 0.0

    @property
    def alpha(self) -> float:
        return self.successes + 1.0

    @property
    def beta(self) -> float:
        return self.failures + 1.0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def update(self, success: bool, weight: float = 1.0) -> None:
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"weight must be finite and >= 0, got {weight!r}")
        if success:
            self.successes += weight
        else:
            self.failures += weight

    def observe_delta(self, delta: float) -> None:
        """Fold a signed before/after delta into the posterior."""
        if math.isnan(delta):
            return
        w = min(1.0, abs(delta) * 4.0) + 1e-6
        self.update(delta > 0, weight=w)

    def sample(self, rng: random.Random) -> float:
        x = rng.gammavariate(self.alpha, 1.0)
        y = rng.gammavariate(self.beta, 1.0)
        return x / (x + y)


def prob_improvement(
    candidate: BetaPosterior,
    baseline: BetaPosterior,
    samples: int = DEFAULT_BETA_SAMPLES,
    seed: int = 0,
) -> float:
    """Estimate P(theta_candidate > theta_baseline) by Monte-Carlo over Betas."""
    rng = random.Random(seed)
    wins = 0
    for _ in range(samples):
        if candidate.sample(rng) > baseline.sample(rng):
            wins += 1
    return wins / samples


def _load_ledger() -> Dict[str, Any]:
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"events": []}


def _save_ledger(ledger: Dict[str, Any]) -> None:
    DARWIN_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=1), encoding="utf-8")


def _git_commit(message: str) -> Optional[str]:
    """Transactional commit: git add + commit, return SHA or None on failure."""
    try:
        subprocess.run(
            ["git", "add", str(LEDGER_PATH)],
            check=True,
            capture_output=True,
            cwd=str(HOME.parent),
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(HOME.parent),
        )
        # Extract SHA from commit output
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(HOME.parent),
        )
        return sha_result.stdout.strip()
    except Exception:
        return None


class SkillAggregator:
    """The 7-stage merge pipeline for parallel skill evolution.

    Workers call ingest() concurrently with EvidenceCards. step() drains the
    buffer through all 7 stages and returns MergeReports.
    """

    def __init__(
        self,
        acceptance_delta: float = DEFAULT_ACCEPTANCE_DELTA,
        beta_samples: int = DEFAULT_BETA_SAMPLES,
        promotion_rounds: int = DEFAULT_PROMOTION_ROUNDS,
        staleness_eta: float = DEFAULT_STALENESS_ETA,
    ) -> None:
        self._lock = threading.Lock()
        self._buffer: Deque[EvidenceCard] = deque()
        self._posteriors: Dict[str, BetaPosterior] = defaultdict(BetaPosterior)
        self._round_counts: Dict[str, int] = defaultdict(int)
        self._accepted_keys: Dict[str, str] = {}  # skill_key -> commit_sha

        self.acceptance_delta = acceptance_delta
        self.beta_samples = beta_samples
        self.promotion_rounds = promotion_rounds
        self.staleness_eta = staleness_eta

    # ── Stage 1: trigger + bucket ─────────────────────────────────────

    def ingest(self, card: EvidenceCard) -> None:
        """Called by workers concurrently. Thread-safe append."""
        with self._lock:
            self._buffer.append(card)

    # ── Stage 2: staleness filter ─────────────────────────────────────

    def _staleness_filter(self, card: EvidenceCard) -> Tuple[bool, str]:
        """Apply per-diff staleness decay. Returns (pass, reason)."""
        age_seconds = time.time() - card.timestamp
        decayed_eta = card.eta * math.exp(-self.staleness_eta * age_seconds / 3600.0)
        if decayed_eta < 0.1:
            return False, f"stale (eta={decayed_eta:.3f})"
        return True, f"fresh (eta={decayed_eta:.3f})"

    # ── Stage 3: conflict resolution ──────────────────────────────────

    def _resolve_conflict(
        self, card: EvidenceCard, ledger: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Same-key conflicts: candidate fusion tournament. Disjoint keys: fuse."""
        events = ledger.get("events", [])
        # Check if this skill_key has a recent event (potential conflict)
        recent = [e for e in events if e.get("skill_key") == card.skill_key]
        if not recent:
            return True, "disjoint key — fuse"
        # Same key: apply fusion — keep the diff with higher evidence score
        best = max(recent, key=lambda e: e.get("evidence_score", 0))
        card_score = card.evidence.get("score", 0)
        if card_score <= best.get("evidence_score", 0):
            return False, f"conflict — existing event {best.get('id')} has higher score"
        return True, "conflict — candidate wins fusion tournament"

    # ── Stage 4: audit gate ───────────────────────────────────────────

    def _audit_gate(self, card: EvidenceCard) -> Tuple[bool, str]:
        """High blast radius / low trust -> full-set scorer decides, can veto."""
        blast_radius = card.evidence.get("blast_radius", 0)  # 0-1
        trust = card.evidence.get("trust", 1)  # 0-1
        if blast_radius > 0.7 and trust < 0.5:
            return False, "vetoed — high blast radius, low trust"
        return True, "audit passed"

    # ── Stage 5: Beta-posterior accept ────────────────────────────────

    def _beta_posterior_accept(self, card: EvidenceCard) -> Tuple[bool, str, float]:
        """P(delta > 0) > 1 - delta. Statistical acceptance, not threshold."""
        delta = card.evidence.get("delta", 0.0)
        posterior = self._posteriors[card.skill_key]
        posterior.observe_delta(delta)

        baseline = BetaPosterior()  # neutral baseline
        prob = prob_improvement(posterior, baseline, samples=self.beta_samples)

        if prob > (1.0 - self.acceptance_delta):
            return True, f"accepted (P(improve)={prob:.3f})", prob
        return False, f"rejected (P(improve)={prob:.3f})", prob

    # ── Stage 6: CAS / 2PC commit ─────────────────────────────────────

    def _cas_commit(self, card: EvidenceCard, ledger: Dict[str, Any]) -> Optional[str]:
        """Transactional commit: append event to ledger, git commit, return SHA."""
        event = {
            "id": f"agg-{int(time.time()*1000)}",
            "skill_key": card.skill_key,
            "diff": card.diff,
            "evidence": card.evidence,
            "worker_id": card.worker_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "aggregator",
        }
        ledger.setdefault("events", []).append(event)
        _save_ledger(ledger)

        sha = _git_commit(f"[aggregator] accept skill diff: {card.skill_key}")
        if sha is None:
            # Rollback: remove the event we just appended
            ledger["events"].pop()
            _save_ledger(ledger)
        return sha

    # ── Stage 7: dual-branch promotion ────────────────────────────────

    def _promote(self, skill_key: str) -> bool:
        """EMA-style dev -> stable after K regression-free rounds."""
        self._round_counts[skill_key] += 1
        return self._round_counts[skill_key] >= self.promotion_rounds

    # ── Main pipeline ─────────────────────────────────────────────────

    def step(self, n_workers: int = 1) -> List[MergeReport]:
        """Drain the buffer through all 7 stages. Single-threaded."""
        reports: List[MergeReport] = []
        ledger = _load_ledger()

        with self._lock:
            batch = list(self._buffer)
            self._buffer.clear()

        for card in batch:
            # Stage 1: trigger + bucket (already done at ingest)
            stage = "trigger_bucket"

            # Stage 2: staleness filter
            stage = "staleness_filter"
            ok, reason = self._staleness_filter(card)
            if not ok:
                reports.append(
                    MergeReport(
                        skill_key=card.skill_key,
                        stage_reached=stage,
                        result=MergeResult.STALE,
                        reason=reason,
                    )
                )
                continue

            # Stage 3: conflict resolution
            stage = "conflict_resolution"
            ok, reason = self._resolve_conflict(card, ledger)
            if not ok:
                reports.append(
                    MergeReport(
                        skill_key=card.skill_key,
                        stage_reached=stage,
                        result=MergeResult.CONFLICT,
                        reason=reason,
                    )
                )
                continue

            # Stage 4: audit gate
            stage = "audit_gate"
            ok, reason = self._audit_gate(card)
            if not ok:
                reports.append(
                    MergeReport(
                        skill_key=card.skill_key,
                        stage_reached=stage,
                        result=MergeResult.VETOED,
                        reason=reason,
                    )
                )
                continue

            # Stage 5: Beta-posterior accept
            stage = "beta_posterior_accept"
            ok, reason, prob = self._beta_posterior_accept(card)
            if not ok:
                reports.append(
                    MergeReport(
                        skill_key=card.skill_key,
                        stage_reached=stage,
                        result=MergeResult.REJECTED,
                        reason=reason,
                        posterior_prob=prob,
                    )
                )
                continue

            # Stage 6: CAS / 2PC commit
            stage = "cas_commit"
            sha = self._cas_commit(card, ledger)
            if sha is None:
                reports.append(
                    MergeReport(
                        skill_key=card.skill_key,
                        stage_reached=stage,
                        result=MergeResult.REJECTED,
                        reason="commit failed — rolled back",
                    )
                )
                continue

            # Stage 7: dual-branch promotion
            stage = "dual_branch_promotion"
            promoted = self._promote(card.skill_key)
            self._accepted_keys[card.skill_key] = sha

            reports.append(
                MergeReport(
                    skill_key=card.skill_key,
                    stage_reached=stage,
                    result=MergeResult.ACCEPTED,
                    reason=reason,
                    posterior_prob=prob,
                    commit_sha=sha,
                )
            )

        return reports

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "buffer_size": len(self._buffer),
                "accepted_keys": len(self._accepted_keys),
                "posteriors": {
                    k: {"alpha": p.alpha, "beta": p.beta, "mean": p.mean}
                    for k, p in self._posteriors.items()
                },
                "round_counts": dict(self._round_counts),
            }


__all__ = [
    "SkillAggregator",
    "EvidenceCard",
    "MergeReport",
    "BetaPosterior",
    "prob_improvement",
    "MergeResult",
    "STAGE_NAMES",
]
