FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml ./
COPY growth_gateway ./growth_gateway
RUN uv pip install --system --no-cache . && useradd --uid 10001 --no-create-home mcp

USER 10001
ENV PORT=8080 PYTHONUNBUFFERED=1 HOME=/tmp
EXPOSE 8080
CMD ["growth-mcp-gateway"]
