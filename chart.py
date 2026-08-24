"""Dependency-free PNG rendering for the return curve command."""

from __future__ import annotations

import struct
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any

try:
    from .calculator import plan_budget
except ImportError:  # Allows the dependency-free module tests to run directly.
    from calculator import plan_budget


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def _png(width: int, height: int, pixels: bytearray) -> bytes:
    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * stride:(y + 1) * stride])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _chunk(b"IEND", b"")
    )


def render_benefit_curve(max_budget: int, *, points: int = 41, **options: Any) -> Path:
    """Render an expected-intimacy curve for budgets from zero to the maximum."""
    width, height = 960, 540
    left, right, top, bottom = 82, 38, 46, 72
    chart_width, chart_height = width - left - right, height - top - bottom
    max_budget = max(1, int(max_budget))
    points = max(2, int(points))
    samples = [
        plan_budget(round(max_budget * index / (points - 1)), max_budget=max_budget, **options)
        for index in range(points)
    ]
    max_value = max(1, max(plan.expected_total for plan in samples))
    pixels = bytearray([250, 250, 253] * width * height)

    def pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            offset = (y * width + x) * 3
            pixels[offset:offset + 3] = bytes(color)

    def line(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], thickness: int = 1) -> None:
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            for offset_x in range(-(thickness // 2), thickness // 2 + 1):
                for offset_y in range(-(thickness // 2), thickness // 2 + 1):
                    pixel(x0 + offset_x, y0 + offset_y, color)
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    grid, axis, curve = (226, 229, 238), (82, 84, 105), (194, 57, 111)
    for index in range(6):
        x = left + round(chart_width * index / 5)
        y = top + round(chart_height * index / 5)
        line(x, top, x, top + chart_height, grid)
        line(left, y, left + chart_width, y, grid)
    line(left, top + chart_height, left + chart_width, top + chart_height, axis, 2)
    line(left, top, left, top + chart_height, axis, 2)

    coordinates = []
    for index, plan in enumerate(samples):
        x = left + round(chart_width * index / (points - 1))
        y = top + chart_height - round(chart_height * plan.expected_total / max_value)
        coordinates.append((x, y))
    for start, end in zip(coordinates, coordinates[1:]):
        line(*start, *end, curve, 3)
    for x, y in coordinates[::5]:
        for offset_x in range(-3, 4):
            for offset_y in range(-3, 4):
                if offset_x * offset_x + offset_y * offset_y <= 9:
                    pixel(x + offset_x, y + offset_y, curve)

    output = Path(tempfile.gettempdir()) / f"astrbot_bilibili_benefit_curve_{int(time.time() * 1000)}.png"
    output.write_bytes(_png(width, height, pixels))
    return output
