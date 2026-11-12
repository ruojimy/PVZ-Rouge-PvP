#include "sim/typed/hero_phase.h"
#include "sim/typed/projectile_rules.h"
#include "core/number_text.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
bool has(const std::vector<std::string>& values,std::string_view name){
    return std::find(values.begin(),values.end(),name)!=values.end();
}
int jump_cap(Seat side,const HeroPlayer& player){
    if(team_of(side)==Seat::plant)return has(player.secrets,"secret:疾行")?3:2;
    const bool pea=has(player.secrets,"zsecret:豌豆"),pressure=has(player.secrets,"zsecret:威压");
    return pea?(pressure?2:1):(pressure?3:2);
}
}
void HeroPhase::initialize(Seat side,Point p,double rule_hp,const std::vector<std::string>& deck,std::vector<std::string> secrets){
    auto& heroes=world_.heroes;const auto team=team_of(side);auto& player=heroes.players.at(seat_index(side)).value();
    const bool sturdy=has(deck,"zombie:坚固脑光墓碑");
    const auto hp=rule_hp+(side==Seat::zombie?((sturdy?8.:0.)+(has(deck,"zsecret:石更！")?20.:0.)):0.);
    std::erase(secrets,std::string("硬化"));
    HeroState avatar;
    avatar.frame=physics_.make_state(p,team==Seat::zombie?"我是僵尸":"正常模式",hp,std::move(secrets));
    avatar.avatar_source=std::make_shared<AttackSource>();avatar.avatar_source->owner.set(std::string(seat_name(team)));
    avatar.avatar_source->id.set("hero:"+std::string(seat_name(side)));
    if(world_.mode!=MatchMode::duel){avatar.actual_seat=side;avatar.avatar_source->seat=side;}
    avatar.max_hp.set(hp);avatar.previous_hp.set(hp);avatar.last_damage.set(0.);avatar.regen_progress.set(0.);
    avatar.balloon_hp.set(team==Seat::zombie && sturdy?12:10);
    heroes.heroes.at(seat_index(side))=std::move(avatar);player.max_hp=player.hp=hp;
}
void HeroPhase::rally_rise(HeroState& a){
    const auto flag=[&]{return rally_.for_owner(world_.mode,a.actual_seat).has_value();};
    if(a.frame.down.or_missing(0.)<=0.){
        a.rally_eligible.erase();a.rally_checked.erase();
        if(flag())a.rally_before.set(true);else a.rally_before.erase();
        return;
    }
    if(!a.rally_eligible.present()){
        const bool before=a.rally_before.or_missing(false);a.rally_before.erase();
        if(!before)return;
        a.rally_eligible.set(true);
    }
    const auto recovery=a.frame.recovery.or_missing(0.);
    if(a.rally_checked.or_missing(false) || recovery<1000.)return;
    a.rally_checked.set(true);const bool early=flag() && recovery<2000.;
    if(early)a.frame.recovery.set(2000.);
    world_.heroes.events.emplace_back(RallyRiseEvent{a.actual_seat.value_or(Seat::zombie),early});
}
bool HeroPhase::float_body(HeroState& a)const{
    auto& p=*a.frame.position.get();const double tile=world_.runtime.tile,width=world_.world_width.get();
    const auto rows=map_.water.size();
    if(!rows || tile<=0. || width<=0.)throw std::logic_error("missing floating body map");
    const double column=std::floor(py::mod(p.x,width)/tile);
    const auto wet=[&](int row){
        if(row<0 || size_t(row)>=rows)return false;
        const auto& cells=map_.water[row];if(cells.empty())throw std::logic_error("empty floating body row");
        return cells[size_t(column)%cells.size()]!=0;
    };
    if(!wet(int(std::floor(p.y/tile))) && !wet(int(std::floor((p.y-tile*.4)/tile)))){
        a.floating_body.erase();return false;
    }
    int row=std::clamp(int(py::floordiv(p.y,tile)),0,int(rows)-1);
    if(!wet(row))row=std::max(0,row-1);
    while(row>0 && wet(row-1))--row;
    const double surface=(row+.45)*tile;
    p.y=p.y>surface?std::max(surface,p.y-tile*2./250.):std::min(surface,p.y+tile/250.);
    p.vx=p.vy=0.;a.floating_body.set(true);return true;
}
void HeroPhase::tag_births(Seat side,HeroState& avatar,size_t before){
    const auto list=world_.runtime.entities.list();const auto team=team_of(side);
    for(size_t i=before;i<list->size();++i){
        const auto& e=list->at(i);auto& source=e->source;
        world_.heroes.tag_entity(source_ref(e),&e->motion.get(),e->flight,team,avatar.avatar_source);
        if(side!=team)source.seat=side;
        if(e->kind!="火")continue;
        if(avatar.launch_attack && avatar.launch_attack->truthy())source.instant_attack=avatar.launch_attack;
        if(team==Seat::zombie){
            auto& chili=e->chili;chili.zombie_fire.set(true);chili.damage_mode.set("enemy");chili.no_hero.set(true);
            chili.explosion.set(ChiliKey::text("launch:"+native_number_text(avatar.frame.chili_lock_until.get())));
            chili.target_rows.set(std::vector<Field<double>>{Field<double>{py::floordiv(e->motion.get().y,world_.runtime.tile)}});
        }
    }
}
void HeroPhase::advance(std::span<const Seat> seats){
    auto& h=world_.heroes;const bool team_mode=world_.mode==MatchMode::duo || world_.mode==MatchMode::coop;
    for(const auto side:seats){
        auto& a=h.hero(side);auto& g=a.frame;auto& player=h.players.at(seat_index(side)).value();
        if(!a.avatar_source)throw std::logic_error("hero physics without source");
        g.water_ice.set(std::max(h.water_ice,a.cold_until.or_missing(0.)-h.tick));
        const auto before=world_.runtime.entities.list()->size();
        const double ice=a.ice.or_missing(0.),butter=a.butter.or_missing(0.),stun=a.stun.or_missing(0.);
        const bool held=butter>0. || ice>1000. || stun>0. || (g.hp.get()<=0. && team_mode);
        const double x=g.position.get()->x;const bool pressed=player.jump_presses>0;
        if(team_of(side)==Seat::plant){
            const double recovery=g.recovery.or_missing(0.);
            if(g.down.or_missing(0.)>0. && recovery>=1000. && recovery<2000. && has(player.secrets,"secret:抖M"))g.recovery.set(2000.);
        }else rally_rise(a);
        if(!(team_mode && g.hp.get()<=0. && float_body(a)))
            physics_.step(a,{held?0:player.move,player.jump_held && !held,pressed && !held},jump_cap(side,player),a.balloon_hp.or_missing(10));
        auto& p=*g.position.get();
        if(held){p.x=x;p.vx=0.;}
        else if(ice>0.){const double width=world_.world_width.get();p.x=py::mod(x+wrap_delta(x,p.x,width)*.5,width);}
        a.ice.set(std::max(0.,ice-1.));a.butter.set(std::max(0.,butter-1.));a.stun.set(std::max(0.,stun-1.));
        tag_births(side,a,before);if(pressed)--player.jump_presses;
    }
}
void HeroPhase::effects(std::span<const Seat> seats,double now,double tail_activation_seconds){
    auto& heroes=world_.heroes;
    for(const auto side:seats){
        auto& avatar=heroes.hero(side);const auto& source=avatar.avatar_source;
        if(!source)throw std::logic_error("hero ability without source");
        HeroContext context(heroes,{side,team_of(side),CombatPhase::player,source,{}});
        const auto& p=*avatar.frame.position.get();
        tracking_.target_index({source,{},Point{p.x,p.y}});
        physics_.effects(avatar,now>=tail_activation_seconds);
        context.close();
    }
}
} // namespace pvz::typed72
