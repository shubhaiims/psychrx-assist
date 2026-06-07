"""Target-symptom pharmacology pathway for child/adolescent ASD.

Medication is never treated as a cure for autism or as treatment for core autism
features. This module only opens medication candidates for a clearly defined
co-occurring target symptom after triggers, communication needs, sensory factors,
medical contributors, and psychosocial supports have been reviewed.
"""
from __future__ import annotations

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import enum_value, has_any, normalise


IRRITABILITY_TARGETS = {"irritability", "distress_agitation"}
ALPHA2_NAMES = {"guanfacine", "clonidine"}
ADHD_NAMES = {"guanfacine", "clonidine", "atomoxetine", "methylphenidate"}
IRRITABILITY_AP_NAMES = {"risperidone", "aripiprazole"}
ANXIETY_NAMES = {"buspirone", "mirtazapine", "sertraline", "fluoxetine"}
DEPRESSION_NAMES = {"duloxetine", "mirtazapine", "bupropion", "fluoxetine"}


def _assessment(ctx: PatientContext):
    return ctx.profile.asd_assessment


def _target(ctx: PatientContext) -> str:
    target = enum_value(_assessment(ctx).target_domain)
    if target != "none":
        return target
    symptoms = ctx.profile.symptoms
    if symptoms.aggression_risk or symptoms.self_injury or symptoms.agitation:
        return "irritability"
    if symptoms.hyperactivity or symptoms.inattention or symptoms.impulsivity:
        return "adhd"
    if symptoms.anxiety or symptoms.ocd:
        return "anxiety"
    if symptoms.depressive:
        return "depression"
    if symptoms.insomnia:
        return "sleep"
    if symptoms.feeding_problem or symptoms.poor_oral_intake:
        return "feeding"
    if symptoms.repetitive_behaviour:
        return "repetitive_behaviour"
    return "none"


def _irritability_level(ctx: PatientContext) -> str:
    level = enum_value(_assessment(ctx).irritability_level)
    symptoms = ctx.profile.symptoms
    if level != "absent":
        return level
    if symptoms.self_injury or symptoms.aggression_risk:
        return "severe"
    if symptoms.agitation:
        return "moderate"
    return "absent"


def _failed_adequate(ctx: PatientContext, names: set[str]) -> bool:
    for trial in ctx.profile.previous_drug_responses:
        if normalise(trial.drug) in names and trial.adequate_trial:
            if normalise(trial.response) in {"none", "intolerable"}:
                return True
    return False


def _needs_psychosocial_first(ctx: PatientContext) -> bool:
    assessment = _assessment(ctx)
    if assessment.psychosocial_intervention_attempted:
        return False
    if assessment.psychosocial_unavailable_due_to_severity:
        return False
    return _irritability_level(ctx) not in {"severe"}


