"""Which way does the slope face at each launch? Uses Open-Meteo's 90 m elevation API.

Samples a ring of points around each launch and reports the direction of steepest descent,
which is the direction the launch faces (and the wind it wants).
"""
import json
import math
import os
import time

import requests

sites = json.load(open("sites.json"))
rows = []
for s in sites:
    pts = [(s["lat"], s["lon"], 0, 0)]
    for r in (200, 400):
        for b in range(0, 360, 15):
            dlat = r * math.cos(math.radians(b)) / 111320
            dlon = r * math.sin(math.radians(b)) / (111320 * math.cos(math.radians(s["lat"])))
            pts.append((s["lat"] + dlat, s["lon"] + dlon, r, b))
    elev = []
    for i in range(0, len(pts), 40):
        chunk = pts[i:i + 40]
        q = {"latitude": ",".join(f"{p[0]:.5f}" for p in chunk), "longitude": ",".join(f"{p[1]:.5f}" for p in chunk)}
        r = requests.get("https://api.open-meteo.com/v1/elevation", params=q, timeout=60)
        j = r.json()
        if "elevation" in j:
            elev += j["elevation"]
            continue
        print("open-meteo said", r.status_code, j, "- falling back to USGS")
        for p in chunk:   # USGS 3DEP point service, one point per call, metres
            u = requests.get("https://epqs.nationalmap.gov/v1/json", params={"x": p[1], "y": p[0], "units": "Meters", "wkid": 4326}, timeout=60)
            elev.append(float(u.json()["value"]))
        time.sleep(1)
    z0 = elev[0]
    out = {"id": s["id"], "elev_ft": round(z0 * 3.28084)}
    for r in (200, 400):
        drops = [(z0 - e, p[3]) for p, e in zip(pts[1:], elev[1:]) if p[2] == r]
        best = max(drops)
        # vector mean of downhill directions, weighted by drop
        x = sum(max(d, 0) * math.sin(math.radians(b)) for d, b in drops)
        y = sum(max(d, 0) * math.cos(math.radians(b)) for d, b in drops)
        out[f"steepest_{r}m"] = best[1]
        out[f"drop_{r}m_ft"] = round(best[0] * 3.28084)
        out[f"mean_downhill_{r}m"] = round((math.degrees(math.atan2(x, y)) + 360) % 360)
        out[f"downhill_sectors_{r}m"] = [b for d, b in drops if d > 0.08 * r]
    rows.append(out)
os.makedirs("probe", exist_ok=True)
json.dump(rows, open("probe/aspect.json", "w"), indent=1)
for r in rows:
    print(r)
