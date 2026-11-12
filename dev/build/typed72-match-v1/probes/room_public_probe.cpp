#include "sim/typed/room_public_codec.h"
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
namespace {
using J=WireObject;
template<class T>void read_field(Field<T>& out,const J& obj,const char* key){const auto it=obj.find(key);if(it==obj.end())out.erase();else if(it->is_null())out.set_null();else out.set(it->get<T>());}
Seat seat(const std::string& name){const auto s=known_seat(name);if(!s)throw std::invalid_argument("invalid fixture seat");return *s;}
J point(Point p){return J::array({p.x,p.y});}
#include "room_native_pose_fixture.inc"
void terrain_read(TerrainCell& cell,const J& raw){read_field(cell.block,raw,"方块");read_field(cell.inner_block,raw,"里方块");
#define READ(n,k) read_field(cell.n,raw,k);
    PVZ72_TILE_NUMBERS(READ)
    PVZ72_TILE_FLAGS(READ)
#undef READ
}
struct PublicProbe:RoomPublicServices {
    TypedBattleState world;RoomState room;RoomPublicState published;EconomyState economy;GraveIdleRules grave_rules;GraveClock graves{world,economy,grave_rules};TargetSight sight;
    std::shared_ptr<std::vector<std::string>> secrets=std::make_shared<std::vector<std::string>>();RoomPublicSync syncer{world,room,published,graves,sight,*this,secrets};
    std::vector<NativeObject> objects;std::vector<J> raw_objects;std::vector<RoomRegistrationView> metadata;std::vector<std::vector<std::pair<std::string,double>>> speeds;
    std::unordered_map<const void*,size_t> indexes;std::unordered_map<std::string,std::shared_ptr<RoomPublicCard>> cards;J raw_cards,trace=J::array();std::vector<Cell> heads;std::vector<Seat> seats;
    std::set<std::string> banned;std::set<int64_t> current_belts;size_t uid=0;bool raging=false,first=false,include_native_pose=false;
    size_t index(const NativeObject& o)const{return std::visit([&](const auto& p){return indexes.at(p.get());},o);}
    std::string id(const NativeObject& o)const{return std::visit([](const auto& p){return p->source.id.or_missing(std::string{});},o);}
    void harden(const PlantRef& p)override{trace.push_back({"harden",indexes.at(p.get())});}
    bool auto_register(const NativeObject& o,Seat s,const std::string& key,bool temporary)override{
        if(!cards.contains(key)||banned.contains(key))return false;auto& raw=raw_objects[index(o)];const auto existing=id(o);const std::string name=existing.empty()?"auto"+std::to_string(++uid):existing;
        raw["_pvp_id"]=name;raw["_pvp_card"]=key;raw["_pvp_owner"]=seat_name(s);raw["_pvp_temporary"]=temporary;raw["_pvp_max_hp"]=raw.value("植物血",raw.value("血量",0.));raw["_pvp_armor_max"]=raw.value("防具血量",0.);
        read_object(index(o));world.native_objects.set(name,o);trace.push_back({"register",index(o),key,seat_name(s),temporary});return true;
    }
    std::shared_ptr<const RoomPublicCard> unit_card(Seat,const std::string& key)override{return cards.at(key);}
    bool base_producer(const std::string& key)const override{return cards.at(key)->producer;}
    RoomRegistrationView registration(const NativeObject& o)const override{auto facts=metadata.at(index(o));facts.secret_speed=speeds.at(index(o));return facts;}
    int jump_cap(Seat s)const override{return seat_index(s)%2?3:0;}
    RoomPublicHeroFacts hero_facts(Seat s)const override{return {100.+seat_index(s)*25.,10.+seat_index(s),seat_index(s)%2!=0,seat_index(s)==3};}
    bool rage()const override{return raging;}
    bool first_soldier()const override{return first;}
    void unit_gone(const NativeObject& o)override{trace.push_back({"gone",id(o)});}
    void death(const RoomPublicDeath& e)override{trace.push_back({"death",e.entity,e.card,seat_name(e.side)});}
    std::span<const Cell> head_only_cells()const override{return heads;}
    void set_belts(const std::set<int64_t>& belts)override{current_belts=belts;trace.push_back({"belts",belts});}
    void read_object(size_t i){
        const auto& raw=raw_objects[i];auto& facts=metadata[i];facts.registered_plant_max_hp=raw.value("_pvp_max_hp",0.);facts.plant_armor_max=raw.value("_pvp_armor_max",0.);facts.zombie_temporary=raw.value("_pvp_temporary",false);facts.floating=raw.value("_pvp_floating",false);facts.coop_dormant=raw.value("_pvp_coop_dormant",false);facts.first_soldier_used=raw.value("_pvp_zs_first_used",false);speeds[i].clear();const auto bonuses=raw.value("_pvp_zs_speed",J::object());for(const auto& [key,v]:bonuses.items())speeds[i].emplace_back(key,v.get<double>());
        std::visit([&](auto& ref){auto& s=ref->source;read_field(s.id,raw,"_pvp_id");read_field(s.owner,raw,"_pvp_owner");read_field(s.content,raw,"_pvp_content");read_field(s.charmed,raw,"魅惑");s.seat=raw.contains("_pvp_seat")?std::optional<Seat>(seat(raw["_pvp_seat"])):std::nullopt;read_field(ref->protection.card,raw,"_pvp_card");ref->protection.grave=raw.value("_pvp_grave",false);ref->protection.hero=raw.value("_pvp_hero",false);},objects[i]);
        if(auto* plant=std::get_if<PlantRef>(&objects[i])){auto& p=**plant;p.source.plant.set(raw.at("植物"));const auto xy=raw.at("坐标");p.cell={xy[0],xy[1]};p.facing=raw.value("方向",1.);read_field(p.hp,raw,"植物血");read_field(p.max_hp,raw,"植物血上限");read_field(p.temporary,raw,"_pvp_temporary");read_field(p.sleep,raw,"睡觉");read_field(p.effect_done,raw,"_pvp_effect_done");read_field(p.copy_card,raw,"_pvp_copy_card");}
        else {auto& z=*std::get<ZombieRef>(objects[i]);z.body.kind=raw.at("僵尸");const auto m=raw.at("位置");z.body.motion.get()={m[0],m[1],m[2],m[3]};z.body.hp=raw.value("血量",0.);z.body.facing=raw.value("方向",1.);z.body.armor_hp=raw.value("防具血量",0.);read_field(z.max_hp,raw,"_pvp_max_hp");read_field(z.armor_max,raw,"_pvp_armor_max");read_field(z.body.ice,raw,"冰冻");read_field(z.body.butter,raw,"黄油");read_field(z.body.stun,raw,"眩晕");read_field(z.native.emerged,raw,"出土");read_field(z.production_rate,raw,"_pvp_production_rate");read_field(z.mature,raw,"_pvp_mature");read_field(z.producer,raw,"_pvp_producer");read_field(z.idle,raw,"_pvp_idle");read_field(z.patch.torch_sleep_until,raw,"_pvp_torch_sleep_until");z.orphan_barrel=raw.value("_pvp_orphan_barrel",false);
            if(raw.contains("_pvp_poison")){auto p=std::make_shared<PoisonState>();read_field(p->level,raw["_pvp_poison"],"level");z.poison.poison.set(p);}else z.poison.poison.erase();}
    }
    void hero_read(Seat s,const J& raw){const auto i=seat_index(s);if(!world.heroes.heroes[i])world.heroes.heroes[i].emplace();if(!world.heroes.players[i])world.heroes.players[i].emplace();read_pose(*world.heroes.heroes[i],raw);world.heroes.players[i]->height=91.;world.heroes.players[i]->max_hp=40.;}
    void rosters(const J& op){
        if(op.contains("live")){world.plant_roster->clear();world.targets->clear();for(const auto& value:op["live"]){const auto& o=objects.at(value.get<size_t>());if(const auto* p=std::get_if<PlantRef>(&o))world.plant_roster->push_back(*p);else world.targets->push_back(CombatTarget::zombie(std::get<ZombieRef>(o)));}}
        if(op.contains("suspended")){world.suspended_graves.clear();for(const auto& value:op["suspended"])world.suspended_graves.push_back(std::get<ZombieRef>(objects.at(value.get<size_t>())));}
    }
    J snapshot(){J heroes=J::object(),units=J::array(),tiles=J::array(),ids=J::array();for(const auto s:seats){const auto& h=published.heroes.at(seat_index(s))->visible;heroes[std::string(seat_name(s))]={{"x",h.position.x},{"y",h.position.y},{"vx",h.velocity.x},{"vy",h.velocity.y},{"hp",h.hp},{"frozen",h.frozen},{"slowed",h.slowed},{"buttered",h.buttered},{"grounded",h.grounded},{"facing",h.facing},{"jumps",h.jumps},{"jump_cap",h.jump_cap},{"poison_level",h.poison},{"resource",h.resource},{"teleport_ready",h.teleport_ready},{"cannon_aimed",h.cannon_aimed},{"absent",h.absent}};if(include_native_pose)heroes[std::string(seat_name(s))]["native_pose"]=encode_native_pose(published.heroes.at(seat_index(s))->native_pose);}
        for(const auto& u:published.units)units.push_back(encode_public_unit(u,raw_cards.at(u.card->id)));for(const auto& row:published.terrain.tiles){J out=J::array();for(const auto& c:row)out.push_back(encode_public_terrain_cell(c));tiles.push_back(out);}for(const auto& entry:world.native_objects.entries())ids.push_back(entry.key);
        return {{"players",heroes},{"units",units},{"tiles",tiles},{"revision",published.terrain.revision},{"belts",current_belts},{"registry",ids},{"trace",trace},{"producer_lost",J::array({room.players[0].producer_lost,room.players[1].producer_lost,room.players[2].producer_lost,room.players[3].producer_lost})}};
    }
};
J run(const J& c){
    PublicProbe p;p.include_native_pose=c.value("include_native_pose",false);p.world.runtime.tile=c.value("tile",48.);p.world.world_width.set(c.value("width",960.));p.world.protection.secrets.enabled=c.value("zsecrets",false);p.raging=c.value("rage",false);p.first=c.value("first",false);*p.secrets=c.value("secrets",std::vector<std::string>{});
    p.raw_cards=c.at("cards");for(const auto& [key,value]:p.raw_cards.items()){auto card=std::make_shared<RoomPublicCard>();card->id=key;card->name=value.value("name",std::string{});card->behavior=value.at("behavior");card->asset=value.value("asset",std::string{});card->cost=value.value("cost",0.);card->damage=value.value("damage",0.);card->producer=value.value("producer",false);card->flying=value.value("flying",false);card->mushroom=value.value("mushroom",false);if(value.contains("range")&&!value["range"].is_null())card->range=value["range"];p.cards.emplace(key,card);}p.banned=c.value("banned",std::set<std::string>{});
    p.world.terrain.empty_blocks=c.value("empty",std::vector<std::string>{"空"});for(const auto& row:c.at("tiles")){std::vector<TileRef> native;std::vector<RoomPublicCell> shown;std::vector<uint8_t> solid,water;for(const auto& raw:row){auto cell=std::make_shared<TerrainCell>();terrain_read(*cell,raw);native.push_back(cell);auto value=RoomPublicTerrain::project(*cell,p.world.terrain);solid.push_back(value.solid);water.push_back(value.water);shown.push_back(value);}p.world.terrain.grid.push_back(native);p.published.terrain.tiles.push_back(shown);p.sight.solid.push_back(solid);p.sight.water.push_back(water);}
    for(const auto& [name,raw]:c.at("heroes").items()){auto s=seat(name);p.seats.push_back(s);p.hero_read(s,raw);}
    p.raw_objects=c.at("objects").get<std::vector<J>>();p.metadata.resize(p.raw_objects.size());p.speeds.resize(p.raw_objects.size());
    for(const auto& raw:p.raw_objects){NativeObject o;if(raw.contains("植物")){const auto xy=raw.at("坐标");o=std::make_shared<CombatPlant>(raw.at("植物"),Cell{xy[0],xy[1]},raw.value("方向",1.));}else o=std::make_shared<CombatZombie>();std::visit([&](const auto& v){p.indexes[v.get()]=p.objects.size();},o);p.objects.push_back(o);p.read_object(p.objects.size()-1);}
    for(const auto& index:c.value("registered",J::array())){const auto& o=p.objects[index.get<size_t>()];p.world.native_objects.set(p.id(o),o);}p.rosters(c);J out=J::array();
    for(const auto& op:c.at("operations")){
        p.rosters(op);if(op.contains("tick"))p.world.heroes.tick=op["tick"];if(op.contains("heads")){p.heads.clear();for(const auto& xy:op["heads"])p.heads.push_back({xy[0],xy[1]});}
        if(op.contains("unit")){const auto i=op.at("unit").get<size_t>();const auto fields=op.value("set",J::object());for(const auto& [key,value]:fields.items())p.raw_objects[i][key]=value;for(const auto& key:op.value("erase",J::array()))p.raw_objects[i].erase(key.get<std::string>());p.read_object(i);}
        if(op.contains("hero"))p.hero_read(seat(op["hero"]),op.at("fields"));
        if(op.contains("cell")){const auto xy=op["cell"];terrain_read(p.world.terrain.native_at(xy[0],xy[1]),op.at("fields"));}
        if(op.contains("hero_mutate")){auto& h=*p.world.heroes.heroes[seat_index(seat(op.at("hero_mutate")))];h.frame.position.get()->x+=7.;h.frame.secrets.get()->push_back("mutation");h.avatar_source->id.set("changed");if(h.poison.present()&&!h.poison.is_null()&&h.poison.get()->layers.present()){h.poison.get()->level.set(9);h.poison.get()->layers.get()->front().second->until+=13.;}h.launch_attack=AttackIdentity::literal("changed");}
        if(op.value("publish",true))p.syncer.sync(p.seats,op.value("terrain",true));out.push_back(p.snapshot());
    }return out;
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: room_public72_probe input output");std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;while(std::getline(input,line))if(!line.empty())output<<run(J::parse(line)).dump()<<'\n';return input.bad()||!output?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
