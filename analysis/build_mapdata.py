import geopandas as gpd, pandas as pd, numpy as np, json, warnings, os
warnings.filterwarnings('ignore')
D='data/hot/'; out={}
stm=gpd.read_file(D+'mainstem.gpkg').to_crs(32645).geometry.unary_union

def lines(gdf, tol_m, maxpts=None):
    g=gdf.to_crs(32645).simplify(tol_m).to_frame('geometry').set_geometry('geometry').to_crs(4326)
    res=[]
    for geom in g.geometry:
        if geom is None or geom.is_empty: continue
        parts=list(geom.geoms) if geom.geom_type.startswith('Multi') else [geom]
        for p in parts:
            if p.geom_type!='LineString': continue
            c=[[round(x,5),round(y,5)] for x,y in p.coords]
            if len(c)>1: res.append(c)
    return res

# --- main stem (fine) ---
st=gpd.read_file(D+'mainstem.gpkg')
out['stem']=lines(st,25)
# --- tributaries ---
w=gpd.read_file(D+'waterways.geojson')
trib=w[(w.geom_type=='LineString')&(w['waterway'].isin(['stream','river']))]
out['trib']=lines(trib,45)
# --- roads by class ---
rd=gpd.read_file(D+'roads.gpkg')
rd=rd[rd.geom_type.isin(['LineString','MultiLineString'])]
out['road_major']=lines(rd[rd['highway'].isin(['trunk','primary'])],25)
out['road_minor']=lines(rd[rd['highway'].isin(['secondary','tertiary','unclassified','residential'])],40)
# --- buildings as centroids, quantised ---
bl=gpd.read_file(D+'buildings.gpkg')
c=bl.to_crs(4326).geometry.centroid
d=bl.to_crs(32645).geometry.centroid.distance(stm)
out['bldg']=[[round(float(p.x),5),round(float(p.y),5),int(min(dd,9999))] for p,dd in zip(c,d)]
# --- point layers ---
def pts(f,keys):
    g=gpd.read_file(D+f); c4=g.to_crs(4326).geometry.centroid
    dd=g.to_crs(32645).geometry.centroid.distance(stm)
    r=[]
    for i in range(len(g)):
        rec={'n':(g.iloc[i].get('name') or g.iloc[i].get('name_en') or None),
             'x':round(float(c4.iloc[i].x),5),'y':round(float(c4.iloc[i].y),5),'d':int(dd.iloc[i])}
        for k in keys:
            v=g.iloc[i].get(k)
            if pd.notna(v): rec[k[:4]]=str(v)
        r.append(rec)
    return r
out['bridges']=pts('bridges.geojson',['highway'])
out['health']=pts('health_facilities.geojson',['amenity'])
out['edu']=pts('education_facilities.geojson',['amenity'])
out['helipad']=pts('airports.geojson',['aeroway'])
out['places']=[p for p in pts('populated_places.geojson',['place']) if p.get('plac') in ('city','town','village','hamlet') or p['d']<1200]
# --- reaches / hotspots ---
rm=pd.read_csv('out/reach_metrics.csv').sort_values('chain_km')
out['reach']=[[round(r.chain_km,1),round(r.lon,5),round(r.lat,5),int(r.z),round(r.BSI,3),
               int(round(r.steep45_500m*100)),int(r.relief_500m),round(r.grad,1)] for r in rm.itertuples()]
# --- AOI ---
aoi=gpd.read_file('data/hot_flood_npl_aoi.geojson')
gg=aoi.geometry.iloc[0].simplify(0.0006)
polys=list(gg.geoms) if gg.geom_type=='MultiPolygon' else [gg]
out['aoi']=[[[round(x,5),round(y,5)] for x,y in p.exterior.coords] for p in polys]
# --- raster meta ---
out['rasters']=json.load(open('out/base_meta.json'))
out['terrain']=json.load(open('out/terrain_meta.json'))
json.dump(out,open('out/mapdata.json','w'),separators=(',',':'))
sz=os.path.getsize('out/mapdata.json')/1e6
print(f"mapdata.json {sz:.2f} MB")
for k,v in out.items():
    if isinstance(v,list): print(f"  {k:12s} {len(v)}")
