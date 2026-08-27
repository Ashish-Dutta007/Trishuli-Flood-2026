import math, os, io, sys, time
from concurrent.futures import ThreadPoolExecutor
import urllib.request
from PIL import Image
Image.MAX_IMAGE_PIXELS=None

SERVICES={
 'imagery':"https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
 'topo':"https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
}
def deg2t(lat,lon,z):
    n=2**z
    return ((lon+180)/360*n,
            (1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n)
def t2deg(x,y,z):
    n=2**z
    lon=x/n*360-180
    lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))
    return lat,lon

def grab(svc,z,W,S,E,N,out):
    x0,y0=deg2t(N,W,z); x1,y1=deg2t(S,E,z)
    tx0,ty0,tx1,ty1=math.floor(x0),math.floor(y0),math.floor(x1),math.floor(y1)
    nx,ny=tx1-tx0+1,ty1-ty0+1
    canvas=Image.new('RGB',(nx*256,ny*256))
    jobs=[(tx,ty) for ty in range(ty0,ty1+1) for tx in range(tx0,tx1+1)]
    fails=[]
    def one(j):
        tx,ty=j
        url=SERVICES[svc].format(z=z,x=tx,y=ty)
        for attempt in range(3):
            try:
                rq=urllib.request.Request(url,headers={'User-Agent':'rapid-flood-assessment/1.0'})
                with urllib.request.urlopen(rq,timeout=30) as r: data=r.read()
                return j, Image.open(io.BytesIO(data)).convert('RGB')
            except Exception as e:
                time.sleep(1+attempt)
        fails.append(j); return j,None
    with ThreadPoolExecutor(max_workers=8) as ex:
        for (tx,ty),im in ex.map(one,jobs):
            if im is not None: canvas.paste(im,((tx-tx0)*256,(ty-ty0)*256))
    # exact geographic bounds of the stitched canvas
    latN,lonW=t2deg(tx0,ty0,z); latS,lonE=t2deg(tx1+1,ty1+1,z)
    canvas.save(out,quality=82,optimize=True)
    print(f"{svc} z{z}: {nx}x{ny} tiles -> {canvas.size} -> {os.path.getsize(out)/1e6:.2f} MB | fails={len(fails)}")
    print(f"   bounds W={lonW:.6f} S={latS:.6f} E={lonE:.6f} N={latN:.6f}")
    return dict(svc=svc,z=z,w=canvas.size[0],h=canvas.size[1],W=lonW,S=latS,E=lonE,N=latN,file=out,fails=len(fails))

if __name__=='__main__':
    import json
    W,S,E,N=85.03,27.82,85.45,28.31
    meta=[]
    meta.append(grab('imagery',13,W,S,E,N,'out/base_imagery_z13.jpg'))
    meta.append(grab('topo',12,W,S,E,N,'out/base_topo_z12.jpg'))
    json.dump(meta,open('out/base_meta.json','w'),indent=1)
