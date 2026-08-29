#!/usr/bin/env python3
"""Generate MineRift bitmap rank badges and deterministic release pack artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FONT_DIR = ASSETS / "cleanresources" / "font"
MINECRAFT_FONT_DIR = ASSETS / "minecraft" / "font"
BADGE_DIR = ASSETS / "cleanresources" / "textures" / "font" / "badges"
DIST = ROOT / "dist"

RANKS = [
    ("owner", "OWNER", "\ue100", "#F43F5E"),
    ("manager", "MANAGER", "\ue101", "#FF5A8B"),
    ("admin", "ADMIN", "\ue102", "#EF4444"),
    ("sr_mod", "SR.MOD", "\ue103", "#FB3C65"),
    ("mod", "MOD", "\ue104", "#FF6B6B"),
    ("helper", "HELPER", "\ue105", "#22D3EE"),
    ("media", "MEDIA", "\ue106", "#38BDF8"),
    ("rift", "RIFT", "\ue107", "#A855F7"),
    ("champ", "CHAMP", "\ue108", "#F59E0B"),
    ("elite", "ELITE", "\ue109", "#F97316"),
    ("hero", "HERO", "\ue10a", "#22C55E"),
    ("novice", "NOVICE", "\ue10b", "#8B5CF6"),
    ("member", "MEMBER", "\ue10c", "#8A8A8A"),
]

FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    ".": ("0", "0", "0", "0", "0", "1", "1"),
}


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def shade(color: tuple[int, int, int], amount: float) -> tuple[int, int, int, int]:
    return tuple(max(0, min(255, round(channel * amount))) for channel in color) + (255,)


def text_width(text: str) -> int:
    return sum(len(FONT[char][0]) + 1 for char in text) - 1


def compact_glyph(glyph: tuple[str, ...]) -> tuple[str, ...]:
    """Keep the readable strokes while fitting labels inside a shorter badge."""
    return tuple(glyph[index] for index in (0, 1, 3, 5, 6))


def render_badge(text: str, color_hex: str) -> Image.Image:
    width = text_width(text) + 5
    # The compact badge is intentionally two pixels shorter than the previous
    # release, matching the reference rank artwork. Keep the one-pixel inset
    # inside the bitmap; the provider ascent below moves the entire badge up.
    height = 7
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = image.load()
    color = rgb(color_hex)
    base = shade(color, 1.0)
    text_shadow = shade(color, 0.30)

    # A compact square rectangle with one flat rank color and no outline.
    for y in range(height):
        for x in range(width):
            pixels[x, y] = base

    # Draw a one-pixel darkened shadow strictly to the right of each stroke.
    # It must not extend below the text; the reference art uses a horizontal
    # offset only.
    cursor = 2
    for char in text:
        glyph = compact_glyph(FONT[char])
        for y, row in enumerate(glyph, start=1):
            for x, bit in enumerate(row, start=cursor):
                if bit == "1":
                    pixels[x + 1, y] = text_shadow
        cursor += len(glyph[0]) + 1

    cursor = 2
    for char in text:
        glyph = compact_glyph(FONT[char])
        for y, row in enumerate(glyph, start=1):
            for x, bit in enumerate(row, start=cursor):
                if bit == "1":
                    pixels[x, y] = (255, 255, 255, 255)
        cursor += len(glyph[0]) + 1
    return image


def generate_badges(regenerate: bool = False) -> None:
    BADGE_DIR.mkdir(parents=True, exist_ok=True)
    providers = []
    for badge_id, label, glyph, color in RANKS:
        badge_path = BADGE_DIR / f"{badge_id}.png"
        # Release builds package the committed PNG bytes unchanged. Pillow's
        # compression output can vary across operating systems even when the
        # pixels are identical, which would otherwise change release SHA-1s.
        if regenerate or not badge_path.exists():
            image = render_badge(label, color)
            image.save(badge_path, optimize=True)
        providers.append({
            "type": "bitmap",
            "file": f"cleanresources:font/badges/{badge_id}.png",
            # Render the complete bitmap one pixel higher without changing
            # the relative placement of the text and shadow inside it.
            "ascent": 7,
            "height": 7,
            "chars": [glyph],
        })
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    (FONT_DIR / "rank_badges.json").write_text(
        json.dumps({"providers": providers}, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8", newline="\n"
    )

    # Plain chat, LuckPerms prefixes and pasted PUA characters use
    # minecraft:default. Mirror the rank providers there so raw glyphs work
    # without a MiniMessage <font:...> wrapper, while preserving other custom
    # default-font providers.
    default_path = MINECRAFT_FONT_DIR / "default.json"
    MINECRAFT_FONT_DIR.mkdir(parents=True, exist_ok=True)
    existing = json.loads(default_path.read_text(encoding="utf-8")) if default_path.exists() else {"providers": []}
    badge_files = {provider["file"] for provider in providers}
    preserved = [
        provider for provider in existing.get("providers", [])
        if provider.get("file") not in badge_files
    ]
    default_path.write_text(
        json.dumps({"providers": preserved + providers}, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8", newline="\n"
    )


def generate_preview() -> None:
    scale = 4
    rows_left = RANKS[:7]
    rows_right = RANKS[7:]
    canvas = Image.new("RGBA", (500, 310), (18, 20, 27, 255))
    for column, ranks in enumerate((rows_left, rows_right)):
        x = 28 + column * 245
        for row, (badge_id, _label, _glyph, _color) in enumerate(ranks):
            badge = Image.open(BADGE_DIR / f"{badge_id}.png").convert("RGBA")
            badge = badge.resize((badge.width * scale, badge.height * scale), Image.Resampling.NEAREST)
            y = 20 + row * 36
            canvas.alpha_composite(badge, (x, y))
    DIST.mkdir(parents=True, exist_ok=True)
    canvas.save(DIST / "rank-badges-preview.png", optimize=True)


def metadata(variant: str) -> dict:
    if variant == "legacy":
        return {
            "pack": {
                "pack_format": 34,
                "supported_formats": [34, 64],
                "description": "MineRift CleanResources - Legacy (1.21-1.21.8)",
            }
        }
    return {
        "pack": {
            "min_format": [69, 0],
            "max_format": 999,
            "description": "MineRift CleanResources - Modern (1.21.9+)",
        }
    }


def zip_tree(source: Path, destination: Path) -> None:
    # Stored entries avoid zlib-version differences between Windows and Linux,
    # keeping the complete ZIP hash reproducible across local/Actions builds.
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                # Fixed metadata makes the release SHA-1 identical on Windows,
                # Linux/GitHub Actions, and future rebuilds of unchanged assets.
                info = zipfile.ZipInfo(path.relative_to(source).as_posix(), (2020, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.create_version = 20
                info.extract_version = 20
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_STORED)


def build_variant(variant: str) -> tuple[Path, str]:
    with tempfile.TemporaryDirectory(prefix=f"cleanresources-{variant}-") as temporary:
        staging = Path(temporary)
        shutil.copytree(ASSETS, staging / "assets")
        for json_file in (staging / "assets").rglob("*.json"):
            canonical = json_file.read_text(encoding="utf-8").replace("\r\n", "\n")
            json_file.write_text(canonical, encoding="utf-8", newline="\n")
        shutil.copy2(ROOT / "pack.png", staging / "pack.png")
        (staging / "pack.mcmeta").write_text(
            json.dumps(metadata(variant), indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        destination = DIST / f"cleanresources-{variant}.zip"
        zip_tree(staging, destination)
    digest = hashlib.sha1(destination.read_bytes()).hexdigest().upper()
    (Path(str(destination) + ".sha1")).write_text(
        digest + "\n", encoding="ascii", newline="\n")
    return destination, digest


def verify_pack(path: Path, expected_hash: str, variant: str) -> None:
    actual = hashlib.sha1(path.read_bytes()).hexdigest().upper()
    assert actual == expected_hash
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        assert "pack.mcmeta" in names and "pack.png" in names
        assert "assets/cleanresources/font/default.json" in names
        assert "assets/cleanresources/font/rank_badges.json" in names
        assert "assets/minecraft/font/default.json" in names
        meta = json.loads(archive.read("pack.mcmeta"))
        if variant == "legacy":
            assert meta["pack"]["pack_format"] == 34
            assert meta["pack"]["supported_formats"] == [34, 64]
        else:
            assert meta["pack"]["min_format"] == [69, 0]
            assert "pack_format" not in meta["pack"]
            assert "supported_formats" not in meta["pack"]


def verify_assets() -> None:
    font = json.loads((FONT_DIR / "rank_badges.json").read_text(encoding="utf-8"))
    providers = font["providers"]
    chars = [provider["chars"][0] for provider in providers]
    assert len(providers) == 13 and len(set(chars)) == 13
    default_font = json.loads((MINECRAFT_FONT_DIR / "default.json").read_text(encoding="utf-8"))
    default_chars = [
        row_char
        for provider in default_font.get("providers", [])
        for row in provider.get("chars", [])
        for row_char in row
        if row_char in chars
    ]
    assert set(default_chars) == set(chars), "Raw rank glyphs are missing from minecraft:default"
    existing = json.loads((FONT_DIR / "default.json").read_text(encoding="utf-8"))
    existing_chars = {
        char for provider in existing.get("providers", []) for row in provider.get("chars", []) for char in row
    }
    assert not existing_chars.intersection(chars), "Rank glyphs overlap an existing CleanResources glyph"
    assert all((BADGE_DIR / f"{badge_id}.png").is_file() for badge_id, *_ in RANKS)
    for badge_id, *_ in RANKS:
        badge = Image.open(BADGE_DIR / f"{badge_id}.png").convert("RGBA")
        assert badge.size[1] == 7
        assert all(badge.getpixel(corner) == badge.getpixel((1, 1)) for corner in (
            (0, 0), (badge.width - 1, 0), (0, badge.height - 1),
            (badge.width - 1, badge.height - 1),
        )), f"{badge_id} does not have a flat rectangular background"
        colors = {
            badge.getpixel((x, y))
            for x in range(badge.width)
            for y in range(badge.height)
        }
        assert len(colors) == 3, f"{badge_id} has unexpected extra colors"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="regenerate badge PNG source assets before building",
    )
    args = parser.parse_args()
    DIST.mkdir(parents=True, exist_ok=True)
    generate_badges(args.regenerate)
    generate_preview()
    verify_assets()
    built = {}
    for variant in ("legacy", "modern"):
        path, digest = build_variant(variant)
        verify_pack(path, digest, variant)
        built[variant] = {"file": path.name, "sha1": digest}
        print(f"{path.name}: {digest}")
    (DIST / "release-manifest.json").write_text(
        json.dumps({"schema": 1, "packs": built}, indent=2) + "\n",
        encoding="utf-8", newline="\n"
    )
    print("Verified 13 unique badges, preserved existing glyphs, and validated both pack ZIPs.")


if __name__ == "__main__":
    main()
