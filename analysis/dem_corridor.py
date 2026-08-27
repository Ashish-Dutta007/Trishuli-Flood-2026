import os, warnings, numpy as np, rasterio, geopandas as gpd
from rasterio.merge import merge
from rasterio.warp import transform_bounds
from shapely.geometry import Point
warnings.filterwarnings('ignore')
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', AWS_NO_SIGN_REQUEST='YES',
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='4', GDAL_HTTP_RETRY_DELAY='2')
B="/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif"
tiles=["N27_00_E085_00","N28_00_E085_00"]
srcs=[rasterio.open(B.format(t=t)) for t in tiles]
bbox=(85.03,27.83,85.42,28.30)
arr,tr=merge(srcs,bounds=bbox)
dem=arr[0].astype('float32'); dem[dem<-1000]=np.nan
print("DEM window:",dem.shape,"res(deg)=",round(tr.a,6),"| elev range %.0f-%.0f m"%(np.nanmin(dem),np.nanmax(dem)))
# metres per pixel at this latitude
lat0=(bbox[1]+bbox[3])/2
px_x=abs(tr.a)*111320*np.cos(np.radians(lat0)); px_y=abs(tr.e)*110540
print("pixel size: %.1f x %.1f m"%(px_x,px_y))
gy,gx=np.gradient(dem,px_y,px_x)
slope=np.degrees(np.arctan(np.hypot(gx,gy)))
print("slope: mean %.1f deg, p90 %.1f, p99 %.1f, max %.1f"%(np.nanmean(slope),np.nanpercentile(slope,90),np.nanpercentile(slope,99),np.nanmax(slope)))
np.save('out/slope.npy',slope); np.save('out/dem.npy',dem)
import json; json.dump({'transform':list(tr)[:6],'bbox':bbox,'shape':list(dem.shape),'px_x':px_x,'px_y':px_y},open('out/dem_meta.json','w'))

# ---- per-reach confinement + landslide-source metrics along main stem ----
st=gpd.read_file('data/hot/mainstem.gpkg').to_crs(32645)
main=max(st.geometry,key=lambda g:g.length); L=main.length
n=63  # ~1 km spacing
pts=gpd.GeoSeries([main.interpolate(L*i/(n-1)) for i in range(n)],crs=32645).to_crs(4326)
inv=~tr
def sample_stats(pt,radius_m):
    col,row=inv*(pt.x,pt.y); col,row=int(col),int(row)
    rx=int(radius_m/px_x); ry=int(radius_m/px_y)
    r0,r1=max(0,row-ry),min(dem.shape[0],row+ry+1); c0,c1=max(0,col-rx),min(dem.shape[1],col+rx+1)
    s=slope[r0:r1,c0:c1]; d=dem[r0:r1,c0:c1]
    if s.size==0: return None
    return dict(z=float(dem[row,col]) if 0<=row<dem.shape[0] and 0<=col<dem.shape[1] else np.nan,
                steep35=float(np.nanmean(s>35)), steep45=float(np.nanmean(s>45)),
                relief=float(np.nanmax(d)-np.nanmin(d)), slp_p90=float(np.nanpercentile(s,90)))
rows=[]
for i,p in enumerate(pts):
    ch=L*i/(n-1)/1000
    a=sample_stats(p,500); b=sample_stats(p,1500)
    rows.append(dict(chain_km=ch,lat=p.y,lon=p.x,z=a['z'],
                     steep35_500m=a['steep35'],steep45_500m=a['steep45'],relief_500m=a['relief'],
                     steep35_1500m=b['steep35'],relief_1500m=b['relief'],slp_p90_1500m=b['slp_p90']))
import pandas as pd
df=pd.DataFrame(rows)
if df.z.iloc[0]<df.z.iloc[-1]: df=df.iloc[::-1].reset_index(drop=True); df['chain_km']=L/1000-df['chain_km']
df.to_csv('out/reach_metrics.csv',index=False)
print("\nwrote out/reach_metrics.csv rows=",len(df))
