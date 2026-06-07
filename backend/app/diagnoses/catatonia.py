"""BAP-aligned rule module for catatonia syndromes.

This pathway deliberately separates ordinary catatonia, malignant catatonia,
neuroleptic malignant syndrome (NMS), and selected withdrawal/special-population
presentations. It provides decision support and escalation prompts, not a
prescription or a substitute for emergency medical care.
"""
from __future__ import annotations

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import enum_value, has_any, normalise


CATATONIA_DIAGNOSES = (
    "catatonia_associated_with_another_mental_disorder",
    "catatonia_induced_by_substances_or_medications",
    "secondary_catatonia",
    "secondary_catatonia_syndrome",
)

DISPLAY_NAMES = {
    "catatonia_associated_with_another_mental_disorder": "Catatonia associated with another mental disorder",
    "catatonia_induced_by_substances_or_medications": "Catatonia induced by substances or medications",
    "secondary_catatonia": "Secondary catatonia",
    "secondary_catatonia_syndrome": "Secondary catatonia syndrome",
}

MOTOR_SIGN_FIELDS = (
    "stupor",
    "mutism",
    "posturing",
    "negativism",
    "stereotypy",
    "echophenomena",
    "rigidity",
    "excitement",
)


def _assessment(ctx: PatientContext):
    return ctx.profile.catatonia_assessment


def _subtype(ctx: PatientContext) -> str:
    return enum_value(_assessment(ctx).subtype)


def _sign_count(ctx: PatientContext) -> int | None:
    recorded = _assessment(ctx).sign_count
    if recorded is not None:
        return recorded
    count = sum(bool(getattr(ctx.profile.symptoms, field)) for field in MOTOR_SIGN_FIELDS)
    return count if count else None


def _lorazepam_outcome(ctx: PatientContext) -> str:
    return enum_value(_assessment(ctx).lorazepam_trial_outcome)


def _lorazepam_adequate(ctx: PatientContext) -> bool:
    assessment = _assessment(ctx)
    if _lorazepam_outcome(ctx) in {"remitted", "intolerable"}:
        return True
    if assessment.lorazepam_trial_limited_by_side_effects:
        return True
    if (
        assessment.lorazepam_current_daily_mg is not None
        and assessment.lorazepam_current_daily_mg >= 16
    ):
        return True
    prior = ctx.previous_response_for("Lorazepam")
    return bool(prior and prior.adequate_trial)


def _persistent_after_lorazepam(ctx: PatientContext) -> bool:
    return _lorazepam_adequate(ctx) and _lorazepam_outcome(ctx) != "remitted"


def _ect_status(ctx: PatientContext) -> str:
    return enum_value(_assessment(ctx).ect_status)


def _nms_severity(ctx: PatientContext) -> str:
    assessment = _assessment(ctx)
    temperature = assessment.temperature_c or 0
    heart_rate = assessment.heart_rate_bpm or 0
    if temperature >= 40 or heart_rate >= 120 or ctx.severity == "emergency":
        return "severe"
    if temperature >= 38 or heart_rate >= 100 or ctx.severity == "severe":
        return "moderate"
    return "mild"


