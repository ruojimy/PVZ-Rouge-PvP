"""Build the bounded residual runtime in isolation; existing frozen sources stay intact."""
import re
from overnight_common import *

folder=B/'residual';source=folder/'native-source';build=folder/'native-build'
assert not source.exists();guard();source.mkdir(parents=True)
assert all(sha(R/p)==h for p,h in read(B/'plan.json')['source_sha256'].items())
shutil.copytree(H/'src',source/'src')
shutil.copytree(H/'sdl_shim',source/'sdl_shim')
shutil.copy2(H/'research_utf8.manifest',source/'research_utf8.manifest')
cmake=(H/'CMakeLists.txt').read_text('utf-8')
needle='get_filename_component(DEV_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)'
assert cmake.count(needle)==1
(source/'CMakeLists.txt').write_text(cmake.replace(needle,'set(DEV_ROOT "'+R.as_posix()+'")'),'utf-8')
path=source/'src/neural_planner.h';code=path.read_text('utf-8')
changes=[
('bool residual_=false,mode_transition_=false;', 'bool residual_=false,mode_transition_=false,bounded_residual_=false;'),
('if(j.at("format")!="pvz-deepset-hybrid-1")throw std::invalid_argument("unknown neural model format");',
 'bounded_residual_=j.at("format")=="pvz-deepset-bounded-residual-1";\n        if(j.at("format")!="pvz-deepset-hybrid-1"&&!bounded_residual_)throw std::invalid_argument("unknown neural model format");'),
('embedding=j.at("embedding");const size_t width=j.at("hidden");',
 'if(bounded_residual_&&(!residual_||feature_version_!=2||policy_version_!=2||enabled_heads[1]||enabled_heads[3]))throw std::invalid_argument("bounded residual requires v2 features/policy and unchanged mode/save heads");\n        embedding=j.at("embedding");const size_t width=j.at("hidden");'),
('bool residual()const{return residual_;}', 'bool residual()const{return residual_;}\n    bool bounded_residual()const{return bounded_residual_;}'),
('if(model->enabled(0)&&c[0]!=5)p.econ_goal=std::clamp(int(p.econ_goal)+c[0]-5,2,model->policy_version()==2?11:10);',
 'if(model->enabled(0)&&c[0]!=5){\n                    if(model->bounded_residual())p.econ_goal=std::max(2.,p.econ_goal+std::clamp(c[0]-5,-1,1));\n                    else p.econ_goal=std::clamp(int(p.econ_goal)+c[0]-5,2,model->policy_version()==2?11:10);\n                }'),
('p.grave_start=std::clamp(int(p.grave_start)+c[2]-5,2,10);',
 'const int delta=model->bounded_residual()?std::clamp(c[2]-5,-1,1):c[2]-5;\n                    p.grave_start=std::clamp(int(p.grave_start)+delta,2,10);')]
for old,new in changes:
    assert code.count(old)==1,old;code=code.replace(old,new)
path.write_text(code,'utf-8');shutil.copy2(H/'night_bounded_contract.cpp',source/'src/neural_contract.cpp')
write(folder/'native-build-plan.json',dict(source_sha256={str(p):sha(p) for p in source.rglob('*') if p.is_file()},
    core_fingerprint_source=str(B/'plan.json'),game_code_changes=False,
    reason='Old non-neutral residual clamping can shrink an r22 economy goal above 12 by more than one. New explicit format enforces a step of at most one and preserves r22 mode/save/memory. Old runtimes reject the new format.'))
cache=(BUILD/'CMakeCache.txt').read_text('utf-8')
cmake_exe=re.search(r'^CMAKE_COMMAND:INTERNAL=(.+)$',cache,re.M).group(1)
command('resid-cmake-configure',[cmake_exe,'-S',source,'-B',build,'-G','Visual Studio 17 2022','-A','x64','-DAI_NN_SDL=system','-DAI_NN_GZIP=OFF'])
command('resid-cmake-build',[cmake_exe,'--build',build,'--config','Release','--parallel','2','--target','headless_match','neural_dataset','neural_contract','teacher_trace'])
assert (build/'ai_nn_build.h').read_text()==(BUILD/'ai_nn_build.h').read_text()
write(folder/'native-prepared.json',dict(binary_sha256={str(p):sha(p) for p in (build/'Release').glob('*.exe')},
    source_sha256=read(folder/'native-build-plan.json')['source_sha256'],game_fingerprint_unchanged=True))
guard();print('isolated bounded residual build prepared')
