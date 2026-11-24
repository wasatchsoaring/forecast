"""Turn HRRR columns into soaring numbers and day ratings.

Works the same on history (analyses) and forecasts, so the percentiles compare like with like.

Per hour, per site:
  top_m     thermal top (m MSL): boundary layer top, capped at cloud base when cumulus form
  above_ft  usable height above launch, in feet
  wstar     convective velocity scale W* (m/s), the usual RASP measure of thermal strength
  wind_*    wind at launch height, in the thermal layer, and at the top (mph, deg)
  flyable   launch wind inside the club limits for at least one launch, and no storm
  soarable  flyable and either thermals worth flying (thermal sites) or ridge wind in range (ridge sites)
"""
import json
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

MT = ZoneInfo("America/Denver")
MS_TO_MPH = 2.23694
M_TO_FT = 3.28084
G, CP, RD = 9.81, 1005.0, 287.0
CLASS_A_M = 17999 / 3.28084
LEVELS = [850, 700, 500]   # the levels live forecasts carry, so history and forecasts use the same profile

SITES = {s["id"]: s for s in json.load(open("sites.json"))}
GRID = {p["id"]: p for p in json.load(open("data/gridpoints.json"))}


def in_range(deg, rng):
    """Is direction deg inside [from, to], going clockwise (handles wrap through north)?"""
    if rng is None:
        return np.ones_like(deg, dtype=bool)
    a, b = rng[0] % 360, rng[1] % 360
    d = deg % 360
    return (d >= a) & (d <= b) if a <= b else (d >= a) | (d <= b)


def wind_dir(u, v):
    return (np.degrees(np.arctan2(-u, -v)) + 360) % 360


def profile_wind(df, z_m, terrain):
    """Interpolate the wind to heights z_m (array, m MSL) from 10 m, 80 m and the pressure levels."""
    n = len(df)
    zs = [np.full(n, terrain + 10.0), np.full(n, terrain + 80.0)]
    us = [df["U10"].values, df["U80"].values]
    vs = [df["V10"].values, df["V80"].values]
    for p in sorted(LEVELS, reverse=True):          # bottom up
        z = df[f"Z{p}"].values.astype(float)
        ok = z > terrain + 150                       # levels below or near the ground are fake
        zs.append(np.where(ok, z, np.nan))
        us.append(np.where(ok, df[f"U{p}"].values, np.nan))
        vs.append(np.where(ok, df[f"V{p}"].values, np.nan))
    Z, U, V = np.vstack(zs).T, np.vstack(us).T, np.vstack(vs).T
    u_out, v_out = np.full(n, np.nan), np.full(n, np.nan)
    for i in range(n):
        m = ~np.isnan(Z[i]) & ~np.isnan(U[i])
        if m.sum() < 2 or np.isnan(z_m[i]):
            continue
        o = np.argsort(Z[i][m])
        u_out[i] = np.interp(z_m[i], Z[i][m][o], U[i][m][o])
        v_out[i] = np.interp(z_m[i], Z[i][m][o], V[i][m][o])
    return u_out, v_out