class AutismSpectrumDisorderModule(DiagnosisRuleModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        if not ctx.extended_rules:
            return []

        target = _target(ctx)
        symptoms = ctx.profile.symptoms
        names: set[str] = set()

        if target in IRRITABILITY_TARGETS:
            level = _irritability_level(ctx)
            if level == "mild":
                names |= ALPHA2_NAMES
            if level in {"moderate", "severe"} or symptoms.self_injury or symptoms.aggression_risk:
                names |= IRRITABILITY_AP_NAMES
            if _failed_adequate(ctx, IRRITABILITY_AP_NAMES):
                names |= IRRITABILITY_AP_NAMES
            if _failed_adequate(ctx, ALPHA2_NAMES):
                names |= IRRITABILITY_AP_NAMES

        elif target == "adhd":
            names |= ALPHA2_NAMES | {"atomoxetine"}
            if _failed_adequate(ctx, ALPHA2_NAMES | {"atomoxetine"}):
                names.add("methylphenidate")
            tic_like = has_any(ctx.profile.comorbidities, ["tic", "tourette"])
            if not (symptoms.anxiety or symptoms.insomnia or tic_like):
                names.add("methylphenidate")

        elif target == "anxiety":
            names |= {"buspirone", "mirtazapine"}
            if symptoms.ocd or symptoms.repetitive_behaviour or _failed_adequate(ctx, {"buspirone", "mirtazapine"}):
                names |= {"sertraline", "fluoxetine"}

        elif target == "depression":
            names |= {"duloxetine", "mirtazapine", "bupropion"}
            if ctx.age_group in {"child", "adolescent"}:
                names.add("fluoxetine")

        elif target == "sleep":
            names.add("melatonin")
            if _failed_adequate(ctx, {"melatonin"}):
                names.add("clonidine")
                if symptoms.depressive or symptoms.anxiety:
                    names.add("mirtazapine")

        elif target == "repetitive_behaviour":
            if symptoms.ocd or symptoms.anxiety:
                names |= {"sertraline", "fluoxetine"}
            if _irritability_level(ctx) in {"moderate", "severe"}:
                names |= IRRITABILITY_AP_NAMES

        elif target == "feeding":
            # No routine medication branch: feeding issues need nutrition, sensory,
            # behavioural and speech/OT assessment first.
            names = set()

        return [drug for drug in all_drugs if normalise(drug.get("name", "")) in names]

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return

        target = _target(ctx)
        name = normalise(drug.get("name", ""))
        assessment = _assessment(ctx)

        if name in IRRITABILITY_AP_NAMES:
            card.add_reason(
                "ASD-IRRITABILITY-ANTIPSYCHOTIC",
                "Risperidone and aripiprazole have the strongest evidence/approval base for "
                "severe irritability, aggression, tantrums or self-injury in autistic children and adolescents.",
                delta=16,
                references=cite("ASD-IRRITABILITY-ANTIPSYCHOTIC"),
            )
            card.add_caution(
                "ASD-ANTIPSYCHOTIC-MONITOR",
                "Use only for a defined high-risk target behaviour with metabolic, EPS, prolactin "
                "and sedation monitoring, plus planned review and discontinuation if ineffective.",
                delta=-8,
                references=cite("ASD-ANTIPSYCHOTIC-MONITOR"),
            )
            card.add_monitoring("Use a target-behaviour rating such as ABC-I or CGI-I and review benefit/adverse effects within a defined trial.")

        if name in ALPHA2_NAMES:
            if target == "adhd":
                card.add_reason(
                    "ASD-ADHD-ALPHA2",
                    "Alpha-2 agonists can be useful for ASD with hyperactivity, impulsivity, "
                    "sleep dysregulation, tics or aggression/irritability vulnerability.",
                    delta=12,
                    references=cite("ASD-ADHD-ALPHA2"),
                )
            else:
                card.add_reason(
                    "ASD-IRRITABILITY-ALPHA2",
                    "For mild irritability or distress in ASD, an alpha-2 agonist may be considered "
                    "before antipsychotic exposure when behavioural/environmental care is insufficient.",
                    delta=9,
                    references=cite("ASD-IRRITABILITY-ALPHA2"),
                )
            card.add_monitoring("Monitor blood pressure, pulse, sedation, dizziness, constipation and rebound hypertension if stopped abruptly.")

        if name == "atomoxetine":
            card.add_reason(
                "ASD-ADHD-ATOMOXETINE",
                "Atomoxetine is a non-stimulant option for ADHD symptoms in ASD, especially when "
                "anxiety, tics, misuse risk or sleep concerns make stimulants less attractive.",
                delta=8,
                references=cite("ASD-ADHD-ATOMOXETINE"),
            )

        if name == "methylphenidate":
            card.add_reason(
                "ASD-ADHD-STIMULANT",
                "Methylphenidate can reduce ADHD symptoms in autistic children, but response is "
                "less predictable and adverse behavioural effects are more common than in ADHD alone.",
                delta=6,
                references=cite("ASD-ADHD-STIMULANT"),
            )
            card.add_caution(
                "ASD-STIMULANT-TOLERABILITY",
                "Start with a low, closely monitored trial and stop if irritability, anxiety, appetite, "
                "sleep or stereotypies worsen.",
                delta=-8,
                references=cite("ASD-STIMULANT-TOLERABILITY"),
            )

        if name in {"buspirone", "mirtazapine"} and target == "anxiety":
            card.add_reason(
                "ASD-ANXIETY-BUSPIRONE-MIRTAZAPINE",
                "For anxiety in ASD, buspirone or mirtazapine may be preferred before SSRIs in "
                "selected patients because of lower behavioural-activation risk.",
                delta=10,
                references=cite("ASD-ANXIETY-BUSPIRONE-MIRTAZAPINE"),
            )

        if name in {"sertraline", "fluoxetine"} and target in {"anxiety", "repetitive_behaviour"}:
            card.add_caution(
                "ASD-SSRI-ACTIVATION",
                "SSRIs may help comorbid anxiety/OCD-like symptoms, but do not reliably improve "
                "core repetitive behaviours in autistic children and may cause activation, agitation or irritability.",
                delta=-10,
                references=cite("ASD-SSRI-ACTIVATION"),
            )
            card.add_monitoring("Monitor early activation, sleep, irritability, suicidality, GI effects and behavioural worsening.")

        if name in DEPRESSION_NAMES and target == "depression":
            card.add_reason(
                "ASD-DEPRESSION-TARGETED",
                "Treat depressive disorder in ASD as a distinct comorbidity with objective mood "
                "assessment, adapted psychotherapy and careful medication monitoring.",
                delta=7,
                references=cite("ASD-DEPRESSION-TARGETED"),
            )

        if name == "melatonin":
            card.add_reason(
                "ASD-SLEEP-MELATONIN",
                "Melatonin is the preferred medication option when insomnia or circadian sleep "
                "difficulty in ASD persists despite sleep-hygiene and behavioural sleep interventions.",
                delta=18,
                references=cite("ASD-SLEEP-MELATONIN"),
            )
            if not assessment.sleep_plan_attempted:
                card.add_caution(
                    "ASD-SLEEP-BEHAVIOURAL-FIRST",
                    "Document a behavioural sleep plan and sleep diary before or alongside melatonin unless risk requires urgent relief.",
                    delta=-6,
                    references=cite("ASD-SLEEP-BEHAVIOURAL-FIRST"),
                )

        if _needs_psychosocial_first(ctx):
            card.add_caution(
                "ASD-PSYCHOSOCIAL-FIRST",
                "Non-pharmacological and environmental interventions have not been documented; "
                "medication should not replace behavioural, communication and sensory supports.",
                delta=-14,
                references=cite("ASD-PSYCHOSOCIAL-FIRST"),
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        missing: list[str] = []
        assessment = _assessment(ctx)
        target = _target(ctx)

        if target == "none":
            missing.append(
                "Select one ASD target symptom domain before medication ranking: irritability/aggression/self-injury, ADHD symptoms, anxiety/OCD-like symptoms, depression, sleep, feeding, repetitive behaviour, or acute distress/agitation."
            )
        if target != "none" and not assessment.target_behaviour_defined:
            missing.append(
                "Define the target symptom in observable terms, with baseline frequency, severity, duration, triggers and functional impact."
            )
        if target != "none" and not assessment.baseline_measure_recorded:
            missing.append(
                "Record a baseline measure for the target symptom (for example ABC-I/CGI-I for irritability, ADHD scale, sleep diary, anxiety/mood scale, or feeding/nutrition baseline)."
            )
        if target in {"irritability", "distress_agitation", "adhd", "anxiety", "repetitive_behaviour"}:
            if not assessment.functional_behaviour_assessment_done:
                missing.append(
                    "Complete functional behaviour assessment: antecedents, consequences, communication function, reinforcement pattern and caregiver/school context."
                )
            if not assessment.communication_needs_reviewed:
                missing.append(
                    "Review communication needs and augmentative/visual supports before interpreting behaviour as primary psychiatric symptoms."
                )
            if not assessment.sensory_triggers_reviewed:
                missing.append(
                    "Review sensory triggers, changes in routine, environmental demands and caregiver/school stressors."
                )
        if target != "none" and not assessment.medical_or_environmental_triggers_reviewed:
            missing.append(
                "Review medical and environmental contributors before medication escalation: pain, constipation, seizures, sleep disorder, infection, medication effects, bullying, trauma, routine change and caregiver stress."
            )
        if target != "none" and _needs_psychosocial_first(ctx):
            missing.append(
                "Document attempted or unavailable behavioural/educational/environmental intervention before medication, unless immediate risk justifies urgent symptomatic treatment."
            )
        if target == "sleep":
            if assessment.sleep_log_days is None or assessment.sleep_log_days < 7:
                missing.append(
                    "Use a sleep diary or caregiver sleep log for at least one week where feasible before medication escalation."
                )
            if not assessment.sleep_plan_attempted:
                missing.append(
                    "Document behavioural sleep intervention: consistent routine, light/screen timing, sensory environment, caffeine/stimulant review and night-time reinforcement plan."
                )
        if target == "feeding" and not assessment.feeding_nutritional_assessment_done:
            missing.append(
                "Feeding target: complete nutrition/growth review, food allergy/medical review, sensory and oral-motor assessment, and mealtime behaviour assessment."
            )
        return missing

    def extra_red_flags(self, ctx: PatientContext) -> list[str]:
        flags: list[str] = []
        symptoms = ctx.profile.symptoms
        target = _target(ctx)
        if symptoms.self_injury:
            flags.append(
                "Self-injury in ASD can become medically dangerous; assess injury severity, pain, communication function, abuse/bullying, and urgent safeguarding needs."
            )
        if symptoms.aggression_risk and _irritability_level(ctx) == "severe":
            flags.append(
                "Severe aggression or dangerous irritability in ASD requires urgent risk assessment, environmental de-escalation and a crisis/safety plan."
            )
        if target == "feeding" and (symptoms.poor_oral_intake or ctx.profile.weight_kg is not None and ctx.profile.weight_kg < 10):
            flags.append(
                "Feeding restriction or poor intake can cause dehydration, malnutrition or growth compromise; involve paediatrics/nutrition urgently when clinically significant."
            )
        if target == "depression" and (ctx.profile.suicide_risk or ctx.suicidality in {"ideation_with_plan", "recent_attempt"}):
            flags.append(
                "Depression with suicidality in an autistic child/adolescent requires urgent safety planning and specialist mental-health review."
            )
        return flags

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        target = _target(ctx)
        notes = [
            "ASD medication rule: do not prescribe to treat autism itself or core social-communication differences. Medication is only for a defined co-occurring target symptom or high-risk behaviour.",
            "Start with psychoeducation, parent/caregiver support, school accommodations, communication supports, visual schedules, sensory/environmental modification and behavioural intervention whenever feasible.",
            "When medication is used in ASD, define the target symptom, baseline measure, expected benefit, adverse-effect monitoring and stop/review point before starting.",
        ]
        if target in IRRITABILITY_TARGETS:
            notes.append(
                "Irritability/aggression/self-injury sequence: assess medical/sensory/communication triggers first; for mild presentations consider alpha-2 agonist after supports; for severe tantrums, aggression or self-injury, risperidone or aripiprazole are the best-supported options with metabolic/EPS/prolactin monitoring."
            )
        elif target == "adhd":
            notes.append(
                "ASD with ADHD symptoms: alpha-2 agonists or atomoxetine may be attractive when sleep, anxiety, tics, aggression or misuse risk are prominent; methylphenidate can be used with low-dose, closely monitored trials."
            )
        elif target == "anxiety":
            notes.append(
                "ASD anxiety: adapt CBT/behavioural supports to language and cognitive level. Buspirone or mirtazapine may be considered before SSRIs in selected autistic youth; SSRIs require activation monitoring."
            )
        elif target == "repetitive_behaviour":
            notes.append(
                "Repetitive behaviour: distinguish core restricted/repetitive behaviour from OCD-like distressing compulsions. Do not use SSRIs for core repetitive behaviour alone; consider them only for comorbid anxiety/OCD-like symptoms with careful monitoring."
            )
        elif target == "depression":
            notes.append(
                "Mood symptoms in ASD require objective assessment and careful differential diagnosis: puberty, environmental change, loss, bullying, social failure experiences, sleep disorder, psychosis, bipolar disorder and medication effects."
            )
        elif target == "sleep":
            notes.append(
                "Sleep sequence: sleep diary and behavioural sleep plan first; melatonin is the preferred medication if insomnia or circadian sleep difficulty persists."
            )
        elif target == "feeding":
            notes.append(
                "Feeding problems in ASD are managed primarily with nutrition, sensory/oral-motor, speech-language and behavioural mealtime intervention; there is no routine medication branch."
            )
        return notes

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        return [
            "Parent/caregiver psychoeducation and support; coordinate with school and paediatric services.",
            "Applied behaviour analysis or other structured behavioural intervention focused on functionally defined targets.",
            "Communication supports such as visual schedules, PECS/social stories or augmentative communication when indicated.",
            "Occupational-therapy/sensory assessment and environmental modification for sensory triggers.",
            "Individualised education plan, social-skills work and CBT adapted to language/cognitive level for anxiety or anger where appropriate.",
            "Feeding, sleep and medical comorbidities should be addressed with paediatrics, nutrition, speech-language and OT input when relevant.",
        ]


MODULE = register(
    AutismSpectrumDisorderModule(
        diagnosis="autism_spectrum_disorder",
        display_name="Autism spectrum disorder",
    )
)
