#!/usr/bin/env python3
"""Recent writing as cards with covers, from the site RSS.

    python3 posts.py      -> assets/posts/*.svg + the block between BLOG-POST-LIST markers
                             in README.md (EN feed) and README.ru.md (RU feed)

Runs daily in .github/workflows/blog.yml and is also called by build.py. Needs Pillow.
Each card embeds a square thumbnail of the post's og:image as base64, because GitHub
does not load external images inside an SVG. File names carry a hash of the post URL,
so a new post gets a new image URL and GitHub's image cache never shows a stale card.
"""
import base64, hashlib, html, io, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "posts")
N = 4
UA = {"User-Agent": "ilia-ae-profile-bot/1.0"}
FEEDS = {"en": ("https://ilia.ae/en/feed/", "README.md"), "ru": ("https://ilia.ae/feed/", "README.ru.md")}
MONTHS = {"en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
          "ru": "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()}
START, END = "<!-- BLOG-POST-LIST:START -->", "<!-- BLOG-POST-LIST:END -->"


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def _xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _wrap(s, width, maxlines):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
            if len(lines) == maxlines:
                break
    if cur and len(lines) < maxlines:
        lines.append(cur)
    if len(" ".join(lines)) < len(s) and lines:
        lines[-1] = lines[-1].rstrip(".,:;") + "…"
    return lines[:maxlines]


def items(lang):
    root = ET.fromstring(_get(FEEDS[lang][0]))
    out = []
    for it in root.findall("./channel/item")[:N]:
        d = parsedate_to_datetime(it.findtext("pubDate"))
        cats = [c.text for c in it.findall("category") if c.text]
        out.append(dict(title=html.unescape(it.findtext("title")).strip(), link=it.findtext("link").strip(),
                        date=f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}", cat=cats[0] if cats else ""))
    return out


def thumb(link, size=240):
    """Square crop of the post's og:image (a 1200x630 card with the cover centred)."""
    from PIL import Image
    page = _get(link).decode("utf-8", "replace")
    m = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    if not m:
        return None
    im = Image.open(io.BytesIO(_get(m.group(1)))).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((size, size), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
    return base64.b64encode(buf.getvalue()).decode()


def card(p, b64):
    W, H, T = 440, 150, 126
    acc, sub = "#4D82E8", "#9aa0a6"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" '
           f'height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
           f'<defs><clipPath id="c"><rect x="12" y="12" width="{T}" height="{T}" rx="10"/></clipPath></defs>',
           f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="#888888" fill-opacity="0.04" '
           f'stroke="#88888850"/>']
    x0 = 22
    if b64:
        out.append(f'<image x="12" y="12" width="{T}" height="{T}" clip-path="url(#c)" '
                   f'preserveAspectRatio="xMidYMid slice" href="data:image/jpeg;base64,{b64}" '
                   f'xlink:href="data:image/jpeg;base64,{b64}"/>')
        out.append(f'<rect x="12.5" y="12.5" width="{T-1}" height="{T-1}" rx="10" fill="none" stroke="#88888840"/>')
        x0 = 12 + T + 16
    y = 38
    for ln in _wrap(p["title"], 33, 4):
        out.append(f'<text x="{x0}" y="{y}" font-size="15" font-weight="700" fill="{acc}">{_xml(ln)}</text>')
        y += 21
    meta = p["date"] + (f"  ·  {p['cat']}" if p["cat"] else "")
    out.append(f'<text x="{x0}" y="{H-20}" font-size="12" fill="{sub}">{_xml(meta)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def block(lang):
    """Write the cards for `lang`, return the README lines that go between the markers."""
    os.makedirs(OUT, exist_ok=True)
    keep, lines = set(), []
    posts = items(lang)
    for p in posts:
        name = f"{lang}-{hashlib.md5(p['link'].encode()).hexdigest()[:10]}.svg"
        keep.add(name)
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            try:
                b64 = thumb(p["link"])
            except Exception as e:  # a missing cover must not break the list
                print("thumb failed:", p["link"], e, file=sys.stderr); b64 = None
            open(path, "w", encoding="utf-8").write(card(p, b64))
        p["img"] = f"assets/posts/{name}"
    for f in os.listdir(OUT):
        if f.startswith(lang + "-") and f not in keep:
            os.remove(os.path.join(OUT, f))
    for n in range(0, len(posts), 2):
        pair = [f'<a href="{p["link"]}"><img src="{p["img"]}" alt="{_xml(p["title"])}" width="49%"/></a>'
                for p in posts[n:n + 2]]
        lines += ['<p align="center">', "\n".join(pair), "</p>"]
    return lines


def update(lang):
    fn = os.path.join(HERE, FEEDS[lang][1])
    s = open(fn, encoding="utf-8").read()
    a, b = s.index(START) + len(START), s.index(END)
    new = s[:a] + "\n" + "\n".join(block(lang)) + "\n" + s[b:]
    if new != s:
        open(fn, "w", encoding="utf-8").write(new)
    return new != s


if __name__ == "__main__":
    for lang in FEEDS:
        print(lang, "updated" if update(lang) else "unchanged")
