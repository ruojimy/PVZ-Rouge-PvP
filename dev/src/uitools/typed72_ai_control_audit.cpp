// typed72_ai_control_audit <output-directory> [layer-set]
// Shadow comparison of one typed controller layer against the generated V class
// of the same Python layer, on one typed battle:
//   1. Before anything acts in a control tick, the V room snapshot is taken.
//   2. The TYPED controller drives: its inputs really go to battle.command_input
//      and each (kind, kwargs, result) is recorded.
//   3. The V controller then steps on the snapshot from (1); its send REPLAYS the
//      typed results in order and records its own inputs. PreviewBattle reads only
//      that snapshot, so the typed moves cannot leak into the V decision.
// The tick passes when both input streams are identical (kind, keys, key order,
// values exactly). Both see the same observation (ai_observe) and the same plan
// (typed r22 planner, already shown equal to V Agent.plan).
#include "pg/pg.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_teams.h"
#include "sim/typed72_app/typed_battle.h"
#include "ui/gen/pm_rv_realtime_controls.h"
#include "ui/gen/pm_rv_field.h"
#include "ui/gen/pm_rv_tactics_v7.h"
#include "ui/gen/pm_rv_ztactics7.h"
#include "ui/gen/pm_rv_tactics11.h"
#include "ui/gen/pm_rv_tactics19.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "core/obj.h"
#include "data/datastore.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>
#pragma comment(lib,"dbghelp.lib")
static LONG WINAPI crash_stack(EXCEPTION_POINTERS* info){
    HANDLE proc=GetCurrentProcess();SymSetOptions(SYMOPT_LOAD_LINES|SYMOPT_UNDNAME);SymInitialize(proc,nullptr,TRUE);
    CONTEXT ctx=*info->ContextRecord;STACKFRAME64 frame{};frame.AddrPC.Offset=ctx.Rip;frame.AddrPC.Mode=AddrModeFlat;
    frame.AddrFrame.Offset=ctx.Rbp;frame.AddrFrame.Mode=AddrModeFlat;frame.AddrStack.Offset=ctx.Rsp;frame.AddrStack.Mode=AddrModeFlat;
    std::fprintf(stderr,"CRASH code=0x%08lx\n",info->ExceptionRecord->ExceptionCode);
    for(int i=0;i<32&&StackWalk64(IMAGE_FILE_MACHINE_AMD64,proc,GetCurrentThread(),&frame,&ctx,nullptr,SymFunctionTableAccess64,SymGetModuleBase64,nullptr);++i){
        char buf[sizeof(SYMBOL_INFO)+512];auto* sym=reinterpret_cast<SYMBOL_INFO*>(buf);sym->SizeOfStruct=sizeof(SYMBOL_INFO);sym->MaxNameLen=511;
        DWORD64 d=0;IMAGEHLP_LINE64 line{};line.SizeOfStruct=sizeof(line);DWORD ld=0;
        const bool has=SymFromAddr(proc,frame.AddrPC.Offset,&d,sym);const bool hl=SymGetLineFromAddr64(proc,frame.AddrPC.Offset,&ld,&line);
        std::fprintf(stderr,"  #%d %s %s:%lu\n",i,has?sym->Name:"?",hl?line.FileName:"?",hl?line.LineNumber:0ul);
    }
    std::fflush(stderr);return EXCEPTION_CONTINUE_SEARCH;
}
#endif
using namespace pvz;
namespace {
using J = nlohmann::json;
V s(const char* text) { return V(text); }
V get(const V& value, const char* key, V fallback = V::none()) { return py::m_get(value, s(key), fallback); }
V attr(const V& value, const char* key) { return pvz::getattr(value, Sym(key)); }
J json(const V& value) { return J::parse(dump(value)); }
void need(bool okay, const std::string& message) { if (!okay) throw std::runtime_error(message); }
std::string team(const std::string& seat) { return seat.rfind("plant", 0) == 0 ? "plant" : "zombie"; }

struct Audit {
    std::filesystem::path out;
    std::vector<std::string> planned;
    std::set<std::string> completed;
    J report{{"complete",false},{"passed",false},{"checks",J::array()},{"scenarios",J::object()}};
    bool reached_end=false;
    void flush() {
        size_t passed=0; for (const auto& c:report["checks"]) if(c.at("passed").get<bool>()) ++passed;
        J unrun=J::array(); for(const auto& id:planned) if(!completed.count(id)) unrun.push_back(id);
        const bool strict=!planned.empty() && completed.size()==planned.size() && completed.size()==report["checks"].size();
        report["planned_checks"]=planned; report["planned_count"]=planned.size(); report["completed_checks"]=completed.size();
        report["pass_count"]=passed; report["fail_count"]=report["checks"].size()-passed;
        report["unrun_checks"]=unrun; report["unrun_count"]=unrun.size(); report["strict_check_accounting"]=strict;
        report["complete"]=reached_end && strict;
        report["passed"]=reached_end && strict && passed==planned.size() && !report.contains("fatal_error");
        report["outcome"]=report["passed"].get<bool>()?"PASS":"FAIL";
        std::ofstream stream(out/"report.json",std::ios::binary); need(bool(stream),"Cannot open report.json");
        stream << report.dump(2,' ',false,J::error_handler_t::replace) << '\n';
    }
    void check(const std::string& id,bool okay,const J& evidence=J::object()) {
        need(std::find(planned.begin(),planned.end(),id)!=planned.end(),"Unplanned check: "+id);
        need(completed.insert(id).second,"Duplicate completed check: "+id);
        report["checks"].push_back({{"id",id},{"passed",okay},{"evidence",evidence}});
        std::fprintf(stderr,"%s %s\n",okay?"PASS":"FAIL",id.c_str()); std::fflush(stderr); flush();
    }
};

struct Call { std::string kind; J data; std::string result; };
J call_json(const std::string& kind,const Args& a) {
    J data=J::array();
    for(const auto& [k,v]:a.kw) data.push_back({k.str(),json(v)});
    return {{"kind",kind},{"data",data}};
}

struct SeatRun {
    std::string seat,layer;
    V controller,field;
    std::vector<Call> typed_calls; size_t replay=0;
    std::vector<J> v_calls;
    bool diverged=false;
    size_t ticks=0,ticks_with_inputs=0,inputs=0,mismatched_ticks=0;
    J first_mismatches=J::array();
    std::map<std::string,size_t> kinds;
    std::map<std::string,int> seq;
    V plan=V::none(); double plan_at=-1e9;
};

struct Match {
    std::string name,mode;
    BattleHandle cold;
    V battle;
    std::vector<SeatRun> seats;
    Match(const std::string& n,const std::string& m,const J& sc,const std::vector<std::pair<std::string,std::string>>& ai):name(n),mode(m) {
        cold=battle_from_scenario(sc);
        battle=typed72app::wrap_battle(cold.battle);
        typed72app::start_battle_session(battle);
        const V terrain=py::deepcopy(attr(battle,"map"));
        for(const auto& [seat,layer]:ai) {
            SeatRun r; r.seat=seat; r.layer=layer;
            if(layer=="v7")r.controller=pm_rv_tactics_v7::new_PlantTactics(Args{});
            else if(layer=="z7")r.controller=pm_rv_ztactics7::new_ZombieTactics(Args{});
            else if(layer=="p11")r.controller=pm_rv_tactics11::new_PlantTactics(Args{});
            else if(layer=="z11")r.controller=pm_rv_tactics11::new_ZombieTactics(Args{});
            else if(layer=="r22")r.controller=team(seat)=="plant"?pm_rv_tactics19::new_PlantTactics(Args{}):pm_rv_tactics19::new_ZombieTactics(Args{});
            else throw std::runtime_error("unknown audit layer "+layer);
            r.field=pm_rv_field::new_Field(Args{terrain});
            seats.push_back(std::move(r));
        }
        for(auto& r:seats) {
            SeatRun* rp=&r;
            // V send: replay the typed results in order, record what V asked for.
            V replay=V::func([rp](const Args& a){
                need(a.pos.size()==2,"send(side, kind, **data)");
                const std::string kind=py_str(a.pos[1]);
                Args rest; rest.kw=a.kw;
                J asked=call_json(kind,rest); rp->v_calls.push_back(asked);
                if(rp->replay<rp->typed_calls.size()){
                    const auto& t=rp->typed_calls[rp->replay++];
                    if(t.kind==kind && t.data==asked.at("data")) return t.result.empty()?V(""):V(t.result);
                }
                rp->diverged=true; return V("");
            });
            callm(r.controller,Sym("bind"),Args{cold.bridge,replay});
        }
    }
    ~Match() { try { callm(battle,Sym("close"),Args{}); } catch(...) {} }
    double time() const { return attr(battle,"time").num(); }
    bool finished() const { return !attr(battle,"result").is_none(); }
    V snapshot_for(const std::string& seat) {
        V snap=callm(battle,Sym("snapshot"),Args({},{{Sym("include_map"),V(false)},{Sym("copy_state"),V(false)}}));
        for(auto kv:py::items_vec(get(snap,"players"))) if(py_str(kv.first)!=seat) kv.second.at(s("input"))=V::dict();
        V room=py_dict({{s("battle"),snap},{s("bans"),py::list(pvz::getattr(battle,Sym("bans"),V::list()))},{s("rules"),py::deepcopy(attr(battle,"rules"))}});
        if(seat!=team(seat)) room.at(s("battle"))=pm_teams::f_local_perspective(Args{snap,V(seat)});
        room.at(s("map"))=attr(battle,"map");
        return room;
    }
    void control(SeatRun& r) {
        const std::string side=team(r.seat);
        const V snap=snapshot_for(r.seat);                       // (1) before anyone acts
        V packet=callm(battle,Sym("ai_observe"),Args{V(r.seat),V(1.)});
        const V obs=get(packet,"observation");
        if(r.plan.is_none()||time()-r.plan_at>=1.5){
            V raw=callm(battle,Sym("ai_plan"),Args{V(r.seat),V(false)});
            r.plan=pm_rv_realtime_controls::f_validate_plan(Args{raw,get(get(get(snap,"battle"),"players"),side.c_str()).is_none()?V::list():get(get(get(get(snap,"battle"),"players"),side.c_str()),"deck")});
            r.plan_at=time();
        }
        // (2) typed drives
        r.typed_calls.clear(); r.v_calls.clear(); r.replay=0; r.diverged=false;
        SeatRun* rp=&r; Match* self=this; const std::string seat=r.seat;
        V record=V::func([rp,self,seat](const Args& a){
            const std::string kind=py_str(a.pos.at(1));
            Args rest; rest.kw=a.kw;
            V input=V::dict(); input.at(s("type"))=V(kind); input.at(s("seq"))=V(double(++rp->seq[seat]));
            for(const auto& [k,v]:a.kw) input.at(V(k.str()))=v;
            V error=callm(self->battle,Sym("command_input"),Args{V(seat),input});
            const std::string res=error.truthy()?py_str(error):std::string{};
            rp->typed_calls.push_back({kind,call_json(kind,rest).at("data"),res});
            return V(res);
        });
        static const bool trace=std::getenv("TYPED72_CTL_TRACE")!=nullptr;
        if(trace){std::fprintf(stderr,"T %s %.3f typed\n",r.seat.c_str(),time());std::fflush(stderr);}
        (void)callm(battle,Sym("ai_control"),Args{V(r.seat),V(r.layer),record});
        if(trace){std::fprintf(stderr,"T %s %.3f v\n",r.seat.c_str(),time());std::fflush(stderr);}
        // (3) V shadows on the snapshot from (1)
        (void)callm(r.controller,Sym("step"),Args{V(side),snap,obs,r.plan,r.field});
        ++r.ticks; r.inputs+=r.typed_calls.size(); if(!r.typed_calls.empty()) ++r.ticks_with_inputs;
        for(const auto& c:r.typed_calls) ++r.kinds[c.kind];
        bool same=!r.diverged && r.v_calls.size()==r.typed_calls.size();
        if(!same){
            ++r.mismatched_ticks;
            if(r.first_mismatches.size()<8){
                J t=J::array(); for(const auto& c:r.typed_calls) t.push_back({{"kind",c.kind},{"data",c.data},{"result",c.result}});
                r.first_mismatches.push_back({{"time",time()},{"typed",t},{"v",r.v_calls}});
            }
        }
    }
    void run(double until) {
        double next=0.;
        while(time()<until && !finished()) {
            callm(battle,Sym("step"),Args{V(1.)});
            if(time()<next) continue;
            next=time()+1./15.;
            for(auto& r:seats) control(r);
        }
    }
    J summary() {
        J seats_j=J::object();
        for(auto& r:seats){
            J kinds=J::object(); for(const auto& [k,n]:r.kinds) kinds[k]=n;
            const V vlog=attr(r.controller,"log");
            J vl=J::object(); for(auto kv:py::items_vec(vlog)) vl[py_str(kv.first)]=kv.second.num();
            const V typed_log=callm(battle,Sym("ai_control_log"),Args{V(r.seat)});
            seats_j[r.seat]={{"layer",r.layer},{"ticks",r.ticks},{"ticks_with_inputs",r.ticks_with_inputs},{"inputs",r.inputs},{"mismatched_ticks",r.mismatched_ticks},
                {"kinds",kinds},{"first_mismatches",r.first_mismatches},{"v_log",vl},{"typed_log",json(typed_log)}};
        }
        return {{"mode",mode},{"time",time()},{"finished",finished()},{"result",json(attr(battle,"result"))},{"seats",seats_j},{"backend",json(callm(battle,Sym("backend_audit"),Args{}))}};
    }
};

J deck(std::initializer_list<const char*> keys) { J out=J::array(); for(const char* k:keys) out.push_back(k); return out; }

void scenario(Audit& a,const std::string& id,const std::string& mode,J sc,const std::vector<std::pair<std::string,std::string>>& ai,double until,size_t min_inputs) {
    Match m(id,mode,sc,ai);
    m.run(until);
    J s=m.summary(); a.report["scenarios"][id]=s;
    bool equal=true,logs=true,active=true;
    for(auto& [seat,row]:s["seats"].items()){
        equal=equal&&row["mismatched_ticks"]==0;
        logs=logs&&row["v_log"]==row["typed_log"];
        active=active&&row["inputs"].get<size_t>()>=min_inputs;
    }
    a.check(id+"_inputs_equal",equal&&active,s["seats"]);
    a.check(id+"_logs_equal",logs,{{"note","Python Counter vs typed log, every key"}});
}
}

