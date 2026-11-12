from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
drafts=root/'tools/typed72/drafts'
p=drafts/'cold_registration.cpp';t=p.read_bytes().decode('utf8')
a='z.registration.grave_anchor.set({motion.x,motion.y});';assert t.count(a)==1
t=t.replace(a,'z.anchor.set({motion.x,motion.y});');p.write_bytes(t.encode('utf8'))
p=drafts/'cold_registration_state.h';t=p.read_bytes().decode('utf8')
nl='\r\n' if '\r\n' in t else '\n'
a='    Field<Point> grave_anchor;'+nl;assert t.count(a)==1
t=t.replace(a,'');p.write_bytes(t.encode('utf8'))
p=root/'tools/typed72/integrate_stage.py';t=p.read_text(encoding='utf8')
a="'cold_deployment.cpp',";assert t.count(a)==1
t=t.replace(a,"'cold_registration.cpp',"+a);p.write_text(t,encoding='utf8')
