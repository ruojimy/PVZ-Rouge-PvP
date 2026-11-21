"""Build an isolated training executable from the verified previous native benchmark."""
import re
import shutil

from zombie_special_setup import OUT,SOURCE,EXE,H,PRIOR_RUN,read,write,sha
from league_data import BUILD
from tempo_pool import cmd
from position_build import replace_once

def build():
    receipt=read(PRIOR_RUN/'build.json')
    dest=OUT/'native-src';dest.mkdir(parents=True,exist_ok=True)
    for name,h in receipt['sources'].items():
        assert sha(SOURCE/name)==h
        shutil.copyfile(SOURCE/name,dest/name)
    shutil.copyfile(H/'zombie_special_gate.inc',dest/'zombie_special_gate.inc')
    p=dest/'position_head.h'
    txt=replace_once(p.read_text('utf8'),'#include "switch_control.inc"','#include "switch_control.inc"\n#include "zombie_special_gate.inc"')
    p.write_text(txt,'utf8')
    p=dest/'option_control.inc'
    p.write_text(replace_once(p.read_text('utf8'),'inline int switch_force=-1;','inline int switch_force=-1;\ninline int specialist_override=-1;'),'utf8')
    p=dest/'single_control.inc'
    p.write_text(replace_once(p.read_text('utf8'),'        if(fork){chosen=switch_force;', '''        if(specialist_override>=1){chosen=(specialist_override==2&&f)?2:1;specialist_override=-1;}
        if(fork){chosen=switch_force;'''),'utf8')
    p=dest/'tactical_session.cpp';txt=p.read_text('utf8')
    txt=replace_once(txt,'    position_ai::Tactics tactics_;','    position_ai::Tactics tactics_;\n    position_ai::ZombieSpecialist specialist_;\n    bool last_special_tactic_=false;')
    txt=replace_once(txt,'        const bool tactical=position_ai::active && side==Seat::zombie;', '''        bool tactical=position_ai::active && side==Seat::zombie;
        const bool specialist=tactical && position_ai::switch_policy.contains("native_gate");
        if(specialist){
            position_ai::native_price=[&](const std::string& key,double x,double y,const std::optional<std::string>& grave,bool unbounded,bool actual){
                return services.quote(key,x,y,grave,unbounded,actual);};
            tactical=specialist_.select(view,services)!=0;
            position_ai::specialist_override=position_ai::special_tactic;
            position_ai::special_tactic=-1;
            if(!tactical&&last_special_tactic_)tactics_=position_ai::Tactics{};
            last_special_tactic_=tactical;
            position_ai::native_price={};
            auto underlying=send;
            send=[&,underlying](const std::string& k,const ai::Args& a){
                auto result=underlying(k,a);
                if(result.empty())specialist_.accepted(k,a,view,services);
                return result;
            };
        }''')
    p.write_text(txt,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',EXE.parent/'SDL2.dll')
    write(OUT/'build.json',dict(binary=sha(EXE),original=receipt['binary'],sources={p.name:sha(p) for p in dest.iterdir()},libraries=receipt['libraries']))

if __name__=='__main__':build()
