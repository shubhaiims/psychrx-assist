"use client";

import { useEffect, useState } from "react";
import { DIAGNOSES as CATALOG_DIAGNOSES } from "@/lib/diagnosisCatalog";
import type { RecommendationReport, DrugOption, GuidelineReference } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

const CATATONIA_DIAGNOSES = new Set([
  "catatonia_associated_with_another_mental_disorder",
  "catatonia_induced_by_substances_or_medications",
  "secondary_catatonia",
  "secondary_catatonia_syndrome",
]);

const ASD_DIAGNOSES = new Set(["autism_spectrum_disorder"]);

const SYMPTOMS: [string, string][] = [
  ["psychotic", "Psychotic features"], ["negative", "Prominent negative symptoms"],
  ["manic", "Manic features"],
  ["depressive", "Depressive features"], ["anxiety", "Prominent anxiety"],
  ["ocd", "Obsessions / compulsions"], ["catatonia", "Catatonia"],
  ["agitation", "Agitation"], ["insomnia", "Insomnia"],
  ["nightmares", "Trauma-related nightmares"], ["hyperarousal", "Hyperarousal"],
  ["reexperiencing", "Trauma re-experiencing"], ["avoidance", "Trauma avoidance"],
  ["dissociation", "Dissociative symptoms"],
  ["poor_oral_intake", "Poor oral intake"], ["immobility", "Immobility"],
  ["self_injury", "Self-injury"], ["hyperactivity", "Hyperactivity"],
  ["inattention", "Inattention"], ["impulsivity", "Impulsivity"],
  ["repetitive_behaviour", "Repetitive behaviour"], ["sensory_sensitivity", "Sensory sensitivity"],
  ["communication_difficulty", "Communication difficulty"], ["feeding_problem", "Feeding problem"],
];

const CATATONIA_SIGNS: [string, string][] = [
  ["stupor", "Stupor"], ["mutism", "Mutism"], ["posturing", "Posturing / catalepsy"],
  ["negativism", "Negativism"], ["stereotypy", "Stereotypy / mannerisms"],
  ["echophenomena", "Echolalia / echopraxia"], ["rigidity", "Rigidity"],
  ["excitement", "Catatonic excitement"], ["autonomic_instability", "Autonomic instability"],
  ["hyperthermia", "Hyperthermia"], ["altered_consciousness", "Altered consciousness"],
];

const LABS: [string, string][] = [
  ["egfr", "eGFR"], ["alt", "ALT"], ["ast", "AST"], ["qtc_ms", "QTc (ms)"],
  ["tsh", "TSH"], ["hba1c", "HbA1c (%)"], ["fasting_glucose", "Fasting glucose"],
  ["triglycerides", "Triglycerides"], ["prolactin", "Prolactin"],
  ["anc", "ANC"], ["platelet_count", "Platelets"], ["creatine_kinase", "Creatine kinase"],
  ["serum_iron", "Serum iron"],
];

const list = (s: string): string[] => s.split(",").map((x) => x.trim()).filter(Boolean);
const numOrNull = (s: string): number | null => (s.trim() === "" ? null : Number(s));

type Trial = {
  drug: string;
  response: string;
  adequate_trial: boolean;
  adequate_dose: boolean;
  adequate_duration: boolean;
  duration_weeks: string;
  dose: string;
  adverse: string;
};
type Sym = Record<string, boolean>;

const RECO_LABEL: Record<string, string> = {
  most_suitable: "Most suitable",
  use_with_caution: "Use with caution",
  relatively_unsuitable: "Relatively unsuitable",
  contraindicated_or_avoid: "Contraindicated / avoid",
};

const SAFETY_ACK_KEY = "psychrx_clinician_safety_ack_v1";

