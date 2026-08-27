import geopandas as gpd, pandas as pd, numpy as np, json, warnings
warnings.filterwarnings('ignore')
D='data/hot/'
out={}
# --- reach metrics ---
rm=pd.read_csv('out/reach_metrics.csv').sort_values('chain_km')
out['reaches']=[dict(km=round(r.chain_km,1),lat=round(r.lat,5),lon=round(r.lon,5),z=int(r.z),
                     grad=round(r.grad,1),s45=round(r.steep45_500m*100),relief=int(r.relief_500m),
                     bsi=round(r.BSI,3)) for r in rm.itertuples()]
# --- main stem polyline (WGS84, simplified) ---
st=gpd.read_file(D+'mainstem.gpkg').to_crs(4326)
stems=[]
for g in st.geometry:
    g=g.simplify(0.0004)
    stems.append([[round(x,5),round(y,5)] for x,y in g.coords])
stems.sort(key=len,reverse=True)
out['stem']=stems[:4]
# --- exposure ---
stm=gpd.read_file(D+'mainstem.gpkg').to_crs(32645).geometry.unary_union
def pts(f,cols):
    g=gpd.read_file(D+f); g4=g.to_crs(4326); c=g.to_crs(32645).geometry.centroid
    d=c.distance(stm); c4=g4.geometry.centroid
    rec=[]
    for i in range(len(g)):
        rec.append(dict(name=(g.iloc[i].get('name') or g.iloc[i].get('name_en') or None),
                        lat=round(c4.iloc[i].y,5),lon=round(c4.iloc[i].x,5),d=int(d.iloc[i]),
                        **{k:(g.iloc[i].get(k) if pd.notna(g.iloc[i].get(k)) else None) for k in cols}))
    return rec
out['bridges']=pts('bridges.geojson',['highway','bridge'])
out['health']=pts('health_facilities.geojson',['amenity'])
out['places']=[r for r in pts('populated_places.geojson',['place','population']) if r['d']<1500]
out['education']=pts('education_facilities.geojson',['amenity'])
out['helipads']=pts('airports.geojson',['aeroway'])
# --- exposure summary table ---
bl=gpd.read_file(D+'buildings.gpkg').to_crs(32645); db=bl.geometry.centroid.distance(stm)
rd=gpd.read_file(D+'roads.gpkg').to_crs(32645)
maj=rd[rd['highway'].isin(['trunk','primary','secondary','tertiary'])]
def klen(sub,buf): return round(sum(g.intersection(stm.buffer(buf)).length for g in sub.geometry)/1000,1)
def cnt(recs,t): return sum(1 for r in recs if r['d']<t)
out['exposure']=[
 dict(layer='Buildings (OSM)',total=int(len(bl)),b100=int((db<100).sum()),b250=int((db<250).sum()),b500=int((db<500).sum())),
 dict(layer='Bridges',total=len(out['bridges']),b100=cnt(out['bridges'],100),b250=cnt(out['bridges'],250),b500=cnt(out['bridges'],500)),
 dict(layer='Schools',total=len(out['education']),b100=cnt(out['education'],100),b250=cnt(out['education'],250),b500=cnt(out['education'],500)),
 dict(layer='Health facilities',total=len(out['health']),b100=cnt(out['health'],100),b250=cnt(out['health'],250),b500=cnt(out['health'],500)),
 dict(layer='Populated places',total=224,b100=cnt(out['places'],100),b250=cnt(out['places'],250),b500=cnt(out['places'],500)),
 dict(layer='Helipads / aeroway',total=len(out['helipads']),b100=cnt(out['helipads'],100),b250=cnt(out['helipads'],250),b500=cnt(out['helipads'],500)),
]
out['roads']=dict(all_km=round(rd.length.sum()/1000,1),all_250=klen(rd,250),all_500=klen(rd,500),
                  maj_km=round(maj.length.sum()/1000,1),maj_250=klen(maj,250),maj_500=klen(maj,500))
# --- rainfall ---
om=json.load(open('data/openmeteo_corridor.json')); tb=json.load(open('data/openmeteo_tibet.json'))
names=["Timure/Rasuwagadhi","Syabrubesi","Betrawati","Bidur","Devighat","Benighat","Mugling","Narayangadh","Tribeni"]
tn=["USGS epicentre","Lhende upper","Gyirong S","Gyirong town","Border N"]
def summ(loc):
    h=loc['hourly']; i=h['time'].index('2026-08-26T08:00')
    f=lambda a,b: round(sum(x or 0 for x in h['precipitation'][a:b]),1)
    return dict(elev=int(loc['elevation']),p24=f(i-24,i),p72=f(i-72,i),p168=f(i-168,i),fwd72=f(i,i+72),
                lat=round(loc['latitude'],4),lon=round(loc['longitude'],4),
                daily=[round(v or 0,1) for v in loc['daily']['precipitation_sum']],dates=loc['daily']['time'])
out['rain_corridor']=[dict(site=n,**summ(l)) for n,l in zip(names,om)]
out['rain_tibet']=[dict(site=n,**summ(l)) for n,l in zip(tn,tb)]
json.dump(out,open('out/payload.json','w'))
print("payload written:", round(len(json.dumps(out))/1024,1),"KB")
print("reaches",len(out['reaches']),"| bridges",len(out['bridges']),"| places<1.5km",len(out['places']),"| stem parts",[len(s) for s in out['stem']])
print("\nEXPOSURE SUMMARY"); print(pd.DataFrame(out['exposure']).to_string(index=False))
print("\nROADS", out['roads'])