class CatatoniaModule(DiagnosisRuleModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        if not ctx.extended_rules:
            return super().candidate_drugs(ctx, all_drugs)

        subtype = _subtype(ctx)
        names = {"lorazepam"}

        if subtype == "nms":
            severity = _nms_severity(ctx)
            if severity in {"moderate", "severe"}:
                names.update({"amantadine", "bromocriptine"})
            if severity == "severe":
                names.add("dantrolene")
        else:
            ect_status = _ect_status(ctx)
            if _persistent_after_lorazepam(ctx) and ect_status in {
                "partial",
                "none",
                "unavailable",
                "contraindicated",
            }:
                names.update({"amantadine", "memantine"})
            if subtype == "antipsychotic_induced" and _persistent_after_lorazepam(ctx):
                names.add("amantadine")
            if subtype in {"chronic_schizophrenia", "clozapine_withdrawal"}:
                names.add("clozapine")
            if subtype == "periodic":
                names.add("lithium")

        return [drug for drug in all_drugs if normalise(drug.get("name", "")) in names]

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return

        name = normalise(drug.get("name", ""))
        subtype = _subtype(ctx)
        assessment = _assessment(ctx)
        challenge = enum_value(assessment.lorazepam_challenge_response)

        if name == "lorazepam":
            card.add_reason(
                "CAT-LORAZEPAM-FIRSTLINE",
                "Lorazepam is a first-line treatment and can also be used as a diagnostic "
                "challenge when catatonia is suspected.",
                delta=14,
                references=cite("CAT-LORAZEPAM-FIRSTLINE"),
            )
            if challenge in {"positive", "partial"}:
                card.add_reason(
                    "CAT-LORAZEPAM-CHALLENGE",
                    "A positive or partial lorazepam challenge supports proceeding with a "
                    "closely monitored scheduled lorazepam trial.",
                    delta=8,
                    references=cite("CAT-LORAZEPAM-CHALLENGE"),
                )
            if _lorazepam_outcome(ctx) == "remitted":
                card.add_reason(
                    "CAT-LORAZEPAM-RESPONSE",
                    "Recorded remission with lorazepam supports continuation long enough to "
                    "stabilise the underlying disorder, followed by a gradual supervised taper.",
                    delta=6,
                    references=cite("CAT-LORAZEPAM-RESPONSE"),
                )
            if has_any(ctx.profile.comorbidities, ["sleep apnea", "sleep apnoea", "respiratory failure", "copd"]):
                card.add_caution(
                    "CAT-LORAZEPAM-RESPIRATORY",
                    "Respiratory disease or sleep apnoea increases benzodiazepine sedation and "
                    "respiratory-depression risk; use monitored specialist care.",
                    delta=-20,
                    references=cite("CAT-LORAZEPAM-RESPIRATORY"),
                )

        if name in {"amantadine", "memantine"}:
            card.add_reason(
                "CAT-NMDA-LATER",
                "An NMDA-modulating option may be considered after an adequate benzodiazepine "
                "trial when ECT is unavailable, contraindicated, ineffective, or only partially effective.",
                delta=9,
                references=cite("CAT-NMDA-LATER"),
            )
            card.add_caution(
                "CAT-NMDA-EVIDENCE",
                "Evidence is limited compared with benzodiazepines and ECT; use with specialist "
                "review and a defined target and stopping plan.",
                delta=-8,
                references=cite("CAT-NMDA-EVIDENCE"),
            )

        if name == "bromocriptine":
            card.add_reason(
                "CAT-NMS-DOPAMINE-AGONIST",
                "For moderate or severe NMS, bromocriptine is a specialist adjunct alongside "
                "immediate withdrawal of dopamine antagonists and intensive supportive care.",
                delta=12,
                references=cite("CAT-NMS-DOPAMINE-AGONIST"),
            )

        if name == "dantrolene":
            card.add_reason(
                "CAT-NMS-DANTROLENE",
                "Dantrolene is reserved for severe NMS as part of emergency specialist treatment.",
                delta=14,
                references=cite("CAT-NMS-DANTROLENE"),
            )

        if name == "amantadine" and subtype == "nms":
            card.add_reason(
                "CAT-NMS-AMANTADINE",
                "Amantadine is a specialist dopaminergic option for moderate or severe NMS.",
                delta=10,
                references=cite("CAT-NMS-AMANTADINE"),
            )

        if name == "clozapine":
            if subtype == "clozapine_withdrawal":
                card.add_reason(
                    "CAT-CLOZAPINE-WITHDRAWAL",
                    "Clozapine-withdrawal catatonia may respond to carefully supervised clozapine "
                    "reinstatement; ECT is an alternative when reinstatement is unsafe or ineffective.",
                    delta=12,
                    references=cite("CAT-CLOZAPINE-WITHDRAWAL"),
                )
            else:
                card.add_reason(
                    "CAT-CHRONIC-CLOZAPINE",
                    "Chronic mild catatonia in schizophrenia may warrant a specialist clozapine trial.",
                    delta=8,
                    references=cite("CAT-CHRONIC-CLOZAPINE"),
                )

        if name == "lithium":
            card.add_reason(
                "CAT-PERIODIC-LITHIUM",
                "Lithium may be considered for prophylaxis of periodic catatonia after the acute "
                "episode has been treated.",
                delta=6,
                references=cite("CAT-PERIODIC-LITHIUM"),
            )
            card.add_caution(
                "CAT-PERIODIC-NOT-ACUTE",
                "Lithium is a recurrence-prevention option for periodic catatonia, not a substitute "
                "for acute benzodiazepine or ECT treatment.",
                delta=-5,
                references=cite("CAT-PERIODIC-NOT-ACUTE"),
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []

        missing: list[str] = []
        assessment = _assessment(ctx)
        sign_count = _sign_count(ctx)
        investigations = ctx.profile.investigations_done

        if sign_count is None:
            missing.append(
                "Record the number of characteristic catatonia signs; the recommended diagnostic threshold is at least three."
            )
        elif sign_count < 3:
            missing.append(
                "Fewer than three characteristic signs are recorded: reassess the diagnosis and differential before applying a catatonia treatment pathway."
            )
        if assessment.bfcrs_score is None:
            missing.append(
                "Record a validated severity measure (BFCRS in adults or an appropriate paediatric scale such as PCRS)."
            )
        if not has_any(investigations, ["physical examination", "neurological examination", "neuro exam"]):
            missing.append(
                "Document collateral history plus physical and neurological examination, including volume status, pressure injury, rigidity and focal signs."
            )
        if ctx.profile.labs.creatine_kinase is None or ctx.profile.labs.serum_iron is None:
            missing.append(
                "Complete the cause/complication screen as indicated: CBC, renal and liver function, electrolytes (especially sodium), glucose, CK, inflammatory markers, serum iron and toxicology."
            )
        if assessment.first_episode:
            if not has_any(investigations, ["ct brain", "mri brain", "neuroimaging"]):
                missing.append(
                    "First episode or unclear cause: consider CT/MRI brain guided by the clinical presentation."
                )
            if not has_any(investigations, ["autoimmune", "nmda receptor antibody", "encephalitis", "csf"]):
                missing.append(
                    "First episode or unclear cause: consider serum and CSF neuronal autoantibodies, including anti-NMDA-receptor testing."
                )
        if (
            ctx.profile.seizure_disorder
            or ctx.profile.symptoms.altered_consciousness
            or has_any(ctx.profile.comorbidities, ["encephalitis", "seizure", "fluctuating consciousness"])
        ) and not has_any(investigations, ["eeg", "electroencephal"]):
            missing.append(
                "Obtain EEG when non-convulsive status epilepticus, encephalitis, seizure activity or fluctuating consciousness is possible."
            )
        if _subtype(ctx) in {"malignant", "nms"}:
            if assessment.temperature_c is None or assessment.heart_rate_bpm is None:
                missing.append(
                    "Record temperature, pulse, blood pressure, respiratory status and serial autonomic observations immediately."
                )
        if enum_value(assessment.lorazepam_challenge_response) == "not_done":
            missing.append(
                "Document whether a monitored lorazepam challenge is appropriate; do not let investigations delay urgent treatment."
            )
        return missing

    def extra_red_flags(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []

        flags: list[str] = []
        subtype = _subtype(ctx)
        symptoms = ctx.profile.symptoms
        assessment = _assessment(ctx)

        if subtype == "malignant" or (
            symptoms.hyperthermia and symptoms.autonomic_instability
        ):
            flags.append(
                "Possible malignant catatonia: medical emergency requiring immediate hospital/ICU-level assessment, withdrawal of dopamine antagonists, supportive care and urgent catatonia treatment."
            )
        if subtype == "nms":
            flags.append(
                "Possible neuroleptic malignant syndrome: stop dopamine antagonists and anticholinergics, transfer for emergency medical care, and treat complications."
            )
            if not assessment.recent_dopamine_antagonist_exposure:
                flags.append(
                    "NMS is selected but recent dopamine-antagonist exposure is not recorded; urgently verify exposure and competing diagnoses."
                )
        if symptoms.poor_oral_intake:
            flags.append(
                "Poor oral intake in catatonia creates dehydration, electrolyte, malnutrition and aspiration risk; assess and support urgently."
            )
        if symptoms.immobility or symptoms.stupor:
            flags.append(
                "Immobility/stupor creates venous thromboembolism, pressure injury, infection and rhabdomyolysis risk; start prevention and monitoring."
            )
        if (
            assessment.temperature_c is not None and assessment.temperature_c >= 38
        ) or symptoms.hyperthermia:
            flags.append(
                "Hyperthermia with catatonic signs requires urgent evaluation for malignant catatonia, NMS, infection and other medical causes."
            )
        if subtype in {"malignant", "nms"} and ctx.care_setting == "outpatient":
            flags.append(
                "The selected emergency catatonia presentation is not appropriate for routine outpatient management."
            )
        return flags

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []

        notes = [
            "Confirm catatonia from observed signs, collateral history and a validated instrument; a practical diagnostic threshold is three or more characteristic signs.",
            "Identify and treat the underlying psychiatric, neurological, medical or substance-related cause while preventing dehydration, aspiration, pressure injury, VTE and rhabdomyolysis.",
            "Benzodiazepines and/or ECT are the evidence-supported first-line treatments. Investigations should be targeted to the differential and must not delay urgent treatment.",
            "Avoid routine antipsychotic treatment when psychosis is absent. If psychosis requires treatment after catatonia stabilises, use a careful specialist risk-benefit assessment, gradual titration and close monitoring.",
        ]
        assessment = _assessment(ctx)
        subtype = _subtype(ctx)
        outcome = _lorazepam_outcome(ctx)
        ect_status = _ect_status(ctx)

        if outcome in {"not_started", "in_progress", "partial", "none"} and not _lorazepam_adequate(ctx):
            notes.append(
                "Lorazepam trial is not yet documented as adequate. BAP defines an adequate trial as remission, stopping because of adverse effects, or titration to at least 16 mg/day without response; complete only in an appropriately monitored setting."
            )
        if _persistent_after_lorazepam(ctx):
            if ect_status in {"not_assessed", "available_not_started"}:
                notes.append(
                    "Persistent catatonia after an adequate lorazepam trial: arrange ECT promptly rather than continuing ineffective medication alone."
                )
            elif ect_status == "in_progress":
                notes.append(
                    "ECT is in progress: monitor objective catatonia severity, medical complications and treatment response after each session."
                )
            elif ect_status in {"partial", "none", "unavailable", "contraindicated"}:
                notes.append(
                    "When ECT is unavailable, contraindicated, ineffective or only partially effective, consider amantadine or memantine with specialist review."
                )
        if outcome == "remitted":
            notes.append(
                "Do not stop lorazepam abruptly after response. Treat the underlying disorder and use a supervised gradual taper; if catatonia relapses, reassess the cause and taper speed."
            )

        if subtype == "malignant":
            notes.extend([
                "Malignant catatonia: stop dopamine antagonists, provide intensive supportive care and start lorazepam urgently.",
                "If response is absent or incomplete within 48-72 hours, arrange urgent bilateral ECT; do not delay while complications progress.",
            ])
        elif subtype == "nms":
            severity = _nms_severity(ctx)
            notes.append(
                f"NMS severity branch: {severity}. Stop dopamine antagonists and anticholinergics and provide ICU-level supportive treatment."
            )
            if severity == "mild":
                notes.append("Mild NMS: lorazepam is the principal medicine considered in the BAP pathway.")
            elif severity == "moderate":
                notes.append(
                    "Moderate NMS: consider lorazepam plus bromocriptine or amantadine, and consider ECT."
                )
            else:
                notes.append(
                    "Severe NMS: consider lorazepam plus dantrolene and bromocriptine or amantadine; strongly consider ECT."
                )
            notes.append(
                "If NMS has not responded adequately within 2-3 days, escalate to ECT. Do not restart an antipsychotic for at least two weeks after full recovery; then choose a lower-risk agent, start low, increase slowly and monitor closely."
            )
        elif subtype == "antipsychotic_induced":
            notes.append(
                "Antipsychotic-induced catatonia: stop the suspected antipsychotic, treat with lorazepam, and consider amantadine only after an inadequate/partial response. Any later antipsychotic restart should be low and slow."
            )
        elif subtype == "benzodiazepine_withdrawal":
            notes.append(
                "Benzodiazepine-withdrawal catatonia: reinstate an appropriate benzodiazepine under supervised care, then plan a gradual taper after stabilisation."
            )
        elif subtype == "clozapine_withdrawal":
            notes.append(
                "Clozapine-withdrawal catatonia: consider carefully supervised clozapine reinstatement or ECT; account for interruption-related retitration and medical safety requirements."
            )
        elif subtype == "chronic_schizophrenia":
            notes.append(
                "Chronic mild catatonia in schizophrenia may respond less reliably to benzodiazepines; specialist clozapine treatment may be considered."
            )
        elif subtype == "periodic":
            notes.append(
                "Periodic catatonia: treat acute episodes with lorazepam and/or ECT; lithium has the strongest published support for recurrence prophylaxis, although evidence remains limited."
            )
        elif subtype == "autism_associated":
            if assessment.clear_change_from_autism_baseline is not True:
                notes.append(
                    "Autism-associated catatonia requires a clear and substantial change from the person's baseline; this has not yet been confirmed."
                )
            notes.append(
                "Autism-associated catatonia: combine environmental/behavioural supports with lorazepam and escalate to ECT for severe or refractory illness."
            )
        return notes

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        return [
            "Use serial BFCRS/PCRS observations and collateral reports to track response.",
            "Provide hydration, nutrition, swallow/aspiration assessment and electrolyte correction.",
            "Prevent venous thromboembolism, pressure injury, contractures, infection and rhabdomyolysis during immobility.",
            "Review and treat the underlying medical, neurological, psychiatric or substance-related cause.",
            "Assess capacity, consent and legal requirements early when ECT may be needed.",
            "Use ICU or high-dependency monitoring for malignant catatonia, NMS or unstable vital signs.",
        ]


for diagnosis in CATATONIA_DIAGNOSES:
    register(
        CatatoniaModule(
            diagnosis=diagnosis,
            display_name=DISPLAY_NAMES[diagnosis],
        )
    )
