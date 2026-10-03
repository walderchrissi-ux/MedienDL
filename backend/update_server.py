"""Kleiner Update-Server zum Testen der Update-Pruefung.

Liefert absichtlich eine hoehere Version als die installierte, damit
sichtbar wird, ob die Pruefung ein Update erkennt.

    python3 backend/update_server.py
"""
import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVE_DIR = ROOT / "data" / "update_test"
PORT = 8899

SERVE_DIR.mkdir(parents=True, exist_ok=True)
(SERVE_DIR / "version.json").write_text(
    json.dumps(
        {
            "version": "2.0.0",
            "notes": "Testupdate: Cookie-Zugriff und Auto-Update sind neu.",
            "url": "https://example.com/MedienDL-2.0.0.dmg",
        },
        indent=2,
    )
)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(SERVE_DIR), **kw)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Update-Testserver auf http://127.0.0.1:{PORT}/version.json", flush=True)
        httpd.serve_forever()