"""MedienDL API — lokaler FastAPI-Server.

Startet standardmaessig nur auf 127.0.0.1. Mit --lan wird auf 0.0.0.0
gebunden (damit ein Handy im gleichen WLAN zugreifen kann) — das gibt
jedes Geraet im Netzwerk Kontrolle ueber den Downloader, also nur im
vertrauten Heimnetz nutzen.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
import core  # noqa: E402
from core import Job, UserError, build_cmd, probe, run_job  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Im PyInstaller-Bundle liegen die Web-Assets unter _internal/web, im
# Quellbaum unter ./web. Beides sauber aufloesen, sonst startet die App leer.
def _find_web() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        candidates += [
            meipass / "web",
            Path(sys.executable).resolve().parent.parent / "web",
            meipass / "Resources" / "web",
        ]
    candidates += [ROOT / "web", Path(__file__).resolve().parent / "web"]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    # nichts gefunden: auf den wahrscheinlichsten Ort zeigen, Fehler kommen
    # spaeter beim Mount sichtbar
    return candidates[0] if candidates else ROOT / "web"


WEB = _find_web()
OUTDIR = Path(os.environ.get("MEDIENDL_OUT", Path.home() / "Downloads" / "MedienDL"))

app = FastAPI(title="MedienDL", docs_url=None, redoc_url=None)

JOBS: dict[str, Job] = {}
TASKS: dict[str, asyncio.Task] = {}

# Innen abgeschnittene Historie, damit die Liste nicht ewig wächst.
MAX_HISTORY = 40


@app.middleware("http")
async def no_cache_shell(request, call_next):
    """Fronted-Dateien nie im HTTP-Cache halten — sonst sieht man nach
    einem Update die alte Oberflaeche."""
    resp = await call_next(request)
    path = request.url.path
    if not path.startswith("/api/") and (
        path in ("/", "/index.html", "/sw.js", "/manifest.json")
        or path.endswith((".html", ".js"))
    ):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.on_event("startup")
async def _startup() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- Schemas


class ProbeReq(BaseModel):
    url: str
    cookies_from_browser: str | None = None


class DownloadReq(BaseModel):
    url: str
    mode: str = Field(default="video", pattern="^(video|audio)$")
    fmt: str = "auto"
    audio_quality: str = Field(default="320", pattern="^(320|256|192|128|0)$")
    thumbnail: bool = True
    playlist: bool = False
    title: str = ""
    max_items: int = Field(default=50, ge=1, le=200)
    # Nur aus der Whitelist in core.SUPPORTED_BROWSERS
    cookies_from_browser: str | None = None


class RevealReq(BaseModel):
    path: str


# ---------------------------------------------------------------- Routen


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "outdir": str(OUTDIR),
        "ytdlp": core.YTDLP_SOURCE,
        "version": core._ytdlp_version(),
        "ffmpeg": bool(core.FFMPEG),
        "ffmpeg_bundled": core.FFMPEG_BUNDLED,
        "bind": app.state.bind if hasattr(app.state, "bind") else "127.0.0.1",
        "platform": platform.system(),
    }


@app.get("/api/version")
async def api_version() -> dict:
    """Version der App — Basis fuer die Update-Anzeige."""
    return {
        "version": core.__version__,
        "ytdlp": core._ytdlp_version(),
        "update_url": core.UPDATE_URL or None,
        "updates_enabled": bool(core.UPDATE_URL),
    }


@app.post("/api/update/check")
async def api_update_check() -> dict:
    """Nach einer neuen Version schauen.

    Ohne konfigurierte Update-URL passiert nichts — es wird nichts
    nachgeladen und keine fremde Adresse kontaktiert.
    """
    if not core.UPDATE_URL:
        return {"update": False, "reason": "Keine Update-Quelle konfiguriert."}

    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            core.UPDATE_URL, headers={"User-Agent": f"MedienDL/{core.__version__}"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as e:
        # Kein Update ist kein Fehler — die App funktioniert auch ohne Netz.
        return {"update": False, "reason": f"Update-Quelle nicht erreichbar ({type(e).__name__})."}

    latest = str(data.get("version", "")).strip()
    notes = str(data.get("notes", ""))[:500]
    url = str(data.get("url", "")).strip()
    # Nur https/http erlauben
    if url and not url.startswith(("https://", "http://")):
        url = ""

    if not latest:
        return {"update": False, "reason": "Antwort ohne Versionsangabe."}

    def tup(v: str) -> tuple:
        out = []
        for part in v.split("."):
            digits = "".join(c for c in part if c.isdigit())
            out.append(int(digits) if digits else 0)
        return tuple(out)

    newer = tup(latest) > tup(core.__version__)
    return {
        "update": newer,
        "current": core.__version__,
        "latest": latest,
        "notes": notes,
        "url": url,
        "reason": None if newer else "Du hast bereits die neueste Version.",
    }


@app.get("/api/browsers")
async def api_browsers() -> dict:
    """Welche Browser mit Cookie-Daten sind auf diesem Rechner vorhanden?

    Nur ein Hinweis fuer die Oberflaeche — es werden keine Cookies gelesen.
    """
    system = platform.system()
    home = Path.home()
    found = []
    for name in core.SUPPORTED_BROWSERS:
        pats: list[Path] = []
        if system == "Darwin":
            base = home / "Library" / "Application Support"
            mapping = {
                "chrome": "Google/Chrome",
                "chromium": "Chromium",
                "brave": "BraveSoftware/Brave-Browser",
                "edge": "Microsoft Edge",
                "firefox": "Mozilla/Firefox/Profiles",
                "opera": "com.operasoftware.Opera",
                "safari": "Apple/Safari",  # Cookies liegen hier anders
                "vivaldi": "Vivaldi",
                "whale": "Whale",
            }
            p = base / mapping.get(name, name)
            pats.append(p)
            if name == "firefox":
                pats = list(p.glob("*.cookies.sqlite")) if p.exists() else []
        elif system == "Windows":
            local = home / "AppData" / "Local"
            roams = home / "AppData" / "Roaming"
            mapping = {
                "chrome": roams / "Google/Chrome/User Data",
                "edge": roams / "Microsoft/Edge/User Data",
                "firefox": roams / "Mozilla/Firefox/Profiles",
                "opera": roams / "Opera Software/Opera Stable",
                "brave": roams / "BraveSoftware/Brave-Browser/User Data",
                "vivaldi": local / "Vivaldi/User Data",
                "chromium": local / "Chromium/User Data",
            }
            p = mapping.get(name)
            if p:
                pats = list(p.glob("*/Network/Cookies")) or [p]
        else:  # Linux
            mapping = {
                "firefox": home / ".mozilla/firefox",
                "chrome": home / ".config/google-chrome",
                "chromium": home / ".config/chromium",
                "brave": home / ".config/BraveSoftware/Brave-Browser",
            }
            p = mapping.get(name)
            if p:
                pats = [p]

        for pat in pats:
            try:
                if pat and pat.exists():
                    found.append(name)
                    break
            except OSError:
                continue
    return {"browsers": found, "system": system}


@app.post("/api/probe")
async def api_probe(req: ProbeReq) -> dict:
    try:
        return await probe(req.url, cookies_from_browser=req.cookies_from_browser)
    except UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unerwarteter Fehler: {e}")


@app.post("/api/download")
async def api_download(req: DownloadReq) -> dict:
    try:
        url = core.validate_url(req.url)
        # Playlists deckeln: max. 50 Einträge, damit nichts Unbeabsichtigtes
        # Gigabytes zieht. Nutzer kann im Frontend bewusst higher setzen.
        cap = min(req.max_items, 50)
        cmd = build_cmd(
            url,
            OUTDIR,
            mode=req.mode,
            fmt=req.fmt,
            audio_quality=req.audio_quality,
            thumbnail=req.thumbnail,
            playlist=req.playlist,
            max_items=cap,
            cookies_from_browser=req.cookies_from_browser,
        )
    except UserError as e:
        raise HTTPException(status_code=400, detail=str(e))

    jid = uuid.uuid4().hex[:8]
    job = Job(id=jid, url=url, title=req.title or url, mode=req.mode)
    JOBS[jid] = job
    task = asyncio.create_task(run_job(job, cmd))
    TASKS[jid] = task
    return {"job_id": jid}


@app.get("/api/jobs")
async def api_jobs() -> dict:
    items = sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)
    return {"jobs": [j.snapshot() for j in items[:MAX_HISTORY]]}


@app.get("/api/jobs/{jid}/events")
async def api_job_events(jid: str) -> StreamingResponse:
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    async def gen():
        # Aktuellen Stand sofort senden, danach nur Aenderungen.
        last = None
        while True:
            snap = job.snapshot()
            if snap != last:
                last = snap
                yield f"data: {json.dumps(snap)}\n\n"
            if not snap["running"]:
                break
            try:
                await asyncio.wait_for(job.queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jobs/{jid}/cancel")
async def api_cancel(jid: str) -> dict:
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job.status in ("queued", "running"):
        job.status = "cancelled"
        job.finished_at = time.time()
        job.message = "Abgebrochen"
        if job.proc:
            try:
                job.proc.terminate()
            except ProcessLookupError:
                pass
        job.emit()
    return {"ok": True}


@app.post("/api/reveal")
async def api_reveal(req: RevealReq) -> dict:
    """Datei im Dateimanager anzeigen — plattformunabhaengig."""
    try:
        target = Path(req.path).resolve()
        base = OUTDIR.resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültiger Pfad.")
    # Nur Dateien im eigenen Ausgabeordner öffnen — nichts beliebiges.
    if not (target == base or base in target.parents):
        raise HTTPException(status_code=400, detail="Pfad liegt nicht im Ausgabeordner.")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Datei existiert nicht (mehr).")

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", "-R", str(target)], check=False)
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", str(target)], check=False)
        else:
            # Linux: Ordner oeffnen, Datei markieren ist nicht einheitlich
            subprocess.run(["xdg-open", str(target.parent)], check=False)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Dateimanager nicht gefunden.")
    return {"ok": True}


# ---------------------------------------------------------------- Static

# Nur mounten, wenn die Web-Assets wirklich da sind — sonst gibt eine
# fehlende Datei einen unlesbaren Crash statt einer klaren Meldung.
if (WEB / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
else:
    @app.get("/")
    async def _missing_web():
        return {
            "detail": (
                f"Web-Oberfläche nicht gefunden (gesucht in {WEB}). "
                "Neu bauen: ./build_app.sh"
            )
        }


if __name__ == "__main__":
    import uvicorn

    bind = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    port = 8765
    app.state.bind = bind
    print(f"\n  MedienDL  ->  http://{'127.0.0.1' if bind == '127.0.0.1' else '<deine-lokale-IP>'}:{port}")
    print(f"  Ausgabe   ->  {OUTDIR}")
    if bind == "0.0.0.0":
        print("  ⚠ LAN-Modus: jedes Gerät im Netzwerk kann den Downloader steuern.\n")
    uvicorn.run(app, host=bind, port=port, log_level="warning")
