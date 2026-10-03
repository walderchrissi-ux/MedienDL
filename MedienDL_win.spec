# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spezifikation fuer MedienDL unter WINDOWS.
#
# ACHTUNG: Diese Datei ist NICHT auf macOS getestet. PyInstaller baut nur
# fuer das System, auf dem es laeuft — der Build muss also auf einem
# Windows-Rechner erfolgen. Siehe build_windows.bat.
#
# Bauen auf Windows:
#   build_windows.bat

import os
import shutil
import stat
import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).resolve()
if not (ROOT / "backend" / "launcher.py").exists():
    ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

# Windows braucht ein .ico als App-Icon. make_icons.py erzeugt es bei Bedarf.
ico = WEB / "icon.ico"
if not ico.exists():
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        import make_icons

        make_icons.write_ico(ico, (16, 32, 48, 64, 128, 256))
    except Exception as e:
        print(f"[spec] icon.ico konnte nicht erzeugt werden: {e}")

# ffmpeg/ffprobe vorbereiten — auf Windows als echte Dateien mit .exe,
# sonst legt PyInstaller sie als Ordner ab und sie sind nicht ausfuehrbar.
STAGE = Path(ROOT / "build") / "_tools"
if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True, exist_ok=True)


def stage(src: Path, name: str) -> bool:
    try:
        if not src.exists():
            return False
        dst = STAGE / name
        shutil.copy2(src, dst)
        # .exe unter Windows sind automatisch ausfuehrbar
        print(f"[spec] {name} bereit")
        return True
    except Exception as e:
        print(f"[spec] {name} nicht kopierbar: {e}")
        return False


have_ffmpeg = have_ffprobe = False

try:
    import imageio_ffmpeg

    ff = Path(imageio_ffmpeg.get_ffmpeg_exe())
    have_ffmpeg = stage(ff, "ffmpeg.exe")
except Exception as e:
    print(f"[spec] kein imageio-ffmpeg ({e})")

# Rueckfall aus dem System (PATH oder typische Orte)
for name in ("ffmpeg", "ffprobe"):
    found = shutil.which(name) or shutil.which(f"{name}.exe")
    if not found:
        for base in (r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"):
            cand = Path(base) / f"{name}.exe"
            if cand.exists():
                found = str(cand)
                break
    if found:
        if name == "ffmpeg" and not have_ffmpeg:
            have_ffmpeg = stage(Path(found), "ffmpeg.exe")
        elif name == "ffprobe" and not have_ffprobe:
            have_ffprobe = stage(Path(found), "ffprobe.exe")

extra_datas = [(str(WEB), "web")]
extra_datas.append((str(STAGE / "ffmpeg.exe"), "."))
extra_datas.append((str(STAGE / "ffprobe.exe"), "."))
if not (have_ffmpeg and have_ffprobe):
    print("[spec] WARNUNG: ffmpeg/ffprobe unvollstaendig — MP3 wird fehlschlagen")

# CA-Zertifikate: ohne die scheitert auf fremden Rechnern jedes HTTPS.
try:
    import certifi

    cacert = Path(certifi.where())
    if cacert.exists():
        extra_datas.append((str(cacert), "certifi"))
        print(f"[spec] Zertifikate mitgenommen: {cacert}")
except Exception as e:
    print(f"[spec] kein certifi ({e})")

a = Analysis(
    [str(ROOT / "backend" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=[],
    datas=extra_datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "anyio",
        "yt_dlp",
        "yt_dlp.compat",
        "yt_dlp.extractor",
        "yt_dlp.downloader",
        "yt_dlp.postprocessor",
        "core",
        "api",
        # Browser-Cookie-Zugriff auf Windows
        "win32crypt",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas", "PIL", "PyQt5", "PySide2",
        "test", "unittest", "pytest", "setuptools", "pip",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MedienDL",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ico) if ico.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MedienDL",
)