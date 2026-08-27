#!/usr/bin/env python3
"""Watch the Copernicus catalogue for the first post-event scene over the corridor.

Safe to run repeatedly (cron or sbatch). Records product ids it has already seen,
so each new scene is announced exactly once. No credentials needed to search.
"""
from __future__ import annotations
import json, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

API   = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
POINT = "POINT(85.34 28.16)"          # Syabrubesi, upper corridor
ONSET = "2026-08-26T02:45:00.000Z"    # flood onset
UA    = "flood-trishuli/0.3 (meashishdutta@gmail.com)"
STATE = Path(__file__).resolve().parents[1] / "data" / "poll_state.json"
LOG   = Path(__file__).resolve().parents[1] / "data" / "poll.log"


def query() -> list[dict]:
    flt = (f"OData.CSC.Intersects(area=geography'SRID=4326;{POINT}') "
           f"and ContentDate/Start gt {ONSET} "
           f"and (startswith(Name,'S1') or startswith(Name,'S2'))")
    url = API + "?" + urllib.parse.urlencode(
        {"$filter": flt, "$orderby": "ContentDate/Start desc", "$top": 50})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r).get("value", [])


def interesting(name: str) -> bool:
    """GRD and L2A are the products the change-detection workflow consumes."""
    return "GRDH" in name or "MSIL2A" in name


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        products = query()
    except Exception as exc:
        with LOG.open("a") as f:
            f.write(f"{now}  ERROR  {type(exc).__name__}: {exc}\n")
        return 1

    state = json.loads(STATE.read_text()) if STATE.exists() else {"seen": []}
    seen = set(state.get("seen", []))
    fresh = [p for p in products if p["Id"] not in seen and interesting(p["Name"])]

    for p in fresh:
        line = (f"{now}  NEW  {p['ContentDate']['Start'][:19]}Z  "
                f"{'SAR' if p['Name'].startswith('S1') else 'OPT'}  {p['Name']}")
        print(line, flush=True)
        with LOG.open("a") as f:
            f.write(line + "\n")

    if not fresh:
        print(f"{now}  no new products ({len(products)} post-event indexed)", flush=True)

    state["seen"] = sorted(seen | {p["Id"] for p in products if interesting(p["Name"])})
    state["last_check"] = now
    state["post_event_count"] = len([p for p in products if interesting(p["Name"])])
    STATE.write_text(json.dumps(state, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
