#include "sim/typed/plant_lookup.h"
#include "sim/typed/chili_effects.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
int64_t integer(double n){if(!std::isfinite(n)||n<=-0x1p63||n>=0x1p63)throw std::out_of_range("chili integer");return int64_t(n);}
std::optional<int64_t> optional_integer(const Field<double>& f){if(!f.present()||f.is_null())return {};try{return integer(f.get());}catch(const std::exception&){return {};}}
bool contains(const std::vector<ChiliKey>& values,const ChiliKey& key){return std::find(values.begin(),values.end(),key)!=values.end();}
ChiliKey player_marker(){return ChiliKey::text("__pvz_sb_player__");}
bool row_mode(const std::optional<FireRows>& rows){return rows&&!rows->empty();}
bool row_hit(const FireRows& rows,std::optional<int> row){return row&&rows.contains(*row);}
bool overlaps(double left,double right,double lo,double hi){return !(right<lo||left>hi);}
ChiliKey explosion(const Entity& e){return !e.chili.explosion.present()?ChiliKey::object(e.identity):e.chili.explosion.is_null()?ChiliKey{}:e.chili.explosion.get();}
}
RecordId ChiliEffects::identity(const CombatTarget& t)const{return t.is_hero()?world_.heroes.cached_proxy(t.hero).identity:t.unit->identity;}
const Motion& ChiliEffects::position(const CombatTarget& t)const{return t.is_hero()?*world_.heroes.cached_proxy(t.hero).position:t.unit->body.motion.get();}
ChiliHits ChiliEffects::hits(const EntityRef& e){if(!e->chili.hits.present())e->chili.hits.set(std::make_shared<std::vector<ChiliKey>>());return e->chili.hits.is_null()?ChiliHits{}:e->chili.hits.get();}
FlameBox ChiliEffects::box(const Entity& e,double scale)const {const auto& p=e.motion.get();const double y=p.y+scale*.22;return {p.x-scale*.68,p.x+scale*.68,y-scale*.95,y+scale*1.35};}
bool ChiliEffects::enemy_fire(const Entity& e)const {
    if(e.kind!="火")return false;const auto& c=e.chili;
    if(c.damage_mode.present()&&!c.damage_mode.is_null()){if(c.damage_mode.get()=="friendly")return false;if(c.damage_mode.get()=="enemy")return true;}
    if(flag(c.friendly_fire))return false;return flag(c.zombie_fire)||c.target_rows.present()||c.explosion.present();
}
FireRows ChiliEffects::target_rows(const Entity& e,double scale)const {
    const auto& c=e.chili;if(auto g=optional_integer(c.ground_row))return {*g-1};FireRows rows;
    if(c.target_rows.present()&&!c.target_rows.is_null()) {
        const auto& value=c.target_rows.get();
        if(const auto* list=std::get_if<std::vector<Field<double>>>(&value)){for(const auto& r:*list)if(auto n=optional_integer(r))rows.insert(*n);}
        else if(auto n=optional_integer(Field<double>(std::get<double>(value))))rows.insert(*n);
    }
    if(rows.empty()){if(auto r=optional_integer(c.row))rows.insert(*r);else if(scale>0.)rows.insert(integer(py::floordiv(e.motion.get().y,scale)));}return rows;
}
std::optional<FireSnap> ChiliEffects::snap(const EntityRef& e) {
    const double scale=world_.runtime.tile;if(scale<=0.)return {};auto& c=e->chili;auto& p=e->motion.get();
    int64_t row,col;
    if(!c.row.present()||c.row.is_null()){row=integer(py::floordiv(p.y,scale));c.row.set(double(row));}else row=integer(c.row.get());
    if(!c.col.present()||c.col.is_null()){col=chili_fire_column({p.x,p.y},scale);c.col.set(double(col));}else col=integer(c.col.get());
    const auto& map=world_.terrain;std::optional<int64_t> ground;
    const auto at=[&](int64_t y){return y<0||y>=map.rows()?TileRef{}:map.at(int(y),col);};
    if(map.rows()>0) {
        if(chili_ground(map,at(row)))ground=row;
        const auto start=std::max<int64_t>(0,std::min<int64_t>(row+1,map.rows()-1));
        for(auto y=start;y<map.rows()&&!ground;++y)if(chili_ground(map,at(y)))ground=y;
        if(!ground&&chili_ground(map,at(row)))ground=row;
    }
    if(ground){p.y=*ground*scale+scale*-1.08;c.ground_row.set(double(*ground));}else {p.y=row*scale;c.ground_row.set_null();}
    c.ground_y.set(p.y);p.vx=0.;p.vy=0.;if(e->gravity.present())e->gravity.set(0.);return FireSnap{row,col,ground,p.y};
}
bool ChiliEffects::launch_locked(std::optional<double> now)const {const auto until=number(world_.heroes.globals.chili_lock_until);return until>0.&&now.value_or(world_.native_time)<until;}
const Field<ChiliHits>& ChiliEffects::mark_player(const EntityRef& e) {
    auto& f=e->chili.hits;if(!f.present())f.set(std::make_shared<std::vector<ChiliKey>>());if(!f.is_null()&&!contains(*f.get(),player_marker()))f.get()->push_back(player_marker());return f;
}
void ChiliEffects::patch_fire(const EntityRef& e) {
    try {
        auto& c=e->chili;if(e->kind!="火"||flag(c.patched))return;const double scale=world_.runtime.tile;if(scale<=0.)return;
        const auto row=integer(py::floordiv(e->motion.get().y,scale)),col=chili_fire_column({e->motion.get().x,e->motion.get().y},scale);
        c.patched.set(true);c.row.set(double(row));c.col.set(double(col));c.hits.set(std::make_shared<std::vector<ChiliKey>>());
        if(!flag(c.zombie_fire)&&(number(world_.heroes.globals.chili_launch)>0.||launch_locked()))mark_player(e);
        snap(e);++counters.patched;
    }catch(const std::exception&){}
}
std::optional<int> ChiliEffects::row_hint(const CombatTarget& target,bool force) {
    if(!target.is_hero())return update_chili_row_hint(world_.terrain,*target.unit,world_.runtime.tile,force);
    auto& p=world_.heroes.cached_proxy(target.hero);
    return update_chili_row_hint(world_.terrain,*p.position,p.gravity,p.chili_row_hint,world_.runtime.tile,force);
}
void ChiliEffects::update_hints(){const auto targets=*world_.targets;for(const auto& t:targets)try{calls_.row_hint(t,false);}catch(const std::exception&){};}
FireRows ChiliEffects::source_rows(const ZombieRef& zombie,std::optional<double> scale) {
    if(auto row=optional_integer(zombie->patch.chili_row_hint))return {*row};
    if(auto row=calls_.row_hint(CombatTarget::zombie(zombie),false))return {*row};
    if(auto row=chili_lane_row(world_.terrain,{zombie->body.motion.get().x,zombie->body.motion.get().y},scale.value_or(world_.runtime.tile)))return {*row};return {};
}
void ChiliEffects::launch_guard(std::optional<double> clock) {
    const double now=clock.value_or(world_.native_time);auto& g=world_.heroes.globals;const double launch=number(g.chili_launch),until=number(g.chili_lock_until);
    if(launch>0.&&until<=0.){g.chili_lock_until.set(now+4.);return;}
    if(until>0.&&now>=until){if(launch>0.){g.chili_launch.set(0.);if(g.position.present()&&!g.position.is_null()&&g.position.get()&&g.position.get()->vy<0.)g.position.get()->vy=0.;++counters.launch_timeout;}g.chili_lock_until.set(0.);}
}
void ChiliEffects::player_hit(const EntityRef& e,FlameBox b,double scale) {
    if(impacts_required_&&!impacts_)throw std::logic_error("missing required native content chili impacts");
    if(impacts_&&!impacts_->chili_player_launch(e))return;
    const auto list=hits(e);if(!list)throw std::invalid_argument("null chili player hit list");auto& hit=*list;const auto marker=player_marker();if(contains(hit,marker))return;
    if(e->chili.explosion.present()&&!e->chili.explosion.is_null()&&e->chili.explosion.get().is_text()){mark_player(e);return;}
    auto& g=world_.heroes.globals;if(!g.position.present()||g.position.is_null()||!g.position.get())return;const auto p=g.position.get();
    if(!overlaps(p->x-scale*.38,p->x+scale*.38,b.left,b.right)||!overlaps(p->y-scale*.95,p->y+scale*.20,b.top,b.bottom))return;
    if(launch_locked()){hit.push_back(marker);++counters.launch_block;return;}
    hit.push_back(marker);g.chili_launch.set(150.);g.chili_lock_until.set(world_.native_time+4.);world_.runtime.screen_shake.set({50.,0.,0.});world_.runtime.sound("戴夫疯狂",{});++counters.player_launch;
}
void ChiliEffects::damage_player(double center_x,FlameBox b,double scale,const ChiliKey& explosion_id,const std::optional<FireRows>& rows) {
    auto& g=world_.heroes.globals;if(g.mode.present()&&!g.mode.is_null()&&g.mode.get()=="我是僵尸")return;
    auto& f=world_.runtime.chili_player_hits;if(!f.present())f.set(std::make_shared<std::vector<ChiliKey>>());const auto ids=f.is_null()?ChiliHits{}:f.get();if(ids&&contains(*ids,explosion_id))return;
    if(!g.position.present()||g.position.is_null()||!g.position.get())return;const auto p=g.position.get();const double px=p->x,py=p->y;
    if(!overlaps(px-scale*.38,px+scale*.38,b.left,b.right))return;
    if(row_mode(rows)){if(!row_hit(*rows,chili_lane_row(world_.terrain,{px,py},scale)))return;}else if(!overlaps(py-scale*.95,py+scale*.20,b.top,b.bottom))return;
    if(ids){ids->push_back(explosion_id);if(ids->size()>256)ids->erase(ids->begin(),ids->begin()+128);}
    const auto before=g.hp;try{services_.damage_player(10.);}catch(const std::exception&){}
    if(before.present()&&!before.is_null()&&g.hp.present()&&!g.hp.is_null()&&g.hp.get()==before.get()){g.hp.set(before.get()-10.);g.hurt.set(1.);}
    p->vx+=(px>=center_x?1.:-1.)*500.*world_.runtime.plk;p->vy-=500.*world_.runtime.plk;g.hurt.set(1.);++counters.player_damage;
}
void ChiliEffects::hit_plants(const EntityRef& e,FlameBox b,double scale,const std::optional<FireRows>& rows) {
    const auto list=hits(e);if(!list)return;auto& hit=*list;const auto plants=*world_.plant_roster;
    for(const auto& p:plants)try {
        const auto id=ChiliKey::object(p->identity);if(contains(hit,id)||p->dead.present()||p->shovel_dead.present()||number(p->hp,1.)<=0.)continue;
        const auto visible=patch_plant_point(world_,*p);if(!visible)continue;const auto point=*visible;
        if(!overlaps(point.x-scale*.48,point.x+scale*.48,b.left,b.right))continue;
        if(row_mode(rows)){if(!rows->contains(p->cell.y))continue;}else if(!overlaps(point.y-scale*.62,point.y+scale*.42,b.top,b.bottom))continue;
        hit.push_back(id);p->hurt.set(1.);p->hp.set(0.);try{plants_.clear(p->cell);}catch(const std::exception&){p->dead.set(DeathMarker(true));}++counters.plant_damage;
    }catch(const std::exception&){}
}
bool ChiliEffects::hit_one(const EntityRef& entity,size_t index,const CombatTarget& target,std::vector<ChiliKey>& hits,FlameBox box,double scale,const std::optional<FireRows>& rows) {
    if(impacts_required_&&!impacts_)throw std::logic_error("missing required native content chili impacts");
    return impacts_?impacts_->chili_hit_one(*this,entity,index,target,hits,box,scale,rows):raw_hit_one(entity,index,target,hits,box,scale,rows);
}
bool ChiliEffects::raw_hit_one(const EntityRef&,size_t index,const CombatTarget& t,std::vector<ChiliKey>& hit,FlameBox b,double scale,const std::optional<FireRows>& rows) {
    const auto id=ChiliKey::object(identity(t));if(contains(hit,id))return false;const auto* proxy=t.is_hero()?&world_.heroes.cached_proxy(t.hero):nullptr;
    if((proxy?proxy->hp:t.unit->body.hp)<=0.)return false;const auto& p=position(t);const double size=std::max(.8,number(proxy?proxy->size:t.unit->body.size,2.));
    const double half=scale*std::max(.28,.18*size);if(!overlaps(p.x-half,p.x+half,b.left,b.right))return false;
    if(row_mode(rows)){if(!row_hit(*rows,chili_lane_row(world_.terrain,{p.x,p.y},scale)))return false;}else if(!overlaps(p.y-scale*.95*size,p.y+scale*.16,b.top,b.bottom))return false;
    hit.push_back(id);if(impacts_)impacts_->chili_ash(index);else damage_.ash(world_.targets->at(index));
    if(t.is_hero())world_.heroes.proxies.at(seat_index(t.hero))->ice.erase();else t.unit->body.ice.erase();return true;
}
void ChiliEffects::hit_zombies(const EntityRef& e,FlameBox b,double scale,bool charmed_only,const std::optional<FireRows>& rows) {
    const auto list=hits(e);if(!list)return;auto& hit=*list;const auto targets=*world_.targets;
    for(size_t i=0;i<targets.size();++i)try {const auto t=targets[i];if(charmed_only&&(t.is_hero()||!t.unit->source.charmed.present()))continue;
        if(hit_one(e,i,t,hit,b,scale,rows)){if(charmed_only)++counters.charmed_damage;else ++counters.unit_damage;}
    }catch(const std::exception&){}
}
void ChiliEffects::enemy_scan(const EntityRef& e,FlameBox b,double scale) {
    const auto rows=target_rows(*e,scale);if(!flag(e->chili.no_hero))damage_player(e->motion.get().x,b,scale,explosion(*e),rows);
    hit_plants(e,b,scale,rows);calls_.hit_zombies(e,b,scale,true,rows);
}
bool ChiliEffects::spawn_fire(const ZombieRef& zombie,bool friendly) {
    const auto& pos=zombie->body.motion.get();const double scale=world_.runtime.tile;if(scale<=0.)return false;const Point point{pos.x,pos.y};
    const auto entities=world_.runtime.entities.list();auto rows=source_rows(zombie,scale);const auto row=rows.empty()?integer(py::floordiv(point.y,scale)):*rows.begin();if(rows.empty())rows.insert(row);
    const double y=row*scale;const auto col=chili_fire_column({point.x,y},scale);size_t spawned=0;
    for(int dx=-7;dx<=7;++dx) {const auto before=entities->size();try {
        services_.add_entity("火",dx<0?-1.:1.,{(col+dx)*scale+scale,y,0.,0.});if(entities->size()<=before)continue;const auto e=entities->back();auto& c=e->chili;
        e->expires.set(std::max(120.,900.-std::abs(dx)*5.));c.zombie_fire.set(true);c.friendly_fire.set(friendly);c.damage_mode.set(friendly?"friendly":"enemy");c.explosion.set(ChiliKey::object(zombie->identity));
        std::vector<Field<double>> list;for(const auto r:rows)list.emplace_back(double(r));c.target_rows.set(std::move(list));patch_fire(e);
        try{const auto bounds=box(*e,scale);if(enemy_fire(*e))calls_.enemy_scan(e,bounds,scale);else if(flag(c.zombie_fire))calls_.hit_zombies(e,bounds,scale,false,target_rows(*e,scale));}catch(const std::exception&){}
        ++spawned;
    }catch(const std::exception&){}}
    if(spawned){world_.runtime.screen_shake.set({100.,0.,0.});world_.runtime.sound("辣椒",{point.x,point.y,0.,0.});++counters.explosions;}return spawned>0;
}
void ChiliEffects::scan() {
    if(impacts_required_&&!impacts_)throw std::logic_error("missing required native content chili impacts");
    const auto entities=world_.runtime.entities.list();const double scale=world_.runtime.tile;if(scale<=0.)return;update_hints();const auto snapshot=*entities;
    for(const auto& e:snapshot)try {
        if(e->kind!="火")continue;if(!flag(e->chili.patched))patch_fire(e);snap(e);const auto bounds=box(*e,scale);
        if(enemy_fire(*e)){calls_.enemy_scan(e,bounds,scale);continue;}
        std::optional<FireRows> rows;if(flag(e->chili.zombie_fire))rows=target_rows(*e,scale);
        calls_.player_hit(e,bounds,scale);calls_.hit_zombies(e,bounds,scale,false,rows);
    }catch(const std::exception&){}
}
} // namespace pvz::typed72
