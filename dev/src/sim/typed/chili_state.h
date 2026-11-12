#pragma once
#include "sim/typed/field.h"
#include "sim/typed/record_identity.h"
#include <string>
#include <memory>
#include <variant>
#include <vector>
namespace pvz::typed72 {
// The fire protocol admits an object identity, a numeric legacy token, a
// string tail-flame/marker token or None. This is not a dynamic state value.
struct ChiliKey {
    std::variant<std::monostate,RecordId,double,std::string> value;
    static ChiliKey object(RecordId id){if(!id.value)throw std::logic_error("unregistered chili source");return {{id}};}
    static ChiliKey number(double n){return {{n}};}
    static ChiliKey text(std::string s){return {{std::move(s)}};}
    bool is_text()const{return std::holds_alternative<std::string>(value);}
    friend bool operator==(const ChiliKey&,const ChiliKey&)=default;
};
using ChiliRows=std::variant<double,std::vector<Field<double>>>;
using ChiliHits=std::shared_ptr<std::vector<ChiliKey>>;
struct ChiliState {
    Field<bool> patched,zombie_fire,friendly_fire,no_hero;
    Field<double> row,col,ground_row,ground_y;
    Field<ChiliHits> hits;
    Field<ChiliRows> target_rows;
    Field<std::string> damage_mode;
    Field<ChiliKey> explosion;
};
struct ChiliCounters {
    uint64_t patched=0,explosions=0,unit_damage=0,charmed_damage=0,plant_damage=0;
    uint64_t player_damage=0,player_launch=0,launch_block=0,launch_timeout=0;
};
} // namespace pvz::typed72
