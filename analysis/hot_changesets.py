#!/usr/bin/env python3
"""Quantify the HOT mapping campaign in the Trishuli corridor from public OSM changesets."""
import urllib.request, xml.etree.ElementTree as ET, time
from collections import Counter
from datetime import datetime, timezone

BBOX="85.05,27.82,85.45,28.32"
UA="flood-trishuli/0.3 (meashishdutta@gmail.com)"
START="2026-08-26T00:00:00Z"

def page(before=None):
    t = f"{START},{before}" if before else START
    url=(f"https://api.openstreetmap.org/api/0.6/changesets?bbox={BBOX}"
         f"&time={t}&closed=true")
    r=urllib.request.Request(url, headers={"User-Agent":UA})
    with urllib.request.urlopen(r, timeout=90) as f:
        return ET.parse(f).getroot().findall("changeset")

seen={}; users=Counter(); edits=0; projects=Counter()
before=None
for _ in range(30):                      # generous page cap
    cs=page(before)
    fresh=[c for c in cs if c.get("id") not in seen]
    if not fresh: break
    for c in fresh:
        seen[c.get("id")]=True
        u=c.get("user"); users[u]+=1
        edits+=int(c.get("changes_count") or 0)
        for t in c.findall("tag"):
            if t.get("k")=="comment":
                for tok in (t.get("v") or "").split():
                    if tok.startswith("#hotosm-project-"): projects[tok]+=1
    oldest=min(c.get("closed_at") for c in cs if c.get("closed_at"))
    if len(cs)<100: break
    before=oldest
    time.sleep(0.5)

print(f"OSM changesets in the corridor since {START[:10]}")
print(f"  changesets : {len(seen)}")
print(f"  edits      : {edits:,}")
print(f"  mappers    : {len(users)}")
print(f"\n  HOT Tasking Manager projects seen:")
for p,n in projects.most_common(): print(f"    {p:28s} {n:4d} changesets")
print(f"\n  most active mappers:")
for u,n in users.most_common(10): print(f"    {u:26s} {n:4d} changesets")
