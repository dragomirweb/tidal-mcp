FROM python:3.11-slim

WORKDIR /app

# MCP server metadata
LABEL io.modelcontextprotocol.server.name="io.github.ibeal/tidal-mcp"

# Install uv for Python package management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY mcp_server/ ./mcp_server/
COPY tidal_api/ ./tidal_api/
COPY auth_cli.py ./
COPY start_mcp.py ./

# Create virtual environment and install dependencies using uv sync
# This respects the uv.lock file and ensures all dependencies are properly installed
RUN uv sync --frozen

# Bake in the TIDAL session so auth persists without volume mounts
COPY tidal-session-oauth.json /tmp/tidal-session-oauth.json

# Run the MCP server (stdio transport, no ports needed)
CMD [".venv/bin/python", "start_mcp.py"]
