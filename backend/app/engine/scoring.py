"""Deterministic scoring primitives.

A ``ScoreCard`` accumulates the effect of individual rules on one drug for one
patient. Each rule records a ``RuleHit`` (what fired, why, the score change, and
the supporting reference) so the result is fully auditable: you can trace every
point of the final score back to a named rule and its citation.

The categorisation thresholds below reproduce the original engine exactly:

    score < 40                     -> relatively_unsuitable
    score < 70  OR any caution     -> use_with_caution
    otherwise                      -> most_suitable

The thresholds are intentionally named constants so a reviewing psychiatrist can
see and adjust them in one place rather than hunting through control flow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal

from app.models import Evidence, RecommendationItem

# --- Categorisation thresholds (clinically reviewable in one place) ----------
RELATIVELY_UNSUITABLE_BELOW = 40
USE_WITH_CAUTION_BELOW = 70

HitKind = Literal["reason", "caution"]


@dataclass
class RuleHit:
    """One rule firing: its id, the human-readable detail, score delta, refs."""

    rule_id: str
    kind: HitKind
    detail: str
    delta: int = 0
    references: List[str] = field(default_factory=list)


@dataclass
class ScoreCard:
    """Accumulates rule effects for a single (patient, drug) pair."""

    drug_name: str
    class_name: str
    score: int
    investigations: List[str] = field(default_factory=list)
    monitoring: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    reasons: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)
    trace: List[RuleHit] = field(default_factory=list)

    # Set by mark_unsuitable(): forces the final category to relatively_unsuitable
    # regardless of score (used for absolute/near-absolute contraindications).
    forced_unsuitable: bool = False

    # ----- rule-firing API -------------------------------------------------

    def add_reason(self, rule_id: str, detail: str, delta: int = 0, references: List[str] | None = None) -> None:
        self.score += delta
        self.reasons.append(detail)
        self.trace.append(RuleHit(rule_id, "reason", detail, delta, list(references or [])))

    def add_caution(self, rule_id: str, detail: str, delta: int = 0, references: List[str] | None = None) -> None:
        self.score += delta
        self.cautions.append(detail)
        self.trace.append(RuleHit(rule_id, "caution", detail, delta, list(references or [])))

    def mark_unsuitable(self, rule_id: str, detail: str, delta: int = 0, references: List[str] | None = None) -> None:
        """Force this drug into 'relatively_unsuitable' regardless of score.

        Use for absolute / near-absolute contraindications (e.g. a dangerous
        interaction) where a high base score must not rescue the option. Records a
        caution-kind hit so the reason is visible in reasons/cautions and rule_trace.
        """
        self.score += delta
        self.forced_unsuitable = True
        self.cautions.append(detail)
        self.trace.append(RuleHit(rule_id, "caution", detail, delta, list(references or [])))

    def add_monitoring(self, item: str) -> None:
        if item not in self.monitoring:
            self.monitoring.append(item)

    def add_investigation(self, item: str) -> None:
        if item not in self.investigations:
            self.investigations.append(item)

    # ----- finalisation ----------------------------------------------------

    def category(self) -> str:
        """Bucket the *raw* (un-clamped) score, matching the original engine.

        A forced-unsuitable override (from mark_unsuitable) takes precedence.
        """
        if self.forced_unsuitable:
            return "relatively_unsuitable"
        if self.score < RELATIVELY_UNSUITABLE_BELOW:
            return "relatively_unsuitable"
        if self.score < USE_WITH_CAUTION_BELOW or self.cautions:
            return "use_with_caution"
        return "most_suitable"

    def to_item(self) -> RecommendationItem:
        return RecommendationItem(
            drug=self.drug_name,
            class_name=self.class_name,
            category=self.category(),
            score=max(min(self.score, 100), 0),  # report clamped to 0..100
            reasons=self.reasons,
            cautions=self.cautions,
            baseline_investigations=self.investigations,
            monitoring=self.monitoring,
            references=self.references,
            rule_trace=[
                Evidence(rule_id=h.rule_id, kind=h.kind, detail=h.detail, delta=h.delta, references=h.references)
                for h in self.trace
            ],
            forced_unsuitable=self.forced_unsuitable,
        )


def new_scorecard(drug: dict) -> ScoreCard:
    """Seed a ScoreCard from a drug knowledge-base entry."""
    return ScoreCard(
        drug_name=drug["name"],
        class_name=drug["class_name"],
        score=drug.get("base_score", 50),
        investigations=list(drug.get("baseline_investigations", [])),
        monitoring=list(drug.get("monitoring", [])),
        references=list(drug.get("references", [])),
    )
