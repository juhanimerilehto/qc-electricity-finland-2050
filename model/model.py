"""Finnish quantum-related electricity scenarios, 2030/2035 checkpoints -> 2050.

Reproducible calculation for Merilehto (2026b). All capacities in MW, energy in TWh/yr.
The 2035 states are retained unchanged from Merilehto (2026a). Post-2035 capacity
follows a desired path toward a 2050 Nordic target, subject to an annual build limit,
a commissioning lag, a retirement fraction and a Finnish connection budget.

Run:  python model.py            (writes ../data/*.csv; asserts the original 2030/2035 results are reproduced)
"""
from __future__ import annotations
import math, json, itertools
from dataclasses import dataclass, replace
from pathlib import Path
import csv

OUT = Path(__file__).resolve().parent.parent / "data"
H = 8760
CASES = ["Base", "Accelerated", "High"]
STATES = ["low", "central", "high"]
Y0, Y1 = 2035, 2050

# ---------------------------------------------------------------- inputs
# Retained 2035 states (Merilehto 2026a, Tables 3 and 6)
C_N35 = {"Base": (20, 80, 180), "Accelerated": (450, 1100, 2000), "High": (1500, 3000, 6000)}
S35 = {"Base": (.25, .32, .40), "Accelerated": (.30, .36, .40), "High": (.40, .40, .42)}
R = {"Base": (.70, .80, .88), "Accelerated": (.65, .78, .88), "High": (.60, .75, .88)}
L = {"Base": (.80, .84, .88), "Accelerated": (.74, .82, .88), "High": (.72, .82, .88)}
M = {"Base": (.75, .65, .55), "Accelerated": (.55, .45, .35), "High": (.45, .35, .25)}
# Original 2030/2035 inputs and results (Merilehto 2026a supporting materials, Zenodo 10.5281/zenodo.21966116)
INPUTS = OUT / "inputs"
KEY = {"Base": "Base", "Accelerated": "Accelerated", "High": "High"}


def load_original():
    """Return {(horizon, case, state): dict(cn, s, r, l, m)} from the original parameter file."""
    out = {}
    with open(INPUTS / "scenario_parameters_2030_2035.csv", newline="", encoding="utf-8") as f:
        for r_ in csv.DictReader(f):
            case = r_["scenario"].split(":")[0].strip()
            for st in STATES:
                out[(int(r_["horizon"]), case, st)] = dict(
                    cn=float(r_[f"nordic_connected_mw_{st}"]), s=float(r_[f"finland_capture_{st}"]),
                    r=float(r_[f"peak_to_connected_{st}"]), l=float(r_[f"operating_load_factor_{st}"]),
                    m=float(r_[f"minimum_stable_fraction_{st}"]))
    return out


ORIG = load_original()
# The hard-coded 2035 constants above must equal the original file exactly
for _c in CASES:
    for _i, _st in enumerate(STATES):
        _o = ORIG[(2035, _c, _st)]
        assert (_o["cn"], _o["s"], _o["r"], _o["l"], _o["m"]) == (C_N35[_c][_i], S35[_c][_i], R[_c][_i], L[_c][_i], M[_c][_i]), (_c, _st)

# Post-2035 construction settings
TARGET = {"Base": (200, 800, 2000), "Accelerated": (2000, 6000, 12000), "High": (6000, 15000, 30000)}
BUILD = {"Base": (30, 120, 300), "Accelerated": (250, 750, 1500), "High": (800, 2000, 4000)}
BUDGET = {"Base": (150, 400, 800), "Accelerated": (1000, 2500, 5000), "High": (3000, 6000, 8000)}
S50 = {"Base": (.20, .30, .40), "Accelerated": (.25, .35, .45), "High": (.30, .40, .50)}
LAG = (4, 3, 2)          # commissioning lag, years (low/central/high)
RET = (.05, .04, .03)    # annual capacity retirement fraction
MID = {"Base": 2044, "Accelerated": 2042, "High": 2040}
WIDTH = 4.0              # logistic scale (years)


