"""Image loading, built-in presets and saved state for the 8x8 display."""
import json
import os
from pathlib import Path

from .device import WIDTH, HEIGHT

BLACK = (0, 0, 0)

_COLORS = {
    ".": BLACK, "Y": (255, 180, 0), "R": (255, 0, 40), "W": (255, 255, 255),
    "G": (0, 220, 60), "B": (0, 120, 255), "P": (200, 0, 255), "C": (0, 220, 220),
    "O": (255, 90, 0), "K": BLACK,
}

PRESETS = {
    "smile": ["..YYYY..", ".YYYYYY.", "YYKYYKYY", "YYYYYYYY",
              "YKYYYYKY", "YYKKKKYY", ".YYYYYY.", "..YYYY.."],
    "wink":  ["..YYYY..", ".YYYYYY.", "YYKYYKKY", "YYYYYYYY",
              "YKYYYYKY", "YYKKKKYY", ".YYYYYY.", "..YYYY.."],
    "sad":   ["..BBBB..", ".BBBBBB.", "BBKBBKBB", "BBBBBBBB",
              "BBBKKBBB", "BBKBBKBB", ".BBBBBB.", "..BBBB.."],
    "heart": ["........", ".RR..RR.", "RRRRRRRR", "RRRRRRRR",
              ".RRRRRR.", "..RRRR..", "...RR...", "........"],
    "star":  ["...YY...", "...YY...", "YYYYYYYY", ".YYYYYY.",
              "..YYYY..", ".YYYYYY.", ".YY..YY.", "YY....YY"],
    "check": ["........", ".......G", "......GG", ".....GG.",
              "G...GG..", "GG.GG...", ".GGG....", "..G....."],
    "cross": ["R......R", "RR....RR", ".RR..RR.", "..RRRR..",
              "..RRRR..", ".RR..RR.", "RR....RR", "R......R"],
    "note":  ["....CCC.", "....C.CC", "....C...", "....C...",
              "..CCC...", ".CCCC...", ".CCCC...", "..CC...."],
}


def preset(name):
    return [[_COLORS[c] for c in row] for row in PRESETS[name]]


def blank():
    return [[BLACK] * WIDTH for _ in range(HEIGHT)]


def load_image(path):
    """Return a list of (pixels, seconds) frames, scaled to 8x8.
    Single images return one frame; animated GIF/WebP/APNG return all."""
    from PIL import Image, ImageSequence
    img = Image.open(path)
    frames = []
    for f in ImageSequence.Iterator(img):
        dur = max(0.05, f.info.get("duration", 100) / 1000)
        rgba = f.convert("RGBA")
        if rgba.size != (WIDTH, HEIGHT):
            # NEAREST keeps pixel art crisp; for photos LANCZOS reads better
            small = max(rgba.size) <= 32
            rgba = rgba.resize((WIDTH, HEIGHT),
                               Image.NEAREST if small else Image.LANCZOS)
        bg = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        rgb = Image.alpha_composite(bg, rgba).convert("RGB")
        frames.append(([[rgb.getpixel((x, y)) for x in range(WIDTH)]
                        for y in range(HEIGHT)], dur))
    return frames


def save_png(pixels, path, scale=1):
    from PIL import Image
    img = Image.new("RGB", (WIDTH, HEIGHT))
    for y in range(HEIGHT):
        for x in range(WIDTH):
            img.putpixel((x, y), tuple(pixels[y][x]))
    if scale > 1:
        img = img.resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)
    img.save(path)


# --- saved state (restored when the mic is plugged in) -----------------------
def _state_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "seiren-emote" / "state.json"


def save_state(pixels=None, brightness=None, image_path=None, rotate=None, flip=None):
    p = _state_path()
    state = load_state()
    if rotate is not None:
        state["rotate"] = int(rotate) % 360
    if flip is not None:
        state["flip"] = bool(flip)
    if pixels is not None:
        state["pixels"] = [[list(c) for c in row] for row in pixels]
        state.pop("image_path", None)
    if image_path is not None:
        state["image_path"] = str(Path(image_path).resolve())
    if brightness is not None:
        state["brightness"] = int(brightness)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state))


def load_state():
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}