def hourly(df, site_id):
    """df: rows for one site, HRRR columns plus a 'time' column in UTC."""
    s, g = SITES[site_id], GRID[site_id]
    terrain = g["terrain_m"]
    launch = (s.get("launch_ft") or terrain * M_TO_FT) / M_TO_FT
    out = pd.DataFrame({"time": df["time"].values})
    out["local"] = pd.to_datetime(out["time"]).dt.tz_localize("UTC").dt.tz_convert(MT)

    hpbl = df["HPBL"].values.astype(float)
    shf = np.clip(df["SHTFL"].values.astype(float), 0, None)
    t2 = df["T2"].values.astype(float)
    td2 = df["TD2"].values.astype(float)
    rho = df["PSFC"].values.astype(float) / (RD * t2)
    wstar = np.cbrt(G / t2 * shf / (rho * CP) * hpbl)
    bl_top = terrain + hpbl
    cloud_base = terrain + 125.0 * np.clip(t2 - td2, 0, None)     # Espy's rule for cumulus base
    cumulus = bl_top > cloud_base
    top = np.where(cumulus, cloud_base, bl_top)
    out["wstar"] = np.round(wstar, 2)
    out["top_m"] = np.round(top)
    usable = np.minimum(top, CLASS_A_M)                              # no climbing into Class A airspace
    out["above_ft"] = np.round((usable - launch) * M_TO_FT)
    out["cloudbase_ft"] = np.round(cloud_base * M_TO_FT)
    out["cumulus"] = cumulus

    ul, vl = profile_wind(df, np.full(len(df), max(launch, terrain + 10.0)), terrain)
    out["wind_mph"] = np.round(np.hypot(ul, vl) * MS_TO_MPH, 1)
    out["wind_dir"] = np.round(wind_dir(ul, vl))
    mid = (launch + np.maximum(top, launch)) / 2
    um, vm = profile_wind(df, mid, terrain)
    out["bl_wind_mph"] = np.round(np.hypot(um, vm) * MS_TO_MPH, 1)
    out["bl_wind_dir"] = np.round(wind_dir(um, vm))
    ut, vt = profile_wind(df, np.maximum(top, launch), terrain)
    out["top_wind_mph"] = np.round(np.hypot(ut, vt) * MS_TO_MPH, 1)
    out["gust_mph"] = np.round(df["GUST"].values.astype(float) * MS_TO_MPH, 1)

    refc = df["REFC"].values.astype(float)
    cape = df["CAPE"].values.astype(float)
    out["storm"] = (refc >= 35) | ((refc >= 25) & (cape >= 500))
    out["rain"] = refc >= 20
    out["cape"] = np.round(cape)

    spd, dirn = out["wind_mph"].values, out["wind_dir"].values
    best_launch = np.array([""] * len(df), dtype=object)
    ok_any = np.zeros(len(df), dtype=bool)
    for L in s["launches"]:
        ok = in_range(dirn, L["ok"]) & (spd >= L["min"]) & (spd <= L["max"])
        if s["type"] == "ridge":
            ok &= spd >= max(L["min"], L["ideal_mph"][0] - 3)
        best_launch = np.where(ok & (best_launch == ""), L["name"], best_launch)
        ok_any |= ok
    out["launch"] = best_launch
    out["flyable"] = ok_any & ~out["storm"].values & ~out["rain"].values

    if s["type"] == "ridge":
        out["soarable"] = out["flyable"]
    else:
        out["soarable"] = out["flyable"] & (out["above_ft"].values >= 1000) & (wstar >= 1.0)
    # one number for "how good is this hour": thousands of feet above launch times thermal strength
    out["score"] = np.where(out["soarable"], np.clip(out["above_ft"].values, 0, None) / 1000 * np.clip(wstar, 0, 4), 0.0)
    if s["type"] == "ridge":
        lo, hi = s["launches"][0]["ideal_mph"]
        closeness = 1 - np.clip(np.maximum(lo - spd, spd - hi), 0, 10) / 10
        out["score"] = np.where(out["soarable"], closeness, 0.0)
    return out


def daily(h, site_id):
    """Summarise hours into local days (8 am to 8 pm Mountain)."""
    s = SITES[site_id]
    h = h[(h["local"].dt.hour >= 8) & (h["local"].dt.hour <= 20)].copy()
    h["date"] = h["local"].dt.date
    rows = []
    for d, x in h.groupby("date"):
        good = x[x["soarable"]]
        row = {"date": str(d), "hours": int(len(x))}
        if s["type"] == "ridge":
            row["score"] = float(good["score"].sum())          # soarable hours, weighted by how close to ideal
        else:
            row["score"] = float(x["score"].max()) if len(x) else 0.0
        row["soarable_hours"] = int(len(good))
        if len(good):
            row["first"] = good["local"].min().strftime("%-I %p").lower()
            row["last"] = (good["local"].max() + timedelta(hours=1)).strftime("%-I %p").lower()
            best = good.loc[good["score"].idxmax()]
            row.update(best_hour=best["local"].strftime("%-I %p").lower(), top_ft=int(best["top_m"] * M_TO_FT),
                       above_ft=int(best["above_ft"]), wstar=float(best["wstar"]),
                       wind=f"{int(best['wind_mph'])} mph from {int(best['wind_dir'])}°", launch=best["launch"])
        row["max_top_ft"] = int(x["top_m"].max() * M_TO_FT) if x["top_m"].notna().any() else None
        row["storm"] = bool(x["storm"].any())
        rows.append(row)
    return rows


def percentile(score, history_scores):
    """Share of history days that scored lower, 0 to 100."""
    hs = np.asarray(history_scores, dtype=float)
    if len(hs) == 0:
        return None
    return float(np.round(100 * ((hs < score).sum() + 0.5 * (hs == score).sum()) / len(hs), 1))


def label(pct, score):
    if score <= 0:
        return "not soarable"
    if pct >= 95:
        return "Top 5%"
    if pct >= 75:
        return "Top 25%"
    if pct >= 50:
        return "Better than usual"
    return "Soarable"
