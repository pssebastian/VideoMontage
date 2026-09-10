"""VideoMontage MCP Server.

Model Context Protocol (MCP) server packaging OpenMontage capabilities for
AI agents (Claude, Cursor, OpenClaw, Hermes, Antigravity).
"""

__version__ = "0.1.0"
__all__ = ["create_server", "main"]

from mcp_server.server import create_server, main
