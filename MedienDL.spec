# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spezifikation fuer MedienDL.app (macOS).
#
# Baut eine eigenstaendige .app: Python-Runtime, FastAPI, yt-dlp und die
# Web-Oberflaeche liegen alle im Bundle. Der Endnutzer braucht weder
# Python noch Homebrew-Installationen von yt-dlp/ffmpeg.
#
# Bauen:  ./build_app.sh

import sys
from pathlib import Path

block_cipher = None

# SPECPATH zeigt je nach Aufruf auf ein anderes Verzeichnis — deshalb den
# Projektordner fest über den Ort der .spec-Datei bestimmen.
ROOT = Path(SPECPATH).resolve()
if not (ROOT / "backend" / "launcher.py").exists():
    ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

# imageio-ffmpeg liefert sein Binary erst zur Laufzeit. Damit die App auch
# ohne System-ffmpeg MP3 kann, wird der echte Pfad zur Build-Zeit ermittelt
# und als Datei ins Bundle gelegt.
#
# Wichtig: PyInstaller behaelt den Original-Dateinamen ("ffmpeg-macos-aarch64-v7.1")
# und legt macOS-Binaries als "binaries" als Ordner ab. Deshalb: die Dateien
# vorher in einem staging-Ordner auf feste Namen (ffmpeg / ffprobe) kopieren
# und als datas einbinden. Nur so sind sie hinterher echte, ausfuehrbare Dateien.
import shutil as _shutil
import stat as _stat

STAGE = Path(ROOT / "build") / "_tools"
if STAGE.exists():
    _shutil.rmtree(STAGE)
STAGE.mkdir(parents=True, exist_ok=True)


def _stage(src: Path, name: str) -> bool:
    """Binaries in den Staging-Ordner legen und ausfuehrbar machen."""
    try:
        if not src.exists():
            return False
        dst = STAGE / name
        _shutil.copy2(src, dst)
        dst.chmod(dst.stat().st_mode | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)
        print(f"[spec] {name} bereit ({dst.stat().st_size // 1024 // 1024} MB)")
        return True
    except Exception as e:
        print(f"[spec] {name} konnte nicht kopiert werden: {e}")
        return False


extra_datas = [(str(WEB), "web")]
have_ffmpeg = have_ffprobe = False

# ffmpeg: imageio-ffmpeg liefert es mit, aber mit Plattform-Namen.
try:
    import imageio_ffmpeg

    ff = Path(imageio_ffmpeg.get_ffmpeg_exe())
    have_ffmpeg = _stage(ff, "ffmpeg")
except Exception as e:
    print(f"[spec] kein imageio-ffmpeg ({e})")

# ffmpeg/ffprobe aus dem System als Rueckfall (Homebrew-Pfade auch ohne Shell)
for name in ("ffmpeg", "ffprobe"):
    found = _shutil.which(name)
    if not found:
        for c in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"):
            if Path(c).exists():
                found = c
                break
    if found:
        try:
            real = Path(found).resolve()
        except Exception:
            real = Path(found)
        if name == "ffmpeg" and not have_ffmpeg:
            have_ffmpeg = _stage(real, "ffmpeg")
        elif name == "ffprobe" and not have_ffprobe:
            have_ffprobe = _stage(real, "ffprobe")

# Beide sind Pflicht fuer den MP3-Export — ohne sie waere die App dort tot.
extra_datas.append((str(STAGE / "ffmpeg"), "."))
extra_datas.append((str(STAGE / "ffprobe"), "."))
if not (have_ffmpeg and have_ffprobe):
    print("[spec] WARNUNG: ffmpeg/ffprobe unvollstaendig — MP3 wird fehlschlagen")

# CA-Zertifikate mitnehmen — ohne die scheitert im Bundle jedes HTTPS.
try:
    import certifi

    cacert = Path(certifi.where())
    if cacert.exists():
        extra_datas.append((str(cacert), "certifi"))
        print(f"[spec] Zertifikate mitgenommen: {cacert}")
except Exception as e:
    print(f"[spec] kein certifi gefunden ({e})")

a = Analysis(
    [str(ROOT / "backend" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=[],
    # Web-Assets, mitgebrachte Tools (ffmpeg/ffprobe) und Zertifikate.
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
        "yt_dlp.compat._legacy",
        "yt_dlp.compat.optional",
        "yt_dlp.extractor",
        "yt_dlp.downloader",
        "yt_dlp.postprocessor",
        "core",
        "api",
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
    console=False,          # kein Terminal-Fenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(WEB / "icon.icns") if (WEB / "icon.icns").exists() else None,
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

# app-Bundle drumherum (.app mit Info.plist fuer den Finder)
app = BUNDLE(
    coll,
    name="MedienDL.app",
    icon=str(WEB / "icon.icns") if (WEB / "icon.icns").exists() else None,
    bundle_identifier="de.mediendl.app",
    info_plist={
        "CFBundleName": "MedienDL",
        "CFBundleDisplayName": "MedienDL",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSUIElement": False,
        "CFBundleDocumentTypes": [],
    },
)