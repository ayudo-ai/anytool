FROM python:3.13-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[server]" 2>/dev/null || pip install --no-cache-dir -e .

# Copy source
COPY anytool/ anytool/
COPY server/ server/

# Create static dir
RUN mkdir -p anytool/static

EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8100/health').raise_for_status()" || exit 1

CMD ["python", "-m", "server.main"]
