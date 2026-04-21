FROM python:3.12-slim

# Install Azure CLI (needed by AzureCliCredential to call `az account get-access-token`)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
        lsb-release \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Port the token endpoint listens on
EXPOSE 8080

# Non-root user for safety
RUN useradd -m appuser
USER appuser

# The Azure home dir is mounted from the host; point the CLI at it.
ENV AZURE_CONFIG_DIR=/home/appuser/.azure
ENV PORT=8080
# ACA identity header value — consuming containers must send this header.
# Override in docker-compose to a secret value if desired.
ENV IDENTITY_HEADER=local-dev-identity-header

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD curl -sf http://localhost:8080/msi/token || exit 1

CMD ["python", "-u", "server.py"]
