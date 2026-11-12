#include "sim/typed/plant_death_rules.h"

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& field){return field.present() && !field.is_null() && field.get();}
}
void PlantDeathPolicy::killed(const PlantRef& plant){
    if(!rules_.zombie_secrets_enabled || world_.heroes.owner(source_ref(plant))!=Seat::plant || yes(plant->secret_killed))return;
    plant->secret_killed.set(true);
    const Point point{(plant->cell.x+.5)*world_.runtime.tile,(plant->cell.y+1.)*world_.runtime.tile};
    for(const auto seat:rules_.brain_holders){
        const auto id=resources_.create(seat,rules_.brains_per_kill,point,"zsecret_brain");
        resources_.remove_motion(id);resources_.collect(id);
    }
    if(rules_.conversion_holders.empty() || yes(plant->temporary))return;
    const auto form=rules_.conversion_forms.find(plant->kind);
    if(form==rules_.conversion_forms.end())return;
    const auto facing=plant->facing==0.?1.:plant->facing;
    state_.conversions.push_back({form->second,point,-facing,rules_.conversion_holders.front()});
}
bool PlantDeathPolicy::supplement(size_t index){
    killed(world_.plant_roster->at(index));
    // Callbacks above may replace the roster. The source reads its numeric
    // index again before deciding whether this death emits a supplement.
    const auto plant=world_.plant_roster->at(index);
    const auto& secrets=*world_.heroes.globals.secrets.get();
    const bool due=std::find(secrets.begin(),secrets.end(),"补光")!=secrets.end() && !yes(plant->transform_succeeded);
    if(due)economy_.death_points.push_back({(plant->cell.x+.5)*world_.runtime.tile,(plant->cell.y+.5)*world_.runtime.tile});
    return due;
}
bool PlantDeathPolicy::second_doom_ash(int64_t index){
    if(!rules_.nuclear_secret)return false;
    if(index<0 || uint64_t(index)>=world_.targets->size())return true;
    const auto target=world_.targets->at(size_t(index));
    if(target.is_hero())return true;
    if(world_.heroes.owner(source_ref(target.unit))==world_.heroes.owner())return false;
    target.unit->body.ash.set(0.);
    return false;
}
} // namespace pvz::typed72
