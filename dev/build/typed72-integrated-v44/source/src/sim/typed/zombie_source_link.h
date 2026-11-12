#pragma once
#include <memory>
namespace pvz::typed72 {
struct CombatZombie;
// Metadata copies never retain a reverse association with a different record.
// source_ref(ZombieRef) establishes the association; its alias owns lifetime.
class ZombieSourceLink {
public:
    ZombieSourceLink()=default;
    ZombieSourceLink(const ZombieSourceLink&) noexcept {}
    ZombieSourceLink(ZombieSourceLink&&) noexcept {}
    ZombieSourceLink& operator=(const ZombieSourceLink& other) noexcept {if(this!=&other)unit_.reset();return *this;}
    ZombieSourceLink& operator=(ZombieSourceLink&& other) noexcept {if(this!=&other)unit_.reset();return *this;}
    void bind(const std::shared_ptr<CombatZombie>& unit) noexcept {unit_=unit;}
    std::shared_ptr<CombatZombie> lock()const noexcept{return unit_.lock();}
private:
    std::weak_ptr<CombatZombie> unit_;
};
} // namespace pvz::typed72
