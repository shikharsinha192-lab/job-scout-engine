"""
gemini_client.py  —  Cost-Optimised AI Router

COST OPTIMISATION STRATEGY (applied in this file):
=======================================================
1. FREE-FIRST ABSOLUTE PRIORITY: Free tier is always exhausted before any paid call.
2. DISK CACHE: Every prompt+response is cached to disk by SHA-256 hash.
   Identical or near-identical prompts (same job, re-run) cost ZERO.
3. BACKOFF + RETRY: On 429, we sleep the exact RetryDelay from the API response
   instead of wasting extra calls. We never hammer a rate-limited endpoint.
4. gemini-2.0-flash-lite: Added as a free-tier model. It is the cheapest model
   available and handles short structured tasks (scoring) very well.
5. PAID KEY GUARD: We track paid call count this process and warn loudly at 5.
6. SMART PROMPT TRUNCATION: Helper exported so callers can trim prompts before sending.
"""
import os
import re
import time
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
    has_modern_genai = True
except ImportError:
    import google.generativeai as genai
    has_modern_genai = False

load_dotenv()

FREE_KEY  = os.environ.get("GEMINI_API_KEY_FREE")
PAID_KEY  = os.environ.get("GEMINI_API_KEY_PAID")
if PAID_KEY == FREE_KEY:
    PAID_KEY = None

# ---------------------------------------------------------------------------
# Model tiers — cheapest viable model first within free tier.
# gemini-2.0-flash-lite is FREE and handles structured JSON scoring well.
# Keep 2.5-flash at top because it gives better extraction quality.
# ---------------------------------------------------------------------------
FREE_TIER_MODELS = [
    ("free", "gemini-2.5-flash",       "HIGH"),
    ("free", "gemini-2.5-flash-lite",  "HIGH"),
    ("free", "gemini-flash-latest",    "HIGH"),
    ("free", "gemini-2.0-flash",       "MEDIUM"),
    ("free", "gemini-2.0-flash-lite",  "MEDIUM"),
]
PAID_TIER_MODEL = ("paid", "gemini-2.5-flash", "HIGH")

_RETRY_SLEEP_S = 2
_NOT_FOUND_SIGNALS = ("404", "not found", "does not exist", "model_not_found", "invalid model")
_FAILED_MODELS = set()
_SPEND_CAP_EXCEEDED = False

# ---------------------------------------------------------------------------
# Disk Response Cache
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / ".cache" / "gemini"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(prompt: str, mime: str) -> str:
    h = hashlib.sha256(f"{mime}||{prompt}".encode("utf-8")).hexdigest()
    return h


def _read_cache(key: str):
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_cache_hit"] = True
            return data
        except Exception:
            pass
    return None


def _write_cache(key: str, result: dict):
    path = _CACHE_DIR / f"{key}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            save = {k: v for k, v in result.items() if k != "_cache_hit"}
            json.dump(save, f)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Paid call budget tracker
# ---------------------------------------------------------------------------
_paid_calls_this_session = 0
_PAID_CALL_WARN_AT = 5


def _paid_call_guard():
    global _paid_calls_this_session
    _paid_calls_this_session += 1
    if _paid_calls_this_session >= _PAID_CALL_WARN_AT:
        print(f"  [COST] PAID call #{_paid_calls_this_session} this session. Check your quota!")


# ---------------------------------------------------------------------------
# Retry-delay parser — extract exact seconds from 429 error body
# ---------------------------------------------------------------------------
def _parse_retry_delay(error_str: str) -> float:
    # Google API returns e.g. 'retryDelay': '7.5s'
    m = re.search(r"'retryDelay':\s*'([\d.]+)s'", error_str)
    if m:
        return float(m.group(1))
    return float(_RETRY_SLEEP_S)


# ---------------------------------------------------------------------------
# Raw model caller
# ---------------------------------------------------------------------------
def _call_model(api_key: str, model_name: str, prompt: str, response_mime_type=None) -> str:
    if has_modern_genai:
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))
        if response_mime_type:
            cfg = types.GenerateContentConfig(response_mime_type=response_mime_type)
            resp = client.models.generate_content(model=model_name, contents=prompt, config=cfg)
        else:
            resp = client.models.generate_content(model=model_name, contents=prompt)
        return resp.text.strip()
    else:
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model_name)
        if response_mime_type:
            resp = m.generate_content(prompt, generation_config={"response_mime_type": response_mime_type}, request_options={"timeout": 30.0})
        else:
            resp = m.generate_content(prompt, request_options={"timeout": 30.0})
        return resp.text.strip()


def _is_quota_error(error_str: str) -> bool:
    return any(kw in error_str for kw in ("429", "RESOURCE_EXHAUSTED", "Quota exceeded"))


