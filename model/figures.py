"""Figures for Merilehto (2026b). Reads ../data/*.csv, writes ../figures/*.pdf."""
from pathlib import Path
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

ROOT = Path(__file__).resolve().parent.parent
D, F = ROOT / "data", ROOT / "paper" / "figures"
F.mkdir(exist_ok=True)

LM = Path("/usr/share/texmf/fonts/opentype/public/lm")
for f in ["lmroman10-regular.otf", "lmroman10-bold.otf", "lmroman10-italic.otf"]:
    if (LM / f).exists():
        fm.fontManager.addfont(str(LM / f))
mpl.rcParams.update({
    "font.family": "Latin Modern Roman", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#8a8984", "axes.linewidth": 0.6, "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.labelcolor": "#0b0b0b", "text.color": "#0b0b0b",
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.minor.width": 0.4, "ytick.minor.width": 0.4,
    "grid.color": "#e4e3df", "grid.linewidth": 0.6, "pdf.fonttype": 3, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03, "mathtext.fontset": "cm", "lines.solid_capstyle": "round",
})
COL = {"Base": "#2a78d6", "Accelerated": "#eb6834", "High": "#1baf7a"}
INK2, INK3, REF = "#52514e", "#8a8984", "#6b6a66"
CASES = ["Base", "Accelerated", "High"]
STATES_ = ["low", "central", "high"]
W1 = 6.3  # full text width, inches


def mw(x, _=None):
    return f"{x/1000:g} GW" if x >= 1000 else f"{x:g} MW"


paths = pd.read_csv(D / "paths.csv")
res = pd.read_csv(D / "results.csv")

# ---------------------------------------------------------- Fig 1: connected-capacity paths, linear scale
import numpy as np
fig, ax = plt.subplots(figsize=(W1, 3.2))
yrs_i = np.linspace(2030, 2035, 21)
for c in CASES:
    p = paths[paths.case == c].pivot(index="year", columns="state", values="C_fi")
    r = res[res.case == c].set_index("state")
    # 2030 checkpoint -> 2035: geometric connection, illustrative only
    seg = {st: np.exp(np.interp(yrs_i, [2030, 2035], np.log([r.loc[st, "C30"], r.loc[st, "C35"]]))) for st in STATES_}
    ax.fill_between(yrs_i, seg["low"], seg["high"], color=COL[c], alpha=0.08, lw=0)
    ax.plot(yrs_i, seg["central"], color=COL[c], lw=1.4, ls=(0, (3, 2)))
    # 2035 -> 2050 constructed paths
    ax.fill_between(p.index, p["low"], p["high"], color=COL[c], alpha=0.16, lw=0)
    ax.plot(p.index, p["central"], color=COL[c], lw=2)
    ax.plot(p.index, p["low"], color=COL[c], lw=0.8, ls=(0, (2, 2)))
    ax.plot(p.index, p["high"], color=COL[c], lw=0.8, ls=(0, (2, 2)))
    for yr, v in [(2030, r.loc["central", "C30"]), (2035, p.loc[2035, "central"]), (2050, p.loc[2050, "central"])]:
        ax.plot([yr], [v], "o", ms=5, color=COL[c], mec="#fcfcfb", mew=1.2, zorder=5)
    ax.annotate(f"{c}\n{mw(p.loc[2050,'central'])}", (2050, p.loc[2050, "central"]), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=8, color=INK2)
ax.set_xlim(2029.6, 2050); ax.set_ylim(0, 8500)
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: "0" if x == 0 else mw(x)))
ax.set_xticks(range(2030, 2051, 5)); ax.grid(axis="y")
ax.set_ylabel("Finnish quantum-related\nconnected capacity")
ax.axvline(2035, color=INK3, lw=0.6)
fig.savefig(F / "fig1_paths.pdf"); plt.close(fig)

# ---------------------------------------------------------- Fig 3: envelopes vs grid markers
fig, ax = plt.subplots(figsize=(W1, 3.3))
y = 0
yt, yl = [], []
for c in CASES:
    r = res[res.case == c].set_index("state")
    for yr, lab, a in [(2030, "2030", 0.25), (2035, "2035", 0.5), (2050, "2050", 1.0)]:
        lo, ce, hi = r.loc["low", f"C{yr%100}"], r.loc["central", f"C{yr%100}"], r.loc["high", f"C{yr%100}"]
        ax.plot([lo, hi], [y, y], color=COL[c], lw=5, alpha=a, solid_capstyle="round")
        ax.plot([ce], [y], "o", ms=6, color=COL[c], mec="#fcfcfb", mew=1.2, alpha=1 if yr == 2050 else .75)
        ax.text(hi * 1.25, y, f"{mw(lo)}–{mw(hi)}", va="center", fontsize=7.5, color=INK2)
        yt.append(y); yl.append(f"{c} {lab}")
        y -= 0.8
    y -= 0.5
for x, lab in [(30, "30 MW\nKJV2026 draft"), (250, "250 MW\nconditional\nconnection model"),
               (5000, "c. 5 GW signed\ndata-centre\nagreements")]:
    ax.axvline(x, color=REF, lw=0.8, ls=(0, (3, 2)), zorder=0)
    ax.text(x, 0.75, lab, ha="center", va="bottom", fontsize=7.2, color=REF, linespacing=1.0,
            bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
ax.set_xscale("log"); ax.set_xlim(0.3, 40000)
ax.xaxis.set_major_formatter(FuncFormatter(mw)); ax.xaxis.set_minor_formatter(NullFormatter())
ax.set_yticks(yt); ax.set_yticklabels(yl); ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False); ax.set_ylim(y + 0.6, 2.2)
ax.set_xlabel("Finnish quantum-related connected capacity (logarithmic scale)")
ax.grid(axis="x", which="major")
fig.savefig(F / "fig3_envelopes.pdf"); plt.close(fig)

