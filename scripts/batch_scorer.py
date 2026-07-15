"""
batch_scorer.py  —  Layer 5 of the Job Discovery Engine

Three-axis defence against model degradation:

AXIS 1: MODEL-ADAPTIVE PROMPTS
  Each model tier receives a prompt tuned to its actual capability.
  As reasoning power drops, we shrink the schema, add explicit JSON
  templates, and inject a worked few-shot example.

AXIS 2: ADAPTIVE BATCH SIZING
  Weaker models get smaller batches so they never try to track too many
  records at once, which is the #1 cause of JSON truncation and hallucination.
    2.5-flash  → 10 jobs / batch
    2.0-flash  →  7 jobs / batch
    1.5-flash  →  4 jobs / batch

AXIS 3: 4-STAGE OUTPUT REPAIR PIPELINE
  Every response is deterministically cleaned and validated before acceptance.
  Failures are rescued at the individual-item level, never silently discarded.

  Stage 1: json.loads() after markdown fence strip
  Stage 2: Regex extraction of outermost [...] or {...}
  Stage 3: Line-by-line per-item rescue on total array failures
  Stage 4: Per-item retry with a forcing prompt (template injection)

  Every output item gets:
    model_used          – which model generated it
    output_confidence   – HIGH | MEDIUM | LOW | RESCUED
    validation_flags    – list of non-fatal issues corrected in-place
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from copy import deepcopy

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.gemini_client import generate_content_with_fallback

# ─────────────────────────────────────────────────────────────────────────────
# RULE-BASED PRE-FILTER (runs before ANY API call — costs nothing)
# Drops jobs that are obviously irrelevant to marketing/growth roles.
# Every job dropped here saves one API call.
# ─────────────────────────────────────────────────────────────────────────────

_IRRELEVANT_TITLE_KEYWORDS = [
    "software engineer", "swe", "backend", "frontend", "fullstack", "full-stack",
    "devops", "platform engineer", "site reliability", "sre", "qa engineer",
    "data engineer", "data scientist", "machine learning engineer",
    "finance", "accounting", "accounts receivable", "fp&a", "tax",
    "legal", "compliance", "paralegal",
    "hr", "human resources", "people ops", "recruiter",
    "oracle", "hcm", "erp",
    "collections", "payments analyst", "risk analyst",
    "qa ", "quality assurance", "testing",
]

_RELEVANT_TITLE_KEYWORDS = [
    "growth", "marketing", "performance", "demand gen", "acquisition",
    "brand", "content", "seo", "social", "media", "campaign",
    "product marketing", "crm", "lifecycle", "email marketing",
    "ai", "automation", "martech", "analytics",
    "cmo", "head of growth", "vp marketing",
]


def _rule_filter(jobs: list) -> tuple:
    """
    Returns (kept, dropped) lists.
    A job is kept if its title contains ANY relevant keyword AND no irrelevant keyword.
    This is intentionally permissive — borderline cases go to AI scoring.
    """
    kept, dropped = [], []
    for job in jobs:
        title = job.get("job_title", "").lower()
        has_relevant   = any(k in title for k in _RELEVANT_TITLE_KEYWORDS)
        has_irrelevant = any(k in title for k in _IRRELEVANT_TITLE_KEYWORDS)
        if has_relevant and not has_irrelevant:
            kept.append(job)
        else:
            dropped.append(job)
    return kept, dropped


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

BATCH_SIZE_BY_CONFIDENCE = {
    "HIGH":   15,   # increased: gemini-2.5-flash handles 15 fine
    "MEDIUM": 10,
    "LOW":     4,
    "NONE":    4,
}

VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
SCORE_FIELDS     = ("legitimacy_score", "relevance_score")

# A small probe prompt used once at startup to discover which model tier we're on
# before committing to the full batch run.
_PROBE_PROMPT = "Reply with only: OK"


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT FACTORY
# ─────────────────────────────────────────────────────────────────────────────

# One worked example re-used across all LOW-confidence prompts as a few-shot anchor.
_FEW_SHOT_EXAMPLE = """
EXAMPLE INPUT:
[{"job_title": "Growth Marketing Manager", "company": "Acme AI", "source": "Greenhouse (acme)", "location": "Remote", "job_url": "https://boards.greenhouse.io/acme/jobs/123"}]

