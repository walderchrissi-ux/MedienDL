"""MedienDL — App-Einstiegspunkt fuer die gebaute macOS-App.

Startet den lokalen Server und oeffnet ein Fenster darauf. Laeuft als
PyInstaller-Bundle (MediaDL.app), aber auch direkt aus dem Quellbaum:

    python backend/launcher.py
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

if __name__ == "__main__" and "frozen" not in globals():
    sys.path.insert(0, str(Path(__file__).resolve().parent))

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def wait_for_server(timeout: float = 20.0) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=1):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    return False


def open_browser_later() -> None:
    time.sleep(1.0)
    webbrowser.open(URL)


def _setup_ssl() -> None:
    """CA-Zertifikate fuer HTTPS bereitstellen.

    PyInstaller liefert keine Zertifikate mit — ohne diese Zeile schlaegt
    im Bundle JEDE HTTPS-Verbindung mit CERTIFICATE_VERIFY_FAILED fehl.
    Reihenfolge: System-Bundle des Rechners, dann das certifi aus der App.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return

    import ssl

    candidates = []
    # 1) System-Certs des Rechners (macOS, Linux-Distributionen)
    for p in (
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/usr/local/etc/openssl/cert.pem",
    ):
        if Path(p).exists():
            candidates.append(p)
    # 2) certifi, falls mitgeliefert
    try:
        import certifi

        candidates.append(certifi.where())
    except Exception:
        pass

    for c in candidates:
        if Path(c).exists():
            os.environ["SSL_CERT_FILE"] = c
            try:
                ssl.create_default_context(cafile=c)
            except Exception:
                continue
            return


def _ensure_ffmpeg_in_env() -> None:
    """Die mitgelieferten ffmpeg/ffprobe fuer yt-dlp sichtbar machen.

    yt-dlp sucht ffmpeg im PATH. Ohne System-ffmpeg (frischer Mac ohne
    Homebrew) findet er die mitgelieferten Tools nicht und der MP3-Export
    scheitert — deshalb werden sie hier direkt in die Umgebung gehaengt.
    """
    import shutil

    if shutil.which("ffmpeg") and os.environ.get("FFMPEG_LOCATION"):
        return

    search = []
    if getattr(sys, "frozen", False):
        search.append(Path(getattr(sys, "_MEIPASS", "")))
    search.append(Path(__file__).resolve().parent)

    for base in search:
        cand = base / "ffmpeg"
        if cand.exists() and cand.is_file():
            os.environ["FFMPEG_LOCATION"] = str(cand)
            os.environ["PATH"] = f"{base}{os.pathsep}{os.environ.get('PATH', '')}"
            return


_setup_ssl()


def main() -> int:
    # Im Bundle wird yt-dlp als Subprozess ueber dieses Flag gestartet
    # (sys.executable ist im Bundle die App selbst, kein Python).
    if "--yt-dlp" in sys.argv:
        try:
            _ensure_ffmpeg_in_env()
            from yt_dlp import main as ytdlp_main

            return ytdlp_main(sys.argv[sys.argv.index("--yt-dlp") + 1:])
        except ImportError:
            sys.stderr.write("yt-dlp ist in dieser App nicht enthalten.\n")
            return 2

    # Im Bundle liegen Web-Assets neben dem Binary.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import uvicorn

    import api  # noqa: E402

    api.app.state.bind = HOST
    api.OUTDIR.mkdir(parents=True, exist_ok=True)

    threading.Thread(target=open_browser_later, daemon=True).start()

    try:
        uvicorn.run(api.app, host=HOST, port=PORT, log_level="error")
    except OSError as e:
        print(f"Port {PORT} ist belegt — laeuft MedienDL bereits? ({e})")
        webbrowser.open(URL)
        time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())