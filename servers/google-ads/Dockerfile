FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

WORKDIR /app
# Official server: https://github.com/googleads/google-ads-mcp
# Pinned on purpose; bump deliberately and re-run scripts/smoke_test.py.
RUN uv pip install --system --no-cache "google-ads-mcp==0.0.4" "fastmcp==4.0.10" \
    && useradd --uid 10001 --no-create-home mcp
COPY serve.py tools_config.yaml ./

USER 10001
ENV PORT=8080 PYTHONUNBUFFERED=1 GOOGLE_ADS_MCP_TOOLS_CONFIG=/app/tools_config.yaml
EXPOSE 8080
CMD ["python", "serve.py"]
