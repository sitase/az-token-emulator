#!/usr/bin/env python3
"""
Azure Managed Identity Token Endpoint Emulator

Emulates two Azure token acquisition surfaces:
  1. IMDS (Instance Metadata Service):
       GET http://169.254.169.254/metadata/identity/oauth2/token
           ?api-version=2018-02-01&resource=<scope>
  2. ACA (Azure Container Apps) managed identity:
       GET $IDENTITY_ENDPOINT?api-version=2019-08-01&resource=<scope>
       Header: X-IDENTITY-HEADER: <IDENTITY_HEADER>

Both are served on port 8080 at:
  /metadata/identity/oauth2/token
  /msi/token

The server reads ~/.azure (mounted from the host) and uses the Azure CLI
credential chain (AzureCliCredential) to acquire tokens, so whatever
account is logged in via `az login` on the host is used.
"""

import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential
from azure.core.exceptions import ClientAuthenticationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("azure-token-emulator")

PORT = int(os.environ.get("PORT", "8080"))
IDENTITY_HEADER = os.environ.get("IDENTITY_HEADER", "emulator-identity-header")

# Build credential chain: try CLI first (uses mounted ~/.azure), fall back to MI
credential = ChainedTokenCredential(
    AzureCliCredential(),
)


def get_token(resource: str) -> dict:
    """Acquire a token for the given resource/scope and return a dict
    matching the Azure IMDS / ACA token response schema."""

    # Normalise: Azure IMDS takes a resource URI; azure-identity wants scopes.
    # If the caller passes a bare resource URI we append /.default.
    if not resource.endswith("/.default") and not resource.endswith("/"):
        scope = resource.rstrip("/") + "/.default"
    else:
        scope = resource

    log.info("Acquiring token for scope: %s", scope)
    token = credential.get_token(scope)

    expires_on = int(token.expires_on) if token.expires_on else int(time.time()) + 3600
    expires_in = max(0, expires_on - int(time.time()))

    return {
        "access_token": token.token,
        "token_type": "Bearer",
        "expires_in": str(expires_in),
        "expires_on": str(expires_on),
        "resource": resource,
        "client_id": os.environ.get("AZURE_CLIENT_ID", "emulated"),
    }


class Handler(BaseHTTPRequestHandler):
    PATHS = {
        "/metadata/identity/oauth2/token",  # IMDS style
        "/msi/token",                        # ACA style
    }

    def log_message(self, fmt, *args):  # redirect to our logger
        log.info(fmt, *args)

    def send_json(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path not in self.PATHS:
            self.send_json(404, {"error": "not_found", "path": parsed.path})
            return

        # resource / scope resolution — clients send either `resource` or `scope`
        resource_list = qs.get("resource") or qs.get("scope") or []
        if not resource_list:
            self.send_json(400, {
                "error": "invalid_request",
                "error_description": "Missing 'resource' or 'scope' query parameter",
            })
            return

        resource = resource_list[0]

        # ACA style requires X-IDENTITY-HEADER; IMDS style requires Metadata: true
        # We accept both but don't hard-fail on missing headers so dev flows are easy.
        identity_hdr = self.headers.get("X-IDENTITY-HEADER", "")
        metadata_hdr = self.headers.get("Metadata", "").lower()
        if not identity_hdr and metadata_hdr != "true":
            log.warning(
                "Request missing both X-IDENTITY-HEADER and 'Metadata: true' — "
                "proceeding anyway (emulator is permissive)"
            )

        try:
            body = get_token(resource)
            log.info("Token acquired, expires_in=%s s", body["expires_in"])
            self.send_json(200, body)
        except ClientAuthenticationError as exc:
            log.error("Authentication failed: %s", exc)
            self.send_json(401, {
                "error": "unauthorized",
                "error_description": str(exc),
            })
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Unexpected error: %s", exc, exc_info=True)
            self.send_json(500, {
                "error": "server_error",
                "error_description": str(exc),
            })

    def do_HEAD(self):
        """Health probe support."""
        self.send_response(200)
        self.end_headers()


if __name__ == "__main__":
    log.info("Azure token emulator starting on port %d", PORT)
    log.info("IDENTITY_HEADER env = %s", IDENTITY_HEADER)
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
