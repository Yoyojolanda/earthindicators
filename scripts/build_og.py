"""Draws the 1200x630 link-preview images (og/*.png) shown when a page is shared on X, Bluesky, etc.
Live pages use the numbers in og/og.json (made by scripts/og_data.js); the home and claims pages get a fixed card.
Run from the repo root: python scripts/build_og.py"""
import json, textwrap, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont("fonts/PoiretOne-Regular.ttf")   # site-name typeface

W, H, DPI = 12, 6.3, 100            # 1200 x 630 px
METHOD = "Datasets, method, code and checks: earthindicators.org/methods.html"
INK, MUTED, ACC, LINE, UMBER = "#1c1c1c", "#5f6368", "#d00000", "#8fa9c4", "#332b19"

def frame():
    fig = plt.figure(figsize=(W, H), dpi=DPI, facecolor="white")
    logo = fig.add_axes([0.045, 0.835, 0.07, 0.13])          # logo top left (img/logo-240.png)
    logo.imshow(plt.imread("img/logo-240.png")); logo.axis("off")
    fig.text(0.125, 0.878, "Earth Indicators", fontsize=30, family="Poiret One", color=UMBER)
    fig.text(0.95, 0.885, "earthindicators.org", fontsize=17, color=MUTED, ha="right")
    return fig

def live(page, d):
    fig = frame()
    fig.text(0.05, 0.74, d["title"], fontsize=34, weight="bold", color=INK)
    fig.text(0.05, 0.47, d["big"], fontsize=76, weight="bold", color=INK)
    fig.text(0.05, 0.38, d["label"], fontsize=19, color=MUTED, wrap=True)
    if len(d["spark"]) > 2:
        ax = fig.add_axes([0.63, 0.15, 0.32, 0.25])   # lower right, clear of the big number
        ys = d["spark"]
        ax.plot(range(len(ys)), ys, color=ACC, lw=3)
        ax.axis("off")
        fig.text(0.95, 0.10, d["sparkLabel"], fontsize=14, color=MUTED, ha="right")
    fig.text(0.05, 0.08, f"Latest: {d['through']}   ·   Data: {d['source']}", fontsize=15, color=MUTED)
    fig.text(0.05, 0.035, METHOD, fontsize=13, color=MUTED)
    fig.savefig(f"og/{page}.png", dpi=DPI, facecolor="white")
    plt.close(fig)

def fixed(page, title, lines):
    fig = frame()
    fig.text(0.05, 0.64, title, fontsize=44, weight="bold", color=INK, va="center")
    fig.text(0.05, 0.34, lines, fontsize=24, color=MUTED, va="center", linespacing=1.5)
    fig.text(0.05, 0.08, "Live data from NOAA, NASA, NSIDC and Copernicus", fontsize=15, color=MUTED)
    fig.text(0.05, 0.035, METHOD, fontsize=13, color=MUTED)
    fig.savefig(f"og/{page}.png", dpi=DPI, facecolor="white")
    plt.close(fig)

def slow(d):
    """Slow signals: a 3 x 2 grid of yearly numbers instead of one number and a sparkline."""
    fig = frame()
    fig.text(0.05, 0.725, d["title"], fontsize=40, weight="bold", color=INK)
    fig.text(0.05, 0.655, "Measured once a year or less often; each figure gives its year", fontsize=19, color=MUTED)
    for i, it in enumerate(d["items"][:6]):
        x, y = 0.05 + (i % 3) * 0.31, 0.51 - (i // 3) * 0.225
        fig.text(x, y, it["big"], fontsize=38, weight="bold", color=ACC if i == 0 else INK)
        fig.text(x, y - 0.025, "\n".join(textwrap.wrap(it["label"], 30)), fontsize=15, color=MUTED, va="top", linespacing=1.3)
    fig.text(0.05, 0.08, "Data: Global Carbon Project, Hawaii Ocean Time-series, RAPID, IUCN, Global Forest Watch, Aono", fontsize=15, color=MUTED)
    fig.text(0.05, 0.035, METHOD, fontsize=13, color=MUTED)
    fig.savefig("og/slow.png", dpi=DPI, facecolor="white")
    return fig

if __name__ == "__main__":
    data = json.load(open("og/og.json"))
    has_slow = "slow" in data
    if has_slow:
        plt.close(slow(data.pop("slow")))
    for page, d in data.items():
        live(page, d)
    fixed("index", "Is the climate changing?", "Every major indicator, updated automatically,\nin plain words.")
    fixed("claims", "Common climate claims,\nanswered with the latest data", "From \u201cit's cooling\u201d to \u201cit's too late\u201d:\nshort answers, live numbers, one link per answer.")
    print("drew the images:", ", ".join(list(data) + ["index", "claims"] + (["slow"] if has_slow else [])))
