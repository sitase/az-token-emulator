#!/usr/bin/env python3
"""
Demo app — logs the authenticated user's UPN and token expiry every 10–20 s.

Relies on the azure-token-emulator sidecar via:
  IDENTITY_ENDPOINT  — ACA-style managed identity URL
  IDENTITY_HEADER    — matching secret header value
"""

import base64
import datetime
import json
import logging
import os
import random
import time
import urllib.parse
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("demo-app")

IDENTITY_ENDPOINT = os.environ["IDENTITY_ENDPOINT"]
IDENTITY_HEADER = os.environ["IDENTITY_HEADER"]
RESOURCE = os.environ.get("AZURE_RESOURCE", "https://management.azure.com/")


def fetch_token() -> dict:
    params = urllib.parse.urlencode({"api-version": "2019-08-01", "resource": RESOURCE})
    req = urllib.request.Request(
        f"{IDENTITY_ENDPOINT}?{params}",
        headers={"X-IDENTITY-HEADER": IDENTITY_HEADER},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def jwt_claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)  # restore base64 padding
    return json.loads(base64.urlsafe_b64decode(payload))


def log_session() -> None:
    try:
        data = fetch_token()
        claims = jwt_claims(data["access_token"])

        upn = (
            claims.get("upn")
            or claims.get("unique_name")
            or claims.get("preferred_username")
            or claims.get("email")
            or "unknown"
        )
        exp = int(data.get("expires_on") or claims.get("exp", 0))
        expires_at = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)

        log.info("UPN: %s | expires: %s", upn, expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"))
    except Exception as exc:
        log.error("Could not fetch/decode token: %s", exc)


if __name__ == "__main__":
    log.info("Demo app started — polling every 10–20 s (resource: %s, endpoint %s)", RESOURCE, IDENTITY_ENDPOINT)
    while True:
        log_session()
        time.sleep(random.uniform(10, 20))
