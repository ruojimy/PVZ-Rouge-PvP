"""Apply the reviewed 72 sides of the finite initial generation merge.

Reviewed conflicts: changed mechanics/arguments and generated class metadata;
the 58-vine conflict also moves an include and retains owning closure captures.
All code outside those hunks stays from the previously reviewed native source.
"""
import hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
work=root/'build/pvp72-generation'
manifest=json.loads((work/'merge-manifest.json').read_text(encoding='utf8'))
pattern=re.compile(r'<<<<<<<[^\n]*\n(.*?)=======\n(.*?)>>>>>>>[^\n]*\n',re.S)
for entry in manifest:
    if 'conflict' not in entry:continue
    p=Path(entry['conflict']);text=p.read_text(encoding='utf8')
    if entry['code']<=0 or entry['code']>=128:raise RuntimeError('Not a content conflict: '+str(p))
    resolved,n=pattern.subn(lambda match:match[2],text)
    if n!=entry['code'] or '<<<<<<<' in resolved:raise RuntimeError('Unexpected conflict shape: '+str(p))
    destination=root/entry['file']
    if destination.read_text(encoding='utf8')!=resolved:destination.write_text(resolved,encoding='utf8')
    entry['reviewed_conflicts']=n;entry['sha256']=hashlib.sha256(destination.read_bytes()).hexdigest()
for entry in manifest:
    destination=root/entry['file'];kind='sim' if 'sim' in destination.parts else 'ui'
    generated=work/'changed'/kind/'gen'/destination.name
    text=destination.read_text(encoding='utf8');new=generated.read_text(encoding='utf8')
    # The 72 advisor adapter changed from composition to a real Room subtype.
    # A three-way insertion can otherwise retain its obsolete forwarding
    # method alongside the new inherited implementation. These adapter bodies
    # are owned entirely by the explicit source above, not by legacy repairs.
    if destination.name=='pm_draft_advisor.cpp':
        methods=re.findall(r'^V (C__DraftRoom::m_[A-Za-z0-9_]+)\(const Args& A\) \{.*?^\}',new,re.S|re.M)
        for name in methods:
            function=re.compile(r'^V '+re.escape(name)+r'\(const Args& A\) \{.*?^\}',re.S|re.M)
            body=function.search(new)[0];seen=[False]
            def keep_owned(match):
                if seen[0]:return ''
                seen[0]=True;return body
            text=function.sub(keep_owned,text)
    required=[line for line in new.splitlines() if line.startswith('#include ') and line not in text]
    text=('\n'.join(required)+'\n' if required else '')+text
    if destination.read_text(encoding='utf8')!=text:destination.write_text(text,encoding='utf8')
    entry['sha256']=hashlib.sha256(destination.read_bytes()).hexdigest()
(work/'reviewed-merge-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('Applied reviewed mechanic/class-metadata merge hunks')
