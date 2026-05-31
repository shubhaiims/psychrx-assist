"use client";

import { useEffect, useMemo, useState } from "react";
import type { IpsRule, RulesListResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

const DIAGNOSES = [
  "any", "major_depressive_disorder", "bipolar_mania", "bipolar_depression",
  "bipolar_maintenance", "schizophrenia", "acute_psychosis", "ocd",
  "generalized_anxiety_disorder", "panic_disorder", "ptsd", "adhd",
  "alcohol_use_disorder", "opioid_use_disorder", "dementia_related_behavioural_symptoms",
];
const POPULATIONS = [
  "any", "adult", "child", "adolescent", "child_adolescent", "elderly", "pregnant",
  "lactating", "childbearing_potential", "renal_impairment", "hepatic_impairment",
  "cardiac", "seizure", "suicide_risk", "non_adherence",
];
const CATEGORIES = [
  "first_line", "preferred", "relatively_preferred", "most_suitable",
  "use_with_caution", "second_line", "caution", "not_preferred", "relatively_unsuitable",
  "avoid", "contraindicated", "contraindicated_or_avoid", "neutral", "informational", "monitoring",
];
const CONTRA = ["none", "relative", "absolute"];

type FormState = {
  rule_id: string;
  guideline_name: string;
  guideline_section: string;
  diagnosis: string;
  population: string;
  drug_or_drug_class: string;
  recommendation_category: string;
  score_modifier: number;
  contraindication_level: string;
  explanation_for_clinician: string;
  condition: string;
  missing_investigations: string;
  monitoring_required: string;
  citation_title: string;
  citation_page: string;
  citation_url: string;
  citation_year: string;
  last_reviewed_by: string;
  last_reviewed_date: string;
  enabled: boolean;
};

const tokToStr = (v: string | string[] | undefined): string =>
  Array.isArray(v) ? v.join(", ") : (v ?? "");
const strToTok = (s: string): string | string[] => {
  const t = s.trim();
  if (!t) return "any";
  return t.includes(",") ? t.split(",").map((x) => x.trim()).filter(Boolean) : t;
};
const arrToLines = (a: string[] | undefined): string => (a ?? []).join("\n");
const linesToArr = (s: string): string[] => s.split("\n").map((x) => x.trim()).filter(Boolean);
const condToStr = (c: IpsRule["condition"]): string =>
  c == null ? "" : typeof c === "string" ? c : JSON.stringify(c, null, 2);

function emptyForm(): FormState {
  return {
    rule_id: "", guideline_name: "", guideline_section: "", diagnosis: "any",
    population: "any", drug_or_drug_class: "any", recommendation_category: "first_line",
    score_modifier: 0, contraindication_level: "none", explanation_for_clinician: "",
    condition: "", missing_investigations: "", monitoring_required: "", citation_title: "",
    citation_page: "", citation_url: "", citation_year: "", last_reviewed_by: "",
    last_reviewed_date: "", enabled: true,
  };
}

function ruleToForm(r: IpsRule): FormState {
  return {
    rule_id: r.rule_id,
    guideline_name: r.guideline_name ?? "",
    guideline_section: r.guideline_section ?? "",
    diagnosis: tokToStr(r.diagnosis),
    population: tokToStr(r.population),
    drug_or_drug_class: tokToStr(r.drug_or_drug_class),
    recommendation_category: r.recommendation_category,
    score_modifier: r.score_modifier ?? 0,
    contraindication_level: r.contraindication_level ?? "none",
    explanation_for_clinician: r.explanation_for_clinician ?? "",
    condition: condToStr(r.condition),
    missing_investigations: arrToLines(r.missing_investigations),
    monitoring_required: arrToLines(r.monitoring_required),
    citation_title: r.citation_title ?? "",
    citation_page: r.citation_page == null ? "" : String(r.citation_page),
    citation_url: r.citation_url ?? "",
    citation_year: r.citation_year == null ? "" : String(r.citation_year),
    last_reviewed_by: r.last_reviewed_by ?? "",
    last_reviewed_date: r.last_reviewed_date ?? "",
    enabled: r.enabled ?? true,
  };
}

function formToRule(f: FormState): { rule?: IpsRule; error?: string } {
  let condition: IpsRule["condition"] = null;
  const ct = f.condition.trim();
  if (ct) {
    try {
      condition = JSON.parse(ct);
    } catch {
      return { error: "Condition must be valid JSON (or left blank). Example: {\"flags_any\": [\"cardiac_disease\"]}" };
    }
  }
  return {
    rule: {
      rule_id: f.rule_id.trim(),
      guideline_name: f.guideline_name,
      guideline_section: f.guideline_section,
      diagnosis: strToTok(f.diagnosis),
      population: strToTok(f.population),
      drug_or_drug_class: strToTok(f.drug_or_drug_class),
      condition,
      recommendation_category: f.recommendation_category,
      score_modifier: Number(f.score_modifier) || 0,
      explanation_for_clinician: f.explanation_for_clinician,
      missing_investigations: linesToArr(f.missing_investigations),
      monitoring_required: linesToArr(f.monitoring_required),
      contraindication_level: f.contraindication_level,
      citation_title: f.citation_title || null,
      citation_page: f.citation_page || null,
      citation_url: f.citation_url || null,
      citation_year: f.citation_year ? (Number(f.citation_year) || f.citation_year) : null,
      last_reviewed_by: f.last_reviewed_by || null,
      last_reviewed_date: f.last_reviewed_date || null,
      enabled: f.enabled,
    },
  };
}

const matchTok = (field: string | string[] | undefined, want: string): boolean => {
  if (want === "all") return true;
  const toks = Array.isArray(field) ? field : [field ?? ""];
  return toks.map((t) => (t ?? "").toLowerCase()).includes(want.toLowerCase());
};

export default function AdminRules() {
  const [rules, setRules] = useState<IpsRule[]>([]);
  const [problems, setProblems] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [fDiagnosis, setFDiagnosis] = useState("all");
  const [fPopulation, setFPopulation] = useState("all");

  const [form, setForm] = useState<FormState | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/rules`);
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as RulesListResponse;
      setRules(data.rules);
      setProblems(data.problems);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(
    () => rules.filter((r) => matchTok(r.diagnosis, fDiagnosis) && matchTok(r.population, fPopulation)),
    [rules, fDiagnosis, fPopulation]
  );

  function startAdd() {
    setForm(emptyForm());
    setIsNew(true);
    setFormError(null);
  }
  function startEdit(r: IpsRule) {
    setForm(ruleToForm(r));
    setIsNew(false);
    setFormError(null);
  }
  function setField<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((p) => (p ? { ...p, [k]: v } : p));
  }

  async function save() {
    if (!form) return;
    const { rule, error: convErr } = formToRule(form);
    if (convErr || !rule) {
      setFormError(convErr ?? "Invalid form");
      return;
    }
    if (!rule.rule_id) {
      setFormError("rule_id is required");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const url = isNew ? `${API_BASE}/rules` : `${API_BASE}/rules/${encodeURIComponent(rule.rule_id)}`;
      const res = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rule),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail ? JSON.stringify(detail.detail) : await res.text());
      }
      setForm(null);
      await load();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled(r: IpsRule) {
    const action = r.enabled === false ? "enable" : "disable";
    try {
      const res = await fetch(`${API_BASE}/rules/${encodeURIComponent(r.rule_id)}/${action}`, { method: "PATCH" });
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    }
  }

  return (
    <main className="container">
      <section className="hero">
        <h1>Rule editor</h1>
        <p>
          Add, edit, and disable IPS CPG guideline rules without touching code. Changes are
          saved to the rule store immediately and applied to new recommendations.
          <a className="heroLink" href="/"> ← back to recommender</a>
        </p>
      </section>

      <section className="warning">
        Rules are clinical content. Verify each rule against the source guideline and set a
        reviewer name and date before relying on it. Saving here changes live behaviour.
      </section>

      {problems.length > 0 && (
        <div className="danger">
          <h3>Validation problems ({problems.length})</h3>
          <ul>{problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
      )}

      <section className="panel">
        <div className="toolbar">
          <div className="filters">
            <div>
              <label>Filter by diagnosis</label>
              <select value={fDiagnosis} onChange={(e) => setFDiagnosis(e.target.value)}>
                <option value="all">All diagnoses</option>
                {DIAGNOSES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label>Filter by population</label>
              <select value={fPopulation} onChange={(e) => setFPopulation(e.target.value)}>
                <option value="all">All populations</option>
                {POPULATIONS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
          <button className="primaryBtn" onClick={startAdd}>+ Add new rule</button>
        </div>

        {loading ? (
          <p className="muted">Loading rules…</p>
        ) : error ? (
          <pre className="error">{error}</pre>
        ) : (
          <table className="adminTable">
            <thead>
              <tr>
                <th>Rule ID</th><th>Diagnosis</th><th>Population</th><th>Drug / class</th>
                <th>Category</th><th>Δ</th><th>Reviewer</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.rule_id} className={r.enabled === false ? "disabledRow" : ""}>
                  <td><code>{r.rule_id}</code><div className="srcFile">{r._source_file}</div></td>
                  <td>{tokToStr(r.diagnosis)}</td>
                  <td>{tokToStr(r.population)}</td>
                  <td>{tokToStr(r.drug_or_drug_class)}</td>
                  <td>{r.recommendation_category}</td>
                  <td>{r.score_modifier}</td>
                  <td>{r.last_reviewed_by || <span className="muted">—</span>}</td>
                  <td>
                    <span className={`statusDot ${r.enabled === false ? "off" : "on"}`}>
                      {r.enabled === false ? "disabled" : "enabled"}
                    </span>
                  </td>
                  <td className="rowActions">
                    <button onClick={() => startEdit(r)}>Edit</button>
                    <button className="ghost" onClick={() => toggleEnabled(r)}>
                      {r.enabled === false ? "Enable" : "Disable"}
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={9} className="muted">No rules match these filters.</td></tr>
              )}
            </tbody>
          </table>
        )}
        <p className="muted small">{filtered.length} of {rules.length} rules shown.</p>
      </section>

      {form && (
        <section className="panel ruleForm">
          <h2>{isNew ? "Add rule" : `Edit ${form.rule_id}`}</h2>

          <div className="formGrid">
            <div className="full">
              <label>Rule ID</label>
              <input value={form.rule_id} disabled={!isNew}
                onChange={(e) => setField("rule_id", e.target.value)}
                placeholder="IPS-MDD-MY-RULE" />
            </div>

            <div>
              <label>Diagnosis (value, comma-list, or “any”)</label>
              <input value={form.diagnosis} onChange={(e) => setField("diagnosis", e.target.value)} />
            </div>
            <div>
              <label>Population (value, comma-list, or “any”)</label>
              <input value={form.population} onChange={(e) => setField("population", e.target.value)} />
            </div>
            <div>
              <label>Drug or drug class (name, class, or “any”)</label>
              <input value={form.drug_or_drug_class} onChange={(e) => setField("drug_or_drug_class", e.target.value)} />
            </div>
            <div>
              <label>Recommendation category</label>
              <select value={form.recommendation_category} onChange={(e) => setField("recommendation_category", e.target.value)}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label>Score modifier</label>
              <input type="number" value={form.score_modifier}
                onChange={(e) => setField("score_modifier", Number(e.target.value))} />
            </div>
            <div>
              <label>Contraindication level</label>
              <select value={form.contraindication_level} onChange={(e) => setField("contraindication_level", e.target.value)}>
                {CONTRA.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="full">
              <label>Explanation for clinician</label>
              <textarea rows={2} value={form.explanation_for_clinician}
                onChange={(e) => setField("explanation_for_clinician", e.target.value)} />
            </div>

            <div className="full">
              <label>Condition (JSON, or blank). e.g. {`{"flags_any":["cardiac_disease"],"drug_qt_risk_in":["moderate","high"]}`}</label>
              <textarea rows={2} value={form.condition} className="mono"
                onChange={(e) => setField("condition", e.target.value)} />
            </div>

            <div>
              <label>Missing investigations (one per line)</label>
              <textarea rows={3} value={form.missing_investigations}
                onChange={(e) => setField("missing_investigations", e.target.value)} />
            </div>
            <div>
              <label>Monitoring required (one per line)</label>
              <textarea rows={3} value={form.monitoring_required}
                onChange={(e) => setField("monitoring_required", e.target.value)} />
            </div>

            <div>
              <label>Guideline name</label>
              <input value={form.guideline_name} onChange={(e) => setField("guideline_name", e.target.value)} />
            </div>
            <div>
              <label>Guideline section</label>
              <input value={form.guideline_section} onChange={(e) => setField("guideline_section", e.target.value)} />
            </div>

            <div>
              <label>Citation title</label>
              <input value={form.citation_title} onChange={(e) => setField("citation_title", e.target.value)} />
            </div>
            <div>
              <label>Citation page</label>
              <input value={form.citation_page} onChange={(e) => setField("citation_page", e.target.value)} />
            </div>
            <div>
              <label>Citation URL</label>
              <input value={form.citation_url} onChange={(e) => setField("citation_url", e.target.value)} />
            </div>
            <div>
              <label>Citation year</label>
              <input value={form.citation_year} onChange={(e) => setField("citation_year", e.target.value)} />
            </div>

            <div>
              <label>Reviewed by</label>
              <input value={form.last_reviewed_by} onChange={(e) => setField("last_reviewed_by", e.target.value)}
                placeholder="Dr A. Reviewer" />
            </div>
            <div>
              <label>Review date</label>
              <input type="date" value={form.last_reviewed_date}
                onChange={(e) => setField("last_reviewed_date", e.target.value)} />
            </div>

            <div className="checkboxRow full">
              <input id="enabled" type="checkbox" checked={form.enabled}
                onChange={(e) => setField("enabled", e.target.checked)} />
              <label htmlFor="enabled">Enabled (applied to recommendations)</label>
            </div>
          </div>

          {formError && <pre className="error">{formError}</pre>}

          <div className="formActions">
            <button className="primaryBtn" onClick={save} disabled={saving}>
              {saving ? "Saving…" : isNew ? "Create rule" : "Save changes"}
            </button>
            <button className="ghost" onClick={() => setForm(null)} disabled={saving}>Cancel</button>
          </div>
        </section>
      )}
    </main>
  );
}
