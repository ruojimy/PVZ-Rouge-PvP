#include "sim/typed/content_particles.h"
#include <cmath>
namespace pvz::typed72 {
void ContentParticles::emit(CombatRuntime& runtime,const std::string& name,Point position,int count,std::optional<int> direction) {
    if(&runtime!=&world_.runtime)throw std::logic_error("content particles belong to another battle");
    if(observe)observe(name,position);
    const auto index=world_.heroes.source_index;
    PlantRef plant;
    if(index&&*index>=0&&uint64_t(*index)<world_.plant_roster->size())plant=world_.plant_roster->at(size_t(*index));
    if(!plant||name!=plant->kind||std::abs(position.x-(plant->cell.x+.5)*runtime.tile)>=.01||
       std::abs(position.y-(plant->cell.y+.5)*runtime.tile)>=.01) {
        runtime.emit_particles_native(name,position,count,direction);return;
    }
    auto& art=runtime.presentation;auto& aliases=art.source_art;
    struct Restore {
        decltype(aliases) table;
        std::vector<std::pair<std::string,std::optional<std::string>>> saved;
        ~Restore(){for(auto& [key,value]:saved){if(value)table[key]=std::move(*value);else table.erase(key);}}
    } restore{aliases,{}};
    const auto& content=plant->source.content;
    if(content.present()&&!content.is_null()&&!content.get().empty()&&art.atlas.contains(content.get())) {
        for(const char* suffix:{"","-受伤","-黑白"}) {
            const auto old=plant->kind+suffix,next=content.get()+suffix;
            if(old==next||!art.atlas.contains(old)||!art.atlas.contains(next))continue;
            const auto previous=aliases.find(old);restore.saved.emplace_back(old,previous==aliases.end()?std::nullopt:std::optional(previous->second));
            aliases[old]=art.sprite_name(next);
        }
    }
    runtime.emit_particles_native(name,position,count,direction);
}
} // namespace pvz::typed72
