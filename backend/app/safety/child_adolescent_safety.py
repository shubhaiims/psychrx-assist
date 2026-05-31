"""child_adolescent_safety — paediatric screening (child & adolescent psychiatry).

Extended only. Antidepressant and atomoxetine boxed-warning suicidality cautions, stimulant
growth/cardiovascular monitoring, and a specialist-involvement advisory.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import PatientAdvisory, SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class ChildAdolescentSafety(SafetyModifier):
    key = "child_adolescent"
    display_name = "Child & adolescent safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.age_group in ("child", "adolescent")

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        if not ctx.extended_rules or ctx.age_group not in ("child", "adolescent"):
            return
        class_name = drug.get("class_name", "")
        name = drug.get("name", "").strip().lower()

        if class_name == "SSRI":
            card.add_caution("PED-AD-SUICIDALITY", "Antidepressants carry a boxed warning for increased suicidal ideation/behaviour in patients under 25; if used, start with close monitoring and safety planning.", delta=-10, references=cite("PED-AD-SUICIDALITY"))
            card.add_monitoring("Close monitoring for emergent suicidality/agitation, especially in the first weeks of treatment and after dose changes (paediatric/young adult).")

        if name == "atomoxetine":
            card.add_caution("PED-ATOMOXETINE-SUICIDALITY", "Atomoxetine carries a boxed warning for suicidal ideation in children/adolescents; monitor mood closely after initiation and dose changes.", delta=-8, references=cite("PED-ATOMOXETINE-SUICIDALITY"))

        if class_name == "Stimulant":
            card.add_investigation("Baseline height/weight and cardiovascular history before starting a stimulant in a child/adolescent.")
            card.add_monitoring("Monitor growth (height/weight), appetite, sleep, and cardiovascular parameters during stimulant treatment in children/adolescents.")

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        if not ctx.extended_rules or ctx.age_group not in ("child", "adolescent"):
            return PatientAdvisory()
        return PatientAdvisory(notes=[
            "Child/adolescent: psychiatric pharmacotherapy generally warrants child-and-adolescent psychiatry involvement; fewer agents are licensed in this age group, dosing differs, and psychosocial/family interventions are central."
        ])


MODIFIER = register(ChildAdolescentSafety())
