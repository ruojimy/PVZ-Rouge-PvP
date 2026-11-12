#pragma once
#include <memory>
namespace pvz::typed72 {
struct Entity;
// AttackSource snapshots contain metadata, never ownership of a live entity.
// Only source_ref(EntityRef) establishes this weak reverse link. The aliasing
// shared_ptr returned there keeps the owner alive through synchronous callbacks.
class EntitySourceLink {
public:
    EntitySourceLink()=default;
    EntitySourceLink(const EntitySourceLink&) noexcept {}
    EntitySourceLink(EntitySourceLink&&) noexcept {}
    EntitySourceLink& operator=(const EntitySourceLink& other) noexcept {if(this!=&other)entity_.reset();return *this;}
    EntitySourceLink& operator=(EntitySourceLink&& other) noexcept {if(this!=&other)entity_.reset();return *this;}
    void bind(const std::shared_ptr<Entity>& entity) noexcept {entity_=entity;}
    std::shared_ptr<Entity> lock()const noexcept{return entity_.lock();}
private:
    std::weak_ptr<Entity> entity_;
};
} // namespace pvz::typed72
