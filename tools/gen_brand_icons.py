#!/usr/bin/env python3
"""
Generate PNG brand assets from SVGs for Home Assistant brands submission.

Requirements:
    pip install cairosvg

Usage:
    python tools/gen_brand_icons.py

Outputs:
    - build/brand/icon.png (256x256)
    - build/brand/logo.png (512x256)
"""
from pathlib import Path
import cairosvg

ROOT = Path(__file__).resolve().parents[1]
SRC_ICON = ROOT / "assets/brand/icon.svg"
SRC_LOGO = ROOT / "assets/brand/logo.svg"
OUT_DIR = ROOT / "build/brand"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Icon 256x256
cairosvg.svg2png(url=str(SRC_ICON), write_to=str(OUT_DIR / "icon.png"), output_width=256, output_height=256)

# Logo 512x256 (wide)
cairosvg.svg2png(url=str(SRC_LOGO), write_to=str(OUT_DIR / "logo.png"), output_width=512, output_height=256)

print("Wrote:")
for p in (OUT_DIR / "icon.png", OUT_DIR / "logo.png"):
    print(" -", p)