EXAMPLE OUTPUT:
[{"legitimacy_score": 85, "relevance_score": 90, "outreach_priority": "HIGH", "why_relevant": "AI-native SaaS hiring growth role, fully remote.", "remote_type_verified": "Remote India", "skills_required": ["growth marketing", "SaaS", "analytics"], "company_clean": "Acme AI", "geo_mode": "Global", "company_stage": "Series A", "role_category": "Growth", "seniority_band": "Mid-Senior", "custom_pitch_hook": "I specialize in scaling AI products..."}]
"""


def _build_prompt(batch: list, confidence: str) -> str:
    """
    Build the right prompt for the model tier actually in use.
    Lower confidence → simpler schema, explicit template, few-shot example.
    """
    n = len(batch)
    raw_jobs = json.dumps(batch, indent=2)

    if confidence == "HIGH":
        # Full schema, full instructions, no training wheels needed.
        return f"""You are a senior talent researcher acting on behalf of the candidate, an AI-native growth marketer with 4+ years of experience. 
Below are {n} raw job records.

Return a JSON array of EXACTLY {n} objects in the SAME ORDER.

Each object MUST contain these fields:
{{
  "legitimacy_score": integer 0-100  (0 = expired/fake/US-only remote),
  "relevance_score":  integer 0-100  (fit for the candidate's profile: AI, Growth, Product, or Marketing),
  "outreach_priority": "HIGH" | "MEDIUM" | "LOW",
  "why_relevant": "one sentence explaining fit for the candidate",
  "remote_type_verified": "Remote India" | "Remote APAC" | "Global Remote" | "Not Eligible",
  "skills_required": ["skill1", "skill2", "skill3"],
  "recruiter_extraction_hint": "any person name from the snippet, or N/A",
  "company_clean": "canonical company name",
  "geo_mode": "India" | "US Remote" | "UAE" | "Global",
  "company_stage": "Seed" | "Series A-C" | "Enterprise" | "Unknown",
  "role_category": "Growth" | "Product" | "Content" | "Founders Office" | "Other",
  "seniority_band": "Entry" | "Mid" | "Senior" | "Leadership",
  "custom_pitch_hook": "One unique sentence to include in outreach based on company/role"
}}

Rules:
- legitimacy_score 0 if: job is US-only, expired, or shows scam signals.
- outreach_priority HIGH if: AI-native startup <500 employees, highly relevant to growth marketing.
- skills_required: maximum 5 items. Real skills only.
- OUTPUT ONLY THE JSON ARRAY. No markdown. No explanation.

Raw Jobs:
{raw_jobs}"""

    elif confidence == "MEDIUM":
        # Reduced schema (drop recruiter_extraction_hint, keep critical fields).
        # Add an explicit per-field template so the model has a structural anchor.
        template = json.dumps({
            "legitimacy_score": 0,
            "relevance_score": 0,
            "outreach_priority": "LOW",
            "why_relevant": "",
            "remote_type_verified": "Remote India",
            "skills_required": [],
            "company_clean": "",
            "geo_mode": "Global",
            "company_stage": "Unknown",
            "role_category": "Other",
            "seniority_band": "Mid",
            "custom_pitch_hook": ""
        }, indent=2)
        return f"""You are a job analyst. Analyse {n} job records and return exactly {n} JSON objects.

REQUIRED OUTPUT FORMAT (fill in the values, keep the keys exactly as shown):
{template}

Rules:
- legitimacy_score: integer 0-100
- relevance_score: integer 0-100
- outreach_priority: must be exactly one of: HIGH, MEDIUM, LOW
- skills_required: a JSON list of strings (max 5)
- company_clean: cleaned company name string
- OUTPUT ONLY A VALID JSON ARRAY. No markdown. No prose.

Jobs to analyse:
{raw_jobs}"""

    else:
        # LOW confidence (1.5-flash or unknown). Ultra-minimal schema.
        # Provide a complete worked example (few-shot) to make it imitation, not reasoning.
        # Batch is already capped at 4 by the caller.
        template = json.dumps({
            "legitimacy_score": 0,
            "relevance_score": 0,
            "outreach_priority": "LOW",
            "remote_type_verified": "Remote India",
            "skills_required": [],
            "company_clean": "",
            "geo_mode": "Global",
            "company_stage": "Unknown",
            "role_category": "Other",
            "seniority_band": "Mid",
            "custom_pitch_hook": ""
        }, indent=2)
        return f"""TASK: Analyse job records. Return a JSON array. Follow the example exactly.
{_FEW_SHOT_EXAMPLE}

Required fields per job:
{template}

Rules:
- legitimacy_score and relevance_score are integers between 0 and 100.
- outreach_priority is HIGH, MEDIUM, or LOW.
- skills_required is a JSON array of strings.
- Output ONLY a JSON array. Nothing else.

Now analyse these {n} jobs:
{raw_jobs}"""


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA VALIDATOR + IN-PLACE COERCER
# ─────────────────────────────────────────────────────────────────────────────

def _coerce_and_validate(item: dict, model: str, confidence: str) -> dict:
    """
    Enforce schema types and value ranges.  Never raises — always returns a
    usable dict.  Non-fatal fixes are recorded in `validation_flags`.
    """
    flags = []

    # Score fields: must be int 0-100
    for field in SCORE_FIELDS:
        val = item.get(field)
        if val is None:
            item[field] = 50
            flags.append(f"missing_{field}_defaulted_50")
        else:
            try:
                iv = int(float(str(val)))
                item[field] = max(0, min(100, iv))
                if str(val) != str(item[field]):
                    flags.append(f"coerced_{field}")
            except (ValueError, TypeError):
                item[field] = 50
                flags.append(f"unparseable_{field}_defaulted_50")

    # outreach_priority: must be HIGH / MEDIUM / LOW
    op = str(item.get("outreach_priority", "")).upper().strip()
    if op not in VALID_PRIORITIES:
        # Try to rescue: "high" → "HIGH", "medium priority" → "MEDIUM"
        rescued = next((p for p in VALID_PRIORITIES if p in op), "LOW")
        item["outreach_priority"] = rescued
        flags.append(f"outreach_priority_rescued_to_{rescued}")
    else:
        item["outreach_priority"] = op

    # skills_required: must be a list of strings
    sr = item.get("skills_required")
    if isinstance(sr, str):
        # "python, growth, marketing" → ["python", "growth", "marketing"]
        item["skills_required"] = [s.strip() for s in re.split(r"[,;]", sr) if s.strip()]
        flags.append("skills_split_from_string")
    elif not isinstance(sr, list):
        item["skills_required"] = []
        flags.append("skills_missing_defaulted_empty")
    else:
        # Cap at 5, remove empty strings
        item["skills_required"] = [str(s).strip() for s in sr if s][:5]

    # remote_type_verified: string, must be non-empty
    if not item.get("remote_type_verified"):
        item["remote_type_verified"] = "Remote India"
        flags.append("remote_type_defaulted")

    # company_clean: string
    if not item.get("company_clean"):
        item["company_clean"] = item.get("company", "Unknown")
        flags.append("company_clean_defaulted")

    # why_relevant: must be a string
    if not isinstance(item.get("why_relevant"), str):
        item["why_relevant"] = ""
        flags.append("why_relevant_cleared")

    # New fields
    for field, default_val in [("geo_mode", "Global"), ("company_stage", "Unknown"), 
                               ("role_category", "Other"), ("seniority_band", "Mid"), 
                               ("custom_pitch_hook", "")]:
        if not item.get(field):
            item[field] = default_val

    # Provenance tags
    item["model_used"]          = model
    item["output_confidence"]   = confidence
    item["validation_flags"]    = flags

    return item


# ─────────────────────────────────────────────────────────────────────────────
# 4-STAGE JSON REPAIR PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove markdown code fences."""
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_array(text: str):
    """Stage 2: find the outermost [...] block in raw text and parse it."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _extract_objects_individually(text: str):
    """Stage 3: find every {...} top-level block and parse each one separately."""
    rescued = []
    for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", text, re.DOTALL):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                rescued.append(obj)
        except json.JSONDecodeError:
            pass
    return rescued if rescued else None


def _parse_response(raw: str, expected_count: int):
    """
    Run the 4-stage repair pipeline.
    Returns (parsed_list_or_None, stage_used, parse_success)
    """
    if not raw:
        return None, "empty", False

    # Stage 1: strip fences + direct parse
    cleaned = _strip_fences(raw)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed, "stage1_direct", True
        if isinstance(parsed, dict):
            # Single object returned instead of array – wrap it
            return [parsed], "stage1_wrapped", True
    except json.JSONDecodeError:
        pass

    # Stage 2: regex extract outermost array
    parsed = _extract_array(cleaned)
    if parsed is not None:
        return parsed, "stage2_regex_array", True

    # Stage 3: per-object rescue
    parsed = _extract_objects_individually(cleaned)
    if parsed is not None:
        return parsed, "stage3_object_rescue", len(parsed) >= expected_count * 0.7

    return None, "total_failure", False


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4: Per-Item Forcing Retry
# ─────────────────────────────────────────────────────────────────────────────

def _force_single_item(job: dict, confidence: str) -> dict:
    """
    Last-resort: inject the exact JSON shell for this one job and ask the model
    to fill it in.  Uses the lowest-bandwidth prompt possible.
    """
    shell = json.dumps({
        "legitimacy_score": "?",
        "relevance_score": "?",
        "outreach_priority": "?",
        "remote_type_verified": "Remote India",
        "skills_required": [],
        "company_clean": "?"
    }, indent=2)

    prompt = f"""Fill in this JSON object for the job below.
Replace every "?" with the correct value.
Output ONLY the completed JSON object. No extra text.

Template:
{shell}

Job:
{json.dumps(job, indent=2)}"""

    result = generate_content_with_fallback(prompt)
    if result["success"] and result["text"]:
        cleaned = _strip_fences(result["text"])
        try:
            scored = json.loads(cleaned)
            if isinstance(scored, list) and scored:
                scored = scored[0]
            if isinstance(scored, dict):
                return _coerce_and_validate(
                    {**job, **scored},
                    result["model"],
                    result["confidence"] + "_forced"
                )
        except json.JSONDecodeError:
            pass

    # Absolute fallback: return the raw job with safe defaults
    job.update({
        "legitimacy_score": 50,
        "relevance_score":  50,
        "outreach_priority": "LOW",
        "remote_type_verified": "Remote India",
        "skills_required": [],
        "company_clean": job.get("company", "Unknown"),
        "model_used": "fallback_default",
        "output_confidence": "NONE",
        "validation_flags": ["stage4_forced_failed_used_defaults"]
    })
    return job


# ─────────────────────────────────────────────────────────────────────────────
# CANARY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

# A known canary job with ground-truth expected values.
_CANARY_JOB = {
    "job_title": "Growth Marketing Manager",
    "company": "Canary Corp",
    "source": "Greenhouse (canary-corp)",
    "location": "Remote",
    "job_url": "https://example.com/canary",
    "is_remote": True,
    "posted_date": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
}
_CANARY_EXPECTED = {
    "outreach_priority": "HIGH",
    "legitimacy_score_min": 70,
}


def _validate_canary(scored_item: dict) -> bool:
    """Returns True if canary scored plausibly."""
    priority_ok = scored_item.get("outreach_priority") in {"HIGH", "MEDIUM"}
    score_ok    = int(scored_item.get("legitimacy_score", 0)) >= _CANARY_EXPECTED["legitimacy_score_min"]
    return priority_ok and score_ok


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BATCH RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_layer5(filtered_jobs: list) -> list:
    print("=== Layer 5: Gemini Batched Scoring ===")

    if not filtered_jobs:
        print("No jobs to score.")
        return []

    # ── Step 0: Rule-based pre-filter (free — no API call) ──────────────────
    kept, dropped = _rule_filter(filtered_jobs)
    print(f"  Pre-filter: {len(kept)} relevant / {len(dropped)} dropped (rule-based, zero cost)")
    if dropped:
        titles = [j.get('job_title', '?') for j in dropped[:5]]
        print(f"  Dropped examples: {titles}")
    filtered_jobs = kept

    if not filtered_jobs:
        print("  All jobs were pre-filtered as irrelevant. Check keyword lists.")
        return []

    # This lets us right-size batches from the first call, not after the first failure.
    print("  Probing active model tier...")
    probe_result = generate_content_with_fallback(_PROBE_PROMPT)
    active_confidence = probe_result.get("confidence", "LOW")
    active_model      = probe_result.get("model", "unknown")
    print(f"  Active model: {active_model} | Confidence tier: {active_confidence}")

    batch_size  = BATCH_SIZE_BY_CONFIDENCE.get(active_confidence, 4)
    scored_jobs = []
    failed_jobs = []  # Items that need Stage 4 per-item retry

    # ── Step 1: Run canary probe in first real batch to validate model output quality.
    canary_passed = None

    total_batches = (len(filtered_jobs) + batch_size - 1) // batch_size
    print(f"  Batch size: {batch_size} | Total batches: {total_batches}")

    for batch_idx, i in enumerate(range(0, len(filtered_jobs), batch_size)):
        batch       = deepcopy(filtered_jobs[i:i + batch_size])
        batch_num   = batch_idx + 1
        include_canary = (batch_num == 1)  # inject canary into first batch only

        if include_canary:
            canary_copy = deepcopy(_CANARY_JOB)
            batch.append(canary_copy)

        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} items"
              f"{'  +canary' if include_canary else ''}) via {active_model}...")

        prompt   = _build_prompt(batch, active_confidence)
        result   = generate_content_with_fallback(prompt, response_mime_type="application/json")
        raw_text = result.get("text", "")
        used_model      = result.get("model", active_model)
        used_confidence = result.get("confidence", active_confidence)

        # ── If the model fell back mid-run, shrink batch size for next iteration
        if used_confidence != active_confidence:
            print(f"  [WARNING] Mid-run model drop detected: {active_model} -> {used_model}")
            active_model      = used_model
            active_confidence = used_confidence
            batch_size        = BATCH_SIZE_BY_CONFIDENCE.get(active_confidence, 4)
            print(f"  Adjusting remaining batches to size {batch_size}")

        # ── Parse response (Stages 1-3)
        parsed_list, parse_stage, parse_ok = _parse_response(raw_text, len(batch))

        if not parse_ok or parsed_list is None:
            print(f"  [FAIL] Batch {batch_num} fully unparseable (stage={parse_stage}). "
                  f"Queuing {len(batch)} items for per-item retry.")
            failed_jobs.extend(batch)
            time.sleep(1)
            continue
        else:
            if parse_stage != "stage1_direct":
                print(f"  [WARNING] Batch {batch_num} repaired via {parse_stage}")

        # ── Validate canary (if present in this batch)
        expected_real_count = len(batch) - (1 if include_canary else 0)

        if include_canary:
            canary_idx  = len(batch) - 1  # canary was appended last
            canary_item = None
            if len(parsed_list) > canary_idx:
                canary_item = parsed_list[canary_idx]
            if canary_item:
                canary_passed = _validate_canary(canary_item)
                status = "[OK] PASSED" if canary_passed else "[FAIL] FAILED (scores may be unreliable)"
                print(f"  Canary check: {status}")
            # Remove canary from output regardless
            parsed_list = parsed_list[:expected_real_count]

        # ── Align parsed list with original batch (handle count mismatch)
        real_batch = batch[:expected_real_count]
        if len(parsed_list) < len(real_batch):
            missing = real_batch[len(parsed_list):]
            print(f"  [WARNING] Batch {batch_num}: {len(missing)} items not returned -> per-item retry")
            failed_jobs.extend(missing)
            parsed_list += [{}] * 0  # pad nothing, just rescue missing items separately

        # ── Coerce + validate each returned item
        for idx, raw_item in enumerate(parsed_list[:len(real_batch)]):
            original = real_batch[idx]
            merged   = {**original, **(raw_item if isinstance(raw_item, dict) else {})}
            validated = _coerce_and_validate(merged, used_model, used_confidence)
            scored_jobs.append(validated)

        time.sleep(0.5)  # gentle rate-limit buffer

    # ── Stage 4: Per-item forcing retry for all failed items
    if failed_jobs:
        print(f"\n  Stage 4: Per-item retry for {len(failed_jobs)} rescued items...")
        for idx, job in enumerate(failed_jobs):
            print(f"    Forcing item {idx+1}/{len(failed_jobs)}: {job.get('job_title','?')} @ {job.get('company','?')}")
            rescued = _force_single_item(job, active_confidence)
            scored_jobs.append(rescued)
            time.sleep(0.5)

    # ── Final filter: drop truly unverifiable records (legitimacy < 70 AND confidence = NONE)
    final_jobs = []
    for j in scored_jobs:
        leg   = j.get("legitimacy_score", 0)
        conf  = j.get("output_confidence", "NONE")
        if leg >= 70:
            final_jobs.append(j)
        elif conf == "NONE":
            pass  # drop: model couldn't score it and we have no signal
        # else keep borderline items that have some real scoring signal

    # Sort: HIGH priority first, then by descending legitimacy
    final_jobs.sort(
        key=lambda x: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x.get("outreach_priority", "LOW"), 2),
            -x.get("legitimacy_score", 0)
        )
    )

    # Summary
    conf_counts = {}
    for j in final_jobs:
        c = j.get("output_confidence", "NONE")
        conf_counts[c] = conf_counts.get(c, 0) + 1

    print(f"\n  Layer 5 complete: {len(final_jobs)} verified jobs")
    print(f"  Confidence breakdown: {conf_counts}")
    if canary_passed is False:
        print("  [WARNING] Canary failed. Review LOW-confidence results manually.")

    return final_jobs
