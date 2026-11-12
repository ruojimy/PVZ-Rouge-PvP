#define PVZ72_DOOM_PROBE_EMBEDDED
#include "doom_probe.cpp"
#include "sim/typed/chili_effects.h"
namespace {
struct ChiliProbe : DoomProbe,ChiliServices,ChiliDispatch {
    ChiliEffects chili;
    J dispatch_calls=J::array();std::vector<ChiliHits> held_hits;
    explicit ChiliProbe(int64_t seed):DoomProbe(seed),chili(battle,damage,*this,*this,*this){}
    void add_entity(std::string n,double f,Motion p)override{DoomProbe::add_entity(std::move(n),f,p);}
    void damage_player(double amount)override{;;world.player_damage(amount);;}
    size_t entity_index(const EntityRef& e)const{for(size_t i=0;i<births.size();++i)if(births[i]==e)return i;throw std::logic_error("unknown flame entity");}
    J rows_json(const std::optional<FireRows>& rows)const{if(!rows)return nullptr;J j=J::array();for(auto n:*rows)j.push_back(n);return j;}
    std::optional<FireRows> rows(const J& op)const{if(!op.contains("rows")||op["rows"].is_null())return {};FireRows r;for(const auto& v:op["rows"])r.insert(v.get<int64_t>());return r;}
    FlameBox bounds(const J& op)const{const auto& b=op.at("box");return {b.at(0),b.at(1),b.at(2),b.at(3)};}
    J box_json(FlameBox b)const{return J::array({b.left,b.right,b.top,b.bottom});}
    std::optional<int> row_hint(const CombatTarget& t,bool force)override{;;auto result=chili.row_hint(t,force);;return result;}
    void enemy_scan(const EntityRef& e,FlameBox b,double s)override{;chili.enemy_scan(e,b,s);}
    void player_hit(const EntityRef& e,FlameBox b,double s)override{;chili.player_hit(e,b,s);}
    void hit_zombies(const EntityRef& e,FlameBox b,double s,bool charmed,const std::optional<FireRows>& r)override{;chili.hit_zombies(e,b,s,charmed,r);}
    RecordId record(const J& j) {
        keys(j,{"unit","plant","entity","hero"});
        if(j.contains("unit"))return units.at(j["unit"].get<size_t>())->identity;
        if(j.contains("plant"))return plant_ref(j["plant"].get<size_t>())->identity;
        if(j.contains("entity"))return births.at(j["entity"].get<size_t>())->identity;
        return world.proxy(parse_seat(j.at("hero").get<std::string>())).identity;
    }
    ChiliKey key(const J& j){if(j.is_null())return {};if(j.is_object())return ChiliKey::object(record(j));if(j.is_string())return ChiliKey::text(j.get<std::string>());return ChiliKey::number(j.is_boolean()?(j.get<bool>()?1.:0.):j.get<double>());}
    J key_json(const ChiliKey& k)const {
        if(const auto* n=std::get_if<double>(&k.value))return *n;if(const auto* s=std::get_if<std::string>(&k.value))return *s;if(std::holds_alternative<std::monostate>(k.value))return nullptr;
        const auto id=std::get<RecordId>(k.value);
        for(size_t i=0;i<units.size();++i)if(units[i]->identity==id)return {{"unit",i}};
        for(size_t i=0;i<births.size();++i)if(births[i]->identity==id)return {{"entity",i}};
        size_t i=0;for(auto handle:battle.plants.order()){if(battle.plants.at(handle)->identity==id)return {{"plant",i}};++i;}
        for(size_t seat=0;seat<world.proxies.size();++seat)if(world.proxies[seat]&&world.proxies[seat]->identity==id)return {{"hero",seat_name(Seat(seat))}};
        throw std::logic_error("unknown chili record identity");
    }
    void read_hits(const J& j,const char* n,Field<ChiliHits>& f){if(!j.contains(n))return;if(j[n].is_null()){f.set_null();return;}auto v=std::make_shared<std::vector<ChiliKey>>();for(const auto& k:j[n])v->push_back(key(k));f.set(v);}
    J hits_json(const ChiliHits& h)const{if(!h)return nullptr;J a=J::array();for(const auto& k:*h)a.push_back(key_json(k));return a;}
    void write_hits(J& j,const char* n,const Field<ChiliHits>& f)const{if(f.present())j[n]=f.is_null()?J(nullptr):hits_json(f.get());}
    void fire_fields(const J& j,Entity& e) {
        keys(j,{"智能辣椒火","智能火命中","智能火行","智能火列","智能火地面行","智能火地面","__pvz_sb_chili_zombie_fire","__pvz_sb_chili_zombie_friendly_fire","__pvz_sb_chili_zombie_explosion_id","__pvz_sb_chili_fire_target_rows","__pvz_sb_chili_fire_damage_mode","__pvz_sb_chili_fire_no_hero","牛顿","消亡","位置"});auto& c=e.chili;
        read(j,"智能辣椒火",c.patched);read(j,"智能火行",c.row);read(j,"智能火列",c.col);read(j,"智能火地面行",c.ground_row);read(j,"智能火地面",c.ground_y);
        read(j,"__pvz_sb_chili_zombie_fire",c.zombie_fire);read(j,"__pvz_sb_chili_zombie_friendly_fire",c.friendly_fire);read(j,"__pvz_sb_chili_fire_no_hero",c.no_hero);read(j,"__pvz_sb_chili_fire_damage_mode",c.damage_mode);
        read_hits(j,"智能火命中",c.hits);const char* id="__pvz_sb_chili_zombie_explosion_id";if(j.contains(id)){if(j[id].is_null())c.explosion.set_null();else c.explosion.set(key(j[id]));}
        const char* rs="__pvz_sb_chili_fire_target_rows";if(j.contains(rs)) {
            if(j[rs].is_null())c.target_rows.set_null();else if(j[rs].is_array()){std::vector<Field<double>> v;for(const auto& n:j[rs]){Field<double> f;if(n.is_null())f.set_null();else f.set(n.get<double>());v.push_back(f);}c.target_rows.set(std::move(v));}
            else c.target_rows.set(j[rs].get<double>());
        }
        read(j,"牛顿",e.gravity);read(j,"消亡",e.expires);if(j.contains("位置"))e.motion=motion(j["位置"]);
    }
    J fire_state(const EntityRef& e) {
        J j=entity(e);const auto& c=e->chili;write(j,"智能辣椒火",c.patched);write(j,"智能火行",c.row);write(j,"智能火列",c.col);write(j,"智能火地面行",c.ground_row);write(j,"智能火地面",c.ground_y);
        write(j,"__pvz_sb_chili_zombie_fire",c.zombie_fire);write(j,"__pvz_sb_chili_zombie_friendly_fire",c.friendly_fire);write(j,"__pvz_sb_chili_fire_no_hero",c.no_hero);write(j,"__pvz_sb_chili_fire_damage_mode",c.damage_mode);write_hits(j,"智能火命中",c.hits);
        if(c.explosion.present())j["__pvz_sb_chili_zombie_explosion_id"]=c.explosion.is_null()?J(nullptr):key_json(c.explosion.get());
        if(c.target_rows.present()) {J r=nullptr;if(!c.target_rows.is_null()){const auto& v=c.target_rows.get();if(const auto* n=std::get_if<double>(&v))r=*n;else {r=J::array();for(const auto& f:std::get<std::vector<Field<double>>>(v))r.push_back(f.is_null()?J(nullptr):J(f.get()));}}j["__pvz_sb_chili_fire_target_rows"]=std::move(r);}
        return j;
    }
    std::shared_ptr<AttackSource> selected_source(const J& op)override {return op.contains("entity_source")?source_ref(births.at(op["entity_source"].get<size_t>())):DoomProbe::selected_source(op);}
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="chili_scope") {
            keys(op,{"op","source","unit_source","entity_source","target","owner","phase","body"});HeroContext c(world,{parse_seat(op.at("target").get<std::string>()),parse_seat(op.at("owner").get<std::string>()),phase(op.value("phase",std::string("entities"))),selected_source(op),{}});operations(op.at("body"),false);c.close();
        }else if(action=="fixture_fire") {
            keys(op,{"op","name","facing","position","source","values"});add_entity(op.value("name",std::string("火")),op.value("facing",1.),motion(op.at("position")));auto e=births.back();
            if(op.contains("source")){J s=op["source"];s["名"]=e->kind;e->source=*source(s);}fire_fields(op.value("values",J::object()),*e);
        }else if(action=="fire_write") {
            keys(op,{"op","entity","values"});fire_fields(op.at("values"),*births.at(op.at("entity").get<size_t>()));
        }else if(action=="fire_globals") {
            keys(op,{"op","time","hits"});if(op.contains("time"))battle.native_time=op.at("time");read_hits(op,"hits",visual.chili_player_hits);
        }else if(action=="hold_fire_hits") {
            keys(op,{"op","entity"});const auto& f=births.at(op.at("entity").get<size_t>())->chili.hits;;
        }else if(action=="fire_plant_write") {
            keys(op,{"op","plant","values"});const auto& v=op.at("values");keys(v,{"死","铲死","植物血"});auto& p=*plant_ref(op.at("plant").get<size_t>());
            read_death(v,"死",p.dead);read_death(v,"铲死",p.shovel_dead);read(v,"植物血",p.hp);
        }else if(action=="fire_unit_write"||action=="fire_proxy_write") {
            keys(op,{"op","target","values"});const auto& v=op.at("values");keys(v,{"冰冻","牛顿","__pvz_sb_chili_zombie_row_hint"});
            if(action=="fire_unit_write"){auto& u=*units.at(op.at("target").get<size_t>());read(v,"冰冻",u.body.ice);read(v,"牛顿",u.body.gravity);read(v,"__pvz_sb_chili_zombie_row_hint",u.patch.chili_row_hint);}
            else{auto& p=world.proxy(parse_seat(op.at("target").get<std::string>()));read(v,"冰冻",p.ice);read(v,"牛顿",p.gravity);read(v,"__pvz_sb_chili_zombie_row_hint",p.chili_row_hint);}
        }else if(action.starts_with("fire_")) {
            keys(op,{"op","entity","unit","target","index","box","rows","scale","charmed_only","friendly","center_x","explosion","now","force","catch"});
            const auto e=op.contains("entity")?births.at(op["entity"].get<size_t>()):EntityRef{};const double s=op.value("scale",visual.tile);
            const auto now=op.contains("now")&&!op["now"].is_null()?std::optional<double>(op["now"].get<double>()):std::nullopt;
            try {
                if(action=="fire_enemy")result=chili.enemy_fire(*e);
                else if(action=="fire_rows")result=rows_json(chili.target_rows(*e,s));
                else if(action=="fire_snap"){if(const auto snap=chili.snap(e))result=J::array({snap->row,snap->col,snap->ground?J(*snap->ground):J(nullptr),snap->y});}
                else if(action=="fire_patch")chili.patch_fire(e);
                else if(action=="fire_spawn")result=chili.spawn_fire(units.at(op.at("unit").get<size_t>()),op.value("friendly",false));
                else if(action=="fire_scan")chili.scan();
                else if(action=="fire_hint"){if(auto r=chili.row_hint(target(op.at("target")),op.value("force",false)))result=*r;}
                else if(action=="fire_source_rows")result=rows_json(chili.source_rows(units.at(op.at("unit").get<size_t>()),op.contains("scale")?std::optional<double>(s):std::nullopt));
                else if(action=="fire_update_hints")chili.update_hints();
                else if(action=="fire_mark"){const auto& f=chili.mark_player(e);result=f.is_null()?J(nullptr):hits_json(f.get());}
                else if(action=="fire_launch_guard")chili.launch_guard(now);
                else if(action=="fire_launch_locked")result=chili.launch_locked(now);
                else if(action=="fire_player_hit")chili.player_hit(e,bounds(op),s);
                else if(action=="fire_damage_player")chili.damage_player(op.at("center_x"),bounds(op),s,key(op.at("explosion")),rows(op));
                else if(action=="fire_hit_plants")chili.hit_plants(e,bounds(op),s,rows(op));
                else if(action=="fire_hit_units")chili.hit_zombies(e,bounds(op),s,op.value("charmed_only",false),rows(op));
                else if(action=="fire_enemy_scan")chili.enemy_scan(e,bounds(op),s);
                else throw std::invalid_argument("unknown chili operation");
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return DoomProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        DoomProbe::extra_snapshot(row);row["entities"]=J::array();row["effect_births"]=J::array();for(const auto& e:*visual.entities.list())row["entities"].push_back(fire_state(e));for(const auto& e:births)row["effect_births"].push_back(fire_state(e));
        J g={{"time",battle.native_time}};write_hits(g,"player_hits",visual.chili_player_hits);row["chili_global"]=std::move(g);row["chili_dispatch"]=dispatch_calls;
        const auto& c=chili.counters;row["chili_counts"]=J::array({c.patched,c.explosions,c.unit_damage,c.charmed_damage,c.plant_damage,c.player_damage,c.player_launch,c.launch_block,c.launch_timeout});
        row["held_fire_hits"]=J::array();for(const auto& h:held_hits)row["held_fire_hits"].push_back(hits_json(h));
        row["chili_unit_fields"]=J::array();for(const auto& u:units){J v=J::object();write(v,"冰冻",u->body.ice);row["chili_unit_fields"].push_back(std::move(v));}
        row["chili_proxy_fields"]=J::object();for(size_t i=0;i<world.proxies.size();++i)if(world.proxies[i]){J v=J::object();write(v,"牛顿",world.proxies[i]->gravity);write(v,"__pvz_sb_chili_zombie_row_hint",world.proxies[i]->chili_row_hint);row["chili_proxy_fields"][seat_name(Seat(i))]=std::move(v);}
    }
};
J run_chili(const J& j){ChiliProbe p(j.value("seed",int64_t(1)));configure_doom(p,j);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_CHILI_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: chili72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("chili fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_chili(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("chili output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
