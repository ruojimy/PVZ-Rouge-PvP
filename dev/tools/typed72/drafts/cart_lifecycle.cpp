#include "sim/typed/cart_lifecycle.h"
#include "sim/typed/content_zombie_state.h"
#include "core/pymath.h"

namespace pvz::typed72 {
double CartLifecycle::action_rate(const CombatZombie& unit) {
    const auto& body=unit.body;
    if(body.ice.or_missing(0.)>1000. || body.butter.or_missing(0.)>0. || body.stun.or_missing(0.)>0. ||
       (unit.source.charmed.present() && unit.source.charmed.get()<200.))return 0.;
    return body.ice.or_missing(0.)>0.?.5:1.;
}
void CartLifecycle::configure(const ZombieRef& unit,std::string_view card) {
    if(card!="zombie:投篮车僵尸" && card!="zombie:小鬼炮")return;
    auto& state=unit->content;
    state.cart_deadline.set(double(world_.heroes.tick)+20000.);
    if(card=="zombie:小鬼炮") {
        state.cannon_animation.set(0.);state.cannon_recoil.set(0.);state.cannon_loaded.set(false);
    }
}
void CartLifecycle::before(const ZombieRef& unit) {
    auto& state=unit->content;
    if(!state.cart_deadline.present() || state.cart_deadline.is_null())return;
    if(unit->body.hp>0. && double(world_.heroes.tick)>=state.cart_deadline.get()) {
        unit->body.hp=0.;unit->protection.basketball.set(0.);
        unit->native.basketball_total.set(0.);unit->native.shooting.set(0.);unit->native.basketball_cd.set(1e9);
        state.cart_expired.set(true);state.cannon_loaded.set(false);
        unit->protection.locked.set(false);unit->protection.lock_done=true;
        if(!unit->body.ash.present())unit->body.ash.set(0.);
        if(!unit->protection.card.present())throw std::logic_error("cart expiry requires a card key");
        services_.cart_expired(unit->source.id,unit->protection.card,80.);
    }
    if(unit->source.content.present() && !unit->source.content.is_null() && unit->source.content.get()=="小鬼炮")
        state.cannon_rate.set(action_rate(*unit));
}
void CartLifecycle::animate(const ZombieRef& unit,bool active,bool fired) {
    auto& state=unit->content;const double rate=state.cannon_rate.or_missing(action_rate(*unit));
    state.cannon_animation.set(state.cannon_animation.or_missing(0.)+rate);
    state.cannon_recoil.set(fired?90.:std::max(0.,state.cannon_recoil.or_missing(0.)-rate));
    state.cannon_loaded.set(active && !fired && state.summon_clock.or_missing(0.)>=800.);
}
void CartLifecycle::draw(const ZombieRef& unit,CartDrawing& drawing) {
    const auto& state=unit->content;const auto& body=unit->body;const double tile=world_.runtime.tile;
    const bool alive=body.hp>0. && !body.ash.present();
    auto image=drawing.copy(drawing.art("小鬼炮-炮身"));
    const double phase=state.cannon_animation.or_missing(0.),recoil=state.cannon_recoil.or_missing(0.)/90.;
    const bool advancing=unit->native.advance.present() && !unit->native.advance.is_null() && unit->native.advance.get()!=0.;
    const double bob=advancing?std::sin(phase/18.)*tile*.015:0.;
    if(alive && state.cannon_loaded.present() && !state.cannon_loaded.is_null() && state.cannon_loaded.get()) {
        const auto imp=drawing.copy(drawing.art("小鬼炮-装填小鬼"));
        const double progress=std::clamp((state.summon_clock.or_missing(0.)-800.)/90.,0.,1.);
        drawing.alpha(imp,int(py::round0(255.*progress)));drawing.blit(image,imp,{0.,py::round0((1.-progress)*tile*.13)});
    }
    const auto overlay=[&](int r,int g,int b,CartBlend blend,int alpha) {
        const auto copy=drawing.copy(image);drawing.fill(copy,r,g,b,blend);drawing.alpha(copy,alpha);drawing.blit(image,copy,{0.,0.});
    };
    if(body.hurt>0.)overlay(255,255,255,CartBlend::rgb_max,120);
    if(body.ice.or_missing(0.)>0.)overlay(95,175,255,CartBlend::rgb_multiply,115);
    if(unit->source.charmed.present())overlay(235,115,255,CartBlend::rgb_multiply,100);
    if(unit->poison.poison.present() && !unit->poison.poison.is_null() && !unit->poison.poison.get()->empty())
        image=drawing.tint_poison(image,unit->poison.poison.get()->level.get());
    if(!alive) {
        const double age=std::max(0.,-body.hp);
        if(body.ash.present())drawing.fill(image,65,65,65,CartBlend::rgb_multiply);
        image=drawing.rotate(image,-std::min(55.,age*.3));drawing.alpha(image,std::max(0,255-int(py::round0(std::min(255.,age)))));
    }
    if(recoil!=0.) {const auto dimensions=drawing.dimensions(image);image=drawing.scale(image,{std::max(1.,py::round0(dimensions.x*(1.-recoil*.045))),dimensions.y});}
    if(body.facing<0.)image=drawing.mirror(image);
    const auto dimensions=drawing.dimensions(image);const auto position=body.motion.get();
    drawing.display(image,{position.x-dimensions.x/2.-body.facing*recoil*tile*.12,position.y-dimensions.y+bob});
    if(alive && body.butter.or_missing(0.)>0.) {
        const auto butter=drawing.saved_art("黄油砸",drawing.art("黄油砸"));const auto size=drawing.dimensions(butter);
        drawing.display(butter,{position.x-size.x/2.,position.y-tile*1.9-size.y/2.});
    }
}
} // namespace pvz::typed72
