"""pregnancy_lactation_safety — pregnancy and lactation screening.

Baseline (unconditional): the per-drug pregnancy/lactation modifiers migrated verbatim
from the original engine.

Extended (clinician-authored): valproate is high-risk in pregnancy *and* in people of
childbearing potential (the per-drug rule only fires once pregnant), plus perinatal and
lactation advisories.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import PatientAdvisory, SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


def _is_valproate(drug: dict) -> bool:
    # By name only — lamotrigine shares the "...antiepileptic" class but is a
    # different (relatively preferred) agent in pregnancy.
    return drug.get("name", "").strip().lower() == "valproate"


class PregnancyLactationSafety(SafetyModifier):
    key = "pregnancy_lactation"
    display_name = "Pregnancy & lactation safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.pregnant_or_planning or ctx.lactating or ctx.childbearing_potential

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        # ----- baseline: pregnancy -----
        if ctx.pregnant_or_planning:
            rule = drug.get("pregnancy", "specialist_review")
            if rule == "avoid":
                card.add_caution("PREG-AVOID", "Avoid or strongly down-rank in pregnancy/planning pregnancy according to current rule entry.", delta=-80, references=cite("PREG-AVOID"))
            elif rule == "specialist_review":
                card.add_caution("PREG-SPECIALIST", "Pregnancy/planning pregnancy: use only after specialist risk-benefit review.", delta=-25, references=cite("PREG-SPECIALIST"))
            elif rule == "relatively_preferred_when_needed":
                card.add_reason("PREG-PREFERRED", "Pregnancy status present: rule entry marks this as relatively preferred when medication is clinically needed.", delta=8, references=cite("PREG-PREFERRED"))

        # ----- baseline: lactation -----
        if ctx.lactating:
            rule = drug.get("lactation", "specialist_review")
            if rule == "avoid":
                card.add_caution("LACT-AVOID", "Avoid or strongly down-rank during lactation according to current rule entry.", delta=-50, references=cite("LACT-AVOID"))
            elif rule == "specialist_review":
                card.add_caution("LACT-SPECIALIST", "Lactation: use after infant-risk and maternal-benefit review.", delta=-15, references=cite("LACT-SPECIALIST"))

        if not ctx.extended_rules:
            return

        # ----- extended: valproate -----
        if _is_valproate(drug):
            if ctx.pregnant_or_planning:
                # Near-absolute in pregnancy: force unsuitable (the baseline avoid
                # penalty already lowers the score; this makes the bucket explicit).
                card.mark_unsuitable("PREG-VALPROATE", "Valproate carries high teratogenic and neurodevelopmental risk and should be avoided in pregnancy/planning pregnancy except where other options have failed and only under specialist supervision.", delta=0, references=cite("PREG-VALPROATE"))
            elif ctx.childbearing_potential:
                card.add_caution("PREG-VALPROATE", "Valproate carries high teratogenic and neurodevelopmental risk; avoid in people of childbearing potential unless other options have failed and an effective pregnancy-prevention plan is in place.", delta=-40, references=cite("PREG-VALPROATE"))
                card.add_investigation("Documented pregnancy-prevention counselling and pregnancy test before valproate.")

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        if not ctx.extended_rules:
            return PatientAdvisory()
        adv = PatientAdvisory()
        if ctx.pregnant_or_planning:
            adv.notes.append("Pregnancy/planning: manage jointly with perinatal psychiatry; weigh the risks of untreated maternal illness against medication risks, prefer agents with more reproductive-safety data, and use the lowest effective dose.")
        if ctx.lactating:
            adv.notes.append("Lactation: prefer agents with established infant-safety data, use the lowest effective dose, and monitor the infant for adverse effects.")
        return adv


MODIFIER = register(PregnancyLactationSafety())
