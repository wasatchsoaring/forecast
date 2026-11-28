"""Turn HRRR columns into soaring numbers and Air School style ratings.

Works the same on history (analyses) and forecasts, so the percentiles compare like with like.

Per hour, per site:
  top_m          boundary layer top (m MSL), capped at cumulus base
  soar_top_m     soarable height: where an average thermal core fades to about 1 m/s, capped at cumulus base
  soar_above_ft  soarable height over launch in feet, capped at 18,000 ft MSL (Class A)
  wstar          W*, average thermal strength (m/s), the usual RASP number
  wind_*         wind at launch height, in the thermal layer, and at the top (mph, deg)
  flyable        daylight, launch wind inside the club limits for at least one launch, no storm or rain
  level          -1 not flyable, 0 marginal, 1 soarable, 2 strong thermals (3 = Top 25% day, 4 = Top 5% day, set later)
"""
import json
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

MT = ZoneInfo("America/Denver")
MS_TO_MPH = 2.23694
M_TO_FT = 3.28084
G, CP, RD = 9.81, 1005.0, 287.0
CLASS_A_M = 17999 / 3.28084
SUN_RISE_DEG = -0.833    # sun's upper edge on a sea-level horizon, with refraction: official sunrise and sunset
SLOT_HOURS = (8, 11, 14, 17)
SOARABLE_FT = 500        # soarable height at least this far above launch
STRONG_W = 3.0           # Air School's "strong thermals": average thermals 3 m/s or more
HCRIT_W = 1.0            # soarable height is where thermals fade to about 1 m/s
CORE = 3.0               # thermal core vs area-average updraft
# Area-average updraft profile w/W* = (z/zi)^(1/3) (1 - 1.1 z/zi) (Lenschow and Stephens, as used by Allen 2006)
_X = np.linspace(1e-4, 1 / 1.1, 4000)
_F = _X ** (1 / 3) * (1 - 1.1 * _X)
_PK = int(np.argmax(_F))
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


def sun_elevation(times_utc, lat, lon):
    """Solar elevation in degrees (NOAA approximation), times as UTC pandas timestamps."""
    t = pd.to_datetime(times_utc)
    doy = t.dt.dayofyear.values
    hour = t.dt.hour.values + t.dt.minute.values / 60
    g = 2 * np.pi / 365 * (doy - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    solar_time = hour * 60 + eqt + 4 * lon
    ha = np.radians(solar_time / 4 - 180)
    la = np.radians(lat)
    cosz = np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha)
    return np.degrees(np.arcsin(np.clip(cosz, -1, 1)))


def hcrit_fraction(wstar):
    """Fraction of the boundary layer depth where a thermal core weakens to HCRIT_W. 0 when it never gets there."""
    need = HCRIT_W / (CORE * np.maximum(np.nan_to_num(wstar, nan=0.0), 1e-6))
    xs, fs = _X[_PK:], _F[_PK:]                  # upper half of the profile, updraft weakening with height
    return np.interp(need, fs[::-1], xs[::-1], left=xs[-1], right=0.0)


def sun_times(day, lat, lon):
    """Official sunrise and sunset (local Mountain time) for a date at a site."""
    local = pd.date_range(pd.Timestamp(day).tz_localize(MT), periods=24 * 60, freq="min")
    elev = sun_elevation(pd.Series(local.tz_convert("UTC")), lat, lon)
    up = elev > SUN_RISE_DEG
    if not up.any():
        return None, None
    i0 = int(np.argmax(up))
    i1 = len(up) - 1 - int(np.argmax(up[::-1]))
    return local[i0].to_pydatetime(), local[i1].to_pydatetime()


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
    soar_top = np.minimum(terrain + hpbl * hcrit_fraction(wstar), np.where(cumulus, cloud_base, np.inf))
    out["wstar"] = np.round(wstar, 2)
    out["top_m"] = np.round(top)                                     # BL top, capped at cumulus base
    out["soar_top_m"] = np.round(soar_top)                           # where thermals fade to about 1 m/s
    out["soar_above_ft"] = np.round((np.minimum(soar_top, CLASS_A_M) - launch) * M_TO_FT)   # no climbing into Class A
    out["cloudbase_ft"] = np.round(cloud_base * M_TO_FT)
    out["cumulus"] = cumulus
    out["t_f"] = np.round((t2 - 273.15) * 9 / 5 + 32)
    out["td_f"] = np.round((td2 - 273.15) * 9 / 5 + 32)
    out["cloud_pct"] = np.round(df["TCDC"].values.astype(float))

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
    ridge_ok = np.zeros(len(df), dtype=bool)
    for L in s["launches"]:
        ok = in_range(dirn, L["ok"]) & (spd >= L["min"]) & (spd <= L["max"])
        best_launch = np.where(ok & (best_launch == ""), L["name"], best_launch)
        ok_any |= ok
        ridge_ok |= ok & (spd >= max(L["min"], L["ideal_mph"][0] - 2))
    out["launch"] = best_launch
    out["daylight"] = sun_elevation(out["time"], s["lat"], s["lon"]) > SUN_RISE_DEG   # official sunrise to sunset (Part 103)
    flyable = ok_any & ~out["storm"].values & ~out["rain"].values & out["daylight"].values
    out["flyable"] = flyable

    # Air School style ladder, each step builds on the one before:
    # -1 not flyable, 0 marginal, 1 soarable, 2 strong thermals (3 and 4, the Top 25% and Top 5% days, come from history)
    thermal_ok = out["soar_above_ft"].values >= SOARABLE_FT
    soarable = flyable & (thermal_ok | (ridge_ok if s["type"] == "ridge" else False))
    level = np.where(flyable, 0, -1)
    level = np.where(soarable, 1, level)
    level = np.where(soarable & thermal_ok & (wstar >= STRONG_W), 2, level)
    out["level"] = level
    out["soarable"] = soarable
    return out


def slots(h, site_id):
    """The four Air School style time slots for each local day, plus each day's best soarable height."""
    h = h.copy()
    h["date"] = h["local"].dt.date
    h["hour"] = h["local"].dt.hour
    days = []
    for d, x in h.groupby("date"):
        day_hours = x[(x["hour"] >= 8) & (x["hour"] <= 17)]
        row = {"date": str(d), "hours": int(len(day_hours)), "slots": {}}
        if len(day_hours):
            row["best_soar_above_ft"] = float(np.nanmax(day_hours["soar_above_ft"].values)) if day_hours["soar_above_ft"].notna().any() else None
            row["tops_ft"] = int(np.nanmax(np.minimum(day_hours["soar_top_m"].values, 99999)) * M_TO_FT) if day_hours["soar_top_m"].notna().any() else None
        for sh in SLOT_HOURS:
            r = x[x["hour"] == sh]
            if len(r):
                r = r.iloc[0]
                row["slots"][sh] = {"level": int(r["level"]), "wind": None if np.isnan(r["wind_mph"]) else int(round(r["wind_mph"])),
                                    "dir": None if np.isnan(r["wind_dir"]) else int(r["wind_dir"]),
                                    "soar_above_ft": None if np.isnan(r["soar_above_ft"]) else float(r["soar_above_ft"]),
                                    "dark": not bool(r["daylight"]), "storm": bool(r["storm"] or r["rain"])}
        days.append(row)
    return days


def percentile(score, history_scores):
    """Share of history days that scored lower, 0 to 100."""
    hs = np.asarray(history_scores, dtype=float)
    if len(hs) == 0:
        return None
    return float(np.round(100 * ((hs < score).sum() + 0.5 * (hs == score).sum()) / len(hs), 1))