@dataclass(frozen=True)
class P:
    case: str
    state: str
    cn35: float; s35: float; r: float; l: float; m: float
    target: float; build: float; budget: float; s50: float
    lag: int; ret: float; mid: float; width: float = WIDTH
    seed: bool = True    # orders already in flight at 2035
    delay: float = 0.0   # shifts the whole post-2035 transition later without renormalising it to 2050
    stop_orders: bool = False  # no new orders after 2035 (pipeline in flight is still delivered)


def params(case: str, state: str, **kw) -> P:
    i = STATES.index(state)
    p = P(case, state, C_N35[case][i], S35[case][i], R[case][i], L[case][i], M[case][i],
          TARGET[case][i], BUILD[case][i], BUDGET[case][i], S50[case][i], LAG[i], RET[i], MID[case])
    return replace(p, **kw)


def S(t: float, p: P) -> float:
    """Normalised logistic transition: S(2035)=0, S(2050)=1.
    With delay > 0 the whole transition is shifted later in calendar time, so the target is
    reached delay years after 2050 rather than being renormalised back to 2050."""
    te = min(max(t - p.delay, Y0), Y1)
    f = lambda x: 1 / (1 + math.exp(-(x - p.mid) / p.width))
    return (f(te) - f(Y0)) / (f(Y1) - f(Y0))


def run(p: P) -> list[dict]:
    yrs = list(range(Y0, Y1 + 1))
    D = {t: p.cn35 + (p.target - p.cn35) * S(t if p.delay else min(t, Y1), p) for t in range(Y0, Y1 + p.lag + 1)}
    C = {Y0: p.cn35}
    arrivals = {t: 0.0 for t in range(Y0 + 1, Y1 + p.lag + 1)}
    k = 1 - p.ret
    # Orders placed before 2035 that arrive in 2036..2035+lag (perfect anticipation, build-capped)
    if p.seed:
        # placed before 2035 against the undelayed path, so a later-recognised delay does not cancel them
        p0 = replace(p, delay=0.0)
        D0 = {t: p.cn35 + (p.target - p.cn35) * S(t, p0) for t in range(Y0, Y0 + p.lag + 1)}
        c = p.cn35
        for t in range(Y0 + 1, Y0 + p.lag + 1):
            a = min(p.build, max(0.0, D0[t] - k * c))
            arrivals[t] = a
            c = k * c + a
    for t in yrs:
        if t > Y0:
            C[t] = k * C[t - 1] + arrivals[t]
        # order placed in year t arrives at t+lag
        ta = t + p.lag
        if p.seed and ta <= Y0 + p.lag:   # already covered by orders in flight at 2035
            continue
        if p.stop_orders:
            continue
        proj = C[t] * k ** p.lag + sum(arrivals[j] * k ** (ta - j) for j in range(t + 1, ta))
        arrivals[ta] = arrivals.get(ta, 0) + min(p.build, max(0.0, D[ta] - proj))
    rows = []
    for t in yrs:
        st = S(t, p)
        s_req = p.s35 + (p.s50 - p.s35) * st
        c_fi35 = p.cn35 * p.s35
        B = c_fi35 + (p.budget - c_fi35) * st
        cfi_unc = s_req * C[t]
        cfi = min(cfi_unc, B) if t > Y0 else c_fi35
        peak = cfi * p.r
        rows.append(dict(case=p.case, state=p.state, year=t, D_nordic=D[t], C_nordic=C[t],
                         s_req=s_req, budget=B, C_fi_unconstrained=cfi_unc, C_fi=cfi,
                         s_eff=cfi / C[t] if C[t] else 0, binding=cfi_unc > B + 1e-9 and t > Y0,
                         peak=peak, floor=peak * p.m, twh=peak * p.l * H / 1e6))
    return rows


