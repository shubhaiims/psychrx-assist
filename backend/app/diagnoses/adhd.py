"""Rule module for attention-deficit/hyperactivity disorder (ADHD).

Encodes widely-accepted ADHD prescribing principles:

* stimulants are first-line for most patients (up-ranked);
* with a cardiac history, stimulants need cardiovascular risk assessment (down-ranked
  and an investigation flagged);
* with comorbid substance use, stimulant misuse/diversion is a concern (down-ranked);
* atomoxetine is a useful non-stimulant alternative (mildly up-ranked).

Extended-rule-set logic (runs only when ``ctx.extended_rules`` is on); each
reason/caution carries a placeholder citation pending psychiatrist sign-off. The
paediatric boxed-warning and growth-monitoring rules live in the child/adolescent
population layer.
"""
from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import has_any

_CARDIAC_KEYWORDS = ["cardiac", "heart", "arrhythmia", "hypertension", "cardiovascular", "palpitation"]
_SUD_KEYWORDS = ["substance", "alcohol", "opioid", "cocaine", "stimulant misuse", "drug use"]


class ADHDModule(DiagnosisRuleModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        class_name = drug.get("class_name", "")
        name = drug.get("name", "").strip().lower()

        if class_name == "Stimulant":
            card.add_reason(
                "ADHD-STIMULANT-FIRSTLINE",
                "Stimulants are first-line pharmacotherapy for ADHD in most patients.",
                delta=10,
                references=cite("ADHD-STIMULANT-FIRSTLINE"),
            )
            if has_any(ctx.profile.comorbidities, _CARDIAC_KEYWORDS):
                card.add_caution(
                    "ADHD-STIMULANT-CARDIAC",
                    "Cardiac history present: assess cardiovascular risk (consider cardiology "
                    "input) before starting a stimulant.",
                    delta=-20,
                    references=cite("ADHD-STIMULANT-CARDIAC"),
                )
                card.add_investigation("Cardiovascular assessment (history, BP/pulse, ECG/cardiology where indicated) before stimulant.")
            if ctx.profile.substance_use or has_any(ctx.profile.comorbidities, _SUD_KEYWORDS):
                card.add_caution(
                    "ADHD-STIMULANT-SUD",
                    "Comorbid substance use: stimulants carry misuse/diversion risk; consider a "
                    "non-stimulant or a closely monitored extended-release option.",
                    delta=-15,
                    references=cite("ADHD-STIMULANT-SUD"),
                )

        if name == "atomoxetine":
            card.add_reason(
                "ADHD-ATOMOXETINE-ALT",
                "Atomoxetine is a non-stimulant option, useful where stimulants are unsuitable "
                "(e.g. substance-use concerns).",
                delta=5,
                references=cite("ADHD-ATOMOXETINE-ALT"),
            )


    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Behavioural strategies and environmental supports; parent training for children.",
            "School/workplace accommodations and routines for sleep and organisation.",
        ]
        return recs

MODULE = register(
    ADHDModule(diagnosis="adhd", display_name="Attention-deficit/hyperactivity disorder")
)
