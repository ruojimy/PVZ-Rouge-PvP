from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
for p in (root/'tools/typed72/drafts/cold_registration_probe.cpp',root/'build/typed72-integrated-v6-probes/probes/cold_registration_probe.cpp'):
    t=p.read_bytes().decode('utf8');n=t.count('z.registration.grave_anchor')
    print(p.name,n)
    t=t.replace('z.registration.grave_anchor','z.anchor');p.write_bytes(t.encode('utf8'))
p=root/'tools/typed72/integrate_probes.py';t=p.read_text(encoding='utf8')
a="('cold-runtime-v2',ROOT/'build/typed72-cold-runtime-v2'),('content-v9',ROOT/'build/typed72-content-controller-v9')]"
assert t.count(a)==1
t=t.replace(a,a[:-1]+",('draft-newer',ROOT/'tools/typed72/drafts/_newer_than_stages')]")
a="    for label,folder in LAYERS:\n";assert t.count(a)==1
t=t.replace(a,"    for label,folder in LAYERS:\n        if not folder.exists():continue\n")
p.write_text(t,encoding='utf8')
d=root/'tools/typed72/drafts/_newer_than_stages';d.mkdir(exist_ok=True)
(d/'cold_registration_probe.cpp').write_bytes((root/'tools/typed72/drafts/cold_registration_probe.cpp').read_bytes())
