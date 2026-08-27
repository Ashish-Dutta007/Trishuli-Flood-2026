#!/usr/bin/env python3
"""Measure wetted channel width before and after, from Sentinel-2 MNDWI.

Both dates sit on the same 45RUM grid, so pixels correspond exactly. Only pixels
cloud-free on BOTH dates are compared, so cloud cannot masquerade as change.
"""
import json, os, urllib.request, warnings, math
import numpy as np, rasterio, geopandas as gpd
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from shapely.ops import unary_union
warnings.filterwarnings("ignore")
os.environ.update(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif")

PRE, POST = "S2C_45RUM_20260812_0_L2A", "S2B_45RUM_20260827_0_L2A"
CLOUD = {3, 8, 9, 10}
RES = 20.0
BUFFER = 600.0          # metres either side of the mapped centreline
THRESHOLDS = (-0.1, 0.0, 0.1)

body = json.dumps({"collections": ["sentinel-2-l2a"], "ids": [PRE, POST], "limit": 5}).encode()
req = urllib.request.Request("https://earth-search.aws.element84.com/v1/search", data=body,
                             method="POST", headers={"Content-Type": "application/json"})
A = {f["id"]: {k: v["href"] for k, v in f["assets"].items()}
     for f in json.load(urllib.request.urlopen(req, timeout=90))["features"]}

# window: the cloud-free downstream reach, in the tile CRS
stem = gpd.read_file("data/hot/mainstem.gpkg").to_crs(32645)
line = unary_union(list(stem.geometry))
minx, miny, maxx, maxy = line.bounds
miny = max(miny, 3_093_000)          # keep inside 45RUM and inside the clear reach
maxy = min(maxy, 3_107_000)
minx, maxx = minx - 1500, maxx + 1500

def band(sid, key, win_ref=None):
    with rasterio.open(A[sid][key]) as ds:
        win = from_bounds(minx, miny, maxx, maxy, transform=ds.transform)
        h, w = int(round((maxy - miny) / RES)), int(round((maxx - minx) / RES))
        rs = Resampling.nearest if key == "scl" else Resampling.bilinear
        return ds.read(1, window=win, boundless=True, fill_value=0,
                       out_shape=(h, w), resampling=rs).astype("float32")

def mndwi(sid):
    g, s = band(sid, "green"), band(sid, "swir16")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where((g + s) > 0, (g - s) / (g + s), np.nan)

pre_w, post_w = mndwi(PRE), mndwi(POST)
pre_c, post_c = band(PRE, "scl"), band(POST, "scl")
clear = ~np.isin(pre_c, list(CLOUD)) & ~np.isin(post_c, list(CLOUD)) \
        & np.isfinite(pre_w) & np.isfinite(post_w)

H, W = pre_w.shape
ys = maxy - (np.arange(H) + 0.5) * RES
xs = minx + (np.arange(W) + 0.5) * RES
XX, YY = np.meshgrid(xs, ys)
from shapely.geometry import Point
buf = line.buffer(BUFFER)
inside = np.zeros((H, W), bool)
bx0, by0, bx1, by1 = buf.bounds
cand = (XX > bx0) & (XX < bx1) & (YY > by0) & (YY < by1)
idx = np.argwhere(cand)
from shapely import points as shpoints, contains
pts = shpoints(XX[cand], YY[cand])
inside[cand] = contains(buf, pts)

region = clear & inside
print(f"window {W}x{H} px at {RES:.0f} m | corridor pixels compared (clear on BOTH dates): {region.sum():,}")
print(f"  cloud-free on both dates: {clear[inside].mean()*100:.1f}% of the {BUFFER:.0f} m corridor\n")

print("wetted area within the corridor, pixels clear on both dates")
print(f"  {'MNDWI thr':>10} {'12 Aug':>12} {'27 Aug':>12} {'change':>12}")
for t in THRESHOLDS:
    a = ((pre_w > t) & region).sum() * RES * RES / 1e6
    b = ((post_w > t) & region).sum() * RES * RES / 1e6
    print(f"  {t:>10.2f} {a:>10.3f}km2 {b:>10.3f}km2 {(b-a)/a*100:>+11.1f}%")

# per-transect width across the channel
main = max(stem.geometry, key=lambda g: g.length)
n = 260
pts_c = [main.interpolate(main.length * i / (n - 1)) for i in range(n)]
res = []
for i in range(2, n - 2):
    p0, p1 = pts_c[i - 2], pts_c[i + 2]
    dx, dy = p1.x - p0.x, p1.y - p0.y
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L                       # unit normal
    offs = np.arange(-400, 401, RES)
    tx = pts_c[i].x + nx * offs
    ty = pts_c[i].y + ny * offs
    cols = ((tx - minx) / RES).astype(int)
    rows = ((maxy - ty) / RES).astype(int)
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    if ok.sum() < 20: continue
    r, c = rows[ok], cols[ok]
    if not region[r, c].all(): continue            # only fully clear transects
    a = (pre_w[r, c] > 0).sum() * RES
    b = (post_w[r, c] > 0).sum() * RES
    if a > 0: res.append((a, b, pts_c[i].y))
res = np.array(res)
print(f"\ntransects fully cloud-free on both dates: {len(res)}")
if len(res):
    print(f"  median wetted width  12 Aug {np.median(res[:,0]):6.0f} m   27 Aug {np.median(res[:,1]):6.0f} m")
    print(f"  mean                 12 Aug {res[:,0].mean():6.0f} m   27 Aug {res[:,1].mean():6.0f} m")
    ratio = res[:,1] / np.maximum(res[:,0], RES)
    print(f"  median width ratio (after/before): {np.median(ratio):.2f}")
    print(f"  transects wider after: {(res[:,1] > res[:,0]).sum()} of {len(res)}"
          f"  ({(res[:,1] > res[:,0]).mean()*100:.0f}%)")
    np.save("out/transect_widths.npy", res)