function FieldList({ label, items, warn }: { label: string; items?: string[]; warn?: boolean }) {
  if (!items || items.length === 0) return null;
  return (
    <div className={`fieldList ${warn ? "warn" : ""}`}>
      <span className="labelTag">{label}</span>
      <ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

function DrugCard({ o }: { o: DrugOption }) {
  return (
    <article className={`drug ${o.category}`}>
      <header className="drugTop">
        <div className="drugId">
          <h4>{o.drug_name}</h4>
          <span className="drugClass">{o.drug_class}</span>
        </div>
        <div className="drugMeta">
          <span className="scoreLabel">Suitability</span>
          <span className="scoreVal">{o.suitability_score}</span>
        </div>
      </header>
      <p className="reason">{o.reason_for_category}</p>

      <FieldList label="Rationale" items={o.why_suitable} />
      <FieldList label="Cautions" items={o.why_caution} />
      <FieldList label="Why unsuitable" items={o.why_unsuitable} />
      <FieldList label="Interaction warnings" items={o.interaction_warnings} warn />
      <FieldList label="Required baseline tests" items={o.required_baseline_tests} />
      <FieldList label="Monitoring" items={o.monitoring_required} />
      <FieldList label="Key adverse effects" items={o.important_side_effects} />

      <div className="notesGrid">
        <div><span className="noteLabel">Pregnancy / lactation</span><p>{o.pregnancy_lactation_note}</p></div>
        <div><span className="noteLabel">Renal</span><p>{o.renal_note}</p></div>
        <div><span className="noteLabel">Hepatic</span><p>{o.hepatic_note}</p></div>
        {o.elderly_note && <div><span className="noteLabel">Older adults</span><p>{o.elderly_note}</p></div>}
        {o.child_adolescent_note && <div><span className="noteLabel">Child / adolescent</span><p>{o.child_adolescent_note}</p></div>}
      </div>

      <details className="more">
        <summary>Dosing &amp; guideline references</summary>
        <p className="small"><strong>Dose:</strong> {o.dose_note_placeholder}</p>
        <FieldList label="Guideline references" items={o.guideline_reference_placeholder} />
      </details>
    </article>
  );
}

function ResultBlock({ tone, title, count, children }:
  { tone: string; title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className={`resultBlock ${tone}`}>
      <div className="blockHead">
        <h3>{title}</h3>
        {count !== undefined && <span className="count">{count}</span>}
      </div>
      <div className="blockBody">{children}</div>
    </section>
  );
}

function DrugList({ options }: { options: DrugOption[] }) {
  if (options.length === 0) return <p className="muted">No option in this category.</p>;
  return <>{options.map((o) => <DrugCard key={o.drug_name} o={o} />)}</>;
}

function RefsTable({ refs }: { refs: GuidelineReference[] }) {
  if (refs.length === 0) return <p className="muted">No references.</p>;
  return (
    <table className="refs">
      <thead><tr><th>Rule</th><th>Citation</th><th>Type</th><th>Status</th></tr></thead>
      <tbody>
        {refs.map((r) => (
          <tr key={r.rule_id}>
            <td><code>{r.rule_id}</code></td>
            <td>{r.citation}</td>
            <td>{r.source_type}</td>
            <td><span className="statusChip">{r.status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Assessment() {
  const [safetyAccepted, setSafetyAccepted] = useState(false);
  const [safetyChecked, setSafetyChecked] = useState(false);
  const [f, setF] = useState({
    age: 35, sex: "female", height_cm: "165", weight_kg: "70",
    pregnancy_status: "not_pregnant", renal_status: "normal", hepatic_status: "normal",
    diagnosis: "major_depressive_disorder", diagnosis_subtype: "", severity: "moderate",
    care_setting: "outpatient",
    total_duration_months: "", current_episode_duration_weeks: "",
    suicide_risk: false, suicidality: "none", non_adherence_risk: false,
    cardiac_disease: false, seizure_disorder: false, cost_concern: false,
    pregnancy_test_done: false,
    catatonia_subtype: "unspecified", catatonia_sign_count: "", bfcrs_score: "",
    catatonia_first_episode: false, temperature_c: "", heart_rate_bpm: "",
    recent_dopamine_antagonist_exposure: false,
    lorazepam_challenge_response: "not_done", lorazepam_trial_outcome: "not_started",
    lorazepam_current_daily_mg: "", lorazepam_trial_limited_by_side_effects: false,
    ect_status: "not_assessed", clear_change_from_autism_baseline: "",
    asd_target_domain: "none", asd_irritability_level: "absent",
    asd_target_behaviour_defined: false, asd_baseline_measure_recorded: false,
    asd_functional_behaviour_assessment_done: false, asd_psychosocial_intervention_attempted: false,
    asd_psychosocial_unavailable_due_to_severity: false,
    asd_medical_or_environmental_triggers_reviewed: false,
    asd_communication_needs_reviewed: false, asd_sensory_triggers_reviewed: false,
    asd_sleep_plan_attempted: false, asd_sleep_log_days: "",
    asd_feeding_nutritional_assessment_done: false,
  });
  const [sym, setSym] = useState<Sym>({
    psychotic: false, negative: false, manic: false, depressive: false, anxiety: false, ocd: false,
    aggression_risk: false, catatonia: false, agitation: false, insomnia: false,
    nightmares: false, hyperarousal: false, reexperiencing: false, avoidance: false,
    dissociation: false, poor_oral_intake: false, immobility: false,
    stupor: false, mutism: false, posturing: false, negativism: false,
    stereotypy: false, echophenomena: false, rigidity: false, excitement: false,
    autonomic_instability: false, hyperthermia: false, altered_consciousness: false,
    self_injury: false, hyperactivity: false, inattention: false, impulsivity: false,
    repetitive_behaviour: false, sensory_sensitivity: false, communication_difficulty: false,
    feeding_problem: false,
  });
  const [labs, setLabs] = useState<Record<string, string>>({});
  const [familyHistory, setFamilyHistory] = useState("");
  const [familyDrugResp, setFamilyDrugResp] = useState("");
  const [comorbidities, setComorbidities] = useState("");
  const [currentMeds, setCurrentMeds] = useState("");
  const [substanceUse, setSubstanceUse] = useState("");
  const [investigationsDone, setInvestigationsDone] = useState("");
  const [otherPrefs, setOtherPrefs] = useState("");
  const [prefWeight, setPrefWeight] = useState(false);
  const [prefSedation, setPrefSedation] = useState(false);
  const [trials, setTrials] = useState<Trial[]>([]);

  const [result, setResult] = useState<RecommendationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(SAFETY_ACK_KEY);
    if (saved === "accepted") {
      setSafetyAccepted(true);
      setSafetyChecked(true);
    }
  }, []);

  const set = (k: string, v: string | number | boolean) => setF((p) => ({ ...p, [k]: v }));
  const setLab = (k: string, v: string) => setLabs((p) => ({ ...p, [k]: v }));

  function addTrial() {
    setTrials((t) => [...t, {
      drug: "", response: "good", adequate_trial: false, adequate_dose: false,
      adequate_duration: false, duration_weeks: "", dose: "", adverse: "",
    }]);
  }
  function updateTrial(i: number, k: keyof Trial, v: string | boolean) {
    setTrials((t) => t.map((row, idx) => (idx === i ? { ...row, [k]: v } : row)));
  }
  function removeTrial(i: number) {
    setTrials((t) => t.filter((_, idx) => idx !== i));
  }

  async function submit() {
    setLoading(true);
    setError(null);
    setResult(null);
    const preferences = [
      ...(prefWeight ? ["avoid_weight_gain"] : []),
      ...(prefSedation ? ["avoid_sedation"] : []),
      ...list(otherPrefs),
    ];
    const payload = {
      age: Number(f.age), sex: f.sex,
      height_cm: numOrNull(f.height_cm), weight_kg: numOrNull(f.weight_kg),
      pregnancy_status: f.pregnancy_status, renal_status: f.renal_status, hepatic_status: f.hepatic_status,
      cardiac_disease: f.cardiac_disease, seizure_disorder: f.seizure_disorder,
      diagnosis: f.diagnosis, diagnosis_subtype: f.diagnosis_subtype || null,
      severity: f.severity, care_setting: f.care_setting,
      total_duration_months: numOrNull(f.total_duration_months),
      current_episode_duration_weeks: numOrNull(f.current_episode_duration_weeks),
      symptoms: sym,
      catatonia_assessment: {
        subtype: f.catatonia_subtype,
        sign_count: numOrNull(f.catatonia_sign_count),
        bfcrs_score: numOrNull(f.bfcrs_score),
        first_episode: f.catatonia_first_episode,
        temperature_c: numOrNull(f.temperature_c),
        heart_rate_bpm: numOrNull(f.heart_rate_bpm),
        recent_dopamine_antagonist_exposure: f.recent_dopamine_antagonist_exposure,
        lorazepam_challenge_response: f.lorazepam_challenge_response,
        lorazepam_trial_outcome: f.lorazepam_trial_outcome,
        lorazepam_current_daily_mg: numOrNull(f.lorazepam_current_daily_mg),
        lorazepam_trial_limited_by_side_effects: f.lorazepam_trial_limited_by_side_effects,
        ect_status: f.ect_status,
        clear_change_from_autism_baseline:
          f.clear_change_from_autism_baseline === ""
            ? null
            : f.clear_change_from_autism_baseline === "yes",
      },
      asd_assessment: {
        target_domain: f.asd_target_domain,
        irritability_level: f.asd_irritability_level,
        target_behaviour_defined: f.asd_target_behaviour_defined,
        baseline_measure_recorded: f.asd_baseline_measure_recorded,
        functional_behaviour_assessment_done: f.asd_functional_behaviour_assessment_done,
        psychosocial_intervention_attempted: f.asd_psychosocial_intervention_attempted,
        psychosocial_unavailable_due_to_severity: f.asd_psychosocial_unavailable_due_to_severity,
        medical_or_environmental_triggers_reviewed: f.asd_medical_or_environmental_triggers_reviewed,
        communication_needs_reviewed: f.asd_communication_needs_reviewed,
        sensory_triggers_reviewed: f.asd_sensory_triggers_reviewed,
        sleep_plan_attempted: f.asd_sleep_plan_attempted,
        sleep_log_days: numOrNull(f.asd_sleep_log_days),
        feeding_nutritional_assessment_done: f.asd_feeding_nutritional_assessment_done,
      },
      suicide_risk: f.suicide_risk, suicidality: f.suicidality, non_adherence_risk: f.non_adherence_risk,
      cost_concern: f.cost_concern,
      family_history: list(familyHistory),
      family_history_drug_response: list(familyDrugResp),
      comorbidities: list(comorbidities),
      current_medications: list(currentMeds),
      substance_use: list(substanceUse),
      investigations_done: list(investigationsDone),
      preferences,
      previous_drug_responses: trials
        .filter((t) => t.drug.trim())
        .map((t) => ({
          drug: t.drug.trim(),
          response: t.response,
          adequate_trial: t.adequate_trial,
          adequate_dose: t.adequate_dose,
          adequate_duration: t.adequate_duration,
          duration_weeks: numOrNull(t.duration_weeks),
          dose: t.dose.trim() || null,
          adverse_effects: list(t.adverse),
        })),
      labs: {
        ...Object.fromEntries(LABS.map(([k]) => [k, numOrNull(labs[k] ?? "")])),
        pregnancy_test_done: f.pregnancy_test_done || null,
      },
    };
    try {
      const res = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult((await res.json()) as RecommendationReport);
      setTimeout(() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const cs = result?.case_summary;

  function acceptSafetyGate() {
    if (!safetyChecked) return;
    setSafetyAccepted(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SAFETY_ACK_KEY, "accepted");
    }
  }

  if (!safetyAccepted) {
    return (
      <main className="container">
        <section className="safetyGate" aria-labelledby="safety-title">
          <div className="gateBadge">Clinician safety gate</div>
          <h1 id="safety-title">PsychRx Support is for qualified clinicians only</h1>
          <p className="gateLead">
            This website supports structured prescribing decisions, but it does not generate
            prescriptions and must not replace clinical judgement, supervision, consent,
            local policy, or guideline review.
          </p>

          <div className="gateGrid">
            <div className="gateCard">
              <h2>What this tool does</h2>
              <ul>
                <li>Ranks medication options into suitability categories.</li>
                <li>Shows reasons, cautions, missing investigations, and monitoring needs.</li>
                <li>Displays rule metadata so clinician-authored logic can be reviewed.</li>
              </ul>
            </div>
            <div className="gateCard warnCard">
              <h2>What it does not do</h2>
              <ul>
                <li>It does not prescribe, diagnose, or advise patients directly.</li>
                <li>It does not replace emergency care, specialist review, or risk assessment.</li>
                <li>It does not validate that every rule is ready for real-world deployment.</li>
              </ul>
            </div>
          </div>

          <div className="validationNotice">
            <strong>Before clinical use:</strong> all local drug rules, guideline mappings,
            contraindication labels, and monitoring prompts must be independently validated by
            qualified psychiatrists and pharmacists.
          </div>

          <label className="gateCheck">
            <input
              type="checkbox"
              checked={safetyChecked}
              onChange={(e) => setSafetyChecked(e.target.checked)}
            />
            <span>
              I am a qualified clinician or supervised clinical user, and I understand that
              final prescribing responsibility remains with the treating clinician.
            </span>
          </label>

          <button className="gateBtn" onClick={acceptSafetyGate} disabled={!safetyChecked}>
            Enter assessment workspace
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="container">
      <div className="pageHead">
        <h1 id="assessment-form">Prescribing assessment</h1>
        <p className="subtle">
          Enter the clinical profile to generate a ranked, guideline-referenced medication
          assessment. This is decision support for prescribers — not a prescription, and not
          for patient self-treatment.
        </p>
      </div>

      {/* 1. Patient profile */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">1</span>
          <div><h2>Patient profile</h2><p>Demographics and physiology</p></div>
        </div>
        <div className="sectionBody">
          <div className="fieldGrid">
            <div className="field"><label>Age</label>
              <input type="number" value={f.age} onChange={(e) => set("age", Number(e.target.value))} /></div>
            <div className="field"><label>Sex</label>
              <select value={f.sex} onChange={(e) => set("sex", e.target.value)}>
                <option value="female">Female</option><option value="male">Male</option><option value="other">Other</option>
              </select></div>
            <div className="field"><label>Height (cm)</label>
              <input type="number" value={f.height_cm} onChange={(e) => set("height_cm", e.target.value)} /></div>
            <div className="field"><label>Weight (kg)</label>
              <input type="number" value={f.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} /></div>
            <div className="field"><label>Pregnancy / lactation</label>
              <select value={f.pregnancy_status} onChange={(e) => set("pregnancy_status", e.target.value)}>
                <option value="not_applicable">Not applicable</option>
                <option value="not_pregnant">Not pregnant</option>
                <option value="pregnant_first_trimester">Pregnant — 1st trimester</option>
                <option value="pregnant_second_trimester">Pregnant — 2nd trimester</option>
                <option value="pregnant_third_trimester">Pregnant — 3rd trimester</option>
                <option value="lactating">Lactating</option>
                <option value="planning_pregnancy">Planning pregnancy</option>
                <option value="unknown">Unknown</option>
              </select></div>
            <div className="field"><label>Renal function</label>
              <select value={f.renal_status} onChange={(e) => set("renal_status", e.target.value)}>
                <option value="normal">Normal</option><option value="mild_impairment">Mild impairment</option>
                <option value="moderate_impairment">Moderate impairment</option>
                <option value="severe_impairment">Severe impairment</option><option value="unknown">Unknown</option>
              </select></div>
            <div className="field"><label>Hepatic function</label>
              <select value={f.hepatic_status} onChange={(e) => set("hepatic_status", e.target.value)}>
                <option value="normal">Normal</option><option value="mild_impairment">Mild impairment</option>
                <option value="moderate_impairment">Moderate impairment</option>
                <option value="severe_impairment">Severe impairment</option><option value="unknown">Unknown</option>
              </select></div>
          </div>
        </div>
      </section>

      {/* 2. Diagnosis */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">2</span>
          <div><h2>Diagnosis</h2><p>Primary diagnosis, severity and course</p></div>
        </div>
        <div className="sectionBody">
          <div className="fieldGrid">
            <div className="field wide"><label>Primary diagnosis</label>
              <select value={f.diagnosis} onChange={(e) => set("diagnosis", e.target.value)}>
                {CATALOG_DIAGNOSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select></div>
            <div className="field"><label>Subtype / specifier (optional)</label>
              <input type="text" value={f.diagnosis_subtype} placeholder="e.g. treatment-resistant, first episode"
                onChange={(e) => set("diagnosis_subtype", e.target.value)} /></div>
            <div className="field"><label>Severity</label>
              <select value={f.severity} onChange={(e) => set("severity", e.target.value)}>
                <option value="mild">Mild</option><option value="moderate">Moderate</option>
                <option value="severe">Severe</option>
                <option value="severe_with_psychotic_features">Severe with psychotic features</option>
                <option value="emergency">Emergency</option>
              </select></div>
            <div className="field"><label>Care setting</label>
              <select value={f.care_setting} onChange={(e) => set("care_setting", e.target.value)}>
                <option value="outpatient">Outpatient</option>
                <option value="emergency_department">Emergency department</option>
                <option value="inpatient">Psychiatric inpatient</option>
              </select></div>
            <div className="field"><label>Illness duration (months)</label>
              <input type="number" value={f.total_duration_months} onChange={(e) => set("total_duration_months", e.target.value)} /></div>
            <div className="field"><label>Current episode (weeks)</label>
              <input type="number" value={f.current_episode_duration_weeks} onChange={(e) => set("current_episode_duration_weeks", e.target.value)} /></div>
            <div className="field wide"><label>Symptom profile</label>
              <div className="checkGroup">
                {SYMPTOMS.map(([k, l]) => (
                  <div className="checkboxRow" key={k}>
                    <input id={`sym-${k}`} type="checkbox" checked={sym[k]} onChange={(e) => setSym((p) => ({ ...p, [k]: e.target.checked }))} />
                    <label htmlFor={`sym-${k}`}>{l}</label>
                  </div>
                ))}
              </div></div>
            {ASD_DIAGNOSES.has(f.diagnosis) && (
              <>
                <div className="field wide">
                  <label>ASD target-symptom pathway</label>
                  <select value={f.asd_target_domain} onChange={(e) => set("asd_target_domain", e.target.value)}>
                    <option value="none">Choose one target symptom</option>
                    <option value="irritability">Irritability / tantrums / aggression / self-injury</option>
                    <option value="adhd">Hyperactivity / impulsivity / inattention</option>
                    <option value="anxiety">Anxiety / OCD-like symptoms</option>
                    <option value="depression">Depression / mood symptoms</option>
                    <option value="sleep">Sleep disturbance</option>
                    <option value="feeding">Feeding / nutrition problem</option>
                    <option value="repetitive_behaviour">Repetitive behaviour</option>
                    <option value="distress_agitation">Acute distress / agitation</option>
                  </select>
                  <span className="hint">Medication is ranked only for a defined target symptom, not for autism itself.</span>
                </div>
                <div className="field"><label>Irritability / risk level</label>
                  <select value={f.asd_irritability_level} onChange={(e) => set("asd_irritability_level", e.target.value)}>
                    <option value="absent">Absent / not target</option><option value="mild">Mild</option>
                    <option value="moderate">Moderate</option><option value="severe">Severe / dangerous</option>
                  </select></div>
                <div className="field"><label>Sleep log days</label>
                  <input type="number" min="0" max="60" value={f.asd_sleep_log_days}
                    onChange={(e) => set("asd_sleep_log_days", e.target.value)} /></div>
                <div className="field wide">
                  <label>ASD pre-medication checks</label>
                  <div className="checkGroup">
                    <div className="checkboxRow">
                      <input id="asd-target-defined" type="checkbox" checked={f.asd_target_behaviour_defined}
                        onChange={(e) => set("asd_target_behaviour_defined", e.target.checked)} />
                      <label htmlFor="asd-target-defined">Target behaviour defined with frequency/severity/impact</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-baseline" type="checkbox" checked={f.asd_baseline_measure_recorded}
                        onChange={(e) => set("asd_baseline_measure_recorded", e.target.checked)} />
                      <label htmlFor="asd-baseline">Baseline rating/measure recorded</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-fba" type="checkbox" checked={f.asd_functional_behaviour_assessment_done}
                        onChange={(e) => set("asd_functional_behaviour_assessment_done", e.target.checked)} />
                      <label htmlFor="asd-fba">Functional behaviour assessment completed</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-psychosocial" type="checkbox" checked={f.asd_psychosocial_intervention_attempted}
                        onChange={(e) => set("asd_psychosocial_intervention_attempted", e.target.checked)} />
                      <label htmlFor="asd-psychosocial">Behavioural / educational / environmental supports attempted</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-urgent" type="checkbox" checked={f.asd_psychosocial_unavailable_due_to_severity}
                        onChange={(e) => set("asd_psychosocial_unavailable_due_to_severity", e.target.checked)} />
                      <label htmlFor="asd-urgent">Immediate severity/risk means medication cannot wait</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-medical" type="checkbox" checked={f.asd_medical_or_environmental_triggers_reviewed}
                        onChange={(e) => set("asd_medical_or_environmental_triggers_reviewed", e.target.checked)} />
                      <label htmlFor="asd-medical">Medical/environmental triggers reviewed</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-communication" type="checkbox" checked={f.asd_communication_needs_reviewed}
                        onChange={(e) => set("asd_communication_needs_reviewed", e.target.checked)} />
                      <label htmlFor="asd-communication">Communication needs/supports reviewed</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-sensory" type="checkbox" checked={f.asd_sensory_triggers_reviewed}
                        onChange={(e) => set("asd_sensory_triggers_reviewed", e.target.checked)} />
                      <label htmlFor="asd-sensory">Sensory triggers/routine change reviewed</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-sleep-plan" type="checkbox" checked={f.asd_sleep_plan_attempted}
                        onChange={(e) => set("asd_sleep_plan_attempted", e.target.checked)} />
                      <label htmlFor="asd-sleep-plan">Behavioural sleep plan attempted</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="asd-feeding" type="checkbox" checked={f.asd_feeding_nutritional_assessment_done}
                        onChange={(e) => set("asd_feeding_nutritional_assessment_done", e.target.checked)} />
                      <label htmlFor="asd-feeding">Feeding/nutrition and sensory/oral-motor assessment done</label>
                    </div>
                  </div>
                </div>
              </>
            )}
            {CATATONIA_DIAGNOSES.has(f.diagnosis) && (
              <>
                <div className="field wide">
                  <label>Catatonia signs</label>
                  <div className="checkGroup">
                    {CATATONIA_SIGNS.map(([k, l]) => (
                      <div className="checkboxRow" key={k}>
                        <input id={`cat-${k}`} type="checkbox" checked={sym[k]}
                          onChange={(e) => setSym((p) => ({ ...p, [k]: e.target.checked }))} />
                        <label htmlFor={`cat-${k}`}>{l}</label>
                      </div>
                    ))}
                  </div>
                  <span className="hint">Record at least three characteristic signs and use BFCRS in adults or PCRS in children where appropriate.</span>
                </div>
                <div className="field"><label>Catatonia presentation</label>
                  <select value={f.catatonia_subtype} onChange={(e) => set("catatonia_subtype", e.target.value)}>
                    <option value="unspecified">Not yet classified</option>
                    <option value="non_malignant">Non-malignant catatonia</option>
                    <option value="malignant">Malignant catatonia</option>
                    <option value="nms">Neuroleptic malignant syndrome</option>
                    <option value="antipsychotic_induced">Antipsychotic-induced catatonia</option>
                    <option value="benzodiazepine_withdrawal">Benzodiazepine-withdrawal catatonia</option>
                    <option value="clozapine_withdrawal">Clozapine-withdrawal catatonia</option>
                    <option value="chronic_schizophrenia">Chronic schizophrenia-associated catatonia</option>
                    <option value="periodic">Periodic catatonia</option>
                    <option value="autism_associated">Autism-associated catatonia</option>
                  </select></div>
                <div className="field"><label>Number of catatonia signs</label>
                  <input type="number" min="0" max="30" value={f.catatonia_sign_count}
                    onChange={(e) => set("catatonia_sign_count", e.target.value)} /></div>
                <div className="field"><label>BFCRS / PCRS total</label>
                  <input type="number" min="0" max="69" value={f.bfcrs_score}
                    onChange={(e) => set("bfcrs_score", e.target.value)} /></div>
                <div className="field"><label>Temperature (C)</label>
                  <input type="number" step="0.1" min="30" max="45" value={f.temperature_c}
                    onChange={(e) => set("temperature_c", e.target.value)} /></div>
                <div className="field"><label>Heart rate (beats/min)</label>
                  <input type="number" min="20" max="250" value={f.heart_rate_bpm}
                    onChange={(e) => set("heart_rate_bpm", e.target.value)} /></div>
                <div className="field"><label>Lorazepam challenge response</label>
                  <select value={f.lorazepam_challenge_response} onChange={(e) => set("lorazepam_challenge_response", e.target.value)}>
                    <option value="not_done">Not done</option><option value="positive">Positive</option>
                    <option value="partial">Partial</option><option value="negative">No response</option>
                  </select></div>
                <div className="field"><label>Scheduled lorazepam trial</label>
                  <select value={f.lorazepam_trial_outcome} onChange={(e) => set("lorazepam_trial_outcome", e.target.value)}>
                    <option value="not_started">Not started</option><option value="in_progress">In progress</option>
                    <option value="remitted">Remission</option><option value="partial">Partial response</option>
                    <option value="none">No response</option><option value="intolerable">Stopped for adverse effects</option>
                  </select></div>
                <div className="field"><label>Current lorazepam total (mg/day)</label>
                  <input type="number" step="0.5" min="0" max="30" value={f.lorazepam_current_daily_mg}
                    onChange={(e) => set("lorazepam_current_daily_mg", e.target.value)} />
                  <span className="hint">For adequacy assessment only; this tool does not generate a dose.</span></div>
                <div className="field"><label>ECT status</label>
                  <select value={f.ect_status} onChange={(e) => set("ect_status", e.target.value)}>
                    <option value="not_assessed">Not assessed</option><option value="available_not_started">Available, not started</option>
                    <option value="in_progress">In progress</option><option value="remitted">Remission</option>
                    <option value="partial">Partial response</option><option value="none">No response</option>
                    <option value="unavailable">Unavailable</option><option value="contraindicated">Contraindicated</option>
                  </select></div>
                <div className="field wide">
                  <div className="checkGroup">
                    <div className="checkboxRow">
                      <input id="cat-first" type="checkbox" checked={f.catatonia_first_episode}
                        onChange={(e) => set("catatonia_first_episode", e.target.checked)} />
                      <label htmlFor="cat-first">First episode or cause unclear</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="cat-dopamine" type="checkbox" checked={f.recent_dopamine_antagonist_exposure}
                        onChange={(e) => set("recent_dopamine_antagonist_exposure", e.target.checked)} />
                      <label htmlFor="cat-dopamine">Recent dopamine-antagonist exposure</label>
                    </div>
                    <div className="checkboxRow">
                      <input id="cat-side-effects" type="checkbox" checked={f.lorazepam_trial_limited_by_side_effects}
                        onChange={(e) => set("lorazepam_trial_limited_by_side_effects", e.target.checked)} />
                      <label htmlFor="cat-side-effects">Lorazepam trial limited by adverse effects</label>
                    </div>
                  </div>
                </div>
                {f.catatonia_subtype === "autism_associated" && (
                  <div className="field"><label>Clear change from autism baseline?</label>
                    <select value={f.clear_change_from_autism_baseline}
                      onChange={(e) => set("clear_change_from_autism_baseline", e.target.value)}>
                      <option value="">Not established</option><option value="yes">Yes</option><option value="no">No</option>
                    </select></div>
                )}
              </>
            )}
            <div className="field wide"><label>Family history of psychiatric illness</label>
              <input type="text" value={familyHistory} placeholder="e.g. bipolar disorder, schizophrenia"
                onChange={(e) => setFamilyHistory(e.target.value)} />
              <span className="hint">Comma-separated.</span></div>
          </div>
        </div>
      </section>

      {/* 3. Risk assessment */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">3</span>
          <div><h2>Risk assessment</h2><p>Suicide, aggression and adherence risk</p></div>
        </div>
        <div className="sectionBody">
          <div className="fieldGrid">
            <div className="field"><label>Suicidality</label>
              <select value={f.suicidality} onChange={(e) => set("suicidality", e.target.value)}>
                <option value="none">None</option><option value="ideation">Ideation</option>
                <option value="ideation_with_plan">Ideation with plan</option>
                <option value="recent_attempt">Recent attempt</option><option value="unknown">Unknown</option>
              </select></div>
            <div className="field wide">
              <label>Risk flags</label>
              <div className="checkGroup">
                <div className="checkboxRow"><input id="suicide_risk" type="checkbox" checked={f.suicide_risk} onChange={(e) => set("suicide_risk", e.target.checked)} /><label htmlFor="suicide_risk">Suicide risk present</label></div>
                <div className="checkboxRow"><input id="aggression" type="checkbox" checked={sym.aggression_risk} onChange={(e) => setSym((p) => ({ ...p, aggression_risk: e.target.checked }))} /><label htmlFor="aggression">Aggression / violence risk</label></div>
                <div className="checkboxRow"><input id="poor-intake" type="checkbox" checked={sym.poor_oral_intake} onChange={(e) => setSym((p) => ({ ...p, poor_oral_intake: e.target.checked }))} /><label htmlFor="poor-intake">Poor oral intake / refusal</label></div>
                <div className="checkboxRow"><input id="immobility" type="checkbox" checked={sym.immobility} onChange={(e) => setSym((p) => ({ ...p, immobility: e.target.checked }))} /><label htmlFor="immobility">Marked immobility</label></div>
                <div className="checkboxRow"><input id="nonadherence" type="checkbox" checked={f.non_adherence_risk} onChange={(e) => set("non_adherence_risk", e.target.checked)} /><label htmlFor="nonadherence">Non-adherence risk</label></div>
              </div>
            </div>
            <div className="field wide"><label>Substance use</label>
              <input type="text" value={substanceUse} placeholder="e.g. alcohol, opioids, cannabis"
                onChange={(e) => setSubstanceUse(e.target.value)} />
              <span className="hint">Comma-separated.</span></div>
          </div>
        </div>
      </section>

      {/* 4. Medical comorbidity */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">4</span>
          <div><h2>Medical comorbidity</h2><p>Physical illness and concurrent medication</p></div>
        </div>
        <div className="sectionBody">
          <div className="fieldGrid">
            <div className="field wide">
              <label>Comorbidity flags</label>
              <div className="checkGroup">
                <div className="checkboxRow"><input id="cardiac" type="checkbox" checked={f.cardiac_disease} onChange={(e) => set("cardiac_disease", e.target.checked)} /><label htmlFor="cardiac">Cardiac illness</label></div>
                <div className="checkboxRow"><input id="seizure" type="checkbox" checked={f.seizure_disorder} onChange={(e) => set("seizure_disorder", e.target.checked)} /><label htmlFor="seizure">Seizure / neurological disorder</label></div>
              </div>
            </div>
            <div className="field wide"><label>Other comorbidities</label>
              <input type="text" value={comorbidities} placeholder="e.g. diabetes, obesity, hypothyroidism"
                onChange={(e) => setComorbidities(e.target.value)} />
              <span className="hint">Comma-separated.</span></div>
            <div className="field wide"><label>Current medications</label>
              <input type="text" value={currentMeds} placeholder="e.g. ibuprofen, carbamazepine"
                onChange={(e) => setCurrentMeds(e.target.value)} />
              <span className="hint">Used to screen for interactions. Comma-separated.</span></div>
          </div>
        </div>
      </section>

      {/* 5. Previous drug trials */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">5</span>
          <div><h2>Previous drug trials</h2><p>Prior response and tolerability</p></div>
        </div>
        <div className="sectionBody">
          {trials.map((t, i) => (
            <div className="trialRow" key={i}>
              <div className="trialGrid">
                <div className="field"><label>Drug</label>
                  <input type="text" value={t.drug} placeholder="e.g. Sertraline" onChange={(e) => updateTrial(i, "drug", e.target.value)} /></div>
                <div className="field"><label>Response</label>
                  <select value={t.response} onChange={(e) => updateTrial(i, "response", e.target.value)}>
                    <option value="good">Good</option><option value="partial">Partial</option>
                    <option value="none">No response</option><option value="intolerable">Intolerable</option>
                    <option value="unknown">Unknown</option>
                  </select></div>
                <div className="field"><label>Adverse effects</label>
                  <input type="text" value={t.adverse} placeholder="comma-separated" onChange={(e) => updateTrial(i, "adverse", e.target.value)} /></div>
                <div className="field"><label>Dose reached</label>
                  <input type="text" value={t.dose} placeholder="e.g. 150 mg/day" onChange={(e) => updateTrial(i, "dose", e.target.value)} /></div>
                <div className="field"><label>Duration (weeks)</label>
                  <input type="number" value={t.duration_weeks} onChange={(e) => updateTrial(i, "duration_weeks", e.target.value)} /></div>
                <button className="removeBtn" onClick={() => removeTrial(i)} type="button">Remove</button>
              </div>
              <div className="checkboxRow" style={{ marginTop: 10 }}>
                <input id={`adeq-${i}`} type="checkbox" checked={t.adequate_trial} onChange={(e) => updateTrial(i, "adequate_trial", e.target.checked)} />
                <label htmlFor={`adeq-${i}`}>Overall adequate trial</label>
              </div>
              <div className="checkGroup" style={{ marginTop: 10 }}>
                <div className="checkboxRow">
                  <input id={`dose-${i}`} type="checkbox" checked={t.adequate_dose} onChange={(e) => updateTrial(i, "adequate_dose", e.target.checked)} />
                  <label htmlFor={`dose-${i}`}>Adequate dose reached</label>
                </div>
                <div className="checkboxRow">
                  <input id={`duration-${i}`} type="checkbox" checked={t.adequate_duration} onChange={(e) => updateTrial(i, "adequate_duration", e.target.checked)} />
                  <label htmlFor={`duration-${i}`}>Adequate duration completed</label>
                </div>
              </div>
            </div>
          ))}
          <button className="addBtn" onClick={addTrial} type="button">+ Add previous trial</button>
          <div className="field wide" style={{ marginTop: 16 }}>
            <label>Family history of drug response</label>
            <input type="text" value={familyDrugResp} placeholder="e.g. good lithium response in mother"
              onChange={(e) => setFamilyDrugResp(e.target.value)} />
            <span className="hint">Comma-separated.</span>
          </div>
        </div>
      </section>

      {/* 6. Investigations */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">6</span>
          <div><h2>Investigations</h2><p>Baseline labs and tests already done</p></div>
        </div>
        <div className="sectionBody">
          <div className="fieldGrid">
            {LABS.map(([k, l]) => (
              <div className="field" key={k}><label>{l}</label>
                <input type="number" value={labs[k] ?? ""} onChange={(e) => setLab(k, e.target.value)} /></div>
            ))}
          </div>
          <div className="checkboxRow" style={{ marginTop: 14 }}>
            <input id="preg_test" type="checkbox" checked={f.pregnancy_test_done} onChange={(e) => set("pregnancy_test_done", e.target.checked)} />
            <label htmlFor="preg_test">Pregnancy test done</label>
          </div>
          <div className="field wide" style={{ marginTop: 14 }}>
            <label>Investigations already completed</label>
            <input type="text" value={investigationsDone} placeholder="e.g. ECG, fasting lipids, TFTs"
              onChange={(e) => setInvestigationsDone(e.target.value)} />
            <span className="hint">These are removed from the “missing investigations” list. Comma-separated.</span>
          </div>
        </div>
      </section>

      {/* 7. Preferences */}
      <section className="formSection">
        <div className="sectionHead">
          <span className="sectionNum">7</span>
          <div><h2>Preferences</h2><p>Shared decision-making factors</p></div>
        </div>
        <div className="sectionBody">
          <div className="fieldGrid">
            <div className="field wide">
              <label>Treatment preferences</label>
              <div className="checkGroup">
                <div className="checkboxRow"><input id="pw" type="checkbox" checked={prefWeight} onChange={(e) => setPrefWeight(e.target.checked)} /><label htmlFor="pw">Avoid weight gain</label></div>
                <div className="checkboxRow"><input id="ps" type="checkbox" checked={prefSedation} onChange={(e) => setPrefSedation(e.target.checked)} /><label htmlFor="ps">Avoid sedation</label></div>
                <div className="checkboxRow"><input id="cc" type="checkbox" checked={f.cost_concern} onChange={(e) => set("cost_concern", e.target.checked)} /><label htmlFor="cc">Cost is a concern</label></div>
              </div>
            </div>
            <div className="field wide"><label>Other preferences</label>
              <input type="text" value={otherPrefs} placeholder="e.g. once-daily, oral only"
                onChange={(e) => setOtherPrefs(e.target.value)} />
              <span className="hint">Recorded for context. Comma-separated.</span></div>
          </div>
        </div>
      </section>

      <div className="submitBar">
        <button className="genBtn" onClick={submit} disabled={loading}>
          {loading ? "Generating assessment…" : "Generate assessment"}
        </button>
        <span className="submitNote">The output scrolls directly into the assessment summary below.</span>
        {error && <pre className="error">{error}</pre>}
      </div>

      {!result && !loading && (
        <div className="emptyState">Complete the profile above and generate an assessment to see ranked options.</div>
      )}

      {/* 8. Results */}
      {result && cs && (
        <div className="results" id="results">
          <div className="resultsHead"><h2>Assessment</h2></div>

          <div className="summaryBand">
            <p className="summaryText">{cs.summary_text}</p>
            <div className="chips">
              <span className="chip">{cs.diagnosis_display}</span>
              {cs.diagnosis_subtype && <span className="chip">{cs.diagnosis_subtype}</span>}
              <span className="chip">Severity: {cs.severity}</span>
              <span className="chip">{cs.care_setting.replaceAll("_", " ")}</span>
              <span className="chip">{cs.age_group}</span>
              {cs.bmi != null && <span className="chip">BMI {cs.bmi}</span>}
              {cs.pregnancy_status && cs.pregnancy_status !== "not_pregnant" && cs.pregnancy_status !== "not_applicable" && <span className="chip">{cs.pregnancy_status}</span>}
              {cs.renal_status !== "normal" && <span className="chip">renal: {cs.renal_status}</span>}
              {cs.hepatic_status !== "normal" && <span className="chip">hepatic: {cs.hepatic_status}</span>}
              {cs.cardiac_disease && <span className="chip">cardiac</span>}
              {cs.seizure_disorder && <span className="chip">seizure</span>}
              {cs.suicide_risk && <span className="chip warn">suicide risk</span>}
              {cs.non_adherence_risk && <span className="chip">non-adherence</span>}
            </div>
          </div>

          {result.red_flags.length > 0 && (
            <div className="danger">
              <h3>Red flags</h3>
              <ul className="plain">{result.red_flags.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}

          <ResultBlock tone="green" title="Most suitable" count={result.most_suitable_options.length}>
            <DrugList options={result.most_suitable_options} />
          </ResultBlock>

          <ResultBlock tone="amber" title="Use with caution" count={result.use_with_caution.length}>
            <DrugList options={result.use_with_caution} />
          </ResultBlock>

          {result.contraindicated_or_avoid.length > 0 && (
            <ResultBlock tone="red" title="Contraindicated / avoid" count={result.contraindicated_or_avoid.length}>
              <DrugList options={result.contraindicated_or_avoid} />
            </ResultBlock>
          )}

          <ResultBlock tone="red" title="Relatively unsuitable" count={result.relatively_unsuitable.length}>
            <DrugList options={result.relatively_unsuitable} />
          </ResultBlock>

          <ResultBlock tone="blue" title="Missing investigations" count={result.missing_investigations.length}>
            {result.missing_investigations.length === 0
              ? <p className="muted">No outstanding baseline investigations flagged.</p>
              : <ul className="plain">{result.missing_investigations.map((m, i) => <li key={i}>{m}</li>)}</ul>}
          </ResultBlock>

          <ResultBlock tone="neutral" title="Required monitoring">
            {result.required_monitoring.length === 0
              ? <p className="muted">None aggregated for the recommended options.</p>
              : <ul className="plain">{result.required_monitoring.map((m, i) => <li key={i}>{m}</li>)}</ul>}
          </ResultBlock>

          <ResultBlock tone="blue" title="Algorithm notes">
            <ul className="plain">{result.algorithm_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          </ResultBlock>

          <ResultBlock tone="neutral" title="Non-pharmacological recommendations">
            <ul className="plain">{result.non_pharmacological_recommendations.map((n, i) => <li key={i}>{n}</li>)}</ul>
          </ResultBlock>

          <ResultBlock tone="grey" title="Guideline references" count={result.guideline_references.length}>
            <RefsTable refs={result.guideline_references} />
          </ResultBlock>

          <div className="overrideNote">
            <h3>Clinician override</h3>
            <p>{result.clinician_override_note}</p>
          </div>
          <p className="disclaimer">{result.disclaimer}</p>
        </div>
      )}
    </main>
  );
}
