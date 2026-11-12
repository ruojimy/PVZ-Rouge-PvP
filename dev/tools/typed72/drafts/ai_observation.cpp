#include "sim/typed/ai_observation.h"
#include <array>
#include <cmath>

namespace pvz::typed72 {
const std::vector<AiVisibleShot>& AiNativeShotView::sample(const EntityRoster& entities,double now,double width){
    if(last_time_&&now==*last_time_)return cached_;
    static constexpr std::array<std::string_view,18> names{"豌豆","僵尸豌豆","冰豆","火豆","蓝火豆","卷心菜","玉米粒","黄油","西瓜","冰瓜","尖刺","篮球","孢子","大孢子","豌豆x","星星","回旋镖","毒镖"};
    std::vector<AiVisibleShot> result;std::unordered_map<std::string,Previous> current;
    result.reserve(entities.size());current.reserve(entities.size());
    for(const auto& entity:entities){
        if(std::find(names.begin(),names.end(),entity->kind)==names.end())continue;
        const auto& owner=entity->source.owner;
        if(!owner.present()||owner.is_null()||(owner.get()!="plant"&&owner.get()!="zombie"))continue;
        const auto& motion=entity->motion.get();if(!std::isfinite(motion.x)||!std::isfinite(motion.y))continue;
        const bool has_id=entity->source.id.present()&&!entity->source.id.is_null()&&!entity->source.id.get().empty();
        if(!has_id&&!entity->identity.value)throw std::logic_error("AI shot has no stable native record identity");
        // Prefix distinguishes a native numeric fallback identity from a
        // literal string ID with identical decimal text, as Python dict does.
        const auto display=has_id?entity->source.id.get():std::to_string(entity->identity.value);
        const auto key=(has_id?"s:":"n:")+display;const auto found=previous_.find(key);
        Point velocity{};double gravity=0.;
        if(found!=previous_.end()&&now-found->second.time>0.&&now-found->second.time<=.5){
            const auto dt=now-found->second.time;
            velocity={ai_wrap_delta(found->second.position.x,motion.x,width)/dt,(motion.y-found->second.position.y)/dt};
            if(found->second.observed_before)gravity=(velocity.y-found->second.velocity.y)/dt;
            velocity.x=std::clamp(velocity.x,-2500.,2500.);velocity.y=std::clamp(velocity.y,-2500.,2500.);gravity=std::clamp(gravity,-3000.,3000.);
        }
        current[key]={{motion.x,motion.y},now,velocity,found!=previous_.end()};
        result.push_back({"visible-shot:"+display,entity->kind,owner.get()=="plant"?Seat::plant:Seat::zombie,
            {motion.x,motion.y},velocity,gravity,10.,true,entity->kind=="冰豆"||entity->kind=="冰瓜",entity->kind=="黄油"});
    }
    previous_=std::move(current);last_time_=now;cached_=std::move(result);seen_+=cached_.size();return cached_;
}
std::vector<AiVisibleShot> AiNativeShotView::visible(Point hero,double width)const{
    std::vector<AiVisibleShot> result;for(const auto& shot:cached_)
        if(std::abs(ai_wrap_delta(hero.x,shot.position.x,width))<=480.&&shot.position.y-hero.y>=-384.&&shot.position.y-hero.y<=256.)result.push_back(shot);
    return result;
}
AiCardCounts ai_own_counts(std::span<const AiUnitView> units,Seat side,std::optional<Seat> seat){
    AiCardCounts counts;
    for(const auto& unit:units){
        if(unit.side!=side||unit.hp<=0.||(seat&&unit.seat.value_or(side)!=*seat))continue;
        const auto it=std::find_if(counts.begin(),counts.end(),[&](const auto& item){return item.first==unit.card;});
        if(it==counts.end())counts.emplace_back(unit.card,1);else ++it->second;
    }
    return counts;
}
} // namespace pvz::typed72
