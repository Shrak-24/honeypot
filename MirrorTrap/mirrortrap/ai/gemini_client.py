"""
mirrortrap/ai/gemini_client.py
──────────────────────────────
Thin wrapper around the Google Generative AI SDK (google-generativeai).
Provides two high-level helpers:
  • analyze_logs()        → returns a structured attacker profile dict
  • generate_fake_data()  → returns a plausible fake credential/file payload

AI Pipeline (analyze_logs):
  Raw logs → summarizer.build_prompt_summary() → compact JSON → Gemini
  Achieves ≥ 70% token reduction vs sending raw rows.
  API response format is unchanged.
"""

import json
import re
import time
import google.generativeai as genai

from mirrortrap.ai.summarizer import build_prompt_summary, estimate_token_reduction

# ---------------------------------------------------------------------------
# Model preference order — gemini-2.0-flash first (best free-tier quota).
# Falls through to cheaper/older models on quota errors or unavailability.
# ---------------------------------------------------------------------------
_MODEL_CANDIDATES = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-pro",
]


# ---------------------------------------------------------------------------
# SDK helpers
# ---------------------------------------------------------------------------

def _get_model(api_key: str, model_name: str) -> genai.GenerativeModel:
    """Configure the SDK and return a GenerativeModel for the given model."""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def _is_quota_error(err_str: str) -> bool:
    return '429' in err_str or 'quota' in err_str.lower() or 'rate' in err_str.lower()


def _is_model_unavailable(err_str: str) -> bool:
    return any(k in err_str.lower() for k in ('not found', 'does not exist', 'deprecated'))


def _generate_with_retry(model: genai.GenerativeModel, prompt: str,
                         max_retries: int = 3) -> str:
    """
    Call model.generate_content() with exponential back-off for 429 errors.
    Always returns a non-empty string or raises — never returns None.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = response.text
            if text:
                return text
            last_exc = ValueError("Gemini returned an empty response.")
            time.sleep(2 ** attempt)
        except Exception as e:
            err = str(e)
            if _is_quota_error(err):
                wait = 2 ** attempt
                print(
                    f"[gemini_client] 429 rate limit (attempt {attempt + 1}/{max_retries}). "
                    f"Waiting {wait}s…"
                )
                time.sleep(wait)
                last_exc = e
            elif _is_model_unavailable(err):
                raise   # signal caller to try next model
            else:
                raise

    raise last_exc or RuntimeError("_generate_with_retry exhausted without result.")


def _extract_json(text: str) -> dict:
    """
    Pull the first JSON block from the model response.
    Falls back to a raw-text result if no valid JSON block is found.
    """
    if not text:
        return {"raw_response": ""}

    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        block = match.group(1)
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        block = match.group(0) if match else None

    if block:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    return {"raw_response": text}


def _try_all_models(api_key: str, prompt: str) -> str:
    """
    Try each model candidate in order. Falls through on model-unavailable
    or quota errors, re-raises only after exhausting all candidates.
    """
    last_quota_exc: Exception | None = None

    for model_name in _MODEL_CANDIDATES:
        try:
            model = _get_model(api_key, model_name)
            return _generate_with_retry(model, prompt)
        except Exception as e:
            err = str(e)
            if _is_model_unavailable(err):
                print(f"[gemini_client] Model '{model_name}' unavailable, trying next…")
                continue
            if _is_quota_error(err):
                print(
                    f"[gemini_client] Quota/rate error on '{model_name}', "
                    f"falling back to next model…"
                )
                last_quota_exc = e
                continue
            raise

    if last_quota_exc:
        raise last_quota_exc
    raise RuntimeError("All Gemini model candidates failed. Check API key and quota.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_logs(logs: list, api_key: str) -> dict:
    """
    Compress raw honeypot logs into a structured summary, then send to
    Gemini to produce an attacker profile.

    Pipeline:
      logs (raw rows)
        → build_prompt_summary()     [group by IP, extract patterns, drop noise]
        → compact JSON               [≥70% fewer tokens than raw]
        → Gemini                     [threat intelligence analysis]
        → structured attacker profile dict

    Parameters
    ----------
    logs    : list[dict]  – mixed rows from attack_logs / activity / sessions
    api_key : str         – Gemini API key

    Returns
    -------
    dict with keys: attacker_type, skill_level, intent, tools_likely_used, summary
    (API response format unchanged)
    """
    if not logs:
        return {"error": "No logs provided for analysis."}

    # ── Step 1: Compress raw logs into compact summary ─────────────────────
    summary = build_prompt_summary(logs)
    reduction_pct = estimate_token_reduction(logs, summary)
    print(
        f"[gemini_client] Log compression: {len(logs)} rows → compact summary "
        f"({reduction_pct:.1f}% token reduction)"
    )

    summary_text = json.dumps(summary, indent=2)

    # ── Step 2: Build focused prompt from compact summary ──────────────────
    prompt = f"""You are a cybersecurity threat intelligence analyst.
Analyze the following honeypot attack summary (pre-processed, compact format) and return
ONLY a JSON object with these exact fields:

- attacker_type      : string  (e.g. "script kiddie", "APT", "opportunistic scanner")
- skill_level        : string  ("low", "medium", "high", "nation-state")
- intent             : string  (brief description of what the attacker was trying to achieve)
- tools_likely_used  : list of strings (inferred tools/techniques from commands and attack patterns)
- summary            : string  (2-3 sentence narrative of the attack campaign)

Attack Summary (compact, grouped by attacker IP):
```json
{summary_text}
```

Key fields explained:
- attack_types: frequency map of attack categories observed
- command_intents: classified intent labels for shell commands executed
- unique_commands: actual shell commands captured during SSH sessions
- credential_combos: number of unique username/password combinations tried

Respond ONLY with a valid JSON object. Do NOT include explanatory text outside the JSON.
"""

    # ── Step 3: Send to Gemini ─────────────────────────────────────────────
    try:
        text = _try_all_models(api_key, prompt)
        return _extract_json(text)
    except Exception as exc:
        return {"error": str(exc)}


def generate_fake_data(context: str, api_key: str) -> dict:
    """
    Ask Gemini to generate believable but entirely fake credential/file data
    tailored to the given attack context.

    Parameters
    ----------
    context : str – free-text description of the target scenario
    api_key : str – Gemini API key

    Returns
    -------
    dict with generated fake data (aws_credentials, db_credentials,
    env_file, internal_config, deploy_script, explanation)
    """
    prompt = f"""You are a cybersecurity honeypot engineer.
Generate ONLY realistic-looking but completely FAKE credential data for this context:

Context: {context}

Return a JSON object with these keys:
- aws_credentials   : object with fake access_key_id, secret_access_key, region
- db_credentials    : object with fake host, port, user, password, dbname per service
- env_file          : string — a realistic .env file body with fake values
- internal_config   : string — a realistic internal config snippet (INI or YAML)
- deploy_script     : string — a short bash/shell script referencing the fake credentials
- explanation       : string — one sentence confirming these are fake honeypot lures

Rules:
- AWS key IDs must start with "AKIA" and be 20 chars long
- Passwords must look strong (mixed case, digits, symbols) but be fake
- NEVER use real credentials
- Respond ONLY with a valid JSON object
"""

    try:
        text = _try_all_models(api_key, prompt)
        return _extract_json(text)
    except Exception as exc:
        return {"error": str(exc)}
