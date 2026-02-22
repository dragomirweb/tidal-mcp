FROM python:3.11-slim

WORKDIR /app

# MCP server metadata
LABEL io.modelcontextprotocol.server.name="io.github.dragomirweb/tidal-mcp"

# Install uv for Python package management (standalone installer avoids QEMU segfaults on arm64)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first (cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy source files (changes here don't invalidate dependency cache)
COPY mcp_server/ ./mcp_server/
COPY tidal_api/ ./tidal_api/
COPY auth_cli.py start_mcp.py ./

# Run as non-root user
RUN useradd -m appuser
USER appuser

# Run the MCP server (stdio transport, no ports needed)
CMD [".venv/bin/python", "start_mcp.py"]
