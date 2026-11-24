"""Shared helpers for reading HRRR from the University of Utah HRRR-Zarr archive."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import numcodecs
import numpy as np
import requests

BASE = "https://hrrrzarr.s3.amazonaws.com"

# short name -> (level, variable) in the sfc store
SFC = {
    "HPBL": ("surface", "HPBL"),          # boundary layer depth, m AGL
    "SHTFL": ("surface", "SHTFL"),        # sensible heat flux, W/m2
    "LHTFL": ("surface", "LHTFL"),        # latent heat flux, W/m2
    "GUST": ("surface", "GUST"),          # surface gust, m/s
    "CAPE": ("surface", "CAPE"),          # J/kg
    "CIN": ("surface", "CIN"),            # J/kg
    "DSWRF": ("surface", "DSWRF"),        # incoming sunshine, W/m2
    "PSFC": ("surface", "PRES"),          # Pa
    "U10": ("10m_above_ground", "UGRD"),
    "V10": ("10m_above_ground", "VGRD"),
    "U80": ("80m_above_ground", "UGRD"),
    "V80": ("80m_above_ground", "VGRD"),
    "T2": ("2m_above_ground", "TMP"),     # K
    "TD2": ("2m_above_ground", "DPT"),    # K
    "RH2": ("2m_above_ground", "RH"),     # %
    "CBASE": ("cloud_base", "HGT"),       # m MSL, -9999 when clear
    "CCEIL": ("cloud_ceiling", "HGT"),    # m
    "CTOP": ("cloud_top", "HGT"),         # m MSL
    "LCL": ("level_of_adiabatic_condensation_from_sfc", "HGT"),  # m
    "REFC": ("entire_atmosphere", "REFC"),  # composite reflectivity, dBZ
    "TCDC": ("entire_atmosphere", "TCDC"),  # total cloud %
    "LCDC": ("low_cloud_layer", "LCDC"),
    "MCDC": ("middle_cloud_layer", "MCDC"),
    "HCDC": ("high_cloud_layer", "HCDC"),
    "PWAT": ("entire_atmosphere_single_layer", "PWAT"),
    "VIS": ("surface", "VIS"),
}

# pressure-level sounding from the prs store
LEVELS = list(range(450, 876, 25))
PRS = {}
for p in LEVELS:
    for short, var in (("T", "TMP"), ("TD", "DPT"), ("U", "UGRD"), ("V", "VGRD"), ("Z", "HGT")):
        PRS[f"{short}{p}"] = (f"{p}mb", var)

DTYPES = {45000: "<f2", 90000: "<f4", 180000: "<f8"}

_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=48, pool_maxsize=48))


def anl_url(kind, dt, level, var, chunk):
    d = dt.strftime("%Y%m%d")
    return f"{BASE}/{kind}/{d}/{d}_{dt:%H}z_anl.zarr/{level}/{var}/{level}/{var}/{chunk}"


def fetch(url, shape=(150, 150), tries=4):
    """Return a decoded chunk, None for a missing object (404), raise after repeated errors."""
    err = None
    for i in range(tries):
        try:
            r = _session.get(url, timeout=60)
            if r.status_code == 404 or r.status_code == 403:
                return None
            r.raise_for_status()
            buf = numcodecs.blosc.decompress(r.content)
            n = int(np.prod(shape))
            return np.frombuffer(buf, dtype=DTYPES[len(buf) * 150 * 150 // n]).reshape(shape)
        except Exception as e:  # network hiccup, retry
            err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url}: {err!r}")


def load_points(path="probe/gridpoints.json"):
    return json.load(open(path))


def extract_hours(hours, points, threads=40):
    """Pull every SFC and PRS field for the given UTC hours.

    Returns {column: array[len(hours), len(points)]} as float32, NaN where missing.
    """
    chunks = sorted({p["chunk"] for p in points})
    cols = {**{k: ("sfc",) + v for k, v in SFC.items()}, **{k: ("prs",) + v for k, v in PRS.items()}}
    out = {c: np.full((len(hours), len(points)), np.nan, dtype="float32") for c in cols}
    jobs = [(hi, c, ch) for hi in range(len(hours)) for c in cols for ch in chunks]
    stats = {"requests": len(jobs), "missing": 0}

    def work(job):
        hi, c, ch = job
        kind, lev, var = cols[c]
        return job, fetch(anl_url(kind, hours[hi], lev, var, ch))

    with ThreadPoolExecutor(threads) as ex:
        for (hi, c, ch), a in ex.map(work, jobs):
            if a is None:
                stats["missing"] += 1
                continue
            for j, p in enumerate(points):
                if p["chunk"] == ch:
                    out[c][hi, j] = a[p["iy"] % 150, p["ix"] % 150]
    return out, stats
