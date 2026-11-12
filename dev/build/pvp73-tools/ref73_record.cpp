// Reference recorder v3 = v2 plus an opt-in REF_DEBUG_TICKS=t0:t1 window that adds
// "dbg":{"seat_tracking":battle._seat_tracking,"flood":{TRACKING_KEYS in g}} to those
// records only. Outside the window (and without the variable) output equals v2.
// Reference recorder for the current 72 backend. Reuses the frozen
// battle_from_scenario/battle_record_jsonl path unchanged; a stream buffer
// splices a digest of both RNG states into each record as it is written, so
// the recorded state lines stay byte-identical to run_battle.exe.
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "pg/pg.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <memory>
#include <fstream>
#include <streambuf>
using namespace pvz;
namespace {
uint64_t digest(const PyRandom& rng) {
    const auto state=rng.state();uint64_t h=1469598103934665603ull;
    const auto mix=[&](uint32_t v){h=(h^v)*1099511628211ull;};
    for(const auto word:state.mt)mix(word);mix(uint32_t(state.mti));return h;
}
class SpliceBuf final:public std::streambuf {
public:
    SpliceBuf(std::ostream& out,V battle):out_(out),battle_(std::move(battle)){}
protected:
    int_type overflow(int_type c)override{if(c!=traits_type::eof())line_.push_back(char(c));if(c=='\n')flush_line();return c;}
    std::streamsize xsputn(const char* s,std::streamsize n)override{
        for(std::streamsize i=0;i<n;++i){line_.push_back(s[i]);if(s[i]=='\n')flush_line();}return n;
    }
private:
    void flush_line() {
        // One record is `{...}\n`; insert before the closing brace.
        line_.resize(line_.size()-2);
        V g=pvz::getattr(battle_,Sym("g"));
        char text[128];std::snprintf(text,sizeof text,",\"rng\":{\"room\":\"%016llx\",\"match\":\"%016llx\"}}\n",
            (unsigned long long)digest(*py::random_of(pvz::getattr(battle_,Sym("rng")))),(unsigned long long)digest(match_of(g).rng()));
        std::string extra;
        if(index_>=debug_from_&&index_<=debug_to_){
            extra=",\"dbg\":{\"seat_tracking\":"+dump(pvz::getattr(battle_,Sym("_seat_tracking"),V::none()))+",\"flood\":{";
            bool first=true;
            for(const char* k:{"人洪水","植洪水","洪水h","洪水","人洪水圈","人洪水cd","人洪水覆盖","植洪水圈","植洪水cd","植洪水覆盖","目标植物","目标位置","输出植物数","paoku","先别追植","wjx","wjy"}){
                const V* v=match_of(g).find_global(V(k));if(!v)continue;
                extra+=std::string(first?"":",")+"\""+k+"\":"+dump(*v);first=false;
            }
            extra+="}}";
        }
        // REF_FRAMES=path: every new native draw frame (battle._frame) after this record.
        if(frames_){
            const V frame=pvz::getattr(battle_,Sym("_frame"),V::none());
            if(!frame.is_none()){const std::string text=dump(frame);if(text!=last_frame_){*frames_<<"{\"record\":"<<index_<<",\"frame\":"<<text<<"}\n";last_frame_=text;}}
        }
        ++index_;
        text[std::strlen(text)-2]=0;  // drop the closing brace and newline, re-added after the debug block
        out_<<line_<<text<<extra<<"}\n";line_.clear();
    }
    std::ostream& out_;V battle_;std::string line_;
    std::unique_ptr<std::ofstream> frames_=[]{const char* s=std::getenv("REF_FRAMES");return s?std::make_unique<std::ofstream>(s,std::ios::binary):std::unique_ptr<std::ofstream>{};}();
    std::string last_frame_;
    int64_t index_=0,debug_from_=-1,debug_to_=-2;
public:
    int64_t index()const{return index_;}
    void debug_window(const char* spec){if(spec&&std::sscanf(spec,"%lld:%lld",&debug_from_,&debug_to_)!=2){debug_from_=-1;debug_to_=-2;}}
};
}
// Same conversion as battle_api.cpp jv (numbers become floats, objects dicts).
static V jv(const nlohmann::json& j){
    if(j.is_null())return V::none();if(j.is_boolean())return V(j.get<bool>());if(j.is_number())return V(j.get<double>());
    if(j.is_string())return V(j.get<std::string>());
    if(j.is_array()){std::vector<V> it;for(auto& x:j)it.push_back(jv(x));return V::list(it);}
    V d=V::dict();for(auto& [k,v]:j.items())d.at(V(k))=jv(v);return d;
}
int main(int argc,char** argv) {
    if(argc!=3){std::fprintf(stderr,"usage: ref72_record scenario out\n");return 1;}
    SDL_SetMainReady();
    SDL_setenv("SDL_VIDEODRIVER","dummy",0);SDL_setenv("SDL_AUDIODRIVER","dummy",0);
    gil::init();data::set_data_dir("extract/data");pg::install_pygame();callm(pg::pygame_module(),Sym("init"),Args{});
    std::ifstream f(u8p(argv[1]),std::ios::binary);const auto sc=nlohmann::json::parse(f);
    try {
        BattleHandle b=battle_from_scenario(sc);
        // REF_SNAPSHOTS=path: drive the room steps here and write battle.snapshot() after each
        // step (the app's view), {"rt":n,"snapshot":{...}} per line. No per-native records.
        if(const char* snap_path=std::getenv("REF_SNAPSHOTS")){
            std::ofstream snaps(u8p(snap_path),std::ios::binary);V bb=b.battle;
            const auto snap=[&](int rt){snaps<<"{\"rt\":"<<rt<<",\"snapshot\":"<<dump(callm(bb,Sym("snapshot"),Args{}))<<"}\n";};
            snap(-1);std::map<std::string,int> seqs;const int n=sc.value("room_ticks",30);
            for(int rt=0;rt<n;++rt){
                const auto key=std::to_string(rt);
                if(sc.contains("inputs")&&sc["inputs"].contains(key))for(auto cmd:sc["inputs"][key]){
                    const std::string side=cmd["side"].get<std::string>();const int seq=seqs.count(side)?seqs[side]+1:0;seqs[side]=seq;
                    cmd.erase("side");cmd["seq"]=seq;
                    V pv=jv(cmd);
                    for(auto& kvp:pv.kv()){
                        if(kvp.second==V("$grave")){V found=V::none();for(auto& u:py::items_vec(pvz::getattr(bb,Sym("units")))){V unit=u.second;if(unit.get(V("behavior"),V::none())==V("grave")&&unit.get(V("hp"),V(0.0)).num()>0&&unit.get(V("side"),V::none())==V("zombie"))found=rd(unit,V("id"));}kvp.second=found;}
                        else if(kvp.second==V("$sun")){V found=V::none();for(auto& r:py::items_vec(pvz::getattr(bb,Sym("resources"))))if(r.second.get(V("side"),V::none())==V(side)){found=r.first;break;}kvp.second=found;}
                    }
                    (void)callm(bb,Sym("command_input"),Args{V(side),pv});
                }
                callm(bb,Sym("step"),Args{});snap(rt);
            }
            std::puts("ok");return 0;
        }
        std::ofstream o(u8p(argv[2]),std::ios::binary);SpliceBuf buffer(o,b.battle);buffer.debug_window(std::getenv("REF_DEBUG_TICKS"));
        // REF_GATE_TICKS=t0:t1: wrap the base _pvp_zombie_gate (the team gate calls it after
        // _switch_plant/_switch_tracking) and log what each zombie's region body will read.
        std::shared_ptr<std::ofstream> gate_log;
        if(const char* spec=std::getenv("REF_GATE_TICKS")){
            long long a=-1,c=-2;std::sscanf(spec,"%lld:%lld",&a,&c);
            gate_log=std::make_shared<std::ofstream>(u8p(std::string(argv[2])+".gate.jsonl"),std::ios::binary);
            Match& G=match_of(pvz::getattr(b.battle,Sym("g")));V& gate=G.global(V("_pvp_zombie_gate"));const V original=gate;
            const V battle_ref=b.battle;gate=V::func([original,a,c,gate_log,&buffer,&G,battle_ref](const Args& args)->V{
                V result=original.call(args);const int64_t tick=buffer.index();
                if(tick<a||tick>c)return result;
                const V l=G.global(V("l"));const V& z=rd(G.global(V("僵尸")),l);const V& pos=rd(z,V("位置"));const double tile=G.global(V("比")).num();
                const int64_t x=int64_t(std::floor(rd(pos,V(0.0)).num()/tile)),y=int64_t(std::floor((rd(pos,V(1.0)).num()-tile*.5)/tile));
                char rdig[24];std::snprintf(rdig,sizeof rdig,"%016llx",(unsigned long long)digest(G.rng()));
                std::string line="{\"t\":"+std::to_string(tick)+",\"l\":"+dump(l)+",\"rd\":\""+std::string(rdig)+"\""+",\"seat\":"+dump(z.get(V("_pvp_seat")))+",\"x\":"+std::to_string(x)+",\"y\":"+std::to_string(y);
                for(const char* k:{"人洪水","植洪水"}){const V* f=G.find_global(V(k));line+=std::string(",\"")+k+"\":";line+=(f&&y>=0)?dump(rd(rd(*f,V(double(y))),V(double(x)))):"null";}
                {const V* f=G.find_global(V("洪水"));for(int k=0;k<2;++k){line+=",\"洪水"+std::to_string(k)+"\":";line+=(f&&y>=0)?dump(rd(rd(rd(*f,V(double(k))),V(double(y))),V(double(x)))):"null";}}
                const V* col=G.find_global(V("同竖尸"));line+=",\"col\":"+(col?dump(col->get(V(double(x)))):std::string("null"));
                // Which saved tracking state holds the live 洪水 grids at this cell?
                const auto cell_of=[&](const V& state,const char* key,int k)->std::string{
                    if(!state.is_dict()&&state.t!=V::OBJ)return "null";const V* f=state.find(V(key));if(!f||!f->has())return "null";
                    const V& grid=k<0?*f:rd(*f,V(double(k)));return dump(rd(rd(grid,V(double(y))),V(double(x))));};
                for(const char* bank:{"_seat_tracking","_rally_trackings"}){
                    const V banks=pvz::getattr(battle_ref,Sym(bank),V::none());line+=std::string(",\"")+bank+"\":{";bool first=true;
                    if(banks.is_dict())for(const auto& [seat,state]:py::items_vec(banks)){line+=std::string(first?"":",")+dump(seat)+":["+cell_of(state,"人洪水",-1)+","+cell_of(state,"洪水",0)+","+cell_of(state,"洪水",1)+"]";first=false;}
                    line+="}";
                }
                for(const char* one:{"_rally_tracking","_rally_tracking_base"}){const V s=pvz::getattr(battle_ref,Sym(one),V::none());line+=std::string(",\"")+one+"\":["+cell_of(s,"人洪水",-1)+","+cell_of(s,"洪水",0)+","+cell_of(s,"洪水",1)+"]";}
                line+=",\"jump_cd\":"+dump(z.get(V("跳跃cd")))+",\"split\":"+dump(z.get(V("分兵")))+",\"pos\":"+dump(pos)+"}\n";
                *gate_log<<line;gate_log->flush();return result;
            });
            // Same window: each plant's turn, with one watched zombie's motion (REF_WATCH_ZOMBIE=index).
            const char* watch_spec=std::getenv("REF_WATCH_ZOMBIE");const int64_t watch=watch_spec?std::atoll(watch_spec):-1;
            V& plant_hook=G.global(V("_pvp_plant_gate"));const V plant_original=plant_hook;
            plant_hook=V::func([plant_original,a,c,watch,gate_log,&buffer,&G](const Args& args)->V{
                const int64_t tick=buffer.index();const bool on=tick>=a&&tick<=c&&watch>=0;
                const auto watched=[&]()->std::string{const V& zs=G.global(V("僵尸"));if(int64_t(zs.len())<=watch)return "null";return dump(rd(rd(zs,V(double(watch))),V("位置")));};
                std::string before=on?watched():"";
                V result=plant_original.call(args);
                if(on){const V l=G.global(V("l"));const V& p=rd(G.global(V("植物")),l);
                    char rdig[24];std::snprintf(rdig,sizeof rdig,"%016llx",(unsigned long long)digest(G.rng()));
                    *gate_log<<"{\"t\":"<<tick<<",\"hook\":\"plant\",\"l\":"<<dump(l)<<",\"rd\":\""<<rdig<<"\""<<",\"plant\":"<<dump(p.get(V("植物")))<<",\"watch_before_gate\":"<<before<<",\"watch_after_gate\":"<<watched()<<"}\n";gate_log->flush();}
                return result;
            });
            // Same window: every g['随'] (native randint) call with its arguments and the current unit index.
            if(const V* found=G.find_global(V("随"))){
                V& rand_hook=G.global(V("随"));const V rand_original=*found;
                rand_hook=V::func([rand_original,a,c,gate_log,&buffer,&G](const Args& args)->V{
                    V result=rand_original.call(args);const int64_t tick=buffer.index();
                    if(tick<a||tick>c)return result;
                    const V* l=G.find_global(V("l"));
                    *gate_log<<"{\"t\":"<<tick<<",\"hook\":\"rand\",\"args\":["<<(args.pos.size()>0?dump(args.pos[0]):"null")<<","<<(args.pos.size()>1?dump(args.pos[1]):"null")
                             <<"],\"result\":"<<dump(result)<<",\"l\":"<<(l?dump(*l):std::string("null"))<<"}\n";
                    gate_log->flush();return result;
                });
            }
            // Same window: g['_pvp_rally_speed'] runs right after the zombie heading is final (zombies.py:344).
            V& speed_hook=G.global(V("_pvp_rally_speed"));const V speed_original=speed_hook;
            speed_hook=V::func([speed_original,a,c,gate_log,&buffer,&G](const Args& args)->V{
                V result=speed_original.call(args);const int64_t tick=buffer.index();
                if(tick<a||tick>c)return result;
                const V l=G.global(V("l"));const V& z=rd(G.global(V("僵尸")),l);
                *gate_log<<"{\"t\":"<<tick<<",\"l\":"<<dump(l)<<",\"hook\":\"speed\",\"hs\":"<<dump(G.global(V("hs")))<<",\"facing\":"<<dump(z.get(V("方向")))
                         <<",\"speed\":"<<dump(result)<<",\"pos\":"<<dump(rd(z,V("位置")))<<"}\n";
                gate_log->flush();return result;
            });
        }std::ostream spliced(&buffer);
        battle_record_jsonl(b,sc,spliced);
        // Settlement and the unbounded event log are read after the frozen recording path ends.
        std::ofstream side(u8p(std::string(argv[2])+".final.json"),std::ios::binary);
        side<<"{\"result\":"<<dump(pvz::getattr(b.battle,Sym("result"),V::none()))<<",\"tick\":"<<dump(pvz::getattr(b.battle,Sym("tick"),V::none()))<<",\"log\":"<<dump(py::iter_list(pvz::getattr(b.battle,Sym("log"),V::list())))<<",\"players\":"<<dump(pvz::getattr(b.battle,Sym("players"),V::none()))<<"}";
        std::puts("ok");
    }catch(PyError& e){std::fprintf(stderr,"PyError %s\n",e.what());return 2;}
    catch(std::exception& e){std::fprintf(stderr,"error %s\n",e.what());return 3;}
    return 0;
}
