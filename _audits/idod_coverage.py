#!/usr/bin/env python3
"""Recompute catheter ID/OD coverage across the 3 catheter registries.

Counts a device as covered when ANY of:
  - enriched/sizing_specs.id_od block exists with spec_status verified/partial
  - legacy regex hit on ID+OD text patterns across record files
"""
import json, glob, re, collections
ROOT = '/mnt/c/Users/Michael/Documents/device_catalog/artifacts/neurointerventional'
REGS = ['neurovascular_microcatheters','neurovascular_access_catheters','thrombectomy_aspiration_catheters']
ID_PAT = re.compile(r'(?:inner|internal)\s+(?:diameter|lumen)|\bID\b\s*[:=]?\s*0?\.\d', re.I)
OD_PAT = re.compile(r'(?:outer|external)\s+diameter|\bOD\b\s*[:=]?\s*0?\.\d|(?:proximal|prox)[^.\n]{0,40}?\d\.\d\s*(?:F|Fr\b)|0?\.\d{3}"?\s*(?:ID|OD)', re.I)

rows=[]
for reg in REGS:
    for devdir in sorted(glob.glob(f'{ROOT}/{reg}/*/')):
        dd=devdir.rstrip('/').split('/')[-1]
        structured=None; has_id=False; has_od=False
        ep=f'{devdir}enriched/{dd}.json'
        try:
            e=json.load(open(ep))
            ss=e.get('sizing_specs')
            if isinstance(ss,dict) and 'id_od' in ss:
                structured=ss.get('spec_status','verified')
        except Exception: pass
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
        has_id=bool(ID_PAT.search(blob)); has_od=bool(OD_PAT.search(blob))
        rows.append({'registry':reg,'devdir':dd,'structured':structured,
                     'has_id':has_id or structured is not None,
                     'has_od':bool(OD_PAT.search(blob)) or structured in ('verified',)})
have=[r for r in rows if r['has_id'] and r['has_od']]
unv=[r['devdir'] for r in rows if r.get('structured')=='unverified']
print(json.dumps({'total':len(rows),'covered':len(have),'missing':len(rows)-len(have),
                  'structured_unverified':len(unv),
                  'by_registry':dict(collections.Counter(r['registry'] for r in rows if not(r['has_id'] and r['has_od'])))}, indent=1))