# ---------------------------------------------------------- Fig 4: materiality (annual energy)
fig, ax = plt.subplots(figsize=(W1, 2.4))
ax.axvspan(11, 35, color="#e4e3df", alpha=0.7, lw=0, zorder=0)
ax.text(11.5, 2.75, "Fingrid 2035 data-centre\nconsumption range, 11–35 TWh", ha="left", fontsize=7.2, color=INK2, va="bottom",
        bbox=dict(boxstyle="square,pad=0.15", fc="#ecebe7", ec="none"))
ax.axvline(28, color=REF, lw=0.8, ls=(0, (3, 2)))
ax.text(28.6, -0.62, "c. 28 TWh: all signed data-centre\nprojects built (Fingrid)", fontsize=7.2, color=REF, va="center",
        bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
for i, c in enumerate(CASES):
    r = res[res.case == c].set_index("state")
    yy = 2 - i
    lo, ce, hi = r.loc["low", "twh50"], r.loc["central", "twh50"], r.loc["high", "twh50"]
    ax.plot([lo, hi], [yy, yy], color=COL[c], lw=5, solid_capstyle="round")
    ax.plot([ce], [yy], "o", ms=6, color=COL[c], mec="#fcfcfb", mew=1.2)
    ax.text(hi + 1.2, yy, f"{lo:.1f}–{hi:.1f} TWh  (central {ce:.1f}: {ce/359*100:.0f}–{ce/131*100:.0f}%)" if ce > 5 else f"{lo:.1f}–{hi:.1f} TWh  (central {ce:.1f}: {ce/359*100:.1f}–{ce/131*100:.1f}%)",
            va="center", fontsize=7.5, color=INK2)
ax.set_yticks([2, 1, 0]); ax.set_yticklabels(CASES); ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False); ax.set_ylim(-1.0, 3.4); ax.set_xlim(0, 90)
ax.set_xlabel("2050 Finnish quantum-related annual electricity (TWh/yr)")
ax.grid(axis="x")
fig.savefig(F / "fig4_materiality.pdf"); plt.close(fig)

# ---------------------------------------------------------- Fig 5: floor / span / headroom
st = pd.read_csv(D / "sticky.csv")
fig, ax = plt.subplots(figsize=(W1, 2.3))
labels = []
for i, (_, r) in enumerate(st.iterrows()):
    yy = 3 - i
    c_floor, c_span = COL["High"], "#a6dfc9"
    ax.barh(yy, r.floor, color=c_floor, height=0.55, edgecolor="#fcfcfb", lw=1)
    ax.barh(yy, r.span, left=r.floor, color=c_span, height=0.55, edgecolor="#fcfcfb", lw=1)
    ax.barh(yy, r.C - r.peak, left=r.peak, color="none", height=0.55, edgecolor=INK3, lw=0.6, hatch="////")
    ax.text(r.floor / 2, yy, f"{r.floor:,.0f}".replace(",", " "), ha="center", va="center", fontsize=7.5, color="#0b0b0b")
    ax.text(r.floor + r.span / 2, yy, f"{r.span:,.0f}".replace(",", " "), ha="center", va="center", fontsize=7.5, color="#0b0b0b")
    st_lab = "central" if r.state == "central" else "upper"
    labels.append(f"High {st_lab}, m = {r.m:.2f}")
ax.set_yticks([3, 2, 1, 0]); ax.set_yticklabels(labels); ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False)
ax.set_xlabel("MW in 2050"); ax.set_xlim(0, 8400); ax.grid(axis="x")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=COL["High"], label="minimum stable floor"),
                   Patch(color="#a6dfc9", label="nominal peak-to-floor span"),
                   Patch(facecolor="none", edgecolor=INK3, hatch="////", label="connection headroom (C − peak)")],
          loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=3, frameon=False)
fig.savefig(F / "fig5_flexibility.pdf"); plt.close(fig)

# ---------------------------------------------------------- Fig 6: tornado
t = pd.read_csv(D / "tornado.csv")
t["swing"] = (t.twh_high - t.twh_low).abs()
t = t.sort_values("swing")
c0 = t.twh_central.iloc[0]
fig, ax = plt.subplots(figsize=(W1, 2.6))
for i, (_, r) in enumerate(t.iterrows()):
    lo, hi = r.twh_low - c0, r.twh_high - c0
    ax.barh(i, lo, left=c0, color="#9ec3ee", height=0.6, edgecolor="#fcfcfb", lw=1)
    ax.barh(i, hi, left=c0, color=COL["Base"], height=0.6, edgecolor="#fcfcfb", lw=1)
    txt_l = f"{r.low_setting}: {r.twh_low:.1f}" if abs(lo) > 1e-6 else f"{r.low_setting}: no change"
    txt_h = f"{r.high_setting}: {r.twh_high:.1f}" if abs(hi) > 1e-6 else f"{r.high_setting}: no change"
    ax.text(min(c0 + lo, c0) - 0.4, i, txt_l, ha="right", va="center", fontsize=7.2, color=INK2)
    ax.text(max(c0 + hi, c0) + 0.4, i, txt_h, ha="left", va="center", fontsize=7.2, color=INK2)
ax.axvline(c0, color="#0b0b0b", lw=0.8)
ax.set_yticks(range(len(t))); ax.set_yticklabels(t.param); ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False); ax.set_xlim(8, 46)
ax.set_xlabel(f"2050 High central annual electricity (TWh/yr); central = {c0:.1f}")
ax.grid(axis="x")
fig.savefig(F / "fig6_tornado.pdf"); plt.close(fig)
print("ok")
