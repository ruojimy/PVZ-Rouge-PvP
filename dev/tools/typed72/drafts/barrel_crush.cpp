#include "sim/typed/barrel_crush.h"
namespace pvz::typed72 {
void NativeBarrelCrush::crush(const ZombieRef& unit,const PlantRef& plant) {
    auto& aliases=world_.runtime.presentation.source_art;
    using AliasMap=std::remove_reference_t<decltype(aliases)>;
    struct Restore {
        AliasMap& table;
        std::vector<std::pair<std::string,std::optional<std::string>>> saved;
        ~Restore(){for(auto& [key,value]:saved){if(value)table[key]=std::move(*value);else table.erase(key);}}
    } restore{aliases,{}};
    const auto text=[](const Field<std::string>& field)->std::string_view {
        return field.present()&&!field.is_null()?std::string_view(field.get()):std::string_view{};
    };
    const auto content=text(plant->source.content);
    const auto art=content.empty()?text(plant->source.variant):content;
    if(!art.empty())for(const auto suffix:{"","-黑白"}) {
        const auto key=plant->kind+suffix,actual=std::string(art)+suffix;
        if(!art_.has_sprite(key)||!art_.has_sprite(actual))continue;
        const auto found=aliases.find(key);
        restore.saved.emplace_back(key,found==aliases.end()?std::nullopt:std::optional(found->second));
        aliases[key]=world_.runtime.presentation.sprite_name(actual);
    }
    const auto owner=world_.heroes.owner(source_ref(unit));
    if(!owner)throw std::logic_error("barrel pusher has no allegiance");
    HeroContext context(world_.heroes,{*owner==Seat::zombie?Seat::plant:Seat::zombie,*owner,CombatPhase::content,source_ref(unit),{}});
    actions_.flatten_plant(plant->cell);
}
} // namespace pvz::typed72
