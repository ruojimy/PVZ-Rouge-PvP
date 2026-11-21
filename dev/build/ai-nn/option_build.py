"""Build the option experiment against the hash-verified previous game kernel."""
import re
import shutil
from option_study import ROOT,PRIOR,H,BUILD,PROGRAM,inputs_ok,read,write,sha,cmd
from position_build import replace_once

def build():
    inputs_ok()
    old=PRIOR/'native-src';src=ROOT/'native-src';src.mkdir(exist_ok=True)
    original=read(PRIOR/'build.json')
    assert all(sha(old/k)==v for k,v in original['sources'].items())
    for k in ('CMakeLists.txt','tactical_session.cpp'):shutil.copyfile(old/k,src/k)
    shutil.copyfile(H/'option_control.inc',src/'option_control.inc')
    code=(old/'position_head.h').read_text('utf8')
    code=replace_once(code,'class Tactics {','#include "option_control.inc"\nclass Tactics {\n    Options options;')
    code=replace_once(code,'sort(list,b,hint);','sort(list,b,hint);\n                options.apply(list,b,service);')
    code=replace_once(code,'if(std::none_of(cells.begin()','if(!options.traveling() && std::none_of(cells.begin()')
    code=replace_once(code,'if(!send("deploy",args).empty())continue;',
                      'if(!send("deploy",args).empty())continue;\n                    options.accepted(b,a);')
    (src/'position_head.h').write_text(code,'utf8')
    code=(old/'position_match.cpp').read_text('utf8')
    code=replace_once(code,'final_snapshot,position_model;','final_snapshot,position_model,option_model;int forced_option=-1;double fork_after=0.;')
    code=replace_once(code,'position_ai::load(o.position_model);','''position_ai::load(o.position_model);
    position_ai::configure_options(o.option_model,o.forced_option,o.fork_after);''')
    code=replace_once(code,'std::vector<SeatAi> seats;', '''if(!o.option_model.empty()){
        ainn::Sha256 h;h.update(read_file_maybe_gz(o.option_model));header["option_sha256"]=h.hex();
    }
    std::vector<SeatAi> seats;''')
    code=replace_once(code,'std::ofstream log_out;', '''position_ai::option_prefix=[&](){
        ainn::Sha256 prefix;prefix.update(digest.hex());prefix.update(ainn::rng_digest(session->rng_state()));
        prefix.update(session->snapshot().dump());return prefix.hex();
    };
    std::ofstream log_out;''')
    code=replace_once(code,'footer["spatial_actions"]=','footer["options"]=position_ai::option_events;footer["spatial_actions"]=')
    code=replace_once(code,'else if(a=="--position-model")','''else if(a=="--option-model")o.option_model=value();
        else if(a=="--force-option")o.forced_option=std::stoi(value());
        else if(a=="--fork-after")o.fork_after=std::stod(value());
        else if(a=="--position-model")''')
    code=replace_once(code,'if(!(o.control_hz>0.)','''if(o.forced_option < -1 || o.forced_option>3 || ((!o.option_model.empty()||o.forced_option>=0)&&o.position_model.empty()))
        throw std::invalid_argument("option controller requires a position model and a valid choice");
    if(!(o.control_hz>0.)''')
    (src/'position_match.cpp').write_text(code,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',src,'-B',ROOT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',ROOT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',PROGRAM.parent/'SDL2.dll')
    write(ROOT/'build.json',dict(binary=sha(PROGRAM),sources={p.name:sha(p) for p in src.iterdir() if p.is_file()},
                                  inherited_sources=original['sources'],libraries=original['libraries']))
