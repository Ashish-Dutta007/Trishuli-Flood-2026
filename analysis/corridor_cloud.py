import os, json, numpy as np, rasterio, warnings
from rasterio.warp import transform as warp
warnings.filterwarnings('ignore')
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', AWS_NO_SIGN_REQUEST='YES',
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='4')
B="https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/45/R/{t}/2026/8/S2B_45R{t}_20260827_0_L2A/SCL.tif"
LBL={0:'no data',1:'saturated',2:'dark/shadow',3:'cloud shadow',4:'vegetation',5:'bare',
     6:'water',7:'unclassified',8:'cloud med',9:'cloud high',10:'thin cirrus',11:'snow/ice'}
USABLE={4,5,6,7}

M=json.load(open('static_src/mapdata.json')) if os.path.exists('static_src/mapdata.json') \
  else json.load(open('/mnt/shared/docker/climascope/app/static/trishuli/mapdata.json'))
# dense sample along the main stem
pts=[]
for line in M['stem']:
    for i in range(len(line)-1):
        a,b=line[i],line[i+1]
        for f in (0,0.5):
            pts.append((a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f))
print(f"river samples: {len(pts)}")

hits={}
for tile in ('UM','UL'):
    url=B.format(t=tile)
    with rasterio.open(url) as ds:
        xs,ys=warp('EPSG:4326', ds.crs, [p[0] for p in pts], [p[1] for p in pts])
        vals=list(ds.sample(zip(xs,ys)))
        arr=np.array([v[0] for v in vals])
        inside=[]
        for k,(x,y) in enumerate(zip(xs,ys)):
            r,c=ds.index(x,y)
            inside.append(0<=r<ds.height and 0<=c<ds.width)
        inside=np.array(inside)
        for k in range(len(pts)):
            if inside[k] and arr[k]!=0:
                hits.setdefault(k,[]).append(int(arr[k]))
        print(f"  tile 45R{tile}: {int((inside&(arr!=0)).sum())} river samples covered")

final={k:v[0] for k,v in hits.items()}
vals=np.array(list(final.values()))
print(f"\nriver samples with valid SCL: {len(vals)} of {len(pts)}")
cnt={c:int((vals==c).sum()) for c in sorted(set(vals.tolist()))}
print("\nSCL along the channel:")
for c,n in sorted(cnt.items(), key=lambda t:-t[1]):
    print(f"  {LBL.get(c,c):16s} {n:5d}  {n/len(vals)*100:5.1f}%")
usable=sum(n for c,n in cnt.items() if c in USABLE)
print(f"\n  USABLE (veg/bare/water/unclass): {usable/len(vals)*100:.1f}% of channel")
print(f"  cloud (8,9,10):                 {sum(n for c,n in cnt.items() if c in (8,9,10))/len(vals)*100:.1f}%")
print(f"  shadow (2,3):                   {sum(n for c,n in cnt.items() if c in (2,3))/len(vals)*100:.1f}%")

# where along the corridor is it clear?
print("\nclear runs by river position (upstream -> downstream, 5% bins):")
order=sorted(final.keys())
bins=10
for b in range(bins):
    lo,hi=int(len(order)*b/bins), int(len(order)*(b+1)/bins)
    seg=[final[k] for k in order[lo:hi]]
    if not seg: continue
    u=sum(1 for v in seg if v in USABLE)/len(seg)*100
    bar='#'*int(u/5)
    print(f"  {b*10:3d}-{(b+1)*10:3d}%  {u:5.1f}% usable  {bar}")
