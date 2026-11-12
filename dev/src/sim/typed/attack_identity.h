// Immutable attack identity, not a general-purpose dynamic value/runtime.
#pragma once
#include <cstdint>
#include <initializer_list>
#include <string>
#include <vector>

namespace pvz::typed72 {
class AttackIdentity {
public:
    static AttackIdentity null();
    static AttackIdentity literal(std::string);
    static AttackIdentity integer(int64_t);
    static AttackIdentity boolean(bool);
    // Lists normalize to tuples only for the native chili-unit hit key.
    static AttackIdentity sequence(const std::vector<AttackIdentity>&,bool list);
    static AttackIdentity native(const std::string& source,int64_t tick);
    static AttackIdentity projectile(const std::string& source);
    const std::string& hero_text() const noexcept {return text_;}
    const std::string& repr() const noexcept {return repr_;}
    const std::string& unit_key() const;
    bool is_null() const noexcept {return null_;}
    bool truthy() const noexcept {return truthy_;}
private:
    AttackIdentity(std::string text,std::string repr,std::string key,bool hashable,bool normalized_hashable,bool is_null,bool truthy)
        :text_(std::move(text)),repr_(std::move(repr)),key_(std::move(key)),hashable_(hashable),normalized_hashable_(normalized_hashable),null_(is_null),truthy_(truthy){}
    std::string text_,repr_,key_;
    bool hashable_=true,normalized_hashable_=true,null_=false,truthy_=true;
};
} // namespace pvz::typed72
