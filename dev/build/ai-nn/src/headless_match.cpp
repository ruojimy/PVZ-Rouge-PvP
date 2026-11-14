// Headless 1v1 AI-vs-AI match on the typed PvP73 kernel: no V runtime, no window.
//
//   headless_match --corpus <dir> --id <局号[,局号...]> --out <jsonl> [--planner r22]
//                  [--control-hz 15] [--limit-seconds N] [--no-ai] [--digest-every K]
//                  [--seq-base 1] [--dump-inputs <scenario.json>] [--inputs <scenario.json>]
//                  [--log <jsonl>] [--no-records] [--seat-order plant,zombie]
//                  [--final-snapshot <json>]
//
// --dump-inputs writes every command the AI seats sent, keyed by room tick, in the scenario
// format of typed72_match_gate ({"room_ticks":N,"inputs":{"<tick>":[{"side":..,"type":..},..]}}).
// --inputs replays such a file instead of running the AI ("external command sequence" mode,
// for cross-checks against the gate or against inputs recorded by the game).
// --log writes the battle log (Session::log_entry), one entry per line.
// --no-records leaves the planner records out of --out (header and result only).
// --final-snapshot writes Session::snapshot() and native_view() of the last tick (diagnosis).
//
// Output (JSON Lines): a "header" line, one "plan" line per replan (tick, seat, the planner's
// input facts, its memory before the call, the plan, and context a network planner may need),
// and a "result" line.
//
// With several ids the matches run one after another in this process and "{id}" in --out is
// replaced by each id. The output file is deterministic (no wall-clock values); timing goes
// to stdout as one JSON line per match.
//
// Scheduling follows AISeat in tools/pvp72_sources/lobby_room.py (see docs/ai-nn/摸底.md):
// the app ticks every AI seat and then lets the room step (app.py App.step), so before each
// room tick every seat gets one chance to act on the current battle time.
#include "plan_codec.h"
#include "neural_planner.h"
#include "sim/typed72_app/cold_file.h"
#include "sim/typed72_app/session.h"
#include <chrono>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#ifdef PVZ_AI_NN_SDL_SHIM
extern "C" unsigned long long pvz_sdl_shim_stretch_calls(void);   // build/ai-nn/sdl_shim
#endif
namespace {
using namespace pvz::typed72app;
using pvz::typed72::Seat;
using ainn::J;

struct Options {
    std::string corpus,out,planner="r22",model,nn_seat="both";
    std::vector<std::string> ids;
    double control_hz=15.,limit_seconds=1800.;
    bool ai=true;
    int digest_every=1;
    int64_t seq_base=1;                    // AISeat's first seq is 1; typed72_match_gate numbers from 0
    std::string dump_inputs,inputs,log,final_snapshot;
    bool records=true;
    std::vector<std::string> seat_order{"plant","zombie"};
};

// rv_realtime_controls.validate_plan as far as it can reject a typed plan: priority cards are
// playable deck cards, quotas are integers in [0, 700] keyed by deck cards, teleport_hp is
// finite. AISeat keeps self.plan unchanged when this fails (and so replans on every control
// tick while it has no plan at all).
bool plan_valid(const AiPlanR22& p,const std::vector<std::string>& deck){
    const auto in_deck=[&](const std::string& k){return std::find(deck.begin(),deck.end(),k)!=deck.end();};
    for(const auto& k:p.priority)if(!in_deck(k)||k.rfind("secret:",0)==0||k.rfind("zsecret:",0)==0)return false;
    for(const auto& [k,q]:p.quotas)if(!in_deck(k)||!std::isfinite(q)||q!=std::floor(q)||q<0.||q>700.)return false;
    return std::isfinite(p.teleport_hp);
}

// One AISeat (battle phase only).
struct SeatAi {
    Seat seat;std::string name;std::vector<std::string> deck;
    double next_ctl=0.,plan_at=-1e9;bool has_plan=false;   // AISeat.next_ctl / plan_at / plan
    int64_t seq=0;                                         // AISeat.seq[seat]; the next send uses ++seq
    uint64_t control_ticks=0,plans=0,plan_rejections=0,sends=0,send_errors=0;
};

J args_json(const std::string& kind,int64_t seq,const ai::Args& data){
    // dict(type=kind, seq=self.seq[seat], **data)
    J payload={{"type",kind},{"seq",seq}};
    for(const auto& [k,v]:data){
        if(std::holds_alternative<std::monostate>(v))payload[k]=nullptr;
        else if(const auto* d=std::get_if<double>(&v))payload[k]=ainn::game_number(*d);
        else if(const auto* b=std::get_if<bool>(&v))payload[k]=*b;
        else if(const auto* t=std::get_if<std::string>(&v))payload[k]=*t;
        else throw std::invalid_argument("unsupported controller argument "+k);   // typed_battle.cpp ai_forward
    }
    return payload;
}

struct MatchResult {J footer;double wall_seconds=0.,game_seconds=0.;int64_t ticks=0;};

MatchResult run_match(const Options& o,const CorpusEntry& entry,const std::string& out_path){
    auto session=Session::create(load_corpus_entry(entry),entry.map);
    if(o.planner=="nn"){
        const auto model=std::make_shared<ainn::NeuralModel>(J::parse(read_file_maybe_gz(o.model)));
        session->set_ai_planner_factory([&,model](Seat,Seat side)->std::unique_ptr<IPlanner>{
            if(o.nn_seat!="both"&&o.nn_seat!=ainn::seat_text(side))return {};
            return std::make_unique<ainn::NeuralPlanner>(side,model);
        });
    }
    std::ofstream out(out_path,std::ios::binary);
    if(!out)throw std::runtime_error("cannot write "+out_path);
    const double plan_every=1.5;   // rv_r7.Agent.plan_every, inherited by r22
    J header={{"type","header"},{"format","pvz-ai-nn-match-1"},{"id",entry.id},{"map",entry.map},{"night",entry.night},{"seed",entry.seed},
        {"bans",entry.bans},{"decks",{{"plant",entry.plant_deck},{"zombie",entry.zombie_deck}}},
        {"plan_every",plan_every},{"control_hz",o.control_hz},{"limit_seconds",o.limit_seconds},
        {"planners",{{"plant",o.ai?(o.nn_seat=="zombie"?"r22":o.planner):"none"},{"zombie",o.ai?(o.nn_seat=="plant"?"r22":o.planner):"none"}}},{"controller",o.ai?"r22":"none"},
        {"seat_order",o.seat_order},{"digest_every",o.digest_every},{"records",o.records},{"unit_fields",ainn::unit_fields()}};
    if(o.planner=="nn"){
        const auto bytes=read_file_maybe_gz(o.model);ainn::Sha256 sha;sha.update(bytes);
        header["model_sha256"]=sha.hex();header["hybrid_heads"]=J::array();
        const auto meta=J::parse(bytes);const std::array<const char*,4> names{"econ_goal","plant_mode","grave_goal","zombie_save"};
        for(size_t h=0;h<names.size();++h)if(meta.at("enabled_heads").at(h).get<bool>())header["hybrid_heads"].push_back(names[h]);
    }
    std::vector<SeatAi> seats;
    J external=nullptr;J dumped=J::object();
    if(!o.inputs.empty()){
        external=J::parse(pvz::typed72app::read_file_maybe_gz(o.inputs));
        header["planners"]={{"plant","external"},{"zombie","external"}};header["controller"]="external";
    }
    else if(o.ai)for(const auto& name:o.seat_order){
        if(name=="plant")seats.push_back({Seat::plant,"plant",entry.plant_deck});
        else seats.push_back({Seat::zombie,"zombie",entry.zombie_deck});
    }
    for(auto& s:seats)s.seq=o.seq_base-1;
    std::map<std::string,int64_t> external_seq{{"plant",o.seq_base-1},{"zombie",o.seq_base-1}};
    uint64_t external_sent=0,external_errors=0;
    header["seq_base"]=o.seq_base;
    out<<header.dump()<<'\n';
    ainn::Sha256 digest;size_t log_read=0;
    std::ofstream log_out;
    if(!o.log.empty()){
        std::string path=o.log;if(const auto at=path.find("{id}");at!=std::string::npos)path.replace(at,4,entry.id);
        log_out.open(path,std::ios::binary);if(!log_out)throw std::runtime_error("cannot write "+path);
    }
    const auto absorb=[&](bool with_rng){
        for(;log_read<session->log_size();++log_read){
            const std::string line=session->log_entry(log_read).dump(-1,' ',false,J::error_handler_t::replace);
            digest.update(line);digest.update("\n",1);
            if(log_out.is_open())log_out<<line<<'\n';
        }
        if(with_rng){digest.update(ainn::rng_digest(session->rng_state()));digest.update("\n",1);}
    };
    // Plan recorder: Session calls this after every ai_plan (set_ai_plan_observer).
    uint64_t plan_records=0;
    if(o.ai&&external.is_null()&&o.records)session->set_ai_plan_observer([&](Seat owner,const AiPlannerInput& in,const AiPlannerMemory& before,const AiPlanR22& plan){
        const auto view=session->ai_control_view(owner);const std::string seat=ainn::seat_text(owner);
        J cooldowns=J::array(),secrets=J::array();
        if(const auto* me=view.player(seat)){for(const auto& [k,t]:me->cooldowns)cooldowns.push_back(J::array({k,ainn::num(t)}));secrets=me->secrets;}
        const SeatAi* state=nullptr;for(const auto& s:seats)if(s.seat==owner)state=&s;
        out<<J{{"type","plan"},{"tick",session->tick()},{"seat",seat},{"planner",header.at("planners").at(seat)},
            {"input",ainn::input_json(in)},{"memory",ainn::memory_json(before)},{"plan",ainn::plan_json(plan)},
            {"context",{{"night",view.map_night},{"deathmatch",view.deathmatch},{"cooldowns",cooldowns},{"secrets",secrets},{"bans",view.bans},
                        {"valid",state?plan_valid(plan,state->deck):false}}}}.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';
        ++plan_records;
    });
    std::string ai_error;
    const auto started=std::chrono::steady_clock::now();
    const int64_t limit_ticks=int64_t(std::llround(o.limit_seconds*30.));
    while(!session->finished()&&session->tick()<limit_ticks){
        if(!external.is_null()){
            const auto key=std::to_string(session->tick());
            if(external.contains("inputs")&&external.at("inputs").contains(key))for(const auto& raw:external.at("inputs").at(key)){
                const auto side=raw.at("side").get<std::string>();J payload=raw;payload.erase("side");payload["seq"]=++external_seq.at(side);
                ++external_sent;if(!session->command(side,payload).empty())++external_errors;
            }
            if(external.contains("room_ticks")&&session->tick()>=external.at("room_ticks").get<int64_t>())break;
        }
        const std::string tick_key=std::to_string(session->tick());
        try{
            for(auto& s:seats){
                const double time=session->clock().time;                   // b.time
                if(time<s.next_ctl)continue;
                s.next_ctl=time+1./o.control_hz;
                const bool replan=!s.has_plan||time-s.plan_at>=plan_every;
                // TypedBattle ai_tick: observation, the plan when due, then the controller.
                (void)session->ai_observe(s.seat,1);                       // room.match_number of a first match
                if(replan){
                    const auto plan=session->ai_plan(s.seat,session->ai_controller_recovering(s.seat));
                    ++s.plans;
                    if(plan_valid(plan,s.deck))s.has_plan=true;else ++s.plan_rejections;
                    s.plan_at=time;
                }
                (void)session->ai_control(s.seat,"r22",[&](const std::string& kind,const ai::Args& data){
                    J payload=args_json(kind,++s.seq,data);
                    const auto error=session->command(s.name,payload);   // AISeat.send -> Room.command -> command_input
                    ++s.sends;if(!error.empty())++s.send_errors;
                    if(!o.dump_inputs.empty()){payload.erase("seq");payload["side"]=s.name;dumped[tick_key].push_back(std::move(payload));}
                    return error;
                });
                ++s.control_ticks;
            }
        }catch(const std::exception& error){
            // The game logs the traceback, backs off on its real-time clock and retries
            // (AISeat.safe_tick). A headless run has no real-time clock: stop and report.
            ai_error=error.what();break;
        }
        session->step();
        absorb(o.digest_every>0&&session->tick()%o.digest_every==0);
    }
    const double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
    absorb(true);
    const auto clock=session->clock();const J players=session->players();
    J footer={{"type","result"},{"id",entry.id},{"finished",session->finished()},{"timeout",!session->finished()&&ai_error.empty()},
        {"result",session->result_json()},{"tick",clock.room_tick},{"native_tick",clock.native_tick},{"time",clock.time},{"deathmatch",clock.deathmatch},
        {"hp",{{"plant",players.at("plant").at("hp")},{"zombie",players.at("zombie").at("hp")}}},
        {"resource",{{"plant",players.at("plant").at("resource")},{"zombie",players.at("zombie").at("resource")}}},
        {"plan_records",plan_records},{"log_entries",session->log_size()},{"log_sha256",digest.hex()},{"ai_error",ai_error.empty()?J(nullptr):J(ai_error)}};
    J ai=J::object();
    for(const auto& s:seats)ai[s.name]={{"control_ticks",s.control_ticks},{"plans",s.plans},{"plan_rejections",s.plan_rejections},{"sends",s.sends},{"send_errors",s.send_errors}};
    footer["ai"]=ai;footer["fixture_retention"]=session->fixture_retention();
    if(!o.final_snapshot.empty()){
        std::string path=o.final_snapshot;if(const auto at=path.find("{id}");at!=std::string::npos)path.replace(at,4,entry.id);
        std::ofstream(path,std::ios::binary)<<J{{"snapshot",session->snapshot()},{"native_view",session->native_view()}}.dump(-1,' ',false,J::error_handler_t::replace);
    }
    if(!external.is_null())footer["external"]={{"sent",external_sent},{"errors",external_errors}};
    if(!o.dump_inputs.empty()){
        std::string path=o.dump_inputs;if(const auto at=path.find("{id}");at!=std::string::npos)path.replace(at,4,entry.id);
        std::ofstream(path,std::ios::binary)<<J{{"map",entry.map},{"room_ticks",clock.room_tick},{"inputs",dumped}}.dump(-1,' ',false,J::error_handler_t::replace);
    }
    out<<footer.dump()<<'\n';
    if(!out)throw std::runtime_error("write failed: "+out_path);
    return {footer,wall,clock.time,clock.room_tick};
}

Options parse(int argc,char** argv){
    Options o;
    for(int i=1;i<argc;++i){
        const std::string a=argv[i];
        const auto value=[&]{if(i+1>=argc)throw std::invalid_argument("missing value for "+a);return std::string(argv[++i]);};
        if(a=="--corpus")o.corpus=value();
        else if(a=="--id"){std::stringstream ss(value());std::string id;while(std::getline(ss,id,','))if(!id.empty())o.ids.push_back(id);}
        else if(a=="--out")o.out=value();
        else if(a=="--planner")o.planner=value();
        else if(a=="--model")o.model=value();
        else if(a=="--nn-seat")o.nn_seat=value();
        else if(a=="--control-hz")o.control_hz=std::stod(value());
        else if(a=="--limit-seconds")o.limit_seconds=std::stod(value());
        else if(a=="--digest-every")o.digest_every=std::stoi(value());
        else if(a=="--no-ai")o.ai=false;
        else if(a=="--seq-base")o.seq_base=std::stoll(value());
        else if(a=="--dump-inputs")o.dump_inputs=value();
        else if(a=="--inputs")o.inputs=value();
        else if(a=="--log")o.log=value();
        else if(a=="--final-snapshot")o.final_snapshot=value();
        else if(a=="--no-records")o.records=false;
        else if(a=="--seat-order"){
            o.seat_order.clear();std::stringstream ss(value());std::string name;while(std::getline(ss,name,','))o.seat_order.push_back(name);
            if(!(o.seat_order==std::vector<std::string>{"plant","zombie"}||o.seat_order==std::vector<std::string>{"zombie","plant"}))throw std::invalid_argument("--seat-order is plant,zombie or zombie,plant");
        }
        else throw std::invalid_argument("unknown option "+a);
    }
    if(o.corpus.empty()||o.ids.empty()||o.out.empty())
        throw std::invalid_argument("usage: headless_match --corpus <dir> --id <局号[,局号...]> --out <jsonl> [--planner r22] [--control-hz 15] [--limit-seconds N] [--no-ai] [--digest-every K] [--seq-base 1] [--dump-inputs <json>] [--inputs <json>] [--log <jsonl>] [--no-records] [--seat-order plant,zombie]");
    if(o.planner!="r22"&&o.planner!="nn")throw std::invalid_argument("unknown planner "+o.planner);
    if(o.planner=="nn"&&o.model.empty())throw std::invalid_argument("--planner nn requires --model");
    if(o.nn_seat!="both"&&o.nn_seat!="plant"&&o.nn_seat!="zombie")throw std::invalid_argument("--nn-seat must be plant, zombie or both");
    if(!(o.control_hz>0.)||!(o.limit_seconds>0.))throw std::invalid_argument("control-hz and limit-seconds must be positive");
    if(o.ids.size()>1&&o.out.find("{id}")==std::string::npos)throw std::invalid_argument("--out needs {id} when several ids are given");
    return o;
}
}
int main(int argc,char** argv){
    try{
        const Options o=parse(argc,argv);
        const auto index=read_corpus_index(o.corpus);
        for(const auto& id:o.ids){
            const CorpusEntry* entry=nullptr;for(const auto& e:index)if(e.id==id)entry=&e;
            if(!entry)throw std::runtime_error("no corpus entry "+id);
            std::string path=o.out;if(const auto at=path.find("{id}");at!=std::string::npos)path.replace(at,4,id);
            const auto r=run_match(o,*entry,path);
            J sdl=nullptr;
#ifdef PVZ_AI_NN_SDL_SHIM
            sdl=pvz_sdl_shim_stretch_calls();   // cumulative for this process
#endif
            std::cout<<J{{"id",id},{"sdl_shim_stretch_calls",sdl},{"wall_seconds",r.wall_seconds},{"game_seconds",r.game_seconds},{"room_ticks",r.ticks},
                {"speed",r.wall_seconds>0.?r.game_seconds/r.wall_seconds:0.},{"ticks_per_second",r.wall_seconds>0.?r.ticks/r.wall_seconds:0.},
                {"winner",r.footer.at("result").is_null()?J(nullptr):r.footer.at("result").value("winner",J(nullptr))},
                {"timeout",r.footer.at("timeout")},{"log_sha256",r.footer.at("log_sha256")}}.dump()<<std::endl;
        }
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
