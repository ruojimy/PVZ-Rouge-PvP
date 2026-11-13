#include "core/function_profile.h"
#include "sim/typed72_app/frame_projection.h"
#include <set>
#include <map>
#include "sim/typed72_app/typed_battle.h"
#include "sim/typed72_app/session.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed/ai_observation_codec.h"
#include "core/obj.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <unordered_map>
namespace pvz::typed72app {
namespace {
using J=nlohmann::json;
V jv(const J& j){
    if(j.is_null())return V::none();
    if(j.is_boolean())return V(j.get<bool>());
    if(j.is_number())return V(j.get<double>());
    if(j.is_string())return V(j.get<std::string>());
    if(j.is_array()){std::vector<V> items;items.reserve(j.size());for(const auto& x:j)items.push_back(jv(x));return V::list(items);}
    V d=V::dict();for(auto i=j.begin();i!=j.end();++i)d.at(V(i.key()))=jv(i.value());return d;
}
J vj(const V& v){return J::parse(dump(v));}
// Python random.getstate() of the typed engine RNG: (3, (mt[0..623], index), None).
struct TypedRng:PyObj {
    std::function<J()> state;
    const char* type_name()const override{return "Random";}
    bool call_method(Sym name,const Args&,V& out)override{
        if(name.str()!="getstate")return false;
        const J s=state();std::vector<V> words;for(const auto& w:s.at("mt"))words.push_back(V(w.get<double>()));words.push_back(V(s.at("mti").get<double>()));
        out=V::tuple({V(3.0),V::tuple(words),V::none()});return true;
    }
};
// battle.director: a typed wave director is bound (truthy); snapshot() is the typed team waves.
struct TypedDirector:PyObj {
    std::function<V()> snapshot;
    V cold;   // the V-constructed WaveDirector: read only for its construction constants
    const char* type_name()const override{return "WaveDirector";}
    // Construction parameters (WaveDirector.__init__) never change in a match; the
    // dynamic wave state is only ever read from the typed snapshot above.
    V property(Sym name,bool& found)override{
        const std::string& n=name.str();
        if((n=="max_zombies"||n=="day"||n=="seed"||n=="coop")&&cold.has()&&!cold.is_none()){found=true;return pvz::getattr(cold,name);}
        found=false;return V();
    }
    bool call_method(Sym name,const Args&,V& out)override{if(name.str()!="snapshot")return false;out=snapshot();return true;}
};
// battle.scripted_spawn_budget: only its construction limit is a public fact; the
// running count lives in the typed battle and is never served from the V object.
struct TypedSpawnBudget:PyObj {
    V cold;
    const char* type_name()const override{return "ScriptedSpawnBudget";}
    V property(Sym name,bool& found)override{
        if(name.str()=="limit"&&cold.has()&&!cold.is_none()){found=true;return pvz::getattr(cold,name);}
        found=false;return V();
    }
};
// A V-record view of one typed unit/avatar (the same Obj type as NativeBattle's native dicts).
// Every write is applied to the typed object; a key the typed state cannot take raises.
struct TypedRecordHook:Obj::Hook {
    std::function<void(const V&,const V&)> write;
    const char* type_name()const override{return "dict";}
    bool set(Obj&,const V& key,const V& value)override{write(key,value);return false;}
    bool call(Obj&,const V& self_v,Sym name,const Args& a,V& out)override{
        if(name.str()!="update")return false;
        V d=a.pos.empty()?V::dict():py::dict_of(a.pos[0]);for(auto& p:a.kw)d.at(V(p.first))=p.second;
        for(auto& p:d.kv())setitem(self_v,p.first,p.second);
        out=V::none();return true;
    }
};
// battle.engine: only the native tick counter is public; the typed engine has no V surface.
struct TypedEngine:PyObj {
    std::function<int64_t()> native_tick;
    V rng;
    const char* type_name()const override{return "TypedEngine";}
    // physics: the V engine's static state constructor (physics.make_state, patch_offsets) used to
    // build acceptance fixtures; it computes a dict and never advances any battle.
    V physics;
    V property(Sym name,bool& found)override{
        if(name.str()=="physics"){found=physics.has()&&!physics.is_none();return physics;}
        if(name.str()=="rng"){found=rng.has()&&!rng.is_none();return rng;}
        found=name.str()=="native_tick";return found?V(double(native_tick())):V();}
};
struct TypedBattle:PyObj {
    V native;
    std::unique_ptr<Session> session;
    V ai_seats=V::tuple({});
    V log_cache=V::list({});size_t logged=0;
    V last_snapshot;J last_json;bool fresh=false;
    FrameProjection frame_projection;
    // battle.g / battle.avatars / battle._native_objects: typed record-format projection, cached per state.
    V native_g,native_avatars,native_objects;bool native_fresh=false;
    void refresh_native(){
        if(native_fresh)return;const J view=session->native_view();++native_projections;
        // Records keep their identity across refreshes (V's native dicts are the same objects
        // for an object's whole life): a held record is refilled in place.
        std::unordered_map<std::string,V> kept;
        const auto record=[this,&kept](const J& fields,bool avatar,const std::string& id){
            const std::string key=(avatar?"a:":"u:")+id;
            auto found=records.find(key);V v;
            if(found!=records.end())v=found->second;
            else{
                v=V::obj();auto hook=std::make_shared<TypedRecordHook>();TypedBattle* self=this;
                hook->write=[self,avatar,id](const V& k,const V& value){self->record_write(avatar,id,k,value);};
                v.o()->hook=hook;
            }
            Obj* o=v.o();
            std::vector<V> stale;o->each([&](V k,const V&){if(!fields.contains(py_str(k)))stale.push_back(k);});for(const auto& k:stale)o->del(k);
            for(auto i=fields.begin();i!=fields.end();++i)o->slot(V(i.key()))=jv(i.value());
            kept.emplace(key,v);return v;
        };
        native_objects=V::dict();native_g=V::dict();
        for(const auto& [k,list]:view.at("g").items()){
            std::vector<V> rows;
            for(const auto& item:list){
                const std::string id=item.contains("_pvp_id")&&item["_pvp_id"].is_string()?item["_pvp_id"].get<std::string>():std::string{};
                if(k!="实体"&&!id.empty()){V r=record(item,false,id);native_objects.at(V(id))=r;rows.push_back(r);}else rows.push_back(jv(item));
            }
            native_g.at(V(k))=V::list(rows);
        }
        native_avatars=V::dict();avatar_lists.clear();
        for(const auto& [side,fields]:view.at("avatars").items()){
            native_avatars.at(V(side))=record(fields,true,side);
            for(auto i=fields.begin();i!=fields.end();++i)if(i.value().is_array())avatar_lists[side][i.key()]=i.value();
        }
        records=std::move(kept);native_fresh=true;
        ditu_seen=view.at("g").contains("ditu")?view.at("g").at("ditu"):J(nullptr);
    }
    std::unordered_map<std::string,V> records;bool records_out=false;
    // Avatar list fields as projected (玩家位置, ...): a held record's list mutated in place
    // (hero_states[s]["玩家位置"][:] = ...) reaches the typed hero at the next step/command,
    // before anything reads it, as the V list is the native state itself.
    std::map<std::string,std::map<std::string,J>> avatar_lists;
    void push_avatar_edits(){
        if(!records_out)return;bool any=false;
        for(auto& [side,lists]:avatar_lists){
            const auto found=records.find("a:"+side);if(found==records.end())continue;
            J fields=J::object();
            for(auto& [key,seen]:lists){const J now=vj(found->second.o()->get(V(key),V::none()));if(now!=seen){fields[key]=now;seen=now;}}
            if(!fields.empty()){session->native_set(true,side,fields);any=true;}
        }
        if(any){fresh=false;players_fresh=false;}
    }
    // After a command or fixture write, records already handed out follow at once (a test holds
    // battle._native_objects[id] across world clicks); steps refresh them at the next access.
    void follow_records(){if(records_out&&!native_fresh)refresh_native();
    }
    // A write through a record view: apply to the typed object; snapshot caches restart.
    void record_write(bool avatar,const std::string& id,const V& key,const V& value){
        J fields=J::object();fields[py_str(key)]=vj(value);
        session->native_set(avatar,id,fields);fresh=false;players_fresh=false;
    }
    // battle.players: persistent plain dicts (Simulation.players are dicts that callers hold
    // across steps), refilled in place after each typed change. A caller's writes stay in the
    // dict, as in V, and the keys the typed state owns reach it at the next command, step or
    // placement boundary (before anything reads them); other changed keys fail loudly there.
    V players_v;bool players_fresh=false,players_out=false;std::map<std::string,J> players_seen;
    static void refill(V& d,const J& row,bool keep_cooldowns){
        std::vector<V> stale;for(const auto& kv:d.kv())if(!row.contains(py_str(kv.first)))stale.push_back(kv.first);for(const auto& k:stale)d.erase(k);
        for(auto i=row.begin();i!=row.end();++i)if(!(keep_cooldowns&&i.key()=="cooldowns"))d.at(V(i.key()))=jv(i.value());
    }
    void sync_players(){
        const J pj=session->players();if(!players_v.is_dict())players_v=V::dict();
        for(auto i=pj.begin();i!=pj.end();++i){
            V rec=players_v.get(V(i.key()),V::none());
            if(!rec.is_dict()){rec=V::dict();players_v.at(V(i.key()))=rec;}
            refill(rec,i.value(),true);
            const J cool=i.value().contains("cooldowns")?i.value()["cooldowns"]:J::object();
            V c=rec.get(V("cooldowns"),V::none());
            if(!c.is_dict()){c=V::dict();rec.at(V("cooldowns"))=c;}
            refill(c,cool,false);
            players_seen[i.key()]=i.value();
        }
        players_fresh=true;
    }
    void push_player_edits(){
        if(!players_out||!players_v.is_dict())return;
        static const std::set<std::string> owned{"resource","teleport_ready_at","seq","marked_until","x","y","stats","input","jump_held"};
        // Simulation._sync_public rewrites these from the avatar; a write lasts until then.
        static const std::set<std::string> derived{"vx","vy","h","w","hp","max_hp","facing","frozen","slowed","buttered","jumps","jump_cap","grounded","poison_level","native_pose"};
        bool any=false;
        for(auto& [side,seen]:players_seen){
            const V rec=players_v.get(V(side),V::none());if(!rec.is_dict())continue;
            const J now=vj(rec);J fields=J::object();
            std::set<std::string> keys;for(auto i=now.begin();i!=now.end();++i)keys.insert(i.key());for(auto i=seen.begin();i!=seen.end();++i)keys.insert(i.key());
            for(const auto& k:keys){
                const J a=now.contains(k)?now[k]:J(nullptr),b=seen.contains(k)?seen[k]:J(nullptr);if(a==b)continue;
                if(k=="cooldowns"){fields["cooldowns_replace"]=a.is_object()?a:J::object();continue;}
                if(owned.count(k)){if(!a.is_null())fields[k]=a;continue;}
                if(derived.count(k))continue;
                throw PyError("NotImplementedError","typed battle.players['"+side+"']['"+k+"'] write is not supported by the typed state");
            }
            if(!fields.empty()){session->fixture_player(side,fields);any=true;}
            seen=now;
        }
        if(any){fresh=false;native_fresh=false;players_fresh=false;}
    }
    // The boundary at which caller edits of the live dicts reach the typed state.
    void push_edits(){push_player_edits();push_avatar_edits();}
    // Every typed state change: snapshot caches restart; handed-out player dicts follow at once.
    // battle.map is the V construction map; a test may edit its tiles (public geometry the mark
    // check reads). Edits since the session started are pushed to the typed published cells.
    // battle.map: the V construction map dict with "tiles" = the typed published cells, rebuilt
    // when the terrain revision moves (NativeBattle._sync_terrain rewrites self.map tiles).
    J map_tiles;V map_v;int64_t map_revision=-1;
    void push_map_edits(){
        if(!map_v.is_dict()||map_tiles.is_null())return;
        const J now=vj(map_v.get(V("tiles"),V::list({})));
        for(size_t r=0;r<now.size()&&r<map_tiles.size();++r)for(size_t c=0;c<now[r].size()&&c<map_tiles[r].size();++c)
            if(now[r][c]!=map_tiles[r][c])session->fixture_tile(int64_t(r),int64_t(c),now[r][c]);
        map_tiles=now;
    }
    V typed_map(){
        const int64_t revision=session->terrain_revision();
        if(map_v.is_dict()&&revision==map_revision)return map_v;
        push_map_edits();
        map_tiles=session->map_tiles();
        V m=V::dict();const V base=pvz::getattr(native,Sym("map"),V::none());
        if(base.is_dict())for(auto& kv:base.kv())m.at(kv.first)=kv.second;
        // Only co-op has a running daylight cycle. PvP/PvE retain the exact
        // admitted static environment, including absent optional keys.
        if(const auto night=session->coop_map_night()){
            V environment=py::dict_of(m.get(V("environment"),V::dict()));
            environment.at(V("night"))=V(*night);m.at(V("environment"))=environment;
        }
        m.at(V("tiles"))=jv(map_tiles);map_v=m;map_revision=revision;return map_v;
    }
    // g["ditu"] edits (whole-cell replacement or key writes) since the last projection.
    J ditu_seen;
    void push_ditu_edits(){
        if(!native_g.is_dict()||ditu_seen.is_null())return;
        const J now=vj(native_g.get(V("ditu"),V::list({})));
        for(size_t r=0;r<now.size()&&r<ditu_seen.size();++r)for(size_t c=0;c<now[r].size()&&c<ditu_seen[r].size();++c)
            if(now[r][c]!=ditu_seen[r][c])session->fixture_ditu(int64_t(r),int64_t(c),now[r][c]);
    }
    void changed(){fresh=false;native_fresh=false;players_fresh=false;if(players_out)sync_players();follow_records();}
    std::unordered_map<std::string,V> cards;  // resolved card dicts are immutable: shared V objects
    // Backend evidence: typed steps/commands run, and the V battle's own clocks at session start
    // (they must never move afterwards: the V battle is not stepped once the session exists).
    bool typed_ai_control=true;
    std::map<std::string,V> control_logs;   // audit evidence: last controller log per seat
    int64_t typed_steps=0,typed_commands=0,snapshot_projections=0,native_projections=0,ai_observations=0,ai_resets=0,ai_plans=0,ai_planner_resets=0,ai_controls=0;
    double v_tick_at_start=-1.,v_native_tick_at_start=-1.;
    // AppProfiler attachment points (battle.profiler / seat_profiler); typed steps do not call them.
    V profiler_v=V::none(),seat_profiler_v=V::none();
    const char* type_name()const override{return "NativeBattle";}
    bool isa(const char* name)const override{return std::strcmp(name,"NativeBattle")==0||std::strcmp(name,"object")==0;}
    void start(){
        if(session)return;
        const V mode=pvz::getattr(native,Sym("mode"),V::none());const std::string m=mode.is_none()?"duel":py_str(mode);
        if(m!="duel"&&m!="duo"&&m!="coop"&&m!="pve")throw PyError("NotImplementedError","typed battle backend does not support mode "+m);
        double seed=1.;
        std::string map_name="家院";
        // The battle_start event the V construction already logged names the map and the seed
        // (Simulation keeps no seed attribute; NativeBattle(..., seed=s) logs it here).
        try{const V first=rd(pvz::getattr(native,Sym("log")),V(0.0));const V name=first.get(V("map"),V::none());if(!name.is_none())map_name=py_str(name);
            const V s=first.get(V("seed"),V::none());if(!s.is_none())seed=s.num();}
        catch(const PyError&){
            const V map=pvz::getattr(native,Sym("map"),V::none());
            if(map.is_dict()){const V name=map.get(V("name"),V::none());if(!name.is_none())map_name=py_str(name);}
        }
        const auto started=std::chrono::steady_clock::now();
        v_tick_at_start=pvz::getattr(native,Sym("tick"),V(-1.0)).num();
        {const V engine=pvz::getattr(native,Sym("engine"),V::none());v_native_tick_at_start=engine.is_none()?-1.:pvz::getattr(engine,Sym("native_tick"),V(-1.0)).num();}
        session=Session::create(export_cold(native,seed),map_name);
        std::fprintf(stderr,"[typed72] battle session started: mode=%s cold_ms=%.1f\n",m.c_str(),
            std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count());
        std::vector<std::string> seats;for(const auto& s:py::iter_list(ai_seats).items())seats.push_back(py_str(s));
        session->set_ai_subsidy_seats(seats);
    }
    void refresh(){
    PVP_PROFILE_SCOPE("TypedBattle::refresh");
        if(fresh)return;
        static const bool direct=[]{const char* p=std::getenv("PVP742_FRAME");return !p||*p!='0';}();
        last_json=session->snapshot(!direct);++snapshot_projections;fresh=true;
        // Units carry their resolved card: convert each distinct card once.
        V units=V::list({});
        for(auto& u:last_json["units"]){
            J card=std::move(u["card"]);u.erase("card");V row=jv(u);
            const auto key=card.is_object()?card.value("id",std::string{})+"|"+card.value("side",std::string{}):card.dump();
            auto found=cards.find(key);if(found==cards.end())found=cards.emplace(key,jv(card)).first;
            row.at(V("card"))=found->second;units.append(row);
        }
        last_json.erase("units");
        last_snapshot=jv(last_json);last_snapshot.at(V("units"))=units;
        if(direct){
            PVP_PROFILE_SCOPE("TypedBattle::frame_projection");
            V frame=frame_projection.project(session->native_frame());
            if(std::getenv("PVP742_VERIFY_FRAME")&&vj(frame)!=session->reference_native_frame())throw PyError("AssertionError","native frame projection drift");
            last_snapshot.at(V("native_frame"))=frame;
        }
    }
    // Simulation.snapshot copy contract: players/result/events/rally/surrender are always deeply
    // detached (room privacy masking edits them); actors are deep copies, or per-actor shallow
    // copies with copy_state=False; the finished native frame is immutable and shared.
    V snapshot(bool include_map,bool copy_state=true){
    PVP_PROFILE_SCOPE("TypedBattle::snapshot");
        if(!session)return callm(native,Sym("snapshot"),Args({},{{Sym("include_map"),V(include_map)},{Sym("copy_state"),V(copy_state)}}));
        refresh();
        V out=V::dict();
        for(const auto& kv:last_snapshot.kv()){
            const std::string key=py_str(kv.first);
            if(key=="native_frame"){out.at(kv.first)=kv.second;continue;}
            if(key=="units"||key=="projectiles"||key=="resources"){
                if(copy_state){out.at(kv.first)=py::deepcopy(kv.second);continue;}
                std::vector<V> rows;for(const auto& row:py::iter_list(kv.second).items())rows.push_back(row.is_dict()?py::dict_of(row):row);
                out.at(kv.first)=V::list(rows);continue;
            }
            out.at(kv.first)=py::deepcopy(kv.second);
        }
        if(include_map)out.at(V("map"))=py::deepcopy(typed_map());   // deepcopy(self.map)
        return out;
    }
    static bool own_method(const std::string& n){return n=="step"||n=="snapshot"||n=="command_input"||n=="clear_input"||n=="close"||n=="placement"||n=="backend_audit"||n=="tutorial_sleep_grave"||n=="grave_awake"||n=="_sync_public"||n=="fixture_place_zombie"||n=="fixture_set_avatar"||n=="spawn"||n=="resource"||n=="_sync_terrain"||n=="line_of_sight"||n=="distance"||n=="ai_observe"||n=="reset_ai_observation"||n=="ai_plan"||n=="reset_ai_planner"||n=="ai_control"||n=="reset_ai_controller"||n=="ai_control_log"||n=="ai_tick";}
    // Methods are always the adapter's: a bound lookup (getattr(battle, "step")) must never
    // reach the V battle's methods, or the V battle would run the dynamic path.
    V bound(Sym name){
        auto self=std::static_pointer_cast<TypedBattle>(shared_from_this());
        return V::func([self,name](const Args& a){V out;if(!self->call_method(name,a,out))throw PyError("AttributeError",name.str());return out;});
    }
    V method(Sym name)override{return own_method(name.str())?bound(name):V();}
    static bool tracing(){static const bool on=std::getenv("TYPED72_TRACE")!=nullptr;return on;}
    V property(Sym name,bool& found)override{
        const std::string& n=name.str();found=true;
        if(tracing())std::fprintf(stderr,"[typed72] attr %s\n",n.c_str());
        if(own_method(n))return bound(name);
        // Capability lookup/reset during cold drafting must not start a battle.
        if(n=="typed_ai_observation"||n=="typed_ai_plan")return V(true);
        if(n=="typed_ai_control")return V(typed_ai_control);
        if(!session){
            if(n=="ai_subsidy_seats")return ai_seats;
            // Live dynamic containers are the typed battle's: handing out the V battle's dicts
            // would leave the caller holding state that the typed session never reads.
            static const std::set<std::string> live{"players","units","avatars","hero_states","g","_native_objects","resources","events",
                "rally_point","surrender_requests","director","commands","command"};
            if(!live.count(n))return pvz::getattr(native,name);
            start();
        }
        if(n=="tick")return V(double(session->tick()));
        if(n=="result")return jv(session->result_json());
        if(n=="players"){push_player_edits();if(!players_fresh)sync_players();players_out=true;return players_v;}
        if(n=="deathmatch")return V(session->clock().deathmatch);
        if(n=="terrain_revision")return V(double(session->terrain_revision()));
        // NativeBattle.units: the public unit dicts by id (the snapshot's unit list, same objects).
        if(n=="units"){refresh();V by_id=V::dict();for(const auto& u:py::iter_list(last_snapshot.get(V("units"),V::list({}))).items())by_id.at(u.get(V("id"),V::none()))=u;return by_id;}
        // Simulation.events (bounded to 128) and the shared path command ("follow"/"attack").
        if(n=="events")return jv(session->events(128));
        if(n=="command"){refresh();return last_snapshot.get(V("command"),V("follow"));}
        if(n=="commands"){refresh();return last_snapshot.get(V("commands"),V::none());}
        if(n=="surrender_requests")return jv(session->surrender_requests_json());
        if(n=="g"){refresh_native();records_out=true;return native_g;}
        if(n=="avatars"){refresh_native();records_out=true;return native_avatars;}
        // NativeBattle.hero_states = dict(self.avatars) (native_battle.py:193): the same typed projection.
        if(n=="director"){
            // A bound typed wave director exists exactly when the snapshot carries team waves.
            refresh();const V team=last_snapshot.get(V("team"),V::none());
            if(team.is_none()||team.get(V("waves"),V::none()).is_none())return V::none();
            auto d=std::make_shared<TypedDirector>();TypedBattle* self=this;
            d->cold=pvz::getattr(native,Sym("director"),V::none());
            d->snapshot=[self]{self->refresh();return self->last_snapshot.get(V("team"),V::dict()).get(V("waves"),V::none());};
            return V::inst(d);
        }
        if(n=="scripted_spawn_budget"){
            auto b=std::make_shared<TypedSpawnBudget>();b->cold=pvz::getattr(native,Sym("scripted_spawn_budget"),V::none());
            return V::inst(b);
        }
        if(n=="hero_states"){refresh_native();records_out=true;return py::dict_of(native_avatars);}
        // Simulation.resources / rally_point: the public resource dicts by id and the shared rally point.
        if(n=="resources"){refresh();V by_id=V::dict();for(const auto& r:py::iter_list(last_snapshot.get(V("resources"),V::list({}))).items())by_id.at(r.get(V("id"),V::none()))=r;return by_id;}
        if(n=="rally_point"){refresh();return last_snapshot.get(V("rally_point"),V::none());}
        if(n=="_native_objects"){refresh_native();records_out=true;return native_objects;}
        // Performance report fields (pm_performance runtime_info / report), from the typed session.
        if(n=="native_cost_ratio"){const auto r=session->native_cost_ratio();return r?V(*r):V::none();}
        if(n=="profiler")return profiler_v;
        if(n=="seat_profiler")return seat_profiler_v;
        if(n=="capture_frames")return V(double(typed_steps));
        if(n=="capture_deferred")return V(0.0);
        if(n=="_frame"){refresh();return last_snapshot.get(V("native_frame"),V::none());}
        if(n=="sim_workers")return V(0.0);
        if(n=="candidate_scans")return V::list({});
        if(n=="log"){
            for(const size_t n=session->log_size();logged<n;++logged)log_cache.append(jv(session->log_entry(logged)));
            return log_cache;
        }
        if(n=="audit_error")return V("");
        if(n=="time")return V(session->clock().time);
        // The V battle never draws after the cold boundary: its recorder has no local pixels,
        // so the renderer replays snapshot["native_frame"] (typed) as usual.
        if(n=="recorder")return pvz::getattr(native,name);
        if(n=="ai_subsidy_seats")return ai_seats;
        if(n=="backend")return V("typed72");
        if(n=="engine"){
            auto e=std::make_shared<TypedEngine>();TypedBattle* self=this;
            {const V engine=pvz::getattr(native,Sym("engine"),V::none());e->physics=engine.is_none()?V::none():pvz::getattr(engine,Sym("physics"),V::none());}
            {auto r=std::make_shared<TypedRng>();r->state=[self]{return self->session->rng_state();};e->rng=V::inst(r);}
            e->native_tick=[self]{return self->session->clock().native_tick;};
            return V::inst(e);
        }
        // Static construction attributes only; the V battle's dynamic state is never read.
        if(n=="map")return typed_map();
        if(n=="dt"||n=="rules"||n=="mode"||n=="seats"||n=="tile"||n=="width"||n=="height"||n=="seed"||n=="bans"||n=="graphics")return pvz::getattr(native,name);
        found=false;return V();
    }
    bool set_property(Sym name,const V& value)override{
        if(name.str()=="profiler"){profiler_v=value;return true;}
        if(name.str()=="time"||name.str()=="deathmatch"){
            // Simulation.time / deathmatch writes (tests): applied to the typed clock state.
            start();push_edits();J f=J::object();f[name.str()]=vj(value);session->fixture_clock(f);changed();return true;
        }
        if(name.str()=="seat_profiler"){seat_profiler_v=value;return true;}
        // Audit-only switch: keep AISeat on the typed-plan + V-controller reference path.
        if(name.str()=="typed_ai_control"){typed_ai_control=value.truthy();return true;}
        if(name.str()=="ai_subsidy_seats"){
            ai_seats=value;pvz::setattr(native,name,value);
            if(session){std::vector<std::string> seats;for(const auto& s:py::iter_list(value).items())seats.push_back(py_str(s));session->set_ai_subsidy_seats(seats);}
            return true;
        }
        return false;
    }
    // AISeat.send(side, kind, **data) as a typed controller output channel.
    std::map<std::string,VActivity> dynamic_v_work;std::map<std::string,uint64_t> dynamic_v_entries;
    void dynamic_v(const char* entry,const VActivity& before,const VActivity& excluded={}){
        const auto after=v_activity();auto& w=dynamic_v_work[entry];++dynamic_v_entries[entry];
        w.boxes+=after.boxes-before.boxes-excluded.boxes;w.calls+=after.calls-before.calls-excluded.calls;
        if(std::getenv("PVP_PURE_TYPED_STRICT")&&(after.boxes-before.boxes>excluded.boxes||after.calls-before.calls>excluded.calls))
            throw PyError("RuntimeError",std::string("pure-typed gate: V work inside typed dynamic entry ")+entry);
    }
    // V work the AI's input boundary (AISeat.send -> Room.command) did inside a typed AI tick.
    static inline thread_local VActivity ai_send_activity{};
    static Session::AiSend ai_forward(const V& send,const V& side){
        return [send,side](const std::string& kind,const ai::Args& data){
            const auto before=v_activity();
            struct Account{VActivity b;~Account(){const auto a=v_activity();ai_send_activity.boxes+=a.boxes-b.boxes;ai_send_activity.calls+=a.calls-b.calls;}} account{before};
            Args call({side,V(kind)});
            for(const auto& [k,v]:data){
                V value;
                if(std::holds_alternative<std::monostate>(v))value=V::none();
                else if(const auto* d=std::get_if<double>(&v))value=V(*d);
                else if(const auto* b=std::get_if<bool>(&v))value=V(*b);
                else if(const auto* t=std::get_if<std::string>(&v))value=V(*t);
                else throw PyError("TypeError","unsupported controller argument "+k);
                call.kw.emplace_back(Sym(k),value);
            }
            const V error=send.call(call);
            return error.truthy()?py_str(error):std::string{};   // `if not self.send(...)`
        };
    }
    // Key order is the Python dict's insertion order (see AiPlanR22).
    static V project_plan(const AiPlanR22& p){
        V d=V::dict();const auto num=[&](const char* k,double v){d.at(V(k))=V(v);};
        V priority=V::list();for(const auto& k:p.priority)priority.append(V(k));
        V quotas=V::dict();for(const auto& [k,q]:p.quotas)quotas.at(V(k))=V(q);
        d.at(V("priority"))=priority;d.at(V("quotas"))=quotas;
        if(p.side==typed72::Seat::plant){
            d.at(V("mode"))=V(p.mode.value());
            num("econ_goal",p.econ_goal);num("wall_goal",p.wall_goal);num("reserve",p.reserve);num("siege_gap",p.siege_gap);
            num("teleport_hp",p.teleport_hp);num("panic_value",p.panic_value);num("bomb_value",p.bomb_value);
            num("siege_step",p.siege_step);num("siege_dwell",p.siege_dwell);num("siege_lobs",p.siege_lobs);
            num("rich",p.rich);num("vine_reserve",p.vine_reserve);d.at(V("global_collect"))=V(p.global_collect);
        }else{
            num("grave_start",p.grave_start);num("grave_max",p.grave_max);num("grave_every",p.grave_every);num("save_horizon",p.save_horizon);
            num("wave_base",p.wave_base);num("wave_growth",p.wave_growth);num("wave_cap",p.wave_cap);num("wave_hold_max",p.wave_hold_max);
            num("teleport_hp",p.teleport_hp);num("tend_every",p.tend_every);num("detonate_value",p.detonate_value);
            if(p.save)d.at(V("save"))=V(*p.save);
            if(p.mode)d.at(V("mode"))=V(*p.mode);
        }
        return d;
    }
    bool call_method(Sym name,const Args& a,V& out)override{
        const std::string& n=name.str();
        // Simulation.snapshot reads self.players / avatars as edited, so it is a boundary too.
        if(session&&n!="backend_audit"&&n!="step"&&n!="command_input"&&n!="placement"&&n!="ai_observe"&&n!="reset_ai_observation"&&n!="ai_plan"&&n!="reset_ai_planner"&&n!="ai_control"&&n!="reset_ai_controller"&&n!="ai_control_log"&&n!="ai_tick")push_edits();
        if(tracing())std::fprintf(stderr,"[typed72] call %s\n",n.c_str());
        if(n=="step"){
            static const V one(1.0);const int steps=int(a.get(0,Sym("steps"),&one).num());
            start();push_edits();
            {const auto before=v_activity();
             for(int i=0;i<steps&&!session->finished();++i){session->step();++typed_steps;fresh=false;native_fresh=false;players_fresh=false;}
             dynamic_v("step",before);}
            if(players_out)sync_players();
            out=V::none();return true;
        }
        if(n=="snapshot"){
            static const V no(false);
            static const V yes(true);
            out=snapshot(a.get(0,Sym("include_map"),&no).truthy(),a.get(1,Sym("copy_state"),&yes).truthy());return true;
        }
        if(n=="command_input"){
            start();
            const std::string side=py_str(a.get(0,Sym("side"),nullptr));
            push_edits();
            {const V payload=a.get(1,Sym("payload"),nullptr);if(payload.is_dict()&&py_str(payload.get(V("type"),V("")))=="mark")push_map_edits();}
            const auto payload=vj(a.get(1,Sym("payload"),nullptr));std::string error;
            {const auto before=v_activity();error=session->command(side,payload);dynamic_v("command_input",before);}
            ++typed_commands;out=V(error);changed();return true;
        }
        if(n=="clear_input"){
            const std::string side=py_str(a.get(0,Sym("side"),nullptr));
            if(session){session->clear_input(side);changed();}else callm(native,Sym("clear_input"),Args{V(side)});
            out=V::none();return true;
        }
        if(n=="placement"){
            if(!session)start();push_edits();
            static const V none=V::none();
            const J r=session->placement(py_str(a.get(0,Sym("side"),nullptr)),py_str(a.get(1,Sym("key"),nullptr)),
                a.get(2,Sym("x"),nullptr).num(),a.get(3,Sym("y"),nullptr).num(),vj(a.get(4,Sym("grave_id"),&none)),vj(a.get(5,Sym("copy_id"),&none)));
            out=V::tuple({jv(r[0]),jv(r[1])});return true;
        }
        if(n=="tutorial_sleep_grave"){start();out=V(session->tutorial_sleep_grave(py_str(a.get(0,Sym("grave_id"),nullptr)),a.get(1,Sym("idle_seconds"),nullptr).num()));changed();return true;}
        if(n=="grave_awake"){start();out=V(session->grave_awake(py_str(a.get(0,Sym("grave_id"),nullptr))));return true;}
        if(n=="_sync_public"){start();session->sync_public();changed();out=V::none();return true;}
        if(n=="_sync_terrain"){
            // NativeBattle._sync_terrain after a g["ditu"] edit: the edited native records are
            // written into the typed terrain, then the public terrain is republished.
            start();push_ditu_edits();session->sync_public();changed();out=V::none();return true;
        }
        if(n=="fixture_place_zombie"){start();const V pos=a.get(1,Sym("position"),nullptr);out=V(session->fixture_place_zombie(py_str(a.get(0,Sym("unit_id"),nullptr)),pos.idx(0).num(),pos.idx(1).num(),a.get(2,Sym("facing"),nullptr).num()));changed();return true;}
        if(n=="fixture_set_avatar"){start();session->fixture_set_avatar(py_str(a.get(0,Sym("side"),nullptr)),vj(a.get(1,Sym("state"),nullptr)));changed();out=V::none();return true;}
        if(n=="spawn"){
            // NativeBattle.spawn(card, side, x, y, facing=1, temporary=False): the typed admission;
            // returns the public unit (or None), as the V helper returns self.units[id].
            start();static const V one(1.0),no(false);
            const V card=a.get(0,Sym("card"),nullptr);const std::string key=card.is_dict()?py_str(card.get(V("id"),V(""))):py_str(card);
            const auto id=session->spawn(key,py_str(a.get(1,Sym("side"),nullptr)),a.get(2,Sym("x"),nullptr).num(),a.get(3,Sym("y"),nullptr).num(),
                a.get(4,Sym("facing"),&one).num(),a.get(5,Sym("temporary"),&no).truthy());
            changed();
            if(!id){out=V::none();return true;}
            refresh();out=V::none();for(const auto& u:py::iter_list(last_snapshot.get(V("units"),V::list({}))).items())if(py_str(u.get(V("id"),V("")))==*id){out=u;break;}
            return true;
        }
        if(n=="resource"){
            // NativeBattle.resource(side, amount, x, y, source): the typed resource admission.
            start();
            const auto id=session->create_resource(py_str(a.get(0,Sym("side"),nullptr)),a.get(1,Sym("amount"),nullptr).num(),
                a.get(2,Sym("x"),nullptr).num(),a.get(3,Sym("y"),nullptr).num(),py_str(a.get(4,Sym("source"),nullptr)));
            changed();out=V(id);return true;
        }
        if(n=="line_of_sight"||n=="distance"){
            // Simulation.distance / line_of_sight (simulation.py:204-210): geometry over two public
            // dicts and the published map tiles (self.map), as in V.
            start();const V a0=a.get(0,Sym("a"),nullptr),b0=a.get(1,Sym("b"),nullptr);
            const double width=pvz::getattr(native,Sym("width")).num(),tile=pvz::getattr(native,Sym("tile")).num();
            const auto num=[](const V& d,const char* k,double dflt){const V v=d.get(V(k),V::none());return v.is_none()?dflt:v.num();};
            const auto pmod=[](double x,double m){const double r=std::fmod(x,m);return r!=0.&&((r<0.)!=(m<0.))?r+m:r;};
            const auto wrap=[&](double from,double to){return pmod(to-from+width/2.,width)-width/2.;};
            const double ax=num(a0,"x",0.),ay=num(a0,"y",0.),ah=num(a0,"h",0.),bx=num(b0,"x",0.),by=num(b0,"y",0.),bh=num(b0,"h",0.);
            const double dx=wrap(ax,bx);
            if(n=="distance"){out=V(std::hypot(dx,(ay-ah/2.)-(by-bh/2.)));return true;}
            const double dy=(by-bh/2.)-(ay-ah/2.);
            const V tiles=typed_map().get(V("tiles"),V::list({}));const auto rows=py::iter_list(tiles);
            const auto solid=[&](double x,double y){
                const auto row=int64_t(std::floor(y/tile)),col=int64_t(std::floor(pmod(x,width)/tile));
                if(row<0)return false;if(row>=int64_t(rows.len()))return true;
                const V line=rows.idx(row);const auto n=int64_t(line.len());return line.idx(int64_t(pmod(double(col),double(n)))).get(V("solid"),V(false)).truthy();
            };
            const int64_t steps=std::max<int64_t>(1,int64_t(std::hypot(dx,dy)/12.));bool clear=true;
            for(int64_t i=1;i<steps&&clear;++i)if(solid(ax+dx*double(i)/double(steps),ay-ah/2.+dy*double(i)/double(steps)))clear=false;
            out=V(clear);return true;
        }
        if(n=="ai_observe"||n=="reset_ai_observation"){
            const auto seat=typed72::known_seat(py_str(a.get(0,Sym("seat"),nullptr)));
            if(!seat)throw PyError("ValueError","unknown AI observation seat");
            if(n=="reset_ai_observation"){
                if(session){session->reset_ai_observation(*seat);++ai_resets;}
                out=V::none();return true;
            }
            start();push_edits();static const V zero(0.);
            const auto packet=session->ai_observe(*seat,int64_t(a.get(1,Sym("match_id"),&zero).num()));
            ++ai_observations;
            // Transitional output boundary only: the observation and shot algorithms above
            // ran on typed authoritative objects. The r22 planner/controller remains V.
            V observation=jv(J(typed72::encode_ai_observation(packet.observation)));
            const auto counts=[](const typed72::AiCardCounts& source){V d=V::dict();for(const auto& [key,n]:source)d.at(V(key))=V(double(n));return d;};
            observation.at(V("own_card_counts"))=counts(packet.own_counts);
            observation.at(V("team_card_counts"))=counts(packet.team_counts);
            V shots=V::list();
            for(const auto& shot:packet.visible_shots){
                V row=V::dict();row.at(V("id"))=V(shot.id);row.at(V("side"))=V(std::string(typed72::seat_name(shot.side)));
                row.at(V("asset"))=V(shot.asset);row.at(V("x"))=V(shot.position.x);row.at(V("y"))=V(shot.position.y);
                row.at(V("vx"))=V(shot.velocity.x);row.at(V("vy"))=V(shot.velocity.y);row.at(V("gravity"))=V(shot.gravity);
                row.at(V("damage"))=V(shot.damage);row.at(V("damage_estimated"))=V(shot.damage_estimated);
                row.at(V("slow"))=V(shot.slow);row.at(V("control"))=V(shot.control);shots.append(row);
            }
            out=V::dict();out.at(V("observation"))=observation;out.at(V("projectiles"))=shots;
            out.at(V("shots_seen"))=V(double(packet.shots_seen));return true;
        }
        if(n=="ai_plan"||n=="reset_ai_planner"){
            const auto seat=typed72::known_seat(py_str(a.get(0,Sym("seat"),nullptr)));
            if(!seat)throw PyError("ValueError","unknown AI planner seat");
            if(n=="reset_ai_planner"){
                // A cold (draft) agent rebuild must not start the battle session.
                if(session){session->reset_ai_planner(*seat);++ai_planner_resets;}
                out=V::none();return true;
            }
            start();push_edits();static const V no(false);
            const auto plan=session->ai_plan(*seat,a.get(1,Sym("recovering"),&no).truthy());
            ++ai_plans;
            // Transitional output boundary: the strategy ran typed; the r22 controller
            // that executes the plan is still V, so the plan crosses as its dict.
            out=project_plan(plan);return true;
        }
        if(n=="ai_tick"){
            // One AISeat control tick of the shipped r22 seat AI, entirely typed:
            // observation, the plan when due, then the controller. No V projection.
            const auto seat=typed72::known_seat(py_str(a.get(0,Sym("seat"),nullptr)));
            if(!seat)throw PyError("ValueError","unknown AI seat");
            static const V zero(0.),no(false);
            const auto match=int64_t(a.get(1,Sym("match_id"),&zero).num());
            const bool replan=a.get(2,Sym("replan"),&no).truthy();
            const V send=a.get(3,Sym("send"),nullptr);
            start();push_edits();
            const V side(std::string(typed72::seat_name(typed72::team_of(*seat))));
            const auto before=v_activity();ai_send_activity={};
            (void)session->ai_observe(*seat,match);++ai_observations;
            std::optional<AiPlanR22> plan;
            if(replan){plan=session->ai_plan(*seat,session->ai_controller_recovering(*seat));++ai_plans;}
            const auto& log=session->ai_control(*seat,"r22",ai_forward(send,side));
            dynamic_v("ai_tick",before,ai_send_activity);
            ++ai_controls;fresh=false;native_fresh=false;players_fresh=false;
            V d=V::dict();for(const auto& [k,v]:log)d.at(V(k))=V(v);
            control_logs[std::string(typed72::seat_name(*seat))]=d;
            out=plan?project_plan(*plan):V::none();return true;
        }
        if(n=="ai_control_log"){
            const auto found=control_logs.find(py_str(a.get(0,Sym("seat"),nullptr)));
            out=found==control_logs.end()?V::dict():found->second;return true;
        }
        if(n=="ai_control"||n=="reset_ai_controller"){
            const auto seat=typed72::known_seat(py_str(a.get(0,Sym("seat"),nullptr)));
            if(!seat)throw PyError("ValueError","unknown AI controller seat");
            if(n=="reset_ai_controller"){if(session)session->reset_ai_controller(*seat);out=V::none();return true;}
            start();push_edits();
            const std::string layer=py_str(a.get(1,Sym("layer"),nullptr));
            const V send=a.get(2,Sym("send"),nullptr);
            const V side(std::string(typed72::seat_name(typed72::team_of(*seat))));
            // Every controller input leaves through the caller's send(side, kind, **data)
            // (AISeat.send -> Room.command), so the room validates and records it.
            Session::AiSend forward=ai_forward(send,side);
            const auto& log=session->ai_control(*seat,layer,forward);
            ++ai_controls;fresh=false;native_fresh=false;players_fresh=false;
            V d=V::dict();for(const auto& [k,v]:log)d.at(V(k))=V(v);
            control_logs[std::string(typed72::seat_name(*seat))]=d;
            out=d;return true;
        }
        if(n=="backend_audit"){
            if(a.has_kw(Sym("reset_function_profile"))&&a.get(0,Sym("reset_function_profile"),nullptr).truthy())function_profile::reset();
            V d=V::dict();d.at(V("backend"))=V("typed72");d.at(V("session"))=V(bool(session));
            if(session)d.at(V("performance"))=jv(session->performance_counters());
            // PvP73 pure-typed gate: V boxes/calls made inside the dynamic entry points (must stay 0).
            {V g=V::dict();for(const auto& [k,v]:dynamic_v_work){V e=V::dict();e.at(V("boxes"))=V(double(v.boxes));e.at(V("calls"))=V(double(v.calls));e.at(V("entries"))=V(double(dynamic_v_entries[k]));g.at(V(k))=e;}
             d.at(V("dynamic_v_work"))=g;}
            {const auto all=v_activity();V tot=V::dict();tot.at(V("boxes"))=V(double(all.boxes));tot.at(V("calls"))=V(double(all.calls));d.at(V("v_activity_total"))=tot;}
            d.at(V("typed_steps"))=V(double(typed_steps));d.at(V("typed_commands"))=V(double(typed_commands));
            d.at(V("typed_tick"))=V(session?double(session->tick()):-1.);
            d.at(V("snapshot_projections"))=V(double(snapshot_projections));
            d.at(V("frame_descriptions"))=V(double(frame_projection.descriptions));
            d.at(V("frame_description_hits"))=V(double(frame_projection.hits));
            d.at(V("native_projections"))=V(double(native_projections));
            d.at(V("ai_observations"))=V(double(ai_observations));d.at(V("ai_resets"))=V(double(ai_resets));
            d.at(V("ai_plans"))=V(double(ai_plans));d.at(V("ai_controls"))=V(double(ai_controls));d.at(V("ai_planner_resets"))=V(double(ai_planner_resets));
            // Audit evidence only: typed planner memory mode and branch counters per seat.
            V notes=V::dict();
            if(session)for(const char* name:{"plant","plant2","zombie","zombie2"}){
                const auto seat=typed72::known_seat(name);if(!seat)continue;
                const auto* planner=session->ai_planner(*seat);if(!planner)continue;
                V row=V::dict();for(const auto& [k,n]:planner->notes())row.at(V(k))=V(double(n));
                row.at(V("mode"))=V(planner->mode());notes.at(V(name))=row;
            }
            d.at(V("ai_planner_notes"))=notes;
            d.at(V("v_tick_at_start"))=V(v_tick_at_start);d.at(V("v_tick_now"))=pvz::getattr(native,Sym("tick"),V(-1.0));
            {const V engine=pvz::getattr(native,Sym("engine"),V::none());d.at(V("v_native_tick_at_start"))=V(v_native_tick_at_start);
             d.at(V("v_native_tick_now"))=engine.is_none()?V(-1.0):pvz::getattr(engine,Sym("native_tick"),V(-1.0));}
            out=d;return true;
        }
        if(n=="close"){session.reset();callm(native,Sym("close"),Args{});out=V::none();return true;}
        return false;
    }
};
}
const char* battle_backend(){return "typed72";}
void start_battle_session(const V& battle){
    if(!battle.is_inst())return;
    if(auto* typed=dynamic_cast<TypedBattle*>(battle.box->inst.get()))typed->start();
}
V wrap_battle(const V& native_battle){
    auto p=std::make_shared<TypedBattle>();p->native=native_battle;
    return V::inst(p);
}
} // namespace pvz::typed72app
