import secrets
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from app.monitoring import init_sentry
from app.models import PatientProfile, RecommendationReport, RecommendationResponse, IpsRuleModel
from app.engine.presentation import build_report
from app.engine.ips_rules import load_ips_rules, ips_rule_problems, reload as reload_ips_rules
from app.engine import rule_store
from app.rules_engine import generate_recommendations

init_sentry()


def parse_cors_origins() -> tuple[list[str], bool]:
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if origins == ["*"]:
        return origins, False
    return origins, True


def rule_store_is_read_only() -> bool:
    if os.getenv("RULE_STORE_READ_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return bool(os.getenv("VERCEL")) and not rule_store.has_persistent_store()


def configured_admin_token() -> str:
    return os.getenv("ADMIN_AUTH_TOKEN", "").strip()


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    token = configured_admin_token()
    if not token:
        return
    if not x_admin_token or not secrets.compare_digest(x_admin_token, token):
        raise HTTPException(status_code=401, detail="Admin token required for rule editing.")


app = FastAPI(
    title="PsychRx Assist API",
    description="Clinician-facing psychiatry medication decision-support starter API.",
    version="0.2.0"
)

cors_allow_origins, cors_allow_credentials = parse_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "PsychRx Assist API running"}


@app.post("/recommend", response_model=RecommendationReport)
def recommend(profile: PatientProfile):
    """Primary endpoint: returns the rich, frontend-ready report (all 12 sections)."""
    return build_report(profile)


@app.post("/recommend/raw", response_model=RecommendationResponse)
def recommend_raw(profile: PatientProfile):
    """Engine result before presentation formatting (useful for debugging/integration)."""
    return generate_recommendations(profile)


@app.get("/rules/ips")
def ips_rules_health(reload: bool = False):
    """Validate and summarise the JSON IPS CPG rules. Pass ?reload=true to re-read the
    folder after editing files. ``problems`` lists any rules that failed validation
    (those are excluded from application until fixed)."""
    if reload:
        reload_ips_rules()
    rules = load_ips_rules()
    problems = ips_rule_problems()
    by_file: dict = {}
    for r in rules:
        by_file.setdefault(r.get("_source_file", "?"), []).append(r["rule_id"])
    return {
        "ok": len(problems) == 0,
        "rule_count": len(rules),
        "problems": problems,
        "rules_by_file": by_file,
    }


@app.get("/rules/store/status")
def rule_store_status():
    return {
        "persistent": rule_store.has_persistent_store(),
        "read_only": rule_store_is_read_only(),
        "admin_token_required": bool(configured_admin_token()),
    }


# --------------------------------------------------------------------------- #
# Admin rule editor API (CRUD over the JSON rule store)                       #
# --------------------------------------------------------------------------- #
# NOTE: route order matters — the static /rules/ips above must precede the
# parametrised /rules/{rule_id} routes below.

@app.get("/rules")
def list_rules(
    diagnosis: str | None = Query(default=None),
    population: str | None = Query(default=None),
    include_disabled: bool = Query(default=True),
):
    """All guideline rules (optionally filtered). Each item includes its source file and
    enabled flag, plus any validation problems for the folder."""
    return {
        "rules": rule_store.list_rules(diagnosis=diagnosis, population=population,
                                       include_disabled=include_disabled),
        "problems": rule_store.list_problems(),
    }


@app.post("/rules", status_code=201)
def create_rule(
    rule: IpsRuleModel,
    file: str | None = Query(default=None),
    _: None = Depends(require_admin_token),
):
    """Create a new rule. Writes to custom_rules.json by default, or ?file=<name>.json."""
    if rule_store_is_read_only():
        raise HTTPException(
            status_code=503,
            detail="Rule editing is disabled in this deployment because the rule store is read-only.",
        )
    try:
        return rule_store.create_rule(rule.model_dump(), target_file=file)
    except rule_store.RuleConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except rule_store.RuleInvalid as exc:
        raise HTTPException(status_code=422, detail=exc.problems)


@app.get("/rules/{rule_id}")
def get_rule(rule_id: str):
    rule = rule_store.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"rule '{rule_id}' not found")
    return rule


@app.put("/rules/{rule_id}")
def update_rule(rule_id: str, rule: IpsRuleModel, _: None = Depends(require_admin_token)):
    if rule_store_is_read_only():
        raise HTTPException(
            status_code=503,
            detail="Rule editing is disabled in this deployment because the rule store is read-only.",
        )
    try:
        return rule_store.update_rule(rule_id, rule.model_dump())
    except rule_store.RuleNotFound:
        raise HTTPException(status_code=404, detail=f"rule '{rule_id}' not found")
    except rule_store.RuleInvalid as exc:
        raise HTTPException(status_code=422, detail=exc.problems)


@app.patch("/rules/{rule_id}/disable")
def disable_rule(rule_id: str, _: None = Depends(require_admin_token)):
    if rule_store_is_read_only():
        raise HTTPException(
            status_code=503,
            detail="Rule editing is disabled in this deployment because the rule store is read-only.",
        )
    try:
        return rule_store.set_enabled(rule_id, False)
    except rule_store.RuleNotFound:
        raise HTTPException(status_code=404, detail=f"rule '{rule_id}' not found")


@app.patch("/rules/{rule_id}/enable")
def enable_rule(rule_id: str, _: None = Depends(require_admin_token)):
    """Re-enable a previously disabled rule (companion to /disable for the editor toggle)."""
    if rule_store_is_read_only():
        raise HTTPException(
            status_code=503,
            detail="Rule editing is disabled in this deployment because the rule store is read-only.",
        )
    try:
        return rule_store.set_enabled(rule_id, True)
    except rule_store.RuleNotFound:
        raise HTTPException(status_code=404, detail=f"rule '{rule_id}' not found")
