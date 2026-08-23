#!/usr/bin/env python3
"""Recompute catheter ID/OD coverage across the 3 catheter registries."""
import json, glob, re, collections
ROOT = '/mnt/c/Users/Michael/Documents/device_catalog/artifacts/neurointerventional'
REGS = ['neurovascular_microcatheters','neurovascular_access_catheters','thrombectomy_aspiration_catheters']
ID_PAT = re.compile(r'(?:inner|internal)\s+(?:diameter|lumen)|\bID\b\s*[:=]?\s*0?\.\d', re.I)
OD_PAT = re.compile(r'(?:outer|external)\s+diameter|\bOD\b\s*[:=]?\s*0?\.\d|(?:proximal|prox)[^.\n]{0,40}?\d\.\d\s*(?:F|Fr\b)|0?\.\d{3}"?\s*(?:ID|OD)', re.I)
rows=[]
for reg in REGS:
    for devdir in sorted(glob.glob(f'{ROOT}/{reg}/*/')):
        parts=[]
        for pat in ['enriched/*.json','merged/*.json','data_by_device/*.md','510k/**/*.json']:
            for f in glob.glob(devdir+pat, recursive=True):
                try:
                    if f.endswith('.json'):
                        d=json.load(open(f))
                        parts.append(' '.join(str(v) for v in (d.values() if isinstance(d,dict) else d) if isinstance(v,(str,list,int,float))))
                    else:
                        parts.append(open(f,encoding='utf-8',errors='replace').read())
                except Exception: pass
        blob=' '.join(parts)
        rows.append({'registry':reg,'devdir':devdir.split('/')[-2],
                     'has_id':bool(ID_PAT.search(blob)),'has_od':bool(OD_PAT.search(blob))})
have=[r for r in rows if r['has_id'] and r['has_od']]
print(json.dumps({'total':len(rows),'have_both':len(have),'missing':len(rows)-len(have),
                  'by_registry':dict(collections.Counter(r['registry'] for r in rows if not(r['has_id'] and r['has_od'])))}, indent=1))
