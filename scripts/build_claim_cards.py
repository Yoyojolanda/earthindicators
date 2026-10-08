"""One share link per claim, with its own link preview.

X, Bluesky and others ignore the #part of a link, so every claims.html#... link showed the same general card.
This script makes, for each claim in claims.html:
  c/<id>.html      a tiny page whose preview (og:/twitter: tags) shows that claim and its short answer;
                   people who open it are sent straight on to claims.html#<id>
  og/c/<id>.png    the 1200x630 preview image: the claim and the short answer
The "Copy link to this answer" buttons on the claims page copy the c/<id>.html link.
Sentences of a short answer that contain a live number (filled in by the browser) are left out of the
preview text, since the preview cannot run the page's code. Pages and images of claims that no longer
exist are removed. Run from the repo root: python scripts/build_claim_cards.py
"""
import html, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import matplotlib.pyplot as plt
from build_og import frame, DPI, INK, MUTED, ACC

SITE = "https://earthindicators.org"


def text(fragment):
    """HTML fragment -> plain text."""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def short_answer(ans):
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"])", ans.strip())
    keep = [s for s in sentences if 'class="live"' not in s]
    return text(" ".join(keep))


def claims():
    s = open("claims.html", encoding="utf-8").read()
    pat = re.compile(r'<details class="claim" id="([^"]+)"[^>]*>\s*<summary><h3 class="ct">(.*?)</h3></summary>\s*'
                     r'<div class="body">\s*<p class="ans">(.*?)</p>', re.S)
    out = []
    for cid, head, ans in pat.findall(s):
        quotes = [text(q) for q in re.findall(r"<q>(.*?)</q>", head, re.S)]
        out.append({"id": cid, "claim": quotes[0] if quotes else text(head), "answer": short_answer(ans)})
    n = s.count('class="claim"')
    if len(out) < n:
        raise SystemExit(f"only {len(out)} of {n} claims could be read; did claims.html change shape?")
    return out


def wrap(fig, s, size, maxw, **kw):
    """Break s into lines no wider than maxw (figure fraction), measured with the real font."""
    r, W = fig.canvas.get_renderer(), fig.bbox.width
    width = lambda t: fig.text(0, 0, t, fontsize=size, **kw).get_window_extent(r).width / W
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if cur and width(t) > maxw:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    for t in fig.texts[:]:                       # remove the measuring texts again
        if t.get_position() == (0, 0) and t.get_text() not in ("",): fig.texts.remove(t)
    return lines


def card(c):
    fig = frame()
    fig.text(0.05, 0.785, "CLAIM", fontsize=16, weight="bold", color=ACC)
    q, r = "\u201c" + c["claim"] + "\u201d", fig.canvas.get_renderer()
    for size in (46, 40, 34, 30):
        qw = wrap(fig, q, size, 0.90, weight="bold")
        if len(qw) <= 3: break
    qt = fig.text(0.05, 0.755, "\n".join(qw), fontsize=size, weight="bold", color=INK, va="top", linespacing=1.15)
    top = qt.get_window_extent(r).y0 / fig.bbox.height - 0.05            # just below the claim
    for asize in (27, 24, 21, 19):
        aw = wrap(fig, c["answer"], asize, 0.90)
        if len(aw) * asize * 1.4 / 630 * 100 / 72 <= top - 0.13: break
    room = max(1, int((top - 0.13) / (asize * 1.4 / 630 * 100 / 72)))
    if len(aw) > room:
        aw = aw[:room]; aw[-1] = aw[-1].rstrip(" ,;:") + " \u2026"
    fig.text(0.05, top, "\n".join(aw), fontsize=asize, color=MUTED, va="top", linespacing=1.4)
    fig.text(0.05, 0.06, "The full answer, with live data from NOAA, NASA, NSIDC and Copernicus", fontsize=15, color=MUTED)
    fig.savefig(f"og/c/{c['id']}.png", dpi=DPI, facecolor="white")
    plt.close(fig)


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Earth Indicators</title>
<meta name="robots" content="noindex">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Earth Indicators">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{site}/c/{id}.html">
<meta property="og:image" content="{site}/og/c/{id}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="description" content="{desc}">
<script>location.replace('../claims.html#{id}')</script>
<style>body{{font:17px/1.5 system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px}}</style>
</head><body>
<p><a href="../claims.html#{id}">{title}: read the answer on Earth Indicators</a></p>
</body></html>
"""


def main():
    os.makedirs("c", exist_ok=True); os.makedirs("og/c", exist_ok=True)
    C = claims()
    for c in C:
        title = "“" + c["claim"] + "”"
        desc = c["answer"] if len(c["answer"]) <= 200 else c["answer"][:197].rsplit(" ", 1)[0] + " …"
        e = lambda v: html.escape(v, quote=True)
        open(f"c/{c['id']}.html", "w", encoding="utf-8").write(PAGE.format(
            site=SITE, id=c["id"], title=e(title), desc=e(desc), alt=e(f"Claim: {title} Short answer: {desc}")))
        card(c)
    ids = {c["id"] for c in C}
    for d, ext in (("c", ".html"), ("og/c", ".png")):
        for f in os.listdir(d):
            if f.endswith(ext) and f[:-len(ext)] not in ids:
                os.remove(os.path.join(d, f))
    print(f"{len(C)} claim links and preview images:", ", ".join(sorted(ids)))


if __name__ == "__main__":
    main()
