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

# Non-root user for safety
RUN useradd -m appuser

COPY server.py /app/server.py
RUN chown appuser:appuser /app/server.py && chmod 644 /app/server.py

USER appuser
# Port the token endpoint listens on
EXPOSE 8088

# The Azure home dir is mounted from the host; point the CLI at it.
ENV AZURE_CONFIG_DIR=/home/appuser/.azure
ENV PORT=8088
# ACA identity header value — consuming containers must send this header.
# Override in docker-compose to a secret value if desired.
ENV IDENTITY_HEADER=local-dev-identity-header

#HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
#    CMD curl -s http://localhost:8088/msi/token

CMD ["python", "-u", "server.py"]
