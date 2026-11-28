"""Rate the latest forecast against each site's history and write the page to site/."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import rate  # noqa: E402

WINDOW_DAYS = 21
REGIONS = [
    ("Point of the Mountain", ["north-side", "south-side"]),
    ("Salt Lake & Davis", ["burn-side", "grandeur", "grandeur-peak", "wire", "cherry", "the-v", "francis-peak"]),
    ("Utah County", ["inspo", "mahogany"]),
    ("Park City & Kamas", ["jupiter", "oakley-ridge"]),
    ("Juab & Sanpete", ["horse-heaven", "wales"]),
    ("Monroe & Marysvale", ["monroe-peak", "cove", "poverty-ridge", "edna", "junction"]),
    ("Moab", ["castleton-tower", "kens-lake"]),
]
REFERENCE = [("Salt Lake Valley", "north-side"), ("Utah Valley", "inspo"), ("Sevier Valley", "poverty-ridge"), ("Moab", "kens-lake")]


def doy_distance(a, b):
    d = abs(a - b)
    return np.minimum(d, 366 - d)


def pct_of(value, hist):
    if value is None or np.isnan(value) or len(hist) == 0:
        return None
    return float(np.round(100 * ((hist < value).sum() + 0.5 * (hist == value).sum()) / len(hist), 1))


def promote(level, soar_above, hist):
    """Strong-thermal hours become Top 25% / Top 5% days when their soarable height beats that share of history days."""
    if level < 2:
        return level, None
    p = pct_of(soar_above, hist)
    if p is None:
        return level, None
    return (4 if p >= 95 else 3 if p >= 75 else 2), p


def clock(dt):
    return dt.strftime("%-I:%M %p").lower() if dt else None


def nz(v, digits=None):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), digits) if digits is not None else int(round(float(v)))


def main():
    fc = pd.read_parquet("data/forecast.parquet")
    fc["site"] = fc["site"].astype(str)
    meta = json.load(open("data/forecast_meta.json"))
    climo = pd.read_parquet("data/climo.parquet") if os.path.exists("data/climo.parquet") else pd.DataFrame(columns=["site", "date", "best_soar_above_ft"])
    if "best_soar_above_ft" not in climo.columns:      # older climo file, rebuilt by the daily job
        climo = pd.DataFrame(columns=["site", "date", "best_soar_above_ft"])
    climo["doy"] = pd.to_datetime(climo["date"]).dt.dayofyear

    region_of = {sid: r for r, ids in REGIONS for sid in ids}
    sites_out, all_dates, ref = [], set(), {}
    for sid, s in rate.SITES.items():
        x = fc[fc["site"] == sid].sort_values("time").reset_index(drop=True)
        if x.empty:
            continue
        h = rate.hourly(x, sid)
        h["date"] = h["local"].dt.date.astype(str)
        h["hour"] = h["local"].dt.hour
        hc = climo[climo["site"] == sid]
        days, hours = {}, {}
        for d, xd in h.groupby("date"):
            doy = date.fromisoformat(d).timetuple().tm_yday
            hist = hc[doy_distance(hc["doy"].values, doy) <= WINDOW_DAYS]["best_soar_above_ft"].dropna().values.astype(float)
            rows = []
            for _, r in xd.iterrows():
                lv, p = promote(int(r["level"]), r["soar_above_ft"], hist)
                rows.append({
                    "h": int(r["hour"]), "lv": lv, "pct": p,
                    "wind": nz(r["wind_mph"]), "dir": nz(r["wind_dir"]),
                    "bl": nz(r["bl_wind_mph"]), "bldir": nz(r["bl_wind_dir"]),
                    "soar": nz(r["soar_top_m"] * rate.M_TO_FT if not np.isnan(r["soar_top_m"]) else None),
                    "over": nz(r["soar_above_ft"]),
                    "bltop": nz(r["top_m"] * rate.M_TO_FT if not np.isnan(r["top_m"]) else None),
                    "w": nz(r["wstar"], 1), "cu": bool(r["cumulus"]), "base": nz(r["cloudbase_ft"]),
                    "cloud": nz(r["cloud_pct"]), "t": nz(r["t_f"]), "td": nz(r["td_f"]),
                    "storm": bool(r["storm"]), "rain": bool(r["rain"]), "dark": not bool(r["daylight"]),
                    "launch": r["launch"],
                })
            day_rows = [r for r in rows if 8 <= r["h"] <= 17]
            slots = {str(r["h"]): r for r in rows if r["h"] in rate.SLOT_HOURS}
            if not slots:
                continue
            all_dates.add(d)
            best_over = max([r["over"] for r in day_rows if r["over"] is not None], default=None)
            tops = max([r["soar"] for r in day_rows if r["soar"] is not None], default=None)
            bltop = max([r["bltop"] for r in day_rows if r["bltop"] is not None], default=None)
            best_lv = max(v["lv"] for v in slots.values())
            best_hr = max(day_rows or list(slots.values()), key=lambda v: (v["lv"], v["soar"] or 0))
            bar = best_hr["soar"] if best_hr["lv"] >= 0 else tops
            rise, sset = rate.sun_times(d, s["lat"], s["lon"])
            days[d] = {
                "sun": {"rise": clock(rise), "set": clock(sset),
                        "tw_start": clock(rise - timedelta(minutes=30)) if rise else None,
                        "tw_end": clock(sset + timedelta(minutes=30)) if sset else None},
                "slots": {k: {"lv": v["lv"], "wind": v["wind"], "dir": v["dir"], "dark": v["dark"], "storm": v["storm"] or v["rain"]} for k, v in slots.items()},
                "best": best_lv,
                "tops": tops, "bltop": bltop, "bar": bar, "bar_lv": best_hr["lv"], "best_over": best_over, "pct": pct_of(best_over, hist) if best_over is not None else None,
                "n_hist": int(len(hist)),
            }
            hours[d] = [r for r in rows if not r["dark"] or r["h"] in rate.SLOT_HOURS]
            for name, rid in REFERENCE:
                if rid == sid:
                    r14 = [r for r in rows if r["h"] == 14]
                    if r14 and r14[0]["bltop"]:
                        ref.setdefault(d, []).append({"name": name, "ft": r14[0]["bltop"]})
        launch_ft = s.get("launch_ft") or rate.GRID[sid]["terrain_m"] * rate.M_TO_FT
        ref_dates = sorted(days)
        p75 = p95 = None
        if ref_dates and len(hc):
            doy0 = date.fromisoformat(ref_dates[0]).timetuple().tm_yday
            hv = hc[doy_distance(hc["doy"].values, doy0) <= WINDOW_DAYS]["best_soar_above_ft"].dropna().values.astype(float)
            if len(hv):
                p75 = int(round(launch_ft + np.percentile(hv, 75)))
                p95 = int(round(launch_ft + np.percentile(hv, 95)))
        sites_out.append({
            "id": sid, "name": s["name"], "area": s["area"], "region": region_of.get(sid, "Other"), "type": s["type"], "hike": bool(s.get("hike")),
            "best_time": s.get("best", ""), "src": s.get("src", ""), "launch_ft": s.get("launch_ft"),
            "lat": s["lat"], "lon": s["lon"],
            "launches": [{"name": L["name"], "ok": L["ok"], "min": L["min"], "max": L["max"], "ideal": L["ideal_mph"]} for L in s["launches"]],
            "days": days, "hours": hours, "p75": p75, "p95": p95,
        })

    data = {
        "built": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "run": meta,
        "history": {"from": str(climo["date"].min()) if len(climo) else None, "to": str(climo["date"].max()) if len(climo) else None,
                    "window_days": WINDOW_DAYS},
        "slots": list(rate.SLOT_HOURS), "dates": sorted(all_dates), "regions": [r for r, _ in REGIONS],
        "reference": ref, "sites": sites_out,
    }
    os.makedirs("site", exist_ok=True)
    json.dump(data, open("site/forecast.json", "w"), separators=(",", ":"))
    tpl = open(os.path.join(os.path.dirname(__file__), "page.html")).read()
    open("site/index.html", "w").write(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))))
    print("built", len(sites_out), "sites,", len(all_dates), "days")


if __name__ == "__main__":
    main()