def ops(cfi, r, l, m):
    peak = cfi * r
    return dict(C=cfi, peak=peak, floor=peak * m, span=peak * (1 - m), twh=peak * l * H / 1e6)


def check_invariants(p: P):
    assert 0 <= p.m <= p.l <= 1 and 0 <= p.r <= 1 and 0 <= p.s35 <= 1 and 0 <= p.s50 <= 1, p


def end(p: P) -> dict:
    return run(p)[-1]


# ---------------------------------------------------------------- outputs
def write_csv(name, rows):
    OUT.mkdir(exist_ok=True, parents=True)
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    res = {}
    paths = []
    for c, s in itertools.product(CASES, STATES):
        p = params(c, s); check_invariants(p)
        rows = run(p); paths += rows
        res[(c, s)] = rows
        # capacity never exceeds target materially, Finnish never exceeds budget
        for r_ in rows:
            assert r_["C_fi"] <= r_["budget"] + 1e-6 or r_["year"] == Y0
    write_csv("paths.csv", paths)

    # 2035 retained table + 2050 results
    # Reproduce the original 2030/2035 results file exactly
    with open(INPUTS / "scenario_results_2030_2035_original.csv", newline="", encoding="utf-8") as f:
        for o in csv.DictReader(f):
            case = o["scenario"].split(":")[0].strip()
            q = ORIG[(int(o["horizon"]), case, o["state"])]
            x = ops(q["cn"] * q["s"], q["r"], q["l"], q["m"])
            for k_, ok in [("C", "finland_connected_mw"), ("peak", "realised_peak_mw"),
                           ("floor", "minimum_stable_import_mw"), ("twh", "annual_electricity_twh")]:
                assert abs(x[k_] - float(o[ok])) < 1e-6, (o["horizon"], case, o["state"], k_)
    tab = []
    for c, s in itertools.product(CASES, STATES):
        p = params(c, s)
        q30 = ORIG[(2030, c, s)]
        r30 = ops(q30["cn"] * q30["s"], q30["r"], q30["l"], q30["m"])
        r35 = ops(p.cn35 * p.s35, p.r, p.l, p.m)
        e = res[(c, s)][-1]
        r40 = [x for x in res[(c, s)] if x["year"] == 2040][0]
        r45 = [x for x in res[(c, s)] if x["year"] == 2045][0]
        tab.append(dict(case=c, state=s, CN30=q30["cn"], C30=r30["C"], peak30=r30["peak"], floor30=r30["floor"],
                        twh30=r30["twh"], C35=r35["C"], peak35=r35["peak"], floor35=r35["floor"], twh35=r35["twh"],
                        C40=r40["C_fi"], twh40=r40["twh"], C45=r45["C_fi"], twh45=r45["twh"],
                        CN50=e["C_nordic"], s_req50=e["s_req"], s_eff50=e["s_eff"], budget50=e["budget"],
                        binding50=e["binding"], C50=e["C_fi"], peak50=e["peak"], floor50=e["floor"],
                        span50=e["peak"] - e["floor"], twh50=e["twh"]))
    write_csv("results.csv", tab)

    # Unseeded pipeline (the earlier draft's convention) for comparison
    unseeded = []
    for c in CASES:
        a = run(params(c, "central", seed=False)); b = res[(c, "central")]
        dips = [x["year"] for i, x in enumerate(a[1:], 1) if x["C_fi"] < a[i - 1]["C_fi"] - 1e-6]
        unseeded.append(dict(case=c, min_C_2036_2038_unseeded=min(x["C_fi"] for x in a[1:4]),
                             min_C_2036_2038_seeded=min(x["C_fi"] for x in b[1:4]),
                             C35=a[0]["C_fi"], years_declining_unseeded=" ".join(map(str, dips)),
                             C50_unseeded=a[-1]["C_fi"], C50_seeded=b[-1]["C_fi"]))
    write_csv("pipeline_seeding.csv", unseeded)

    # Sticky-floor sensitivity (2050 High upper and central)
    sticky = []
    for s in ["central", "high"]:
        e = res[("High", s)][-1]; p = params("High", s)
        for lab, m in [("paired", p.m), ("sticky", .78)]:
            o = ops(e["C_fi"], p.r, p.l, m)
            sticky.append(dict(state=s, variant=lab, m=m, **o))
    write_csv("sticky.csv", sticky)

    # Recovery arithmetic with connection headroom (4 h event, 50% energy rebound)
    rec = []
    for st in sticky:
        D_ = st["span"]; dt = 4; rho = .5
        E = D_ * dt / 1e3  # GWh
        p = params("High", st["state"])
        head_peak = st["C"] - st["peak"]                       # headroom above realised peak
        head_mean = st["C"] - st["peak"] * p.l                 # headroom above annual-mean import
        rec.append(dict(state=st["state"], variant=st["variant"], span=D_, gwh_not_served=E,
                        rebound_gwh=rho * E, nominal_4h_rebound_mw=rho * E * 1e3 / 4,
                        headroom_above_peak=head_peak, headroom_above_mean=head_mean,
                        hours_at_peak_headroom=rho * E * 1e3 / head_peak,
                        hours_at_mean_headroom=rho * E * 1e3 / head_mean,
                        fits_4h_at_mean=rho * E * 1e3 / 4 <= head_mean))
    write_csv("recovery.csv", rec)

    # Operating-parameter drift sensitivity at 2050 central states
    drift = []
    for c in CASES:
        e = res[(c, "central")][-1]; p = params(c, "central")
        variants = {
            "retained": (p.r, p.l, p.m),
            "flexible maturation (m-10pp)": (p.r, p.l, max(0, p.m - .10)),
            "sticky maturation (m=ell-0.06)": (p.r, p.l, p.l - .06),
            "dense utilisation (r,ell=0.88)": (.88, .88, p.m),
            "headroom-heavy (r-0.10)": (p.r - .10, p.l, p.m),
        }
        for k_, (r_, l_, m_) in variants.items():
            assert 0 <= m_ <= l_ <= 1
            o = ops(e["C_fi"], r_, l_, m_)
            drift.append(dict(case=c, variant=k_, r=r_, l=l_, m=m_, **o))
    write_csv("drift.csv", drift)

    # One-way tornado on 2050 High central annual energy
    base = params("High", "central"); e0 = end(base)["twh"]
    torn = []
    def tw(label, lo_p, hi_p, lo_lab, hi_lab):
        lo = end(lo_p)["twh"]; hi = end(hi_p)["twh"]
        torn.append(dict(param=label, low_setting=lo_lab, high_setting=hi_lab, twh_low=lo, twh_high=hi, twh_central=e0))
    tw("Nordic 2050 target", replace(base, target=base.target * .6), replace(base, target=base.target * 1.4), "9 GW", "21 GW")
    tw("Requested FI share 2050", replace(base, s50=.30), replace(base, s50=.50), "30%", "50%")
    tw("FI connection budget", replace(base, budget=4000), replace(base, budget=8000), "4 GW", "8 GW")
    tw("Peak-to-connected $r$", replace(base, r=.65), replace(base, r=.85), "0.65", "0.85")
    tw("Operating load factor $\\ell$", replace(base, l=.72), replace(base, l=.88), "0.72", "0.88")
    tw("Build limit (Nordic)", replace(base, build=1000), replace(base, build=3000), "1.0 GW/yr", "3.0 GW/yr")
    tw("Deployment delay (shift)", replace(base, delay=5), replace(base, delay=-3), "+5 yr", "3 yr earlier")
    tw("Commissioning lag", replace(base, lag=5), replace(base, lag=2), "5 yr", "2 yr")
    write_csv("tornado.csv", torn)

    # Timing sensitivity: midpoint +/-3 years, all central states
    timing = []
    for c in CASES:
        for dm in (-3, 0, 3):
            rows = run(params(c, "central", mid=MID[c] + dm))
            g = {x["year"]: x for x in rows}
            timing.append(dict(case=c, midpoint=MID[c] + dm, C40=g[2040]["C_fi"], C45=g[2045]["C_fi"],
                               C50=g[2050]["C_fi"], twh45=g[2045]["twh"], twh50=g[2050]["twh"]))
    write_csv("timing.csv", timing)

    # Stalled construction, central states. (a) cancel: no deliveries after 2035, pipeline cancelled;
    # (b) stop: orders already in flight at 2035 are delivered, no new orders thereafter.
    stalled = []
    for c in CASES:
        p = params(c, "central")
        cn_cancel = p.cn35 * (1 - p.ret) ** 15
        o_cancel = ops(cn_cancel * p.s50, p.r, p.l, p.m)
        e_stop = end(replace(p, stop_orders=True))
        stalled.append(dict(case=c, CN50_cancel=cn_cancel, C50_cancel=o_cancel["C"], twh50_cancel=o_cancel["twh"],
                            CN50_stop=e_stop["C_nordic"], C50_stop=e_stop["C_fi"], twh50_stop=e_stop["twh"]))
    write_csv("stalled.csv", stalled)

    # Real delay: shift the whole post-2035 transition later (not renormalised to 2050)
    delay = []
    for c in CASES:
        for d in (0, 3, 5, 10):
            g = {x["year"]: x for x in run(params(c, "central", delay=d))}
            delay.append(dict(case=c, delay=d, C40=g[2040]["C_fi"], C45=g[2045]["C_fi"], C50=g[2050]["C_fi"],
                              twh50=g[2050]["twh"], CN50=g[2050]["C_nordic"]))
    write_csv("delay.csv", delay)

    # Hosting share sensitivity at central Nordic 2050 states
    host = []
    for c in CASES:
        e = res[(c, "central")][-1]; p = params(c, "central")
        row = dict(case=c, CN50=e["C_nordic"], budget=p.budget)
        for sh in (.1, .2, .3, .4, .5):
            row[f"s{int(sh*100)}"] = min(sh * e["C_nordic"], p.budget)
        host.append(row)
    write_csv("hosting.csv", host)

    # Top-down Nordic check
    td = []
    for c, s in itertools.product(CASES, STATES):
        p = params(c, s); cn = res[(c, s)][-1]["C_nordic"]
        twh = cn * p.r * p.l * H / 1e6
        td.append(dict(case=c, state=s, CN50=cn, nordic_twh=twh,
                       x_FI2025=twh / 84.5, share_IEA2030=twh / 950, share_IEA2035=twh / 1200))
    write_csv("topdown.csv", td)

    # Materiality vs national denominators
    mat = []
    for t in tab:
        mat.append(dict(case=t["case"], state=t["state"], twh50=t["twh50"],
                        vs2035_lo=t["twh50"] / 162, vs2035_hi=t["twh50"] / 110,
                        vs2045_lo=t["twh50"] / 359, vs2045_hi=t["twh50"] / 131,
                        vs_dc_pipeline_28=t["twh50"] / 28, peak_vs_record=t["peak50"] / 15553,
                        C_vs_dc_signed_5GW=t["C50"] / 5000))
    write_csv("materiality.csv", mat)

    # Intensity decomposition check: present-system and FTQC anchors
    intensity = []
    for c in CASES:
        e = res[(c, "central")][-1]
        intensity.append(dict(case=c, C50=e["C_fi"],
                              present_system_equiv_20kW=e["C_fi"] * 1e3 / 20,
                              Mqubit_at_100kW_per_M=e["C_fi"] * 1e3 / 100))
    write_csv("intensity.csv", intensity)

    print(json.dumps({k: v for k, v in [("results", tab)]}, indent=0, default=float)[:200])


if __name__ == "__main__":
    main()
