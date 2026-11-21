"""Compile an observational twin for compact legal-alternative training examples."""
import re
import shutil
from position_study import OUT,H,BUILD,BIN,cmd,sha,write
from position_build import replace_once


def build():
    root=OUT/'capture-src';root.mkdir(exist_ok=True)
    origin=OUT/'native-src'
    src=(origin/'position_head.h').read_text('utf-8-sig')
    src=replace_once(src,'bool producer=false;double mobility=0.,range=0.,damage=0.;',
                     'bool producer=false;double mobility=0.,range=0.,damage=0.;Weights features{};')
    src=replace_once(src,'a.score=std::inner_product(x.begin()','a.features=x; a.score=std::inner_product(x.begin()')
    marker='class Tactics {'
    capture=r'''
inline std::vector<float> example(const std::vector<Action>& list,const Action& selected,ai::Services& svc,double t,const std::vector<ai::Spot>& cells){
    static double last=-100.;
    if(t-last<(selected.kind==wait?5.:.8))return {};
    std::vector<float> values(selected.features.begin(),selected.features.end());
    std::set<std::tuple<int,std::string,std::string,double,double>> seen;
    auto add=[&](const Action& x){
        auto k=std::make_tuple(int(x.kind),x.card,x.source,x.x,x.y);
        if(!seen.insert(k).second||&x==&selected||x.features==selected.features)return false;
        if(x.kind==approach){
            const bool water=svc.card(x.card).name.rfind("水上",0)==0;
            if(std::none_of(cells.begin(),cells.end(),[&](const ai::Spot& s){return s.x==x.x&&s.y-24.==x.y&&s.water==water;}))return false;
        }
        if(x.kind==build||x.kind==spawn){
            std::optional<std::string> src=x.source.empty()?std::nullopt:std::optional(x.source);
            if(!svc.preview(x.card,x.x,x.y,src,false).empty())return false;
        }
        values.insert(values.end(),x.features.begin(),x.features.end());
        return true;
    };
    // Include high-ranking choices, another action family, another source, and lower-ranked alternatives.
    for(auto kind:{wait,build,spawn,approach}){
        int n=0;for(const auto& x:list)if(x.kind==kind&&add(x)&&++n==2)break;
    }
    const size_t stride=std::max<size_t>(1,list.size()/17);
    for(size_t i=0;i<list.size()&&values.size()<11*weights.size();i+=stride)add(list[i]);
    if(values.size()<2*weights.size())return {};
    last=t;return values;
}
inline void save_example(const std::vector<float>& v){
    if(v.empty())return;
    static std::ofstream data([](){const char* dest=std::getenv("PVZ_POSITION_EXAMPLES");if(!dest)throw std::runtime_error("Missing example output");return dest;}(),std::ios::binary);
    const uint32_t count=uint32_t(v.size()/weights.size());data.write(reinterpret_cast<const char*>(&count),sizeof(count));
    data.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(float));if(!data)throw std::runtime_error("Example write failed");
}
'''
    src=replace_once(src,marker,capture+'\n'+marker)
    src=replace_once(src,'if(a.kind==wait){record(b,a,hint,list.size());break;}',
                     'if(a.kind==wait){save_example(example(list,a,service,v.time,cells));record(b,a,hint,list.size());break;}')
    src=replace_once(src,'target_card=a.card;target_x=a.x;','save_example(example(list,a,service,v.time,cells));target_card=a.card;target_x=a.x;')
    src=replace_once(src,'if(!send("deploy",args).empty())continue;','auto sample=example(list,a,service,v.time,cells);if(!send("deploy",args).empty())continue;save_example(sample);')
    (root/'position_head.h').write_text(src,'utf8')
    for name in ['position_match.cpp','tactical_session.cpp','CMakeLists.txt']:shutil.copyfile(origin/name,root/name)
    exe=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    dest=OUT/'capture-build'
    cmd(exe,'-S',root,'-B',dest,'-G','Visual Studio 17 2022','-A','x64')
    cmd(exe,'--build',dest,'--config','Release','--parallel',2)
    shutil.copy2(BIN/'SDL2.dll',dest/'Release/SDL2.dll')
    write(OUT/'capture-build.json',dict(binary=sha(dest/'Release/position_match.exe'),source=sha(root/'position_head.h'),
         basis='Adds diagnostic candidate features before executing the chosen action. Each replay must match the original native battle hash and outcome.'))
if __name__=='__main__':build()

