#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/seat_path_tracking.h"
#include <map>
#include <tuple>

namespace pvz::typed72 {
class SeptemberZombieServices {
public:
    virtual ~SeptemberZombieServices()=default;
    virtual void alias_art(const std::string&,const std::string&)=0;
    virtual void hide_headhunt_plants(const ZombieRef&)=0;
};
struct SeptemberPathBank {
    PathSnapshot snapshot;
    std::optional<int64_t> tick;
};
using SeptemberPathKey=std::tuple<bool,int64_t,int64_t,uint64_t>;
class SeptemberZombies {
public:
    SeptemberZombies(TypedBattleState& world,ZombieNavigation& navigation,const NativePathRules& rules,
                     SeatPathTracking& snapshots,ContentTargets& targets,const SeatCommands& commands,
                     const RallyPoints& rallies,const std::vector<Seat>& present,const uint64_t& revision,
                     const bool& scripted,SeptemberZombieServices& services)
        :world_(world),navigation_(navigation),tracking_(world,navigation,rules),snapshots_(snapshots),
         targets_(targets),commands_(commands),rallies_(rallies),present_(present),revision_(revision),
         scripted_(scripted),services_(services){}
    void gate(const ZombieRef&);
    bool wave_chase(const ZombieRef&);
    void finish(const ZombieRef&);
    void chase(const ZombieRef&,const std::shared_ptr<Motion>& goal,SeptemberPathKey,
               const std::shared_ptr<Motion>& tracking_goal={});
    const auto& banks()const{return banks_;}
private:
    TypedBattleState& world_;
    ZombieNavigation& navigation_;
    PathTracking tracking_;
    SeatPathTracking& snapshots_;
    ContentTargets& targets_;
    const SeatCommands& commands_;
    const RallyPoints& rallies_;
    const std::vector<Seat>& present_;
    const uint64_t& revision_;
    const bool& scripted_;
    SeptemberZombieServices& services_;
    std::map<SeptemberPathKey,std::shared_ptr<SeptemberPathBank>> banks_;
    bool ordered(const ZombieRef&)const;
};
} // namespace pvz::typed72
