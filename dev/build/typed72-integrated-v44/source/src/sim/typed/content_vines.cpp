#include "sim/typed/content_vines.h"
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
bool named(const Field<std::string>& value,std::string_view name){return value.present()&&!value.is_null()&&value.get()==name;}
}
bool ContentVines::configure(const PlantRef& plant,std::string_view name) {
    if(name!="阳光藤蔓"&&name!="忧郁藤蔓"&&name!="抓人草")return false;
    plant->source.content.set(std::string(name));plant->sleep.erase();plant->small_puff.erase();
    if(name=="阳光藤蔓") {
        plant->kind=std::string(name);const double hp=hardening_?9.:6.;plant->hp.set(hp);plant->max_hp.set(hp);plant->content_state.maximum_hp.set(hp);
        plant->content_state.hardening_form.set(std::string(name));plant->content_state.vine_clock.set(0.);plant->content_state.vine_produced.set(false);
    }
    wake_cell(plant);return true;
}
void ContentVines::wake_cell(const PlantRef& vine) {
    if(!named(vine->source.content,"忧郁藤蔓")||vine->hp.or_missing(0.)<=0.||vine->dead.present())return;
    for(const auto& plant:*world_.plant_roster)if(plant!=vine&&plant->cell==vine->cell){plant->content_state.awake_forever.set(true);plant->sleep.erase();}
}
std::optional<size_t> ContentVines::coffee_target(Cell cell) {
    std::vector<size_t> sleepers;for(size_t i=0;i<world_.plant_roster->size();++i) {
        const auto& plant=world_.plant_roster->at(i);
        if(plant->cell==cell&&plant->sleep.present()&&plant->hp.or_missing(0.)>0.&&!plant->dead.present()&&!named(plant->source.content,"抓人草触手"))sleepers.push_back(i);
    }
    if(sleepers.empty())return {};for(size_t i=0;i+1<sleepers.size();++i)world_.plant_roster->at(sleepers[i])->sleep.erase();return sleepers.back();
}
double ContentVines::rest_factor(const PlantRef& plant) {
    const double hp=plant->hp.or_missing(0.);if(!plant->rest_hp.present()||plant->rest_hp.is_null()||hp<plant->rest_hp.get())plant->rest_since.set(double(world_.heroes.tick));
    plant->rest_hp.set(hp);const double quiet=(world_.heroes.tick-plant->rest_since.get())/250.,ramp=(quiet-rules_.rest_seconds)/std::max(1e-9,rules_.ramp_seconds);
    return 1.+rules_.rest_bonus*std::min(1.,std::max(0.,ramp));
}
void ContentVines::tick() {
    const double rate=world_.protection.deathmatch?rules_.multiplier:1.;const auto roster=world_.plant_roster;
    for(size_t i=0;i<roster->size();++i) {
        const auto plant=roster->at(i);auto& state=plant->content_state;
        if(yes(state.awake_forever))plant->sleep.erase();if(named(plant->source.content,"忧郁藤蔓"))wake_cell(plant);
        if(!named(plant->source.content,"阳光藤蔓")||plant->hp.or_missing(0.)<=0.||plant->dead.present()||plant->sleep.present())continue;
        const double rest=rest_factor(plant);state.vine_clock.get()+=rate*rest/std::max(.01,plant->aura_factor.or_missing(1.))/250.;
        const double period=state.vine_produced.get()?16.:6.;if(state.vine_clock.get()+1e-9>=period) {
            state.vine_clock.get()-=period;state.vine_produced.set(true);
            resources_.create(plant->source.seat.value_or(Seat::plant),15.,{(plant->cell.x+.5)*world_.runtime.tile,(plant->cell.y+.5)*world_.runtime.tile},plant->source.id.or_missing("vine"));
        }
    }
}
} // namespace pvz::typed72
