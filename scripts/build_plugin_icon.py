"""Render the Claude Code plugin icon from the Service Architect site favicon.

A faithful raster port of `public/favicon.svg` in service_architect_vue3, scaled
from its 256 unit viewBox to 1024 px. The plugin directory accepts PNG and JPEG
only, so the vector source cannot be shipped directly.

No image dependency: the PNG is encoded here and the shapes are anti-aliased from
signed distance fields. Re-run after changing the site icon; the directory takes
the listing icon only on first submission.
"""
import math
import struct
import sys
import zlib
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "plugins/service-architect/.claude-plugin/icon.png"

SIZE = 1024
K = SIZE / 256.0  # the favicon viewBox is 256 units

BG_FROM = (0x2b, 0x3a, 0x67)
BG_TO = (0x0f, 0x1b, 0x3c)
EDGE_FROM = (0x5e, 0xc8, 0xff)
EDGE_TO = (0x4a, 0x90, 0xe2)
EDGE_ALPHA = 0.9
OUTLINE = (0x0f, 0x1b, 0x3c)

TILE_XY = 8 * K
TILE_WH = 240 * K
TILE_R = 52 * K

HUB = (128 * K, 128 * K)
TOP = (128 * K, 58 * K)
LEFT = (66 * K, 164 * K)
RIGHT = (190 * K, 164 * K)

EDGES = ((HUB, TOP), (HUB, LEFT), (HUB, RIGHT), (TOP, LEFT), (TOP, RIGHT))
EDGE_W = 9 * K
OUTLINE_W = 4 * K

NODES = ((TOP, 24 * K, (0x7f, 0xdb, 0xff)),
         (LEFT, 24 * K, (0x4a, 0x90, 0xe2)),
         (RIGHT, 24 * K, (0x4a, 0x90, 0xe2)),
         (HUB, 27 * K, (0xff, 0xff, 0xff)))

# diagonal sweep across the glyph, matching the SVG's 0%,0% -> 100%,100% vector
GX0, GY0 = LEFT[0], TOP[1]
GX1, GY1 = RIGHT[0], LEFT[1]


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def rounded_rect(x, y, half_w, half_h, radius):
    dx = abs(x) - (half_w - radius)
    dy = abs(y) - (half_h - radius)
    return (math.hypot(max(dx, 0.0), max(dy, 0.0)) + min(max(dx, dy), 0.0)) - radius


def segment(x, y, a, b, width):
    ax, ay = a
    vx, vy = b[0] - ax, b[1] - ay
    px, py = x - ax, y - ay
    t = clamp01((px * vx + py * vy) / (vx * vx + vy * vy))
    return math.hypot(px - vx * t, py - vy * t) - width * 0.5


def over(dst, src, alpha):
    if alpha <= 0.0:
        return dst
    if alpha >= 1.0:
        return src
    inv = 1.0 - alpha
    return (dst[0] * inv + src[0] * alpha,
            dst[1] * inv + src[1] * alpha,
            dst[2] * inv + src[2] * alpha)


def coverage(d):
    return clamp01(0.5 - d)


cx0 = TILE_XY + TILE_WH * 0.5
raw = bytearray()
for py in range(SIZE):
    raw.append(0)
    y = py + 0.5
    for px in range(SIZE):
        x = px + 0.5
        tile = rounded_rect(x - cx0, y - cx0, TILE_WH * 0.5, TILE_WH * 0.5, TILE_R)
        alpha = coverage(tile)
        if alpha <= 0.0:
            raw += b"\x00\x00\x00\x00"
            continue
        bg_t = clamp01(((x - TILE_XY) / TILE_WH + (y - TILE_XY) / TILE_WH) * 0.5)
        colour = mix(BG_FROM, BG_TO, bg_t)
        edge_t = clamp01(((x - GX0) / (GX1 - GX0) + (y - GY0) / (GY1 - GY0)) * 0.5)
        best = min(segment(x, y, a, b, EDGE_W) for a, b in EDGES)
        colour = over(colour, mix(EDGE_FROM, EDGE_TO, edge_t), coverage(best) * EDGE_ALPHA)
        for (nx, ny), r, tone in NODES:
            colour = over(colour, tone, coverage(math.hypot(x - nx, y - ny) - r))
        for (nx, ny), r, _ in NODES:
            ring = abs(math.hypot(x - nx, y - ny) - r) - OUTLINE_W * 0.5
            colour = over(colour, OUTLINE, coverage(ring))
        raw += bytes((int(colour[0] + 0.5), int(colour[1] + 0.5), int(colour[2] + 0.5),
                      int(alpha * 255 + 0.5)))


def chunk(tag, payload):
    body = tag + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
       + chunk(b"IEND", b""))

destination = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
destination.write_bytes(png)
print(f"{destination} {SIZE}x{SIZE} {len(png)} bytes")
