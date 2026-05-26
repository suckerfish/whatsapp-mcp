# syntax=docker/dockerfile:1

FROM python:3.11-slim

RUN pip install uv

WORKDIR /app
COPY whatsapp-mcp-server/ ./

RUN uv sync --no-dev

EXPOSE 8765

ENV MCP_TRANSPORT=http
ENV MCP_PORT=8765

ENTRYPOINT ["uv", "run", "main.py"]
