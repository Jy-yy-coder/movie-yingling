# -*- coding: utf-8 -*-
"""为缺失的海报生成占位图（真海报恢复后可覆盖）。"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "data" / "enriched" / "movies_core.json"
POSTER_DIR = ROOT / "data" / "posters"
THUMB_DIR = ROOT / "data" / "enriched" / "posters_thumb"

REGION_COLORS = {
    "华语": (28, 54, 78),
    "日本": (62, 36, 42),
    "韩国": (42, 36, 62),
    "欧美": (36, 48, 42),
}
ACCENT = {
    "华语": (212, 175, 110),
    "日本": (220, 140, 140),
    "韩国": (170, 160, 220),
    "欧美": (140, 190, 170),
}


def _font(size: int) -> ImageFont.ImageFont:
    for name in (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        p = Path(name)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                pass
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    text = (text or "").encode("utf-8", "ignore").decode("utf-8").strip() or "未命名"
    lines: list[str] = []
    cur = ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = ch
        if len(lines) >= 4:
            break
    if cur and len(lines) < 4:
        lines.append(cur)
    return lines


def main() -> None:
    core = json.loads(CORE.read_text(encoding="utf-8"))
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    f_title = _font(42)
    f_meta = _font(28)
    f_id = _font(22)

    made = skipped = 0
    for m in core:
        mid = str(m["movie_id"])
        jpg = POSTER_DIR / f"{mid}.jpg"
        webp = THUMB_DIR / f"{mid}.webp"
        if jpg.exists() and webp.exists() and jpg.stat().st_size > 1000:
            skipped += 1
            continue

        region = m.get("region") or "欧美"
        bg = REGION_COLORS.get(region, (40, 40, 48))
        ac = ACCENT.get(region, (180, 180, 180))
        w, h = 400, 600
        img = Image.new("RGB", (w, h), bg)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 8], fill=ac)
        d.rectangle([0, h - 8, w, h], fill=ac)

        title = m.get("title") or mid
        title_show = title.split(" ", 1)[0] if " " in title else title
        lines = _wrap(d, title_show, f_title, w - 48)
        y = 180
        for line in lines:
            tw = d.textlength(line, font=f_title)
            d.text(((w - tw) / 2, y), line, font=f_title, fill=(245, 240, 230))
            y += 52

        meta = f"{m.get('year') or ''} · {region}"
        tw = d.textlength(meta, font=f_meta)
        d.text(((w - tw) / 2, y + 20), meta, font=f_meta, fill=ac)

        rating = m.get("rating")
        if rating:
            rtxt = f"豆瓣 {rating}"
            tw = d.textlength(rtxt, font=f_meta)
            d.text(((w - tw) / 2, y + 60), rtxt, font=f_meta, fill=(200, 200, 200))

        tw = d.textlength(mid, font=f_id)
        d.text(((w - tw) / 2, h - 48), mid, font=f_id, fill=(120, 120, 130))

        img.save(jpg, "JPEG", quality=85)
        img.resize((160, 240), Image.Resampling.LANCZOS).save(webp, "WEBP", quality=80)
        made += 1

    print(
        f"done made={made} skipped={skipped} "
        f"jpg={len(list(POSTER_DIR.glob('*.jpg')))} "
        f"webp={len(list(THUMB_DIR.glob('*.webp')))}"
    )


if __name__ == "__main__":
    main()
