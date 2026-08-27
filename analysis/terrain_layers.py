import os, json, math, numpy as np, rasterio
from rasterio.merge import merge
from PIL import Image
os.environ.update(AWS_NO_SIGN_REQUEST='YES', GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif')
B=("/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/"
   "Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif")
meta=json.load(open('out/base_meta.json'))
img=[m for m in meta if m['svc']=='imagery'][0]
W,S,E,N=img['W'],img['S'],img['E'],img['N']
tiles=["N27_00_E084_00","N27_00_E085_00","N28_00_E084_00","N28_00_E085_00"]
srcs=[rasterio.open(B.format(t=t)) for t in tiles]
arr,tr=merge(srcs,bounds=(W-0.01,S-0.01,E+0.01,N+0.01))
dem=arr[0].astype('float32'); dem[dem<-1000]=np.nan
print("DEM",dem.shape)

lat0=(S+N)/2
px_x=abs(tr.a)*111320*math.cos(math.radians(lat0)); px_y=abs(tr.e)*110540
gy,gx=np.gradient(dem,px_y,px_x)
slope=np.degrees(np.arctan(np.hypot(gx,gy)))
aspect=np.arctan2(-gx,gy)
az,alt=np.radians(315),np.radians(45)
hs=(np.sin(alt)*np.cos(np.radians(slope))+
    np.cos(alt)*np.sin(np.radians(slope))*np.cos(az-aspect))
hs=np.clip(hs,0,1)

# ---- inverse-map Web Mercator canvas -> DEM pixels ----
OW,OH = img['w']//2, img['h']//2       # half-res terrain layers
def merc_y(lat): return math.log(math.tan(math.pi/4+math.radians(lat)/2))
myN,myS = merc_y(N), merc_y(S)
xs = W + (np.arange(OW)+0.5)/OW*(E-W)
ys_m = myN - (np.arange(OH)+0.5)/OH*(myN-myS)
lats = np.degrees(2*np.arctan(np.exp(ys_m))-math.pi/2)
col = ((xs-tr.c)/tr.a).astype(int)
row = ((lats-tr.f)/tr.e).astype(int)
col=np.clip(col,0,dem.shape[1]-1); row=np.clip(row,0,dem.shape[0]-1)
RR,CC = np.meshgrid(row,col,indexing='ij')

hs_o = hs[RR,CC]; sl_o = slope[RR,CC]
# hillshade PNG (grayscale)
Image.fromarray((np.nan_to_num(hs_o,nan=0.5)*255).astype('uint8'),'L')\
     .save('out/layer_hillshade.png',optimize=True)
# slope hazard overlay: transparent below 30 deg, ramp to red at 55+
a=np.clip((sl_o-30)/25,0,1); a=np.nan_to_num(a)
rgba=np.zeros((OH,OW,4),dtype='uint8')
rgba[...,0]=(60+195*a).astype('uint8')
rgba[...,1]=(140*(1-a)+40*a).astype('uint8')
rgba[...,2]=(170*(1-a)+35*a).astype('uint8')
rgba[...,3]=(a*205).astype('uint8')
Image.fromarray(rgba,'RGBA').save('out/layer_slope.png',optimize=True)
for f in ['out/layer_hillshade.png','out/layer_slope.png']:
    print(f, round(os.path.getsize(f)/1e6,2),"MB", Image.open(f).size)
json.dump(dict(W=W,S=S,E=E,N=N,w=OW,h=OH,
               pct_over45=float(np.nanmean(sl_o>45)),pct_over35=float(np.nanmean(sl_o>35))),
          open('out/terrain_meta.json','w'))
print("area >45 deg: %.1f%% | >35 deg: %.1f%%"%(np.nanmean(sl_o>45)*100,np.nanmean(sl_o>35)*100))
