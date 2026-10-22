#!/usr/bin/env python3
"""
Company OS — Local Dashboard Preview Server
Serves the generated interactive HTML dashboard on localhost for beta testing.
"""

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dashboard.generator import DashboardGenerator
from inventory.scanner import WorkspaceScanner


def serve_dashboard(
    profile_path: str = "examples/seed-b2b-saas.json",
    inventory_path: str = "examples/sample-drive-inventory.json",
    port: int = 8080,
    host: str = "127.0.0.1",
):
    # 1. Generate latest dashboard HTML into a temporary or public folder
    gen = DashboardGenerator()
    scanner = WorkspaceScanner()

    p_path = BASE_DIR / profile_path
    i_path = BASE_DIR / inventory_path
    out_html = BASE_DIR / "dashboard" / "index.html"

    with open(p_path, "r", encoding="utf-8") as f:
        import json
        profile = json.load(f)

    inv = scanner.load_snapshot(i_path)
    gen.generate(profile, inv, output_path=out_html)

    print(f"📊 Dashboard compiled at: {out_html}")
    print(f"🚀 Launching local server at: http://{host}:{port}/index.html")

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(out_html.parent), **kwargs)

    with socketserver.TCPServer((host, port), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard server.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve Company OS Dashboard")
    parser.add_argument("--profile", default="examples/seed-b2b-saas.json")
    parser.add_argument("--inventory", default="examples/sample-drive-inventory.json")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")

    args = parser.parse_args()
    serve_dashboard(args.profile, args.inventory, port=args.port, host=args.host)
