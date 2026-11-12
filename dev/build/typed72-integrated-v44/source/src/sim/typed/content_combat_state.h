#pragma once
namespace pvz::typed72 {
// One instance is owned by NativeContent and shared by all of its installed
// damage wrappers. A nested velocity bonus must not apply content multipliers
// twice, including when the inner call throws.
struct ContentCombatState { int damage_depth=0; };
class ContentDamageDepth {
public:
    explicit ContentDamageDepth(ContentCombatState& state):state_(state){++state_.damage_depth;}
    ~ContentDamageDepth(){--state_.damage_depth;}
    ContentDamageDepth(const ContentDamageDepth&)=delete;
    ContentDamageDepth& operator=(const ContentDamageDepth&)=delete;
private:
    ContentCombatState& state_;
};
} // namespace pvz::typed72
