#!/usr/bin/env python
"""Point d'entrée du serveur MCP Coach-PFE (transport stdio pour Cursor)."""

from mcp_server.server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
