#pragma once
#include "sim/typed/ai_geometry.h"
#include "sim/typed/native_tracking.h"
#include <map>
#include <tuple>
namespace pvz::typed72 {
struct AiFiringCard {std::string id,name,behavior;std::optional<double> range;bool producer=false,lob=false,star=false,homing=false;};
struct AiFiringTarget {Point position;double height=0.;};
struct AiFiringFrame {const TargetSight& terrain;std::span<const AiFiringTarget> targets;double width=3456.,tile=48.;};
enum class AiFiringReason {own_mechanics,unknown_terrain,target,unreachable_targets,open_corridor,blocked_corridor};
std::string_view ai_firing_reason_name(AiFiringReason);
struct AiFiringAssessment {bool allowed=false;AiFiringReason reason=AiFiringReason::blocked_corridor;std::optional<double> distance;};
struct AiArcSolution {double time,vx,vy;};
struct AiFiringSignature {double width,tile;std::vector<std::vector<uint8_t>> solid;std::vector<std::array<double,3>> targets;friend bool operator==(const AiFiringSignature&,const AiFiringSignature&)=default;};
// A context lasts one tactical observation. Its memo is discarded with that
// observation; geometry and target facts are borrowed from the public view.
class AiFiring {
public:
    explicit AiFiring(const AiFiringFrame& frame):frame_(frame){}
    static bool ballistic(const AiFiringCard&);
    static std::optional<AiArcSolution> arc_solution(double dx,double dy,double speed,double gravity,bool high=false);
    static std::optional<double> body_entry(Point from,Point to,double tx,double foot,double height,double half_width);
    bool clear_segment(Point from,Point to)const;
    bool clear_guided_arc(Point start,double target_x,double foot,double height,double speed,double gravity)const;
    bool clear_arc(Point start,Point target,const AiFiringCard&,std::optional<double> foot={},std::optional<double> height={})const;
    AiFiringAssessment assessment(const AiFiringCard&,Point,int facing=1);
    std::optional<int> direction(const AiFiringCard&,Point,int facing=1);
    const AiFiringSignature& signature();
    std::shared_ptr<const AiFiringSignature> shared_signature(){signature();return signature_;}
private:
    const AiFiringFrame& frame_;
    std::shared_ptr<const AiFiringSignature> signature_;
    std::map<std::tuple<std::string,int64_t,int64_t,int>,AiFiringAssessment> memo_;
    AiFiringAssessment check(const AiFiringCard&,int64_t col,int64_t row,int facing)const;
};
struct AiFiringFailures {
    struct Failure {std::shared_ptr<const AiFiringSignature> signature;double until;uint64_t repeats,order;};
    using Key=std::tuple<std::string,int64_t,int64_t,int>;
    std::map<Key,Failure> entries;uint64_t serial=0;
    bool lane_blocked=false;std::string last_blocked_card;
    uint64_t blocked_lane_count=0,turn_count=0;
    std::optional<int> direction(AiFiring&,const AiFiringCard&,Point,int facing,double now,double width,double tile);
};
} // namespace pvz::typed72
