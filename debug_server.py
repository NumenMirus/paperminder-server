#!/usr/bin/env python3
"""
Standalone debug UI server for PaperMinder.

This server runs the debug UI on localhost:8001, separate from the main API.
It binds only to 127.0.0.1 (localhost) for local development and debugging.

Usage:
    python debug_server.py

Then access the debug UI at: http://127.0.0.1:8001
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Configuration
PORT = 8001
HOST = "127.0.0.1"  # Localhost only - not accessible from external networks
STATIC_DIR = Path(__file__).parent / "src" / "static"


class DebugHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler that serves static files from src/static directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        """Custom log messages to include server identification."""
        sys.stderr.write(f"[DEBUG UI SERVER] {self.address_string()} - [{self.log_date_time_string()}] {format % args}\n")

    def end_headers(self):
        """Add security headers to prevent caching and restrict access."""
        # Prevent caching
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def start_debug_server():
    """Start the debug UI server on localhost."""

    # Check if static directory exists
    if not STATIC_DIR.exists():
        print(f"Error: Static files directory not found: {STATIC_DIR}")
        print("The debug UI files may not be installed. Continuing without debug UI.")
        sys.exit(1)

    # Create the server
    try:
        with socketserver.TCPServer((HOST, PORT), DebugHTTPRequestHandler) as httpd:
            print(f"╔═══════════════════════════════════════════════════════════════╗")
            print(f"║          PaperMinder Debug UI Server (localhost only)         ║")
            print(f"╠═══════════════════════════════════════════════════════════════╣")
            print(f"║  Server running at: http://{HOST}:{PORT}                      ║")
            print(f"║  Press Ctrl+C to stop the server                              ║")
            print(f"╚═══════════════════════════════════════════════════════════════╝")
            print()
            print(f"⚠️  IMPORTANT: This server is only accessible from this machine.")
            print(f"    It binds to 127.0.0.1 and is NOT accessible from external")
            print(f"    networks, making it safe for local development.")
            print()

            # Start serving
            httpd.serve_forever()

    except KeyboardInterrupt:
        print("\n\n[DEBUG UI SERVER] Shutting down...")
        httpd.server_close()
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"Error: Port {PORT} is already in use.")
            print(f"Another process may be running on http://{HOST}:{PORT}")
            print("Please stop that process or choose a different port.")
            sys.exit(1)
        else:
            raise


if __name__ == "__main__":
    start_debug_server()
