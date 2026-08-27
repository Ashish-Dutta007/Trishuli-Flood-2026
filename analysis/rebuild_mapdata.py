#!/usr/bin/env python3
"""Rebuild mapdata.json using the live OSM cut for the layers the campaign is editing."""
import geopandas as gpd, pandas as pd, numpy as np, json, warnings
from shapely.ops import unary_union
warnings.filterwarnings("ignore")
HDX = "data/hot/"; LIVE = "data/hot_live/"
out = json.load(open("/mnt/shared/docker/climascope/app/static/trishuli/mapdata.json"))

stm = gpd.read_file(HDX + "mainstem.gpkg").to_crs(32645).geometry.unary_union

def dist(gdf):
    return gdf.to_crs(32645).geometry.centroid.distance(stm)

# --- buildings: live ---
b = gpd.read_file(LIVE + "buildings.geojson")
b4 = b.to_crs(4326).geometry.centroid
d = dist(b)
ts = b["timestamp"].astype(str).str[:10] if "timestamp" in b else pd.Series([""] * len(b))
out["bldg"] = [[round(float(p.x), 5), round(float(p.y), 5), int(min(dd, 9999)),
                1 if t >= "2026-08-26" else 0]
               for p, dd, t in zip(b4, d, ts)]

# --- bridges: live ---
br = gpd.read_file(LIVE + "bridges.geojson")
br4 = br.to_crs(4326).geometry.centroid
dbr = dist(br)
def tagname(row):
    t = row.get("tags")
    if isinstance(t, str):
        try: t = json.loads(t)
        except Exception: t = {}
    return (t or {}).get("name")
out["bridges"] = [{"n": tagname(br.iloc[i]), "x": round(float(br4.iloc[i].x), 5),
                   "y": round(float(br4.iloc[i].y), 5), "d": int(dbr.iloc[i])}
                  for i in range(len(br))]

# --- roads: live, split by class ---
rd = gpd.read_file(LIVE + "roads.geojson")
def cls(row):
    t = row.get("tags")
    if isinstance(t, str):
        try: t = json.loads(t)
        except Exception: t = {}
    return (t or {}).get("highway", "")
rd["hw"] = [cls(rd.iloc[i]) for i in range(len(rd))]
def lines(sub, tol):
    g = sub.to_crs(32645).simplify(tol).to_frame("geometry").set_geometry("geometry").to_crs(4326)
    res = []
    for geom in g.geometry:
        if geom is None or geom.is_empty: continue
        parts = list(geom.geoms) if geom.geom_type.startswith("Multi") else [geom]
        for p in parts:
            if p.geom_type != "LineString": continue
            c = [[round(x, 5), round(y, 5)] for x, y in p.coords]
            if len(c) > 1: res.append(c)
    return res
out["road_major"] = lines(rd[rd.hw.isin(["trunk", "primary"])], 25)
out["road_minor"] = lines(rd[rd.hw.isin(["secondary", "tertiary", "unclassified", "residential"])], 40)

counts = {"buildings": len(out["bldg"]),
          "buildings_new": sum(1 for x in out["bldg"] if x[3] == 1),
          "bridges": len(out["bridges"]),
          "road_major": len(out["road_major"]), "road_minor": len(out["road_minor"])}
out["osm"] = dict(counts, snapshot=json.load(open(LIVE + "manifest.json"))["osm_snapshot"]
                  if __import__("os").path.exists(LIVE + "manifest.json") else None)
json.dump(out, open("out/mapdata_live.json", "w"), separators=(",", ":"))
print(json.dumps(counts, indent=1))
import os; print("size MB:", round(os.path.getsize("out/mapdata_live.json") / 1e6, 2))
