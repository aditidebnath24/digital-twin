"""
Standalone Mistral rate-limit diagnostic.

This bypasses your project's LLMProvider entirely and talks to the
Mistral REST API directly with `requests`, so we can:
  1. See the exact HTTP status + body Mistral returns.
  2. Read the rate-limit headers Mistral sends back (if any).
  3. Confirm whether it's a one-off or happens on every call.
  4. Test with a delay between calls to rule out burst/RPS throttling.

Run:
    python test_mistral_limits.py

Requires only `requests` and `python-dotenv` (both likely already
installed since your project uses dotenv).
"""

from __future__ import annotations

import os
import time
import json

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL = os.getenv("LLM_MODEL", "mistral-small-latest")
URL = "https://api.mistral.ai/v1/chat/completions"


def check_key():
    if not API_KEY:
        print("MISTRAL_API_KEY is not set in your environment / .env file.")
        raise SystemExit(1)
    print(f"Using API key: {API_KEY[:6]}...{API_KEY[-4:]}  (length={len(API_KEY)})")
    print(f"Using model:   {MODEL}")


def single_call(label: str):
    print(f"\n--- {label} ---")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 5,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    t0 = time.time()
    resp = requests.post(URL, headers=headers, json=payload, timeout=30)
    elapsed = time.time() - t0

    print(f"Status code : {resp.status_code}  (in {elapsed:.2f}s)")

    # Print any rate-limit-related headers Mistral sends back
    rl_headers = {
        k: v for k, v in resp.headers.items() if "ratelimit" in k.lower() or "retry" in k.lower()
    }
    if rl_headers:
        print("Rate-limit headers:")
        for k, v in rl_headers.items():
            print(f"  {k}: {v}")
    else:
        print("No rate-limit headers returned (Mistral doesn't always send them).")

    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    print("Response body:")
    print(json.dumps(body, indent=2) if isinstance(body, dict) else body)

    return resp.status_code, body


def main():
    check_key()

    # Call 1: immediate
    status1, body1 = single_call("Call 1 (immediate)")

    if status1 == 429:
        print(
            "\n>>> Got 429 on the very first call with a clean request. "
            "This strongly points to an account/tier-level limit "
            "(free tier cap, expired trial, or no billing on file), "
            "not a burst/frequency issue.\n"
        )
    elif status1 == 200:
        print("\n>>> Call 1 succeeded. Now waiting 10s and trying again "
              "to see if repeated calls trigger throttling...\n")
        time.sleep(10)
        status2, body2 = single_call("Call 2 (after 10s wait)")
        if status2 == 429:
            print(
                "\n>>> Call 1 succeeded but Call 2 (after a 10s gap) got 429. "
                "This suggests a very tight per-minute/per-hour or "
                "monthly token cap, not a simple burst issue.\n"
            )
        else:
            print("\n>>> Both calls succeeded. Your account is not "
                  "currently rate-limited under normal usage.\n")
    elif status1 == 401:
        print("\n>>> 401 Unauthorized: your API key itself is invalid/expired. "
              "This is NOT a rate limit — check MISTRAL_API_KEY.\n")
    elif status1 == 403:
        print("\n>>> 403 Forbidden: account/subscription issue (inactive, "
              "suspended, or lacking permission for this model) — "
              "check console.mistral.ai billing/account status.\n")
    else:
        print(f"\n>>> Unexpected status {status1}: see body above for details.\n")


if __name__ == "__main__":
    main()