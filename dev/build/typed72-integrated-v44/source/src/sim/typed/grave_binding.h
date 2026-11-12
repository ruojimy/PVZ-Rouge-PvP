#pragma once
#include "sim/typed/zombie_actions.h"
#include <list>
#include <unordered_map>

namespace pvz::typed72 {
enum class GraveBindingEventKind { started,consumed,cancelled };
enum class GraveBindingReason { none,plant_unavailable,target_unavailable };
struct GraveBindingEvent {
    GraveBindingEventKind kind;
    Field<std::string> source_id;
    std::string target_id;
    int64_t native_tick;
    GraveBindingReason reason=GraveBindingReason::none;
};
class GraveBindingServices {
public:
    virtual ~GraveBindingServices()=default;
    virtual void grave_consumed(const ZombieRef&,const PlantRef&)=0;
    virtual void grave_event(GraveBindingEvent)=0;
};
class GraveBinding {
public:
    struct Link {
        PlantRef plant;
        ZombieRef target;
        std::string target_id;
        Cell cell;
    };
    GraveBinding(TypedBattleState& world,ZombieActionState& actions,PlantLifecycle& terrain,GraveBindingServices& services)
        :world_(world),actions_(actions),terrain_(terrain),services_(services){}
    GraveBinding(const GraveBinding&)=delete;
    void attach(const PlantRef&,std::string target_id);
    void before_native_tick();
    void destroy(Cell);
    void close();
    const auto& links()const{return links_;}
    const auto& cancelled()const{return cancelled_;}
    bool closed()const{return closed_;}
    int depth()const{return depth_;}
    // The renderer receives the validated overlay cell without changing the
    // authoritative terrain used by movement, planting or network snapshots.
    std::shared_ptr<const Link> draw_target(size_t plant_index)const;
    class Plants {
    public:
        explicit Plants(GraveBinding& bridge):bridge_(bridge) {
            if(bridge_.closed_)throw std::logic_error("native grave binding is closed");
            bridge_.before_native_tick();++bridge_.depth_;
        }
        ~Plants(){--bridge_.depth_;}
        Plants(const Plants&)=delete;
    private:
        GraveBinding& bridge_;
    };
private:
    TypedBattleState& world_;
    ZombieActionState& actions_;
    PlantLifecycle& terrain_;
    GraveBindingServices& services_;
    std::list<std::shared_ptr<Link>> links_;
    std::unordered_map<CombatPlant*,decltype(links_)::iterator> by_plant_;
    std::unordered_map<CombatPlant*,PlantRef> cancelled_;
    int depth_=0;
    bool closed_=false;
    ZombieRef resolve(const std::string&)const;
    Cell target_cell(const CombatZombie&)const;
    bool valid(const Link&)const;
    void erase(const PlantRef&);
    void cancel(const Link&,GraveBindingReason);
    void remove_completion_coin(const CombatPlant&);
    void event(GraveBindingEventKind,const Link&,GraveBindingReason=GraveBindingReason::none);
};
} // namespace pvz::typed72
