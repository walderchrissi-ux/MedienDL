"""Schneller Smoke-Test der Engine, ohne Server."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
from core import build_cmd, fmt_bytes, fmt_duration, validate_url, _friendly_error, _cookie_args, UserError

ok = True

# 1) URL-Validierung
for good in ["https://youtube.com/watch?v=abc", "http://tiktok.com/@u/video/1"]:
    validate_url(good)
print("✓ URL-Validierung akzeptiert http(s)")
for bad in ["", "file:///etc/passwd", "ftp://x.test", "http://localhost:8765", "javascript:alert(1)"]:
    try:
        validate_url(bad)
        print(f"✗ hätte blockiert werden müssen: {bad!r}")
        ok = False
    except UserError:
        pass
print("✓ URL-Validierung blockiert non-http, localhost, leer")

# 2) Formatierung
assert fmt_bytes(1536) == "1.5 KB", fmt_bytes(1536)
assert fmt_bytes(0) == "?"
assert fmt_duration(65) == "1:05", fmt_duration(65)
assert fmt_duration(3725) == "1:02:05", fmt_duration(3725)
print("✓ Byte-/Zeit-Formatierung korrekt")

# 3) Befehlsbau Video
v = build_cmd("https://y.test", Path("/tmp/out"), mode="video")
vj = " ".join(v)
assert "bv*+ba/b" in vj, "video format missing"
assert "-o /tmp/out/%(title).150B [%(id)s].%(ext)s" in vj, "output template missing"
assert "--write-thumbnail" in v, "thumbnail flag missing"
print("✓ Video-Befehl enthält beste Video+Audio, Template, Thumbnail")

# 4) Befehlsbau Audio
a = build_cmd("https://y.test", Path("/tmp/out"), mode="audio", audio_quality="256")
aj = " ".join(a)
assert "-x --audio-format mp3 --audio-quality 256" in aj, aj
assert "--write-thumbnail" not in a
print("✓ Audio-Befehl extrahiert MP3, ohne Thumbnail")

# 5) Progress-Parser
class J:
    downloaded = total = 0; progress = 0.0; speed = ""; eta = ""; message = ""
j = J()
hit = core._parse_progress("HDP|downloading|5242880|10485760|NA|1048576|12", j)
assert hit and j.downloaded == 5242880 and j.total == 10485760, vars(j)
assert abs(j.progress - 50.0) < 0.1, j.progress
assert j.speed.startswith("1.0 MB"), j.speed
j2 = J()
core._parse_progress("HDP|downloading|100|NA|999|NA|NA", j2)
assert j2.total == 999, j2.total  # Fallback auf estimate
print("✓ Progress-Parser liest Bytes, Speed, ETA, Estimate-Fallback")

# 6) Fehlerbereinigung
msg = core._clean_error("\n[download] Destination: x\nERROR: [youtube] abc: Video unavailable")
assert "Video unavailable" in msg and "ERROR" not in msg, msg
print("✓ yt-dlp-Fehler werden auf eine Zeile bereinigt")

# YouTube-Mix/Radio muss blockiert werden (endlose Playlist).
mixes = [
    "https://www.youtube.com/watch?v=gXidD-11Qw0&list=RDgXidD-11Qw0&start_radio=1",
    "https://www.youtube.com/watch?v=abc&list=RDabc",
]
for m in mixes:
    try:
        validate_url(m)
        print(f"✗ Mix hätte blockiert werden müssen: {m}")
        ok = False
    except UserError as e:
        assert "Mix" in str(e), str(e)
print("✓ YouTube-Mix (list=RD) wird blockiert")

# Normale Playlists bleiben erlaubt
validate_url("https://www.youtube.com/playlist?list=PL1234567890")
validate_url("https://www.youtube.com/watch?v=abc&list=PL1234567890")
print("✓ Normale Playlists weiterhin erlaubt")

# YouTube-Bot-Sperre wird in eine verstaendliche Meldung uebersetzt.
bot_msg = _friendly_error("ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies-from-browser")
assert "Bot-Schutz" in bot_msg, bot_msg
assert "--cookies" not in bot_msg, "Roh-Fehler noch enthalten"
print("✓ YouTube-Bot-Sperre wird verständlich übersetzt")

# Altersprüfung / Mitglieder-Only werden nicht umgangen, sondern erklärt.
assert "Altersverifikation" in _friendly_error("Sign in to confirm your age")
assert "Bezahlschranken" in _friendly_error("Join this channel to get access to members-only content")
print("✓ Alters-/Mitglieder-Sperren werden erklärt, nicht umgangen")

# Cookie-Argumente: nur bekannte Browser, keine freien Pfade.
assert _cookie_args("chrome", None) == ["--cookies-from-browser", "chrome"]
assert _cookie_args(None, None) == []
assert _cookie_args("../../etc/passwd", None) == [], "Pfad darf nicht durchgereicht werden"
assert _cookie_args("firefox", None) == ["--cookies-from-browser", "firefox"]
assert _cookie_args("/etc/passwd", None) == []
print("✓ Cookie-Argumente nur fuer bekannte Browser")

cmd_c = build_cmd("https://x.test", Path("/tmp"), cookies_from_browser="chrome")
assert "--cookies-from-browser chrome" in " ".join(cmd_c)
print("✓ build_cmd reicht Browser-Cookies durch")

# Versionsvergleich der Update-Pruefung
def tup(v):
    return tuple(int("".join(c for c in p if c.isdigit()) or 0) for p in v.split("."))
assert tup("1.2.0") > tup("1.1.0")
assert tup("1.1.0") == tup("1.1.0")
assert tup("2.0.0") > tup("1.9.9")
print("✓ Versionsvergleich fuer Update-Pruefung korrekt")

print("\nAlle Engine-Tests bestanden." if ok else "\nFEHLER — siehe oben.")
sys.exit(0 if ok else 1)