int main(int argc,char** argv) {
    if(argc<2) { std::fprintf(stderr,"Usage: typed72_ai_control_audit <output-directory> [1|2]\n"); return 2; }
    const std::string set=argc>2?argv[2]:"1";
    const std::string P=set=="3"?"r22":set=="2"?"p11":"v7",Z=set=="3"?"r22":set=="2"?"z11":"z7";
#ifdef _WIN32
    SetUnhandledExceptionFilter(crash_stack);
#endif
    Audit audit;
    audit.planned={"duel_inputs_equal","duel_logs_equal","duel_long_inputs_equal","duel_long_logs_equal","duo_inputs_equal","duo_logs_equal"};
    const char* only=std::getenv("TYPED72_CTL_ONLY");
    try {
        audit.out=std::filesystem::absolute(u8p(argv[1])); std::filesystem::create_directories(audit.out/"userdata");
        audit.report["scope"]="Controller layer "+P+"/"+Z+": typed vs the generated V class of the same Python layer; typed drives, V shadows on the pre-tick snapshot with replayed results.";
        audit.flush();
#ifdef _WIN32
        _putenv_s("PVP_USERDATA",p8(audit.out/"userdata").c_str());
        _putenv_s("SDL_VIDEODRIVER","dummy"); _putenv_s("SDL_AUDIODRIVER","dummy");
#endif
        SDL_SetMainReady(); gil::init(); data::set_data_dir("extract/data"); py::g_real_clock=true;
        pg::install_pygame(); init_pvp_modules();
        pm_rv_realtime_controls::init(); pm_teams::init(); pm_rv_field::init(); pm_rv_tactics_v7::init(); pm_rv_ztactics7::init(); pm_rv_tactics11::init(); pm_rv_tactics19::init();
        const J decks{{"plant",deck({"plant:向日葵","plant:豌豆射手","plant:坚果","plant:樱桃炸弹","plant:卷心菜投手","plant:花盆","plant:双发射手"})},
            {"zombie",deck({"zombie:脑光墓碑","zombie:普通僵尸","zombie:路障僵尸","zombie:铁桶僵尸","zombie:撑杆跳僵尸","zombie:坚固脑光墓碑","zombie:橄榄球僵尸"})}};
        if(!only||std::string(only)=="duel")scenario(audit,"duel","duel",{{"seed",17},{"mode","duel"},{"decks",decks}},{{"plant",P},{"zombie",Z}},150.,50);
        if(!only||std::string(only)=="duel_long")scenario(audit,"duel_long","duel",{{"seed",23},{"mode","duel"},{"decks",decks},{"rules",{{"hero_hp",4000}}}},{{"plant",P},{"zombie",Z}},300.,100);
        J duo_decks=decks; duo_decks["plant2"]=deck({"plant:双子向日葵","plant:卷心菜投手","plant:高坚果","plant:花盆"}); duo_decks["zombie2"]=deck({"zombie:成长脑光墓碑","zombie:铁桶僵尸","zombie:坚固脑光墓碑"});
        if(!only||std::string(only)=="duo")scenario(audit,"duo","duo",{{"seed",41},{"mode","duo"},{"decks",duo_decks}},{{"plant",P},{"plant2",P},{"zombie",Z},{"zombie2",Z}},150.,30);
        audit.reached_end=true; audit.flush();
    } catch(const std::exception& e) {
        audit.report["fatal_error"]=e.what(); try { audit.flush(); } catch(...) {}
        std::fprintf(stderr,"TYPED72_AI_CONTROL_AUDIT FAIL: %s\n",e.what()); return 1;
    }
    const bool ok=audit.report["passed"].get<bool>();
    std::fprintf(stderr,"TYPED72_AI_CONTROL_AUDIT %s %zu/%zu\n",ok?"PASS":"FAIL",size_t(audit.report["pass_count"]),audit.planned.size());
    return ok?0:1;
}
