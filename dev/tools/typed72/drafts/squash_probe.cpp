#define PVZ72_SERVICE_PROBE_EMBEDDED
#include "service_probe.cpp"
#include "sim/typed/squash_effects.h"
namespace {
struct SquashProbe:ServiceProbe,SquashCallbacks {
    SquashEffects squash;
    std::vector<std::optional<NativeAimTarget>> held;
    explicit SquashProbe(int64_t seed):ServiceProbe(seed),squash(battle,*this,collision){}
    void add_entity(std::string n,double f,Motion p)override{ChiliProbe::add_entity(std::move(n),f,p);}
    void clear_plant(Cell c)override{PlantProbe::clear(c);}
    void ash_zombie(size_t i)override{calls.push_back(J::array({"squash_ash",i}));before("squash_ash");chain.damage.ash(battle.targets->at(i));after("squash_ash");}
    void damage_zombie(size_t i,double d,double a)override{calls.push_back(J::array({"squash_damage",i,d,a}));before("squash_damage");chain.damage.ordinary(battle.targets->at(i),d,a);after("squash_damage");}
    void player_damage(double a)override{calls.push_back(J::array({"squash_player",a}));before("squash_player");ChiliProbe::damage_player(a);after("squash_player");}
    J id_json(RecordId id)const{try{return key_json(ChiliKey::object(id));}catch(const std::logic_error&){return {{"temporary",true}};}}
    void id_read(const J& j,const char* k,Field<RecordId>& f){if(j.contains(k)){if(j[k].is_null())f.set_null();else f.set(ChiliProbe::record(j[k]));}}
    void id_write(J& j,const char* k,const Field<RecordId>& f)const{if(f.present())j[k]=f.is_null()?J(nullptr):id_json(f.get());}
    void point_read(const J& j,const char* k,Field<Point>& f){if(j.contains(k)){if(j[k].is_null())f.set_null();else f.set(point(j[k]));}}
    void point_write(J& j,const char* k,const Field<Point>& f)const{if(f.present())j[k]=f.is_null()?J(nullptr):J::array({f.get().x,f.get().y});}
    SquashTargetRecord parse_record(const J& j){keys(j,{"kind","target_index","target_id","point","direction"});SquashTargetRecord r;read(j,"kind",r.kind);read(j,"target_index",r.index);read(j,"direction",r.direction);id_read(j,"target_id",r.identity);point_read(j,"point",r.point);return r;}
    Field<SquashTargetRecord> record_field(const J& j){Field<SquashTargetRecord> f;if(j.is_null())f.set_null();else f.set(parse_record(j));return f;}
    J record_json(const SquashTargetRecord& r)const{J j=J::object();write(j,"kind",r.kind);write(j,"target_index",r.index);write(j,"direction",r.direction);id_write(j,"target_id",r.identity);point_write(j,"point",r.point);return j;}
    SquashLock parse_lock(const J& j){keys(j,{"target_index","target_id","initial_speed","gravity","hit_t","direction","ahead_tiles","created","late_armed"});SquashLock l;
        read(j,"target_index",l.target_index);id_read(j,"target_id",l.target_id);read(j,"initial_speed",l.initial_speed);read(j,"gravity",l.gravity);read(j,"hit_t",l.hit_time);read(j,"direction",l.direction);read(j,"ahead_tiles",l.ahead_tiles);read(j,"created",l.created);read(j,"late_armed",l.late_armed);return l;}
    J lock_json(const SquashLock& l)const{J j=J::object();write(j,"target_index",l.target_index);id_write(j,"target_id",l.target_id);write(j,"initial_speed",l.initial_speed);write(j,"gravity",l.gravity);write(j,"hit_t",l.hit_time);write(j,"direction",l.direction);write(j,"ahead_tiles",l.ahead_tiles);write(j,"created",l.created);write(j,"late_armed",l.late_armed);return j;}
    void squash_fields(CombatZombie& u,const J& v){J other=v;other.erase("移速");other.erase("__pvz_sb_squash_zombie_used");fields(u,other);read(v,"移速",u.native.move_speed);read(v,"__pvz_sb_squash_zombie_used",u.patch.squash_used);}
    void squash_entity(Entity& e,const J& v){J other=v;for(const auto k:{"智能窝瓜","大坐","坐下","弹跳x","__pvz_sb_squash_zombie_entity","__pvz_sb_squash_zombie_friendly","__pvz_sb_squash_zombie_hit","__pvz_sb_squash_zombie_age","__pvz_sb_squash_zombie_target","__pvz_sb_source_zombie_id"})other.erase(k);entity_fields(e,other);auto& q=e.squash;
        read(v,"大坐",q.big_sit);read(v,"坐下",q.sit);read(v,"弹跳x",q.bounce_x);read(v,"__pvz_sb_squash_zombie_entity",q.zombie_entity);read(v,"__pvz_sb_squash_zombie_friendly",q.friendly);read(v,"__pvz_sb_squash_zombie_hit",q.hit);read(v,"__pvz_sb_squash_zombie_age",q.age);id_read(v,"__pvz_sb_source_zombie_id",q.source_zombie);
        if(v.contains("智能窝瓜")){if(v["智能窝瓜"].is_null())q.lock.set_null();else q.lock.set(parse_lock(v["智能窝瓜"]));}if(v.contains("__pvz_sb_squash_zombie_target"))q.target=record_field(v["__pvz_sb_squash_zombie_target"]);
    }
    J squash_entity_json(const EntityRef& e){auto j=service_entity(e);const auto& q=e->squash;write(j,"大坐",q.big_sit);write(j,"坐下",q.sit);write(j,"弹跳x",q.bounce_x);write(j,"__pvz_sb_squash_zombie_entity",q.zombie_entity);write(j,"__pvz_sb_squash_zombie_friendly",q.friendly);write(j,"__pvz_sb_squash_zombie_hit",q.hit);write(j,"__pvz_sb_squash_zombie_age",q.age);id_write(j,"__pvz_sb_source_zombie_id",q.source_zombie);
        if(q.lock.present())j["智能窝瓜"]=q.lock.is_null()?J(nullptr):lock_json(q.lock.get());if(q.target.present())j["__pvz_sb_squash_zombie_target"]=q.target.is_null()?J(nullptr):record_json(q.target.get());return j;}
    PlantZombieConfig squash_config(const J& op){auto c=*native_plant_zombie_config("倭瓜僵尸");const auto v=op.value("config",J::object());keys(v,{"jump_speed","fire_anim","missing"});read(v,"jump_speed",c.jump_speed);read(v,"fire_anim",c.fire_anim);for(const auto& k:v.value("missing",J::array())){if(k=="jump_speed")c.jump_speed.erase();else if(k=="fire_anim")c.fire_anim.erase();else throw std::invalid_argument("squash config");}return c;}
    J describe(const std::optional<NativeAimTarget>& t){if(!t)return nullptr;J kind="player",index=-1,obj=nullptr;if(const auto* p=std::get_if<PlantRef>(&t->object)){kind="plant";index=t->index;obj=id_json((*p)->identity);}else if(const auto* z=std::get_if<CombatTarget>(&t->object)){kind="zombie";index=t->index;obj=label(*z);}return J::array({kind,index,obj,J::array({t->captured_point.x,t->captured_point.y}),t->direction,t->angle});}
    J aim_json(const BallisticAim& a){if(!a.target)return J::array({nullptr,nullptr});const auto& t=*a.target;return J::array({J::array({t.index,id_json(t.identity),J::array({t.point.x,t.point.y}),t.direction}),J::array({a.velocity.x,a.velocity.y})});}
    static J solution_json(const std::optional<BallisticSolution>& s){return s?J::array({s->time,s->vx,s->vy}):J(nullptr);}
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="squash_unit"){keys(op,{"op","unit","values"});squash_fields(*units.at(op.at("unit").get<size_t>()),op.at("values"));}
        else if(action=="squash_entity_write"){keys(op,{"op","entity","values"});squash_entity(*births.at(op.at("entity").get<size_t>()),op.at("values"));}
        else if(action=="squash_roster"){keys(op,{"op","entities"});auto list=std::make_shared<EntityRoster>();for(const auto& i:op.at("entities"))list->push_back(births.at(i.get<size_t>()));visual.entities.replace(list);}
        else if(action=="squash_splash"){keys(op,{"op","enabled","index","width","catch"});try{result=squash.splash_secret(op.value("enabled",true),op.contains("index")&&!op["index"].is_null()?std::optional<int64_t>(op["index"].get<int64_t>()):std::nullopt,op.value("width",960.));}catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}}
        else if(action=="squash_solve"){keys(op,{"op","origin","point","velocity","speed","gravity","max_time"});result=solution_json(NativeBallistics::intercept(point(op.at("origin")),point(op.at("point")),point(op.at("velocity")),op.at("speed"),op.at("gravity"),op.value("max_time",95.)));}
        else if(action=="squash_candidate"){keys(op,{"op","origin","point","direction","scale","size"});const auto r=SquashEffects::candidate(point(op.at("origin")),point(op.at("point")),op.at("direction"),op.value("scale",48.),op.value("size",2.));result=r?J::array({r->first,r->second}):J(nullptr);}
        else if(action=="squash_velocity"){keys(op,{"op","target","direction"});const auto v=squash.ballistics.velocity(target(op.at("target")),op.value("direction",1.));result=J::array({v.x,v.y});}
        else if(action=="squash_resolve"){keys(op,{"op","record"});const auto r=squash.resolve(record_field(op.at("record")));result=J::array({r.kind?J(*r.kind):J(nullptr),nullptr,r.point?J::array({r.point->x,r.point->y}):J(nullptr)});if(r.target){J object;if(const auto* p=std::get_if<PlantRef>(&r.target->object))object=id_json((*p)->identity);else object=label(std::get<CombatTarget>(r.target->object));result[1]=J::array({r.target->index,object});}}
        else if(action=="squash_pick"||action=="squash_update"||action=="squash_spawn"){
            keys(op,{"op","unit","config","sourced","held","none","catch"});const auto u=units.at(op.at("unit").get<size_t>());try{const auto a=squash.pick(u);
                if(action=="squash_pick"){held.push_back(a.target);result=J::array({describe(a.target),J::array({a.center.x,a.center.y})});}
                else if(action=="squash_update"){if(op.value("sourced",true))squash.update(u,squash_config(op));else squash.raw_update(u,squash_config(op));}
                else{const auto t=op.value("none",false)?std::optional<NativeAimTarget>{}:op.contains("held")?held.at(op.at("held").get<size_t>()):a.target;result=op.value("sourced",true)?squash.spawn(u,t,a.center,squash_config(op)):squash.raw_spawn(u,t,a.center,squash_config(op));}
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(action=="squash_finish")squash.finish_entities();
        else if(action=="squash_pending")result=squash.pending();
        else if(action=="squash_tick")squash.update_entities();
        else if(action=="squash_kill"){keys(op,{"op","plant"});squash.kill_plant(plant_ref(op.at("plant").get<size_t>()));}
        else if(action=="squash_damage_unit"){keys(op,{"op","index","target","direction"});squash.damage_charmed(op.at("index").get<size_t>(),target(op.at("target")),op.value("direction",1.));}
        else if(action.starts_with("squash_")){
            keys(op,{"op","entity","squash","index","target","point","velocity","speed","direction","late","lock","record","impact_x","sourced","catch"});const auto e=births.at(op.at("entity").get<size_t>());
            try{if(action=="squash_ballistic_pick")result=aim_json(squash.ballistics.pick(e,op.value("squash",false)));
                else if(action=="squash_current")result=aim_json(squash.ballistics.current(e,op.at("index")));
                else if(action=="squash_locked")result=aim_json(squash.ballistics.squash_locked(e,parse_lock(op.at("lock"))));
                else if(action=="squash_apply"||action=="squash_compute"){const BallisticTarget t{op.value("index",int64_t(0)),ChiliProbe::record(op.at("target")),point(op.at("point")),op.value("direction",1.)};
                    if(action=="squash_apply")result=squash.apply_solution(e,t,point(op.at("velocity")),op.at("speed"),op.value("late",false));else {auto [s,g]=squash.ballistics.compute(e,t,point(op.at("velocity")),op.at("speed"));result=J::array({solution_json(s),g});}}
                else if(action=="squash_patch")squash.patch_entity(e);
                else if(action=="squash_enemy")result=squash.enemy(e);
                else if(action=="squash_damage_player"){if(!squash.damage_player(e,op.at("impact_x"),op.value("direction",1.)))result=false;}
                else if(action=="squash_hit"){const auto r=op.contains("record")?record_field(op["record"]):e->squash.target;if(op.value("sourced",true))squash.hit(e,r,op.at("impact_x"));else squash.raw_hit(e,r,op.at("impact_x"));}
                else throw std::invalid_argument("unknown squash operation");
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return ServiceProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override{
        ServiceProbe::extra_snapshot(row);row["squash_counts"]=J::array({squash.patches,squash.attacks,squash.damages});row["squash_units"]=J::array();for(const auto& u:units){J j=J::object();write(j,"移速",u->native.move_speed);write(j,"__pvz_sb_squash_zombie_used",u->patch.squash_used);row["squash_units"].push_back(std::move(j));}
        row["entities"]=J::array();row["effect_births"]=J::array();for(const auto& e:*visual.entities.list())row["entities"].push_back(squash_entity_json(e));for(const auto& e:births)row["effect_births"].push_back(squash_entity_json(e));
        row["velocity_observations"]=J::array();std::vector<uint64_t> ids;for(const auto& [id,value]:battle.ballistics.positions)ids.push_back(id);std::sort(ids.begin(),ids.end(),[&](auto a,auto b){return id_json({a}).dump()<id_json({b}).dump();});for(const auto id:ids){const auto& v=battle.ballistics.positions.at(id);row["velocity_observations"].push_back(J::array({id_json({id}),v.point.x,v.point.y,v.time}));}
    }
};
J run_squash(const J& j){SquashProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.at("services");base.erase("services");const auto sc=base.at("squash");base.erase("squash");const auto dc=base.value("death_config",J::object());base.erase("death_config");configure_doom(p,base);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);for(size_t i=0;i<sc.at("units").size();++i)p.squash_fields(*p.units.at(i),sc.at("units")[i]);p.operations(j.at("operations"));return p.states;}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: squash72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("squash fixture files");std::string line;while(std::getline(in,line))if(!line.empty())out<<run_squash(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("squash output");return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
