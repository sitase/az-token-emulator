# Azure Token Endpoint Emulator

A lightweight Docker image that emulates the Azure Managed Identity token
endpoint for local development with Docker Compose.  It reads credentials from
a `~/.azure` directory mounted from the host (populated by `az login`) and
returns real tokens — so your application code is tested against actual Azure
resources without any code changes.

## How it works

Azure SDKs acquire tokens from one of two surfaces depending on the environment:

| Surface | URL pattern | Required header |
|---|---|---|
| **IMDS** (VMs, AKS) | `http://169.254.169.254/metadata/identity/oauth2/token` | `Metadata: true` |
| **ACA** (Container Apps) | `$IDENTITY_ENDPOINT` | `X-IDENTITY-HEADER: $IDENTITY_HEADER` |

This emulator serves both paths on port **8080**:

```
GET /metadata/identity/oauth2/token?resource=<uri>&api-version=2018-02-01
GET /msi/token?resource=<uri>&api-version=2019-08-01
```

Tokens are obtained by calling `az account get-access-token` via
`AzureCliCredential`, so whatever account/subscription is active on the host
is used.

## Prerequisites

```bash
az login          # or az login --tenant <id>
az account set -s <subscription-id>   # if you have multiple
```

## Quick start

```bash
# 1. Build the emulator image
docker compose build azure-token-emulator

# 2. Start everything
docker compose up
```

## Environment variables

### Emulator container

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Listening port |
| `IDENTITY_HEADER` | `local-dev-identity-header` | Expected value of `X-IDENTITY-HEADER`; emulator is permissive and logs a warning if missing |
| `AZURE_CONFIG_DIR` | `/home/appuser/.azure` | Path inside the container where the CLI config is mounted |

### Application container (set by docker-compose.yml)

| Variable | Value | Purpose |
|---|---|---|
| `IDENTITY_ENDPOINT` | `http://azure-token-emulator:8080/msi/token` | Tells `ManagedIdentityCredential` where to fetch tokens |
| `IDENTITY_HEADER` | same as emulator | Sent as `X-IDENTITY-HEADER` by the SDK |
| `AZURE_POD_IDENTITY_AUTHORITY_HOST` | `http://azure-token-emulator:8080` | Overrides IMDS base URL for azure-identity ≥ 1.8 |

## Response format

The emulator returns JSON matching the Azure IMDS / ACA schema:

```json
{
  "access_token": "<JWT>",
  "token_type": "Bearer",
  "expires_in": "3599",
  "expires_on": "1713700000",
  "resource": "https://vault.azure.net",
  "client_id": "emulated"
}
```

## Using a specific tenant or account

Set `AZURE_TENANT_ID` in the emulator service if you need to force a specific
tenant:

```yaml
environment:
  AZURE_TENANT_ID: 00000000-0000-0000-0000-000000000000
```

## Directory layout

```
azure-token-emulator/
  Dockerfile
  server.py
  requirements.txt
docker-compose.yml
```
