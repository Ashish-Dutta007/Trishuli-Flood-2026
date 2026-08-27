#!/usr/bin/env python3
"""Re-cut the Trishuli corridor OSM extract from HOT's raw-data-api.

The HDX snapshot (hot_flood_npl) lags the live mapping campaign, so exposure
counts drift while HOT Tasking Manager projects are active. This pulls the same
AOI straight from raw-data-api, which tracks OSM minutely.
"""
from __future__ import annotations
import json, sys, time, io, zipfile, urllib.request, urllib.error
from pathlib import Path

API = "https://api-prod.raw-data.hotosm.org/v1"
UA = "flood-trishuli/0.3 (meashishdutta@gmail.com)"
HERE = Path(__file__).resolve().parents[1]
AOI = HERE / "data" / "hot_flood_npl_aoi.geojson"
OUT = HERE / "data" / "hot_live"

LAYERS = {
    "buildings": {"tags": {"allGeometry": {"joinOr": {"building": []}}},
                  "geometryType": ["polygon"]},
    "roads":     {"tags": {"allGeometry": {"joinOr": {"highway": []}}},
                  "geometryType": ["line"]},
    "bridges":   {"tags": {"allGeometry": {"joinOr": {"bridge": []}}},
                  "geometryType": ["line", "polygon"]},
}


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(API + path, method="POST",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def snapshot(name: str, spec: dict, geometry: dict, timeout_s: int = 900) -> Path:
    body = {"geometry": geometry, "outputType": "geojson", "fileName": f"trishuli_{name}",
            "filters": {"tags": spec["tags"]}, "geometryType": spec["geometryType"],
            # HDX cuts on intersect; ST_WITHIN would drop anything crossing the AOI edge
            "useStWithin": False}
    task = post("/snapshot/", body)
    tid = task.get("task_id")
    if not tid:
        raise RuntimeError(f"{name}: no task_id in {task}")
    print(f"  {name:10s} task {tid}", flush=True)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st = get(f"{API}/tasks/status/{tid}/")
        state = st.get("status")
        if state == "SUCCESS":
            url = st["result"]["download_url"]
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                        timeout=300) as r:
                blob = r.read()
            OUT.mkdir(parents=True, exist_ok=True)
            dest = OUT / f"{name}.geojson"
            if blob[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    member = next(m for m in z.namelist() if m.endswith(".geojson"))
                    dest.write_bytes(z.read(member))
            else:
                dest.write_bytes(blob)
            print(f"  {name:10s} -> {dest.name} ({dest.stat().st_size:,} bytes)", flush=True)
            return dest
        if state in ("FAILURE", "REVOKED"):
            raise RuntimeError(f"{name}: task {state}: {st}")
        time.sleep(5)
    raise TimeoutError(f"{name}: task {tid} did not finish in {timeout_s}s")


def main() -> None:
    aoi = json.loads(AOI.read_text())
    geom = aoi["features"][0]["geometry"] if aoi.get("type") == "FeatureCollection" else aoi["geometry"]
    status = get(f"{API}/status/")
    print(f"raw-data-api OSM snapshot: {status.get('lastUpdated')}")
    counts = {}
    for name, spec in LAYERS.items():
        path = snapshot(name, spec, geom)
        counts[name] = len(json.loads(path.read_text()).get("features", []))
    print("\nlive feature counts:")
    for k, v in counts.items():
        print(f"  {k:10s} {v:7d}")
    (OUT / "manifest.json").write_text(json.dumps(
        {"osm_snapshot": status.get("lastUpdated"), "counts": counts,
         "retrieved": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
