#pragma once
#include "sim/typed/content_target.h"

namespace pvz::typed72 {
class ContentTaunts {
public:
    virtual ~ContentTaunts()=default;
    virtual std::optional<ContentTarget> taunt_target(const ContentTarget&,std::optional<ContentTarget>)=0;
};
class ContentQueries {
public:
    ContentQueries(TypedBattleState& world,ContentTargets& targets,ContentTaunts& taunts)
        :world_(world),targets_(targets),taunts_(taunts){}
    std::vector<ContentTarget> enemies(const std::shared_ptr<AttackSource>& source);
    std::optional<ContentTarget> nearest(const ContentTarget& source);
    std::optional<ContentTarget> route(const ContentTarget& source,std::optional<ContentTarget> goal,
                                      std::span<const ContentTarget> candidates)const;
    std::shared_ptr<AttackSource> source(const ContentTarget&)const;
private:
    TypedBattleState& world_;
    ContentTargets& targets_;
    ContentTaunts& taunts_;
};
} // namespace pvz::typed72
