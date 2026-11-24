"""Rate the latest forecast against each site's history and write the page to site/."""
import json
import os
import sys
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import rate  # noqa: E402

WINDOW_DAYS = 21


def doy_distance(a, b):
    d = abs(a - b)
    return np.minimum(d, 366 - d)


def main():
    fc = pd.read_parquet("data/forecast.parquet")
    fc["site"] = fc["site"].astype(str)
    meta = json.load(open("data/forecast_meta.json"))
    climo = pd.read_parquet("data/climo.parquet") if os.path.exists("data/climo.parquet") else pd.DataFrame(columns=["site", "date", "score"])
    climo["doy"] = pd.to_datetime(climo["date"]).dt.dayofyear
    hist_from = str(climo["date"].min()) if len(climo) else None
    hist_to = str(climo["date"].max()) if len(climo) else None

    sites_out = []
    for sid, s in rate.SITES.items():
        x = fc[fc["site"] == sid].sort_values("time").reset_index(drop=True)
        if x.empty:
            continue
        h = rate.hourly(x, sid)
        days = [d for d in rate.daily(h, sid) if d["hours"] >= 6]
        hc = climo[climo["site"] == sid]
        for d in days:
            doy = date.fromisoformat(d["date"]).timetuple().tm_yday
            hist = hc[doy_distance(hc["doy"].values, doy) <= WINDOW_DAYS]["score"].values
            d["pct"] = rate.percentile(d["score"], hist)
            d["n_hist"] = int(len(hist))
            d["label"] = rate.label(d["pct"] or 0, d["score"])
            d["share_soarable"] = float(np.round(100 * (hist > 0).mean())) if len(hist) else None
        hours = {}
        hh = h[(h["local"].dt.hour >= 7) & (h["local"].dt.hour <= 20)]
        for _, r in hh.iterrows():
            key = r["local"].date().isoformat()
            hours.setdefault(key, []).append({
                "h": r["local"].strftime("%-I%p").lower(),
                "wind": None if np.isnan(r["wind_mph"]) else int(round(r["wind_mph"])),
                "dir": None if np.isnan(r["wind_dir"]) else int(r["wind_dir"]),
                "bl": None if np.isnan(r["bl_wind_mph"]) else int(round(r["bl_wind_mph"])),
                "top": None if np.isnan(r["top_m"]) else int(round(r["top_m"] * rate.M_TO_FT, -2)),
                "above": None if np.isnan(r["above_ft"]) else int(round(r["above_ft"], -2)),
                "w": None if np.isnan(r["wstar"]) else round(float(r["wstar"]), 1),
                "base": None if np.isnan(r["cloudbase_ft"]) else int(round(r["cloudbase_ft"], -2)),
                "cu": bool(r["cumulus"]),
                "fly": bool(r["flyable"]),
                "soar": bool(r["soarable"]),
                "storm": bool(r["storm"]),
                "rain": bool(r["rain"]),
                "launch": r["launch"],
            })
        sites_out.append({
            "id": sid, "name": s["name"], "area": s["area"], "type": s["type"], "best": s.get("best", ""),
            "src": s.get("src", ""), "launch_ft": s.get("launch_ft"),
            "launches": [{"name": L["name"], "ok": L["ok"], "min": L["min"], "max": L["max"], "ideal": L["ideal_mph"]} for L in s["launches"]],
            "days": days, "hours": hours,
        })

    data = {
        "built": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "run": meta, "history": {"from": hist_from, "to": hist_to, "window_days": WINDOW_DAYS},
        "sites": sites_out,
    }
    os.makedirs("site", exist_ok=True)
    json.dump(data, open("site/forecast.json", "w"), separators=(",", ":"))
    tpl = open(os.path.join(os.path.dirname(__file__), "page.html")).read()
    open("site/index.html", "w").write(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))))
    print("built", len(sites_out), "sites,", sum(len(s["days"]) for s in sites_out), "site-days")


if __name__ == "__main__":
    main()