def _is_spend_cap_error(error_str: str) -> bool:
    err_lower = error_str.lower()
    return any(kw in err_lower for kw in ("spending cap", "spend cap", "spending limit", "spend limit"))


def _is_not_found_error(error_str: str) -> bool:
    err_lower = error_str.lower()
    return any(kw in err_lower for kw in _NOT_FOUND_SIGNALS)


# ---------------------------------------------------------------------------
# Public API — cached, rate-limit-aware cascade
# ---------------------------------------------------------------------------

def generate_content_with_fallback(prompt: str, response_mime_type: str = None,
                                   skip_cache: bool = False) -> dict:
    global _SPEND_CAP_EXCEEDED
    if _SPEND_CAP_EXCEEDED:
        return {"text": "", "model": "none", "confidence": "NONE",
                "key_tier": "none", "success": False}

    mime = response_mime_type or "text"

    # --- Cache lookup ---
    if not skip_cache:
        ckey = _cache_key(prompt, mime)
        cached = _read_cache(ckey)
        if cached:
            print(f"  [Cache] HIT ({cached.get('model')}) — zero API cost")
            return cached

    # --- Free-key cascade ---
    if FREE_KEY:
        for key_tier, model_name, confidence in FREE_TIER_MODELS:
            if model_name in _FAILED_MODELS:
                continue
            try:
                text = _call_model(FREE_KEY, model_name, prompt, response_mime_type)
                print(f"  [Router] [OK] {model_name} (free, confidence={confidence})")
                result = {
                    "text": text, "model": model_name,
                    "confidence": confidence, "key_tier": "free", "success": True,
                }
                if not skip_cache:
                    _write_cache(ckey, result)
                return result
            except Exception as e:
                err = str(e)
                if _is_spend_cap_error(err):
                    print("  [Router] Monthly spend cap exceeded detected. Disabling all API calls.")
                    _SPEND_CAP_EXCEEDED = True
                    return {"text": "", "model": "none", "confidence": "NONE",
                            "key_tier": "none", "success": False}
                if _is_not_found_error(err) or model_name == "gemini-2.5-flash":
                    _FAILED_MODELS.add(model_name)
                    if _is_not_found_error(err):
                        print(f"  [Router] {model_name} skipped (model not found): {err[:80]}")
                        continue
                    print(f"  [Router] {model_name} failed (added to skip list): {err[:120]}")
                else:
                    print(f"  [Router] {model_name} failed transiently (not skipped): {err[:120]}")
                if _is_quota_error(err):
                    delay = _parse_retry_delay(err)
                    print(f"  [Router] Quota hit — sleeping {delay:.1f}s (exact retryDelay)")
                    time.sleep(delay)
                continue

    # --- Paid-key fallback (guarded) ---
    if PAID_KEY:
        _, model_name, confidence = PAID_TIER_MODEL
        print(f"  [Router] All free models exhausted -> PAID key ({model_name})")
        _paid_call_guard()
        try:
            text = _call_model(PAID_KEY, model_name, prompt, response_mime_type)
            result = {
                "text": text, "model": model_name,
                "confidence": confidence, "key_tier": "paid", "success": True,
            }
            if not skip_cache:
                _write_cache(ckey, result)
            return result
        except Exception as e:
            err = str(e)
            if _is_spend_cap_error(err):
                print("  [Router] Monthly spend cap exceeded detected. Disabling all API calls.")
                _SPEND_CAP_EXCEEDED = True
            print(f"  [Router] PAID key also failed: {err}")
            return {"text": "", "model": model_name, "confidence": "NONE",
                    "key_tier": "paid", "success": False}

    print("  [Router] CRITICAL: No API keys configured.")
    return {"text": "", "model": "none", "confidence": "NONE",
            "key_tier": "none", "success": False}


# ---------------------------------------------------------------------------
# Helper: trim a prompt to a max token budget (rough: 1 token ~ 4 chars)
# ---------------------------------------------------------------------------
def trim_prompt(prompt: str, max_tokens: int = 6000) -> str:
    """
    Aggressively trims the middle of a prompt to stay under a token budget.
    Keeps the instruction header and the tail (where output instructions live).
    This prevents ballooning costs from giant resume or JD inputs.
    """
    max_chars = max_tokens * 4
    if len(prompt) <= max_chars:
        return prompt
    # Keep first 60% + last 40%
    head = int(max_chars * 0.60)
    tail = int(max_chars * 0.40)
    truncated = prompt[:head] + "\n...[TRUNCATED FOR TOKEN BUDGET]...\n" + prompt[-tail:]
    print(f"  [TokenGuard] Prompt trimmed: {len(prompt)} -> {len(truncated)} chars")
    return truncated
