"""Tiny PNG chart generator (no external deps).

Provides helpers to render simple charts as PNG bytes:
- pack_png: encode RGBA buffer to PNG
- draw_line, fill_rect: primitive drawing
- generate_insights_chart: composite chart for realm insights
"""
from __future__ import annotations

import struct
import zlib
from typing import Iterable, Tuple, List, Dict


def pack_png(width: int, height: int, rgba: bytes) -> bytes:
    assert len(rgba) == width * height * 4
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(
            ">I", len(data)
        ) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,  # bit depth
        6,  # RGBA
        0,
        0,
        0,
    )
    # Add filter byte 0 for each row
    scanlines = bytearray()
    row_bytes = width * 4
    for y in range(height):
        start = y * row_bytes
        scanlines.append(0)
        scanlines.extend(rgba[start : start + row_bytes])
    compressed = zlib.compress(bytes(scanlines), level=9)
    return b"".join([sig, chunk(b"IHDR", ihdr), chunk(b"IDAT", compressed), chunk(b"IEND", b"")])


class Image:
    def __init__(self, w: int, h: int, bg: Tuple[int, int, int, int] = (20, 24, 28, 255)):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 4)
        r, g, b, a = bg
        for i in range(0, len(self.buf), 4):
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b
            self.buf[i + 3] = a

    def set_px(self, x: int, y: int, color: Tuple[int, int, int, int]):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = (y * self.w + x) * 4
        r, g, b, a = color
        # Simple alpha blend over existing pixel
        if a >= 255:
            self.buf[i : i + 4] = bytes((r, g, b, 255))
        else:
            br, bg, bb, ba = self.buf[i], self.buf[i + 1], self.buf[i + 2], self.buf[i + 3]
            na = a + (ba * (255 - a) // 255)
            if na == 0:
                out = (0, 0, 0, 0)
            else:
                nr = (r * a + br * ba * (255 - a) // 255) // max(1, na)
                ng = (g * a + bg * ba * (255 - a) // 255) // max(1, na)
                nb = (b * a + bb * ba * (255 - a) // 255) // max(1, na)
                out = (nr, ng, nb, na)
            self.buf[i : i + 4] = bytes(out)

    def fill_rect(self, x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int, int]):
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w - 1, x1)
        y1 = min(self.h - 1, y1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set_px(x, y, color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int, int]):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set_px(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


# --- Tiny 3x5 bitmap font for labels (A–Z, 0–9, basic punctuation) ---
# Each glyph is 3 columns x 5 rows; rows are bitmasks (MSB left of 3 bits)
FONT_3x5: Dict[str, List[int]] = {
    "A": [0b111, 0b101, 0b111, 0b101, 0b101],
    "B": [0b110, 0b101, 0b110, 0b101, 0b110],
    "C": [0b111, 0b100, 0b100, 0b100, 0b111],
    "D": [0b110, 0b101, 0b101, 0b101, 0b110],
    "E": [0b111, 0b100, 0b110, 0b100, 0b111],
    "F": [0b111, 0b100, 0b110, 0b100, 0b100],
    "G": [0b111, 0b100, 0b101, 0b101, 0b111],
    "H": [0b101, 0b101, 0b111, 0b101, 0b101],
    "I": [0b111, 0b010, 0b010, 0b010, 0b111],
    "J": [0b001, 0b001, 0b001, 0b101, 0b111],
    "K": [0b101, 0b110, 0b100, 0b110, 0b101],
    "L": [0b100, 0b100, 0b100, 0b100, 0b111],
    "M": [0b101, 0b111, 0b111, 0b101, 0b101],
    "N": [0b101, 0b111, 0b111, 0b111, 0b101],
    "O": [0b111, 0b101, 0b101, 0b101, 0b111],
    "P": [0b111, 0b101, 0b111, 0b100, 0b100],
    "Q": [0b111, 0b101, 0b101, 0b111, 0b001],
    "R": [0b111, 0b101, 0b111, 0b110, 0b101],
    "S": [0b111, 0b100, 0b111, 0b001, 0b111],
    "T": [0b111, 0b010, 0b010, 0b010, 0b010],
    "U": [0b101, 0b101, 0b101, 0b101, 0b111],
    "V": [0b101, 0b101, 0b101, 0b101, 0b010],
    "W": [0b101, 0b101, 0b111, 0b111, 0b101],
    "X": [0b101, 0b101, 0b010, 0b101, 0b101],
    "Y": [0b101, 0b101, 0b010, 0b010, 0b010],
    "Z": [0b111, 0b001, 0b010, 0b100, 0b111],
    "0": [0b111, 0b101, 0b101, 0b101, 0b111],
    "1": [0b010, 0b110, 0b010, 0b010, 0b111],
    "2": [0b111, 0b001, 0b111, 0b100, 0b111],
    "3": [0b111, 0b001, 0b111, 0b001, 0b111],
    "4": [0b101, 0b101, 0b111, 0b001, 0b001],
    "5": [0b111, 0b100, 0b111, 0b001, 0b111],
    "6": [0b111, 0b100, 0b111, 0b101, 0b111],
    "7": [0b111, 0b001, 0b010, 0b010, 0b010],
    "8": [0b111, 0b101, 0b111, 0b101, 0b111],
    "9": [0b111, 0b101, 0b111, 0b001, 0b111],
    " ": [0b000, 0b000, 0b000, 0b000, 0b000],
    ":": [0b000, 0b010, 0b000, 0b010, 0b000],
    "-": [0b000, 0b000, 0b111, 0b000, 0b000],
    "/": [0b001, 0b001, 0b010, 0b100, 0b100],
    "%": [0b101, 0b001, 0b010, 0b100, 0b101],
    ".": [0b000, 0b000, 0b000, 0b000, 0b010],
    ",": [0b000, 0b000, 0b000, 0b010, 0b100],
}


def draw_text(img: Image, x: int, y: int, text: str, color: Tuple[int, int, int, int], scale: int = 2):
    cx = x
    text = text.upper()
    for ch in text:
        glyph = FONT_3x5.get(ch, FONT_3x5[" "])
        for ry, row in enumerate(glyph):
            for rx in range(3):
                if (row >> (2 - rx)) & 1:
                    # scaled rect
                    img.fill_rect(cx + rx * scale, y + ry * scale, cx + rx * scale + (scale - 1), y + ry * scale + (scale - 1), color)
        cx += (3 + 1) * scale  # 1px space


def _norm(v: float, vmin: float, vmax: float) -> float:
    if vmax <= vmin:
        return 0.0
    return max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))


def _fmt_gold(copper: int) -> str:
    g = copper // 10000
    s = (copper % 10000) // 100
    c = copper % 100
    if g:
        return f"{g}g {s}s"
    if s:
        return f"{s}s {c}c"
    return f"{c}c"


def generate_insights_chart(insights: Dict) -> bytes:
    """Create a composite insights chart PNG.

    Layout (no text):
    - Top area: sparkline of online samples over last 24h
    - Bottom area: two bars for Alliance/Horde split
    """
    W, H = 640, 220
    img = Image(W, H, bg=(22, 28, 34, 255))
    # Colors
    GRID = (40, 48, 56, 255)
    LINE = (46, 204, 113, 255)  # green
    PEAK = (231, 76, 60, 200)  # red
    BAR_A = (52, 152, 219, 255)  # blue
    BAR_H = (231, 76, 60, 255)  # red
    TEXT = (232, 238, 244, 255)
    SUBT = (160, 170, 180, 255)

    # Regions
    pad = 10
    top_h = 160
    bx, by, bw, bh = pad, pad, W - pad * 2, top_h - pad
    # Grid bars
    for i in range(1, 5):
        y = by + int(i * (bh) / 5)
        img.fill_rect(bx, y, bx + bw, y, GRID)

    # Title
    draw_text(img, bx, by - 6, "ONLINE 24H", SUBT, scale=2)
    # Sparkline from concurrency
    cc = insights.get("concurrency") or {}
    samples: List[int] = []
    if isinstance(cc.get("series"), list):
        samples = [int(v) for v in cc["series"] if isinstance(v, (int, float))]
    # If series not provided, synthesize a small series around current
    cur = int(cc.get("current") or 0)
    if not samples:
        samples = [max(0, cur - 2), cur, max(0, cur - 1), cur, min(cur + 1, cur + 3)]
    vmin = min(samples) if samples else 0
    vmax = max(samples) if samples else 1
    prev = None
    for i, v in enumerate(samples):
        x = bx + int(i * (bw - 1) / max(1, len(samples) - 1))
        y = by + bh - int(_norm(v, vmin, vmax) * (bh - 1))
        if prev is not None:
            img.draw_line(prev[0], prev[1], x, y, LINE)
        prev = (x, y)

    # Optional peak marker
    peak = int(cc.get("peak") or vmax)
    py = by + bh - int(_norm(peak, vmin, vmax) * (bh - 1))
    img.fill_rect(bx, py, bx + bw, py, PEAK)
    # Labels for peak/current
    draw_text(img, bx + bw - 120, by + 2, f"CUR:{cur}", TEXT, scale=2)
    draw_text(img, bx + 4, py - 10, f"PEAK:{peak}", TEXT, scale=2)

    # Bars: population
    pop = insights.get("population") or {}
    a = int(pop.get("alliance") or 0)
    h = int(pop.get("horde") or 0)
    denom = max(1, a + h)
    bar_area_top = top_h + 10
    bar_area_bottom = H - 10
    bar_h = bar_area_bottom - bar_area_top
    bar_w = (W - 3 * pad) // 2
    # Alliance bar
    ah = int(bar_h * (a / denom))
    hx0 = pad
    img.fill_rect(hx0, bar_area_bottom - ah, hx0 + bar_w, bar_area_bottom, BAR_A)
    # Horde bar
    hh = int(bar_h * (h / denom))
    hx1 = pad * 2 + bar_w
    img.fill_rect(hx1, bar_area_bottom - hh, hx1 + bar_w, bar_area_bottom, BAR_H)
    # Labels for bars
    ap = int(pop.get("alliance_pct") or 0)
    hp = int(pop.get("horde_pct") or 0)
    draw_text(img, hx0, bar_area_top - 6, f"ALLIANCE {a} ({ap}%)", TEXT, scale=2)
    draw_text(img, hx1, bar_area_top - 6, f"HORDE {h} ({hp}%)", TEXT, scale=2)

    # Footer mini-legend: auctions/economy
    auc = insights.get("auctions") or {}
    eco = insights.get("economy") or {}
    legend_y = H - 20
    auc_txt = f"AUCT {int(auc.get('active') or 0)} AVG {_fmt_gold(int(auc.get('avg_buyout_copper') or 0))}"
    eco_txt = f"GOLD {int(eco.get('total_gold') or 0)}g PER {eco.get('per_capita_gold') or 0}g"
    draw_text(img, pad, legend_y, auc_txt, SUBT, scale=2)
    draw_text(img, W // 2, legend_y, eco_txt, SUBT, scale=2)

    return pack_png(W, H, bytes(img.buf))


__all__ = ["generate_insights_chart", "pack_png"]
