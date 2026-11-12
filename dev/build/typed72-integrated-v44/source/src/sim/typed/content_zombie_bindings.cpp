#include "sim/typed/content_zombie_bindings.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
namespace pvz::typed72 {
namespace {
bool named(const Field<std::string>& field,std::string_view name){return field.present() && !field.is_null() && field.get()==name;}
bool listed(const Field<std::string>& field,const std::vector<std::string>& names) {
    return field.present() && !field.is_null() && std::find(names.begin(),names.end(),field.get())!=names.end();
}
}
bool ContentZombieBindings::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));if(row<0)return false;if(uint64_t(row)>=published_.solid.size())return true;
    const auto& line=published_.solid.at(size_t(row));
    return line.at(size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile))%line.size())!=0;
}
double ContentZombieBindings::movement_factor(const ZombieRef& unit)const {
    if(world_.heroes.owner(source_ref(unit))!=Seat::zombie)return 1.;
    double bonus_sum=0.;for(const auto& [tag,bonus]:unit->patch.speed_factors)bonus_sum+=bonus;return 1.+bonus_sum;
}
double ContentZombieBindings::unit_scale(const ZombieRef& unit)const{return unit_scale_factor(unit->source,collision_);}
double ContentZombieBindings::bite_damage(const ZombieRef& unit,const ContentTarget& target) {
    if(unit->patch.no_attack.present() && !unit->patch.no_attack.is_null() && unit->patch.no_attack.get())return 0.;
    double base;
    if(listed(unit->source.variant,rules_.black_variants))base=3.;
    else if(named(unit->protection.card,"zombie:墓碑吞噬者僵尸") || unit->body.kind=="墓碑吞噬者僵尸")
        base=unit->body.hp<=unit->max_hp.or_missing(300.)*.5?6.:3.;  // PvP73
    else base=unit->patch.bite_plant.or_missing(1.);
    if(named(unit->protection.card,"zombie:巨人僵尸") || named(unit->protection.card,"zombie:红眼巨人") ||
       named(unit->protection.card,"zombie:角斗士巨人"))base=10.;
    double bite_rate=1.;
    if(world_.protection.secrets.enabled && world_.heroes.owner(source_ref(unit))==Seat::zombie) {
        if(world_.protection.focused(unit->damage_target()))bite_rate+=1.;if(world_.protection.berserk())bite_rate+=1.;
    }
    const double rate=(unit->body.berserk.present()?4.:1.)*bite_rate;
    if(const auto* body=std::get_if<CombatTarget>(&target)) {
        if(body->is_hero())return (listed(unit->source.variant,rules_.black_hero_bite_variants)?3.:base)*rate;
        double amount=base*rate*10.;
        if(body->unit->source.charmed.present() && !unit->source.charmed.present() && charm_secret_)amount*=.5;
        return amount;
    }
    return base*rate;
}
} // namespace pvz::typed72
