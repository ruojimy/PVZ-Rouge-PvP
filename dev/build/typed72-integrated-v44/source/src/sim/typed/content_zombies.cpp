#include "sim/typed/content_zombies.h"
#include "sim/typed/content_zombie_state.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present() && !value.is_null() && value.get();}
bool named(const Field<std::string>& value,std::string_view name){return value.present() && !value.is_null() && value.get()==name;}
std::string name_of(const ZombieRef& unit) {
    const auto& name=unit->source.content;
    return name.present() && !name.is_null()?name.get():std::string{};
}
bool flyer(std::string_view name){return name=="海盗鹦鹉" || name=="乌鸦";}
bool held(const CombatZombie& unit) {
    return unit.body.ice.or_missing(0.)>1000. || unit.body.butter.or_missing(0.)>0. || unit.body.stun.or_missing(0.)>0.;
}
}
bool ContentZombies::custom(std::string_view name)const {
    return name=="稻草人" || name=="乌鸦" || std::find(rules_.custom_zombies.begin(),rules_.custom_zombies.end(),name)!=rules_.custom_zombies.end();
}
bool ContentZombies::follow(const CombatZombie& unit)const {
    return commands_.for_owner(world_.mode,unit.source.seat)==PathMode::follow_hero;
}
bool ContentZombies::rally(const CombatZombie& unit)const {
    return rally_.for_owner(world_.mode,unit.source.seat).has_value();
}
Point ContentZombies::destination(const CombatZombie& unit) {
    return paths_.destination(unit.source.seat,terrain_revision_).value();
}
Seat ContentZombies::following_seat(const CombatZombie& unit)const {
    if(unit.source.seat && std::find(present_.begin(),present_.end(),*unit.source.seat)!=present_.end())return *unit.source.seat;
    return Seat::zombie;
}
void ContentZombies::restore_player(CombatZombie& unit) {
    if(!unit.content.player_position.present())return;
    world_.heroes.globals.position=unit.content.player_position;
    unit.content.player_position.erase();
}
void ContentZombies::release_pending_destination() {
    const auto unit=last_;
    if(!unit)return;
    restore_player(*unit);controllers_.september_finish(unit);
}
void ContentZombies::cart_gate(const ZombieRef& unit,std::string_view name) {
    if(name=="小鬼炮")unit->native.basketball_cd.set(1e9);
    if(unit->body.kind!="投篮车僵尸")return;
    auto& state=unit->content;auto& body=unit->body;auto& native=unit->native;
    if(!state.player_position.present())state.player_position=world_.heroes.globals.position;
    const bool charmed=unit->source.charmed.present();
    Seat side=charmed || follow(*unit)?Seat::zombie:Seat::plant;
    if(side==Seat::zombie)side=following_seat(*unit);
    const bool has_rally=rally(*unit) && !charmed;
    if(!has_rally)world_.heroes.globals.position.set(std::make_shared<Motion>(*world_.heroes.hero(side).frame.position.get()));
    const auto& hero=*world_.heroes.globals.position.get();
    const auto goal=has_rally?destination(*unit):Point{hero.x,hero.y};
    const double tile=world_.runtime.tile,dx=wrap_delta(body.motion.get().x,goal.x,world_.world_width.get());
    if(name=="小鬼炮" || follow(*unit) || has_rally) {
        const double stopping=has_rally?.4:follow(*unit) && !charmed?2.:20.;
        body.facing=dx>=0.?1.:-1.;native.advance.set(std::abs(dx)>stopping*tile?2.:0.);
        if(native.advance.get()==0.)body.motion.get().vx=0.;
    }
    if(named(unit->protection.card,"zombie:投篮车僵尸") && unit->protection.basketball.or_missing(0.)<=0.) {
        unit->protection.basketball.set(0.);native.shooting.set(0.);native.basketball_cd.set(1e9);
        if(!follow(*unit) && !has_rally)native.advance.set(2.);
    }
    if((follow(*unit) || has_rally) && !charmed && name!="小鬼炮") {
        state.saved_basketball_cd.set(native.basketball_cd.or_missing(0.));native.basketball_cd.set(1e9);
    }
}
void ContentZombies::art_gate(const ZombieRef& unit,std::string_view name) {
    const auto& body=unit->body;
    if(name=="海盗船长") {
        const bool moving=body.hp>0. && unit->native.biting.or_missing(0.)==0. && std::abs(body.motion.get().vx)>.01;
        const auto frame=moving?1+int(py::mod(std::floor(double(world_.heroes.tick)/35.),2.)):0;
        for(const auto part:{"-身","-首"})controllers_.alias_art(body.kind+part,std::string(name)+part+std::to_string(frame));
    }else if(custom(name)) {
        for(const auto part:{"-身","-首"})for(const auto suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"})
            controllers_.alias_art(body.kind+part+suffix,"_pvp_content_blank");
        if(name=="滚桶僵尸" && body.hand=="滚桶")
            for(const auto suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"})controllers_.alias_art(std::string("滚桶")+suffix,"_pvp_content_blank");
        if(name=="小鬼炮")for(const auto part:{"轮子","投篮臂","投篮臂-空"})controllers_.alias_art(part,"_pvp_content_blank");
        if(body.butter.or_missing(0.)>0.)controllers_.alias_art("黄油砸","_pvp_content_blank");
    }
    if(unit->poison.poison.present() && !unit->poison.poison.is_null() && !unit->poison.poison.get()->empty())controllers_.tint_poison(unit);
}
void ContentZombies::gate(size_t index) {
    const auto unit=world_.targets->at(index).unit;
    if(!unit)throw std::logic_error("content zombie gate requires a body");
    last_=unit;controllers_.cart_before(unit);
    // The black football dash may push other units before this gate.
    if(unit->source.variant.or_missing("")=="黑橄榄僵尸"||unit->body.kind=="黑橄榄球僵尸")queries_.invalidate();
    const auto name=name_of(unit);
    controllers_.september_gate(unit);controllers_.zombies56_gate(unit);
    if(!unit->content.player_position.present())controllers_.september_wave_chase(unit);
    unit->grenadier.before.set(unit->body.motion.get());
    zombies64_.gate(unit);controllers_.zombies70_gate(unit);
    auto& body=unit->body;
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    if(name=="滚桶僵尸" && !unit->source.charmed.present() && body.hand_hp>0.) {
        if(rally(*unit)) {
            const double dx=wrap_delta(body.motion.get().x,destination(*unit).x,width);
            if(std::abs(dx)>tile*.4)unit->content.barrel_direction.set(dx>0.?1.:-1.);
        }
        controllers_.barrel_correct_pair(unit);body.facing=unit->content.barrel_direction.get();
        const auto position=body.motion.get();const double direction=body.facing;
        const bool obstacle=controllers_.solid({position.x+direction*tile*.4,position.y-tile*.4});
        const bool grounded=controllers_.solid({position.x,position.y-tile*.19});
        if(!held(*unit) && position.vy>=0. && grounded && obstacle && !controllers_.solid({position.x,position.y-tile*1.8}))
            body.motion.get().vy=-world_.runtime.plk*400.;
    }
    cart_gate(unit,name);art_gate(unit,name);
}
void ContentZombies::stun_stars(const ZombieRef& unit,std::string_view name) {
    if(unit->body.stun.or_missing(0.)<=0. || !drawing_)return;
    const auto point=unit->body.motion.get();const double tile=world_.runtime.tile;
    const double height=name=="小鬼炮"?tile*1.9:custom(name) || name=="抓人草触手"?
        controllers_.image_height(std::string(name)+"-帧0"):
        tile*(unit->body.size.or_missing(0.)==3.?3.:2.)*controllers_.unit_scale(unit);
    const double dimension=std::max(1.,std::trunc(tile*.2));
    for(int index=0;index<3;++index) {
        const double angle=double(world_.heroes.tick)/50.+index*0x1.921fb54442d18p+1*2./3.;
        controllers_.stun_star({point.x+std::cos(angle)*tile*.4-tile*.1,
            point.y-height-tile*.3+std::sin(angle)*tile*.08},{dimension,dimension});
    }
}
void ContentZombies::finish_summoner(const ZombieRef& unit,std::string_view name,double factor) {
    bool active=true,fired=false;
    auto& state=unit->content;auto& position=unit->body.motion.get();
    if(name=="小鬼炮") {
        factor=state.cannon_rate.or_missing(factor);
        Seat side=unit->source.charmed.present() || follow(*unit)?Seat::zombie:Seat::plant;
        if(named(world_.heroes.hero(side).avatar_source->owner,"zombie"))side=following_seat(*unit);
        const auto& hero=*world_.heroes.hero(side).frame.position.get();
        const auto goal=rally(*unit) && !unit->source.charmed.present()?destination(*unit):Point{hero.x,hero.y};
        const double dx=wrap_delta(position.x,goal.x,world_.world_width.get());
        unit->body.facing=dx>=0.?1.:-1.;
        const bool following=(follow(*unit) || rally(*unit)) && !unit->source.charmed.present();
        active=!following && std::abs(dx)<=20.*world_.runtime.tile;
        if(active){position.x=unit->grenadier.before.get().x;position.vx=0.;}
    }
    if(active)state.summon_clock.get()+=factor;
    const double period=name=="小鬼炮"?1000.:2000.;
    if(active && factor>0. && state.summon_clock.get()>=period) {
        if(summons_.summon(unit,name=="海盗船长"?"海盗鹦鹉":"小鬼僵尸",name=="小鬼炮",0.,false)) {
            state.summon_clock.get()-=period;fired=true;
        }else state.summon_clock.set(period);
    }
    if(name=="小鬼炮")controllers_.cart_animate(unit,active,fired);
}
void ContentZombies::flyer_bite_effect(const ZombieRef& unit,const ContentTarget& target) {
    if(const auto* plant=std::get_if<PlantRef>(&target)) {
        const auto& secrets=*world_.heroes.globals.secrets.get();
        if((*plant)->kind=="雷蘑菇" || named((*plant)->protection.card,"plant:雷蘑菇") ||
           ((*plant)->kind=="大喷菇" && std::find(secrets.begin(),secrets.end(),"雷霆")!=secrets.end()))
            unit->body.stun.set(std::max(unit->body.stun.or_missing(0.),250.));
        if((*plant)->kind=="大蒜")unit->body.stun.set(std::max(unit->body.stun.or_missing(0.),125.));
    }else if(const auto body=std::get<CombatTarget>(target);body.is_hero()) {
        const auto& secrets=world_.heroes.players.at(seat_index(body.hero)).value().secrets;
        if(std::find(secrets.begin(),secrets.end(),"secret:体香")!=secrets.end())
            unit->body.stun.set(std::max(unit->body.stun.or_missing(0.),125.));
    }
}
void ContentZombies::finish_flyer(const ZombieRef& unit,std::string_view name,double factor,std::optional<ContentTarget> target) {
    const bool charmed=unit->source.charmed.present();
    bool rallying=rally(*unit) && !charmed,following=(follow(*unit) || rallying) && !charmed;
    if(following) {
        const auto seat=following_seat(*unit);world_.heroes.proxy(seat);
        ContentTarget goal=CombatTarget::player(seat);
        if(rallying) {
            const auto flag=rally_.for_owner(world_.mode,unit->source.seat).value();
            auto temporary=std::make_shared<CombatZombie>();
            temporary->body.motion={flag.x,flag.y+world_.runtime.tile,0.,0.};
            goal=CombatTarget::zombie(temporary);
        }
        const auto blocker=queries_.route_enemies(CombatTarget::zombie(unit),goal);
        const auto taunted=taunts_.taunt_target(CombatTarget::zombie(unit),{});
        target=taunted?taunted:blocker;
        if(taunted || blocker!=std::optional<ContentTarget>(goal)){rallying=false;following=false;}
    }
    if(!target)return;
    const auto before=unit->grenadier.before.get();auto& position=unit->body.motion.get();position=before;
    const auto aim=targets_.point(*target),start=targets_.point(CombatTarget::zombie(unit));
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    double dx=wrap_delta(start.x,aim.x,width),dy=aim.y-start.y;
    if(rallying) {
        const auto flag=rally_.for_owner(world_.mode,unit->source.seat).value();
        dx=wrap_delta(before.x,flag.x,width);dy=flag.y-start.y;
    }
    unit->content.target.set(world_.heroes.source_id(queries_.source(*target)));
    if(factor==0.)return;
    const double length=std::max(1.,std::hypot(dx,dy));
    const double speed=world_.runtime.plk*110.*factor*(name=="乌鸦"?.5:1.)*controllers_.movement_factor(unit);
    bool impulse_present=unit->body.hurt!=0.;
    // Python's short circuit leaves the blown marker in place while hurt.
    if(!impulse_present){impulse_present=yes(unit->body.blown);unit->body.blown.erase();}
    const double impulse=impulse_present?before.vx:0.;
    const double travel=following && length<=(rallying?.4:2.)*tile?0.:std::min(speed,std::max(0.,length-tile*.08));
    position.x=py::mod(before.x+dx/length*travel+impulse,width);position.y+=dy/length*travel;
    position.vx=impulse*.9;position.vy=0.;unit->body.facing=dx>=0.?1.:-1.;
    if(!following && length<tile*.75 && unit->native.biting.or_missing(0.)<=0.) {
        const double amount=controllers_.bite_damage(unit,*target);
        targets_.damage(source_ref(unit),*target,amount,unit->body.facing);
        unit->native.biting.set(110.);flyer_bite_effect(unit,*target);
    }
}
void ContentZombies::finish() {
    const auto unit=std::exchange(last_,{});if(!unit)return;
    struct Moved {ContentQueries& queries;ZombieRef unit;~Moved(){try{queries.moved(CombatTarget::zombie(unit));}catch(...){queries.invalidate();}}} moved{queries_,unit};
    const auto name=name_of(unit);auto& body=unit->body;auto& state=unit->content;
    const bool alive=body.hp>0. && !body.ash.present();
    controllers_.september_finish(unit);controllers_.zombies56_finish(unit);restore_player(*unit);
    if(state.saved_basketball_cd.present()) {
        unit->native.basketball_cd.set(std::max(1.,state.saved_basketball_cd.get()-1.));state.saved_basketball_cd.erase();
    }
    if(name=="滚桶僵尸" && !alive)controllers_.barrel_detach(unit,body.hand_hp!=0.?body.hand_hp:state.barrel_remaining.or_missing(0.));
    if(name=="滚桶僵尸" && body.hand_hp<=0. && !unit->source.charmed.present())controllers_.barrel_break(unit);
    zombies64_.finish(unit,alive);
    // Red-eye carry/throw also relocates a friendly unit, so rebuild before
    // the next query rather than updating only the giant's own point.
    if(name=="红眼巨人")queries_.invalidate();
    if(!alive){controllers_.draw_content_zombie(unit);return;}
    if(name=="稻草人")scarecrows_.advance(unit,held(*unit)?0.:body.ice.or_missing(0.)>0.?.5:1.);
    stun_stars(unit,name);
    const bool stopped=held(*unit) || (unit->source.charmed.present() && unit->source.charmed.get()<200.);
    const double factor=stopped?0.:body.ice.or_missing(0.)>0.?.5:1.;
    const auto target=unit->source.charmed.present() || flyer(name)?queries_.nearest(CombatTarget::zombie(unit)):std::nullopt;
    if(unit->source.charmed.present() && target) {
        const auto goal=targets_.point(*target),origin=targets_.point(CombatTarget::zombie(unit));
        const double dx=wrap_delta(origin.x,goal.x,world_.world_width.get());
        body.facing=dx>=0.?1.:-1.;state.target.set(world_.heroes.source_id(queries_.source(*target)));
        const auto* collider=std::get_if<CombatTarget>(&*target);
        if(body.size.or_missing(0.)==2. && !yes(unit->patch.no_attack) && collider && collider->is_hero() &&
           std::abs(dx)+std::abs(origin.y-goal.y)<=world_.runtime.tile && factor!=0. && unit->native.biting.or_missing(0.)<=0.) {
            targets_.damage(source_ref(unit),*target,controllers_.bite_damage(unit,*target),body.facing);unit->native.biting.set(110.);
        }
    }
    if(name=="滚桶僵尸") {
        if(unit->source.charmed.present()){body.hand.clear();body.hand_hp=0.;state.barrel_discarded.set(true);}
        else if(!yes(state.barrel_broken) && !yes(unit->poison.killed)) {
            controllers_.barrel_move(unit,factor);controllers_.barrel_contact(unit,factor);
        }
        if(body.hand_hp>0.)body.facing=state.barrel_direction.get();
    }
    if(name=="海盗船长" || name=="小鬼炮")finish_summoner(unit,name,factor);
    if(flyer(name))finish_flyer(unit,name,factor,target);
    controllers_.draw_content_zombie(unit);
}
} // namespace pvz::typed72
