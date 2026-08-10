"""Procedurally generate simple book-cover images (used by the demo seeder).

No network or stock photos needed — each cover is drawn locally with Pillow:
a diagonal gradient in the category colour, decorative shapes and the book
title/author typeset on it, saved under MEDIA_ROOT/covers/.
"""

from pathlib import Path

from django.conf import settings

W, H = 480, 640  # 3:4 aspect ratio, same as the catalogue cards

# category -> (dark, light) gradient colours
PALETTES = {
    "DATABASE": ((14, 116, 144), (56, 189, 248)),
    "PROGRAMMING": ((49, 46, 129), (129, 140, 248)),
    "NETWORKING": ((19, 78, 74), (45, 212, 191)),
    "MATHEMATICS": ((146, 64, 14), (251, 191, 36)),
    "ELECTRONICS": ((88, 28, 135), (192, 132, 252)),
    "ENGINEERING": ((15, 23, 42), (148, 163, 184)),
    "FICTION": ((159, 18, 57), (251, 113, 133)),
    "OTHER": ((6, 78, 59), (52, 211, 153)),
}

try:
    from PIL import Image, ImageDraw, ImageFont

    _FONT_DIRS = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/dejavu"),
        Path("/Library/Fonts"),
        Path("C:/Windows/Fonts"),
    ]

    def _load(name, fallback_size):
        for d in _FONT_DIRS:
            p = d / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p))
                except OSError:
                    pass
        return ImageFont.load_default(size=fallback_size)

    _bold = _load("DejaVuSans-Bold.ttf", 34)
    _regular = _load("DejaVuSans.ttf", 22)
    _small = _load("DejaVuSans.ttf", 16)

    try:
        _bold = _bold.font_variant(size=34)
    except Exception:
        pass
    try:
        _regular = _regular.font_variant(size=22)
    except Exception:
        pass
    try:
        _small = _small.font_variant(size=16)
    except Exception:
        pass

    PIL_AVAILABLE = True
except Exception:  # Pillow missing entirely
    PIL_AVAILABLE = False


def _gradient(draw, dark, light, w, h):
    """Diagonal gradient from dark (top-left) to light (bottom-right)."""
    steps = w + h
    for i in range(steps):
        t = i / max(1, steps - 1)
        r = int(dark[0] + (light[0] - dark[0]) * t)
        g = int(dark[1] + (light[1] - dark[1]) * t)
        b = int(dark[2] + (light[2] - dark[2]) * t)
        # diagonal line for this step
        x0, y0 = max(0, i - h), min(i, h)
        x1, y1 = min(i, w), max(0, i - w)
        draw.line([(x0, y0), (x1, y1)], fill=(r, g, b))


def _center(draw, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def make_cover_image(title, author, category, isbn):
    """Return a PIL Image for the given book metadata."""
    dark, light = PALETTES.get(category, PALETTES["OTHER"])
    img = Image.new("RGB", (W, H), dark)
    draw = ImageDraw.Draw(img, "RGBA")
    _gradient(draw, dark, light, W, H)

    # decorative translucent circles
    draw.ellipse([270, -110, 560, 180], fill=(255, 255, 255, 26))
    draw.ellipse([330, -60, 500, 110], outline=(255, 255, 255, 60), width=4)
    draw.ellipse([-120, 430, 170, 720], fill=(255, 255, 255, 22))

    # header tag
    draw.rectangle([36, 40, 36 + 150, 40 + 30], fill=(255, 255, 255, 34))
    draw.text((36 + 12, 40 + 7), "UMS LIBRARY", font=_small, fill=(255, 255, 255, 235))

    # spine line
    draw.rectangle([36, 205, 136, 211], fill=(255, 255, 255, 150))

    MAX_W = W - 72  # keep text inside side margins

    def wrap_px(text, font):
        """Wrap words so every rendered line fits within MAX_W pixels."""
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= MAX_W:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def fitted(lines, base_font, max_size, min_size):
        """Shrink the font until every line fits MAX_W."""
        size = max_size
        while size > min_size:
            font = base_font.font_variant(size=size)
            if all(draw.textlength(l, font=font) <= MAX_W for l in lines):
                return font
            size -= 2
        return base_font.font_variant(size=min_size)

    # title (pixel-wrapped, auto-shrunk)
    y = 235
    title_lines = wrap_px(title, _bold)[:5]
    title_font = fitted(title_lines, _bold, 34, 20)
    for line in title_lines:
        y += _center(draw, y, line, title_font, (255, 255, 255, 245)) + 8

    # author
    y += 18
    author_lines = wrap_px(author, _regular)[:2]
    author_font = fitted(author_lines, _regular, 22, 14)
    for line in author_lines:
        y += _center(draw, y, line, author_font, (255, 255, 255, 210)) + 5

    # category + ISBN at the bottom
    label = category.title()
    _center(draw, H - 88, label.upper(), _small, (255, 255, 255, 190))
    draw.rectangle([W / 2 - 40, H - 62, W / 2 + 40, H - 60], fill=(255, 255, 255, 90))
    _center(draw, H - 48, f"ISBN {isbn}", _small, (255, 255, 255, 170))

    # border
    draw.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0, 40), width=2)
    return img


def attach_generated_cover(book):
    """Draw a cover for a library.models.Book row and save it into media/covers/.

    Returns True when a cover file was written. Safe no-op without Pillow."""
    if not PIL_AVAILABLE:
        return False
    try:
        img = make_cover_image(book.title, book.author, book.category, book.isbn)
        rel = Path("covers") / f"seed-{book.isbn}.png"
        target = Path(settings.MEDIA_ROOT) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "PNG")
        book.cover = str(rel).replace("\\", "/")
        book.save(update_fields=["cover"])
        return True
    except Exception:
        return False
