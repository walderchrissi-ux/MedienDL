"""Erzeugt die PWA-Icons (PNG) ohne externe Abhaengigkeiten.

Rechnet eine einfache Verlaufs-Kachel mit einem Download-Pfeil
ueber freiformige Alpha-Maskierung und schreibt echte PNG-Dateien.
"""
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web"
# Für die PWA reichen 192/512; die .ico-Datei braucht zusätzlich die
# kleinen Windows-Größen, deshalb hier alle erzeugen.
SIZES = (16, 32, 48, 64, 128, 192, 256, 512)
PWA_SIZES = (192, 512)


def lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def make_pixel(x: int, y: int, size: int) -> tuple:
    """RGBA fuer ein Pixel: Verlauf + weisser Pfeil."""
    t = (x + y) / (2 * size)
    r, g, b = lerp((91, 140, 255), (155, 107, 255), t)

    # Pfeil: Schaft + Spitze, zentriert, auf 60% der Kachel
    u, v = x / size, y / size
    arrow = False
    shaft_w, shaft_top, shaft_bot = 0.075, 0.30, 0.60
    if abs(u - 0.5) < shaft_w and shaft_top < v < shaft_bot:
        arrow = True
    # Spitze: nach unten verjüngtes Dreieck
    if 0.60 <= v <= 0.76:
        half = 0.20 * (1 - (v - 0.60) / 0.16)
        if abs(u - 0.5) < half:
            arrow = True
    # Basislinie
    if 0.80 <= v <= 0.855 and 0.24 < u < 0.76:
        arrow = True

    if arrow:
        return (255, 255, 255, 255)
    return (r, g, b, 255)


def rounded_alpha(x: int, y: int, size: int) -> bool:
    """True, wenn das Pixel in einem abgerundeten Quadrat liegt."""
    rad = size * 0.22
    m = size * 0.0
    cx = min(max(x, rad), size - rad)
    cy = min(max(y, rad), size - rad)
    return (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad or (m <= x < size - m and m <= y < size - m)


def write_png(path: Path, size: int) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # Filter: none
        for x in range(size):
            r, g, b, a = make_pixel(x, y, size)
            if not rounded_alpha(x, y, size):
                a = 0
            raw += bytes((r, g, b, a))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
    print(f"  {path.name}  ({size}x{size}, {len(png) // 1024} KB)")


if __name__ == "__main__":
    for s in SIZES:
        write_png(OUT / f"icon-{s}.png", s)
    print(f"  (PWA nutzt: {', '.join(f'icon-{s}.png' for s in PWA_SIZES)})")

    # Windows braucht ein .ico mit mehreren Groessen in EINER Datei.
    # Wird nur erzeugt, wenn jemand den Windows-Build vorbereitet —
    # deshalb tolerant, falls die PNG-Rohdaten nicht im Speicher liegen.
    try:
        import struct as _struct

        ic = OUT / "icon.icns"
        ico = OUT / "icon.ico"
        entries = []
        for s in (16, 32, 48, 64, 128, 256):
            p = OUT / f"icon-{s}.png"
            if p.exists():
                entries.append((s, p.read_bytes()))
        if entries:
            # ICO-Container: Header + Verzeichnis + PNG-Nutzlasten
            n = len(entries)
            header = _struct.pack("<HHH", 0, 1, n)
            offset = 6 + 16 * n
            dir_entries, blobs = b"", b""
            for s, data in entries:
                dir_entries += _struct.pack(
                    "<BBBBHHII",
                    0 if s >= 256 else s,   # 0 = 256
                    0 if s >= 256 else s,
                    0, 0, 1, 32, len(data), offset,
                )
                blobs += data
                offset += len(data)
            ico.write_bytes(header + dir_entries + blobs)
            print(f"  icon.ico  ({len(entries)} Größen, {len(header+dir_entries+blobs)//1024} KB)")
    except Exception as e:
        print(f"  icon.ico übersprungen: {e}")
