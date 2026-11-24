"""Print the months that still need a history file, as a GitHub Actions output line."""
import json
import os
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
months = []
y, m = 2020, 12
while (y, m) <= (now.year, now.month):
    key = f"{y}-{m:02d}"
    current = (y, m) == (now.year, now.month)
    if current or not os.path.exists(f"data/hrrr/{key}.parquet"):
        months.append(key)
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
# backfill.trigger can hold "all" or a list of months to limit a run
want = open("backfill.trigger").read().split() if os.path.exists("backfill.trigger") else ["all"]
if "all" not in want:
    months = [m_ for m_ in want if m_[:4].isdigit()]
print("months=" + json.dumps(months))
