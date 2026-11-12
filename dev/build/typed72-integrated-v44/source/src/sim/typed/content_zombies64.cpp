#include "sim/typed/content_zombies64.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& field){return field.present() && !field.is_null() && field.get();}
bool text(const Field<std::string>& field){return field.present() && !field.is_null() && !field.get().empty();}
std::string content_name(const AttackSource& source){return text(source.content)?source.content.get():"";}
bool slime(std::string_view name){return name=="史莱姆僵尸" || name=="中型史莱姆" || name=="小型史莱姆";}
double factor(const Zombie& body) {
    if(body.ice.or_missing(0.)>1000. || body.butter.or_missing(0.)>0. || body.stun.or_missing(0.)>0.)return 0.;
    return body.ice.or_missing(0.)>0.?.5:1.;
}
Field<std::string> nullable_id(const AttackSource& source) {
    auto id=source.id;if(!id.present())id.set_null();return id;
}
bool id_less(const Field<std::string>& first,const Field<std::string>& second) {
    if(first.is_null() && second.is_null())return false;
    return first.or_missing("")<second.or_missing("");
}
struct BanExemption {
    int& count;
    explicit BanExemption(TypedBattleState& world):count(world.spawn_ban_exempt){++count;}
    ~BanExemption(){--count;}
};
}
bool ContentZombies64::configure(const ZombieRef& unit,std::string_view name,double hp,bool observed) {
    if(name!="红眼巨人" && !slime(name) && name!="传送带僵尸" && name!="掷弹兵僵尸")return false;
    const std::string configured_name(name);name=configured_name;
    unit->source.content.set(configured_name);unit->body.hp=hp;unit->max_hp.set(hp);
    unit->base_speed.set(unit->native.move_speed.or_missing(0.));
    if(observed)unit->patch.observed_max_hp.set(hp);
    auto& state=unit->content64;
    if(name=="红眼巨人") {
        unit->native.throw_imp.set(0.);unit->native.half_hp.set(hp/2.);state.throw_clock.set(0.);state.grab.set_null();
    }else if(slime(name)) {
        state.split.set(false);
        const auto carrier=unit->source.seat?*unit->source.seat:parse_seat(unit->source.owner.or_missing("zombie"));
        const auto& secrets=world_.heroes.players.at(seat_index(carrier)).value().secrets;
        state.sticky.set(std::find(secrets.begin(),secrets.end(),"zsecret:黏糊糊")!=secrets.end());
    }else if(name=="掷弹兵僵尸") {
        unit->grenadier.phase.set(GrenadierPhase::ready);unit->grenadier.clock.set(0.);unit->grenadier.seen_hp.set(hp);
    }
    return true;
}
std::string_view ContentZombies64::hand_kind(const CombatZombie& unit) {
    if(text(unit.content64.hand_kind))return unit.content64.hand_kind.get();
    if(unit.source.content.present() && !unit.source.content.is_null()) {
        if(unit.source.content.get()=="垃圾桶僵尸")return "垃圾桶";
        if(unit.source.content.get()=="传送带僵尸")return "传送带";
    }
    return unit.body.hand;
}
void ContentZombies64::gate(const ZombieRef& unit) {
    const auto name=content_name(unit->source);taunts_.apply(unit);
    if(slime(name) || name=="掷弹兵僵尸") {
        for(const auto part:{"-身","-首"})for(const auto suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"})
            services_.alias_art(unit->body.kind+part+suffix,"_pvp_content_blank");
        if(unit->body.butter.or_missing(0.)>0.)services_.alias_art("黄油砸","_pvp_content_blank");
    }else if(name=="红眼巨人") {
        for(const auto part:{"-身","-首"})services_.alias_art(std::string("巨人僵尸")+part,std::string("红眼巨人僵尸")+part);
    }else if(name=="传送带僵尸") {
        for(const auto part:{"-身","-首"})services_.alias_art(std::string("梯子僵尸")+part,std::string("传送带僵尸")+part);
    }
    if(unit->body.hand=="梯子" && hand_kind(*unit)=="传送带")services_.alias_art("梯子","传送带");
    const auto& phase=unit->grenadier.phase;
    if(name=="掷弹兵僵尸" && phase.present() && !phase.is_null() && phase.get()==GrenadierPhase::wind)
        unit->grenadier.hold_x.set(unit->body.motion.get().x);
    if(on_belt(unit))for(auto* field:{&unit->body.ice,&unit->body.butter,&unit->body.stun})
        if(field->or_missing(0.)>0.)field->set(0.);
}
bool ContentZombies64::on_belt(const ZombieRef& unit)const {
    if(belt_keys.empty() || unit->protection.grave)return false;
    const auto& p=unit->body.motion.get();const double tile=world_.runtime.tile;
    for(const double delta:{.1,-tile*.5,-tile*1.2}) {
        const auto row=int64_t(std::floor((p.y+delta)/tile));if(row<0 || row>=world_.terrain.rows())continue;
        const auto& line=world_.terrain.grid.at(size_t(row));
        if(line.empty())throw std::domain_error("empty conveyor terrain row");
        const auto col=int64_t(py::mod(std::floor(p.x/tile),double(line.size())));
        if(!belt_keys.contains(row*65536+col))continue;
        const auto& cell=*line.at(size_t(col));
        if(yes(cell.belt) && text(cell.block) && cell.block.get()=="梯子块")return true;
    }
    return false;
}
void ContentZombies64::tag_belt(std::string_view name,Point point) {
    if(name!="梯子块" || !world_.heroes.source_index || *world_.heroes.source_index<0)return;
    const auto roster=world_.targets;const auto index=size_t(*world_.heroes.source_index);
    if(index>=roster->size() || !roster->at(index).unit)return;
    const auto unit=roster->at(index).unit;if(hand_kind(*unit)!="传送带")return;
    const int row=int(std::floor(point.y/world_.runtime.tile));
    if(!world_.terrain.valid_row(row))return;
    const auto& line=world_.terrain.grid.at(size_t(row));if(line.empty())throw std::domain_error("empty conveyor row");
    const int64_t col=int64_t(py::mod(std::floor(point.x/world_.runtime.tile),double(line.size())));
    const auto cell=line.at(size_t(col));if(!text(cell->block) || cell->block.get()!="梯子块")return;
    cell->belt.set(true);Zombie64Event event{Zombie64Event::Kind::belt_placed};event.cell={row,col};event.entity=unit->source.id;
    services_.zombie64_event(event);services_.publish_terrain();
}
void ContentZombies64::finish(const ZombieRef& unit,bool alive) {
    const auto name=content_name(unit->source);
    if(on_belt(unit) && alive) {
        auto& velocity=unit->body.motion.get().vy;velocity-=world_.runtime.plk*12.;velocity=std::max(velocity,-world_.runtime.plk*700.);
    }
    if(slime(name)){if(!alive)split(unit);services_.draw_zombie(unit);return;}
    if(name=="掷弹兵僵尸"){grenadiers_.advance(unit,alive);services_.draw_zombie(unit);return;}
    if(name=="红眼巨人" && alive)redeye(unit);
}
ZombieRef ContentZombies64::throwable(const ZombieRef& giant)const {
    const auto owner=world_.heroes.owner(source_ref(giant));const auto origin=giant->body.motion.get();
    ZombieRef best;double nearest=0.;const auto roster=world_.targets;
    for(size_t index=0;index<roster->size();++index) {
        const auto unit=roster->at(index).unit;
        if(!unit || unit==giant || unit->protection.grave || unit->orphan_barrel || unit->body.hp<=0. || unit->body.ash.present())continue;
        if(world_.heroes.owner(source_ref(unit))!=owner)continue;
        const auto& content=unit->source.content;const auto& size=unit->body.size;
        const double scale=!size.present() || size.is_null() || size.get()==0.?2.:size.get();
        if((text(content) && (content.get()=="海盗鹦鹉" || content.get()=="乌鸦")) || yes(unit->flight) || scale>2.)continue;
        if(text(unit->content64.thrown_by) || text(unit->content64.grabbed_by))continue;
        const auto& point=unit->body.motion.get();
        const double distance=std::hypot(wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y);
        if(distance>3.*world_.runtime.tile)continue;
        if(!best || distance<nearest || (distance==nearest && id_less(unit->source.id,best->source.id))){best=unit;nearest=distance;}
    }
    return best;
}
void ContentZombies64::redeye(const ZombieRef& giant) {
    const double advance=factor(giant->body);auto& state=giant->content64;
    if(state.grab.present() && !state.grab.is_null() && state.grab.get()) {
        const auto grab=state.grab.get();std::optional<NativeObject> found;
        if(grab->id.present() && !grab->id.is_null())found=world_.native_objects.get(grab->id.get());
        const auto* body=found?std::get_if<ZombieRef>(&*found):nullptr;
        const auto target=body?*body:ZombieRef{};
        if(!target || target->body.hp<=0. || target->body.ash.present())state.grab.set_null();
        else {
            const double direction=giant->body.facing>=0.?1.:-1.;const auto& point=giant->body.motion.get();
            target->body.motion.get()={py::mod(point.x+direction*world_.runtime.tile*.55,world_.world_width.get()),
                point.y-world_.runtime.tile*2.4,0.,0.};
            grab->ticks+=advance;
            if(grab->ticks>=75.) {
                target->content64.grabbed_by.erase();target->content64.thrown_by=nullable_id(giant->source);
                auto& p=target->body.motion.get();p.vx=direction*world_.runtime.plk*800.;p.vy=-world_.runtime.plk*600.;
                target->body.facing=direction;state.grab.set_null();
                services_.zombie64_event({Zombie64Event::Kind::throw_unit,giant->source.id,target->source.id});
                try{world_.runtime.play_sound("小鬼1");}catch(const std::exception&){}
            }
        }
        return;
    }
    const double period=2000.*(giant->body.hp<=giant->max_hp.or_missing(2000.)/2.?.5:1.);
    state.throw_clock.set(std::min(period,state.throw_clock.or_missing(0.)+advance));
    if(state.throw_clock.get()<period || !advance)return;
    const auto target=throwable(giant);if(!target)return;
    state.throw_clock.set(0.);target->content64.grabbed_by=nullable_id(giant->source);
    state.grab.set(std::make_shared<RedeyeGrab>(RedeyeGrab{nullable_id(target->source),0.}));
    services_.zombie64_event({Zombie64Event::Kind::grab,giant->source.id,target->source.id});
}
bool ContentZombies64::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));if(row<0)return false;
    if(uint64_t(row)>=published_.solid.size())return true;
    const auto& cells=published_.solid.at(size_t(row));if(cells.empty())throw std::domain_error("empty published thrown row");
    const auto col=size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile));return cells.at(col%cells.size())!=0;
}
void ContentZombies64::landed() {
    const auto roster=world_.targets;
    for(size_t index=0;index<roster->size();++index)if(const auto unit=roster->at(index).unit) {
        const auto& p=unit->body.motion.get();
        if(text(unit->content64.thrown_by) && p.vy>=0. && (solid({p.x,p.y+world_.runtime.tile*.08}) || unit->body.hp<=0.))
            unit->content64.thrown_by.erase();
    }
}
void ContentZombies64::launch_slime(const ZombieRef& child,const ScriptedSpawnOrigin& source,bool sticky,double direction,bool far) {
    const auto point=source.position.get();child->native.entry.set(500.);child->content64.sticky.set(sticky);
    if(source.source->charmed.present())child->source.charmed.set(200.);
    child->body.motion.get()={py::mod(point.x+direction*world_.runtime.tile*(far?.6:.3),world_.world_width.get()),
        point.y-world_.runtime.tile*.5,direction*world_.runtime.plk*(far?480.:260.),-world_.runtime.plk*(far?360.:300.)};
    child->body.facing=direction;
}
bool ContentZombies64::deferred_slime(const ScriptedSpawnOrigin& source,std::string name,bool sticky,double direction,bool far) {
    const auto point=source.position.get();std::optional<SpawnedContentZombie> child;
    {
        HeroContext context(world_.heroes,{Seat::zombie,world_.heroes.owner(source.source).value(),CombatPhase::summon,source.source,{}});
        BanExemption exemption(world_);
        child=services_.spawn_slime(name,{point.x,point.y},direction,{source,Field<bool>(sticky)});
    }
    if(!child)return false;
    launch_slime(child->unit,source,sticky,direction,far);
    Zombie64Event event{Zombie64Event::Kind::slime_split,source.source->id};event.card="zombie:"+name;event.children={child->id};
    services_.zombie64_event(event);return true;
}
void ContentZombies64::split(const ZombieRef& unit) {
    auto& state=unit->content64;if(yes(state.split))return;state.split.set(true);
    if(unit->body.ash.present() || (-1026.<unit->body.hp && unit->body.hp<=-1024.))return;
    const auto name=content_name(unit->source);
    const std::string child_name=name=="史莱姆僵尸"?"中型史莱姆":name=="中型史莱姆"?"小型史莱姆":"";
    if(child_name.empty())return;
    const auto source=source_ref(unit);const auto owner=world_.heroes.owner(source).value();const auto point=unit->body.motion.get();
    std::vector<std::string> children;
    {
        HeroContext context(world_.heroes,{Seat::zombie,owner,CombatPhase::summon,source,{}});BanExemption exemption(world_);
        const std::array<int,4> slots{-1,1,-2,2};const size_t count=yes(state.sticky)?4:2;
        for(size_t index=0;index<count;++index) {
            const int slot=slots[index];const double direction=slot<0?-1.:1.;const bool far=std::abs(slot)==2;
            if(!budget_.can_spawn(1,source)) {
                const auto snapshot=scripted_spawn_origin(unit);const bool sticky=yes(state.sticky);
                budget_.defer(source,"slime:"+child_name,slot,[this,snapshot,child_name,sticky,direction,far]() {
                    return deferred_slime(snapshot,child_name,sticky,direction,far);
                });
                continue;
            }
            ScriptedSpawnOrigin parent;parent.source=std::make_shared<AttackSource>();parent.public_id=nullable_id(unit->source);
            const auto child=services_.spawn_slime(child_name,{point.x,point.y},direction,{parent,{}});if(!child)continue;
            ScriptedSpawnOrigin live;live.source=source;live.position.set(unit->body.motion.get());
            launch_slime(child->unit,live,yes(state.sticky),direction,far);children.push_back(child->id);
        }
    }
    if(!children.empty()) {
        Zombie64Event event{Zombie64Event::Kind::slime_split,unit->source.id};event.card="zombie:"+child_name;event.children=std::move(children);
        services_.zombie64_event(event);
    }
}
} // namespace pvz::typed72
