"""Integrate shooting only after the unchanged pea-chain proof closes."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def edit(name,old,new,count=1):
    p=ROOT/name;s=p.read_text(encoding='utf8');assert s.count(old)==count,(name,old,s.count(old));p.write_text(s.replace(old,new),encoding='utf8')
def main():
    state=json.loads((ROOT/'test_results/typed72-20261105/checkpoint-pea-chain/status.json').read_text(encoding='utf8'));assert state['schema']==17 and len(state['verification'])==42
    for name,digest in state['source_files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for name in ('plant_zombie_shooting.h','plant_zombie_shooting.cpp','shooting_probe.cpp','verify_shooting.py'):
        dest=ROOT/('src/sim/typed' if name.startswith('plant_') else 'tools/typed72')/name;assert not dest.exists();shutil.copy2(Path(__file__).parent/name,dest)
    edit('src/sim/typed/targets.h','    Field<double> shotgun_volley;','    Field<double> shotgun_volley;\n    Field<double> shooting_cooldown,burst_left,burst_cooldown,jump_assist_cooldown;')
    p=ROOT/'tools/typed72/pea_probe.cpp';s=p.read_text(encoding='utf8');assert s.count('int main(')==1;s=s.replace('int main(','#ifndef PVZ72_PEA_PROBE_EMBEDDED\nint main(');s+='\n#endif\n';p.write_text(s,encoding='utf8')
    p=ROOT/'src/sim/typed/CMakeLists.txt';s=p.read_text(encoding='utf8');s+='\nset(PVZ_TYPED_SHOOTING_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/plant_zombie_shooting.cpp" CACHE FILEPATH "Native plant-zombie shooting negative control")\ntarget_sources(pvztyped72 PRIVATE "${PVZ_TYPED_SHOOTING_SOURCE}")\nadd_executable(shooting72_probe "${PVZ_TYPED_ROOT}/tools/typed72/shooting_probe.cpp")\ntarget_link_libraries(shooting72_probe PRIVATE pvztyped72)\ntarget_include_directories(shooting72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party")\n';p.write_text(s,encoding='utf8')
    edit('tools/typed72/verify_components.py',"('peas','verify_peas.py','pea72_probe.exe')]","('peas','verify_peas.py','pea72_probe.exe'),('shooting','verify_shooting.py','shooting72_probe.exe')]")
    edit('tools/typed72/build_android_components.py',"'squash','pea']","'squash','pea','shooting']")
    print('Plant-zombie shooting sources integrated; compilation and verification remain required.')
if __name__=='__main__':main()
