#pragma once
#include "sim/typed/field.h"
#include "cold_card_fields.h"
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <variant>
#include <vector>
namespace pvz::typed72 {
using ColdNumber=std::variant<bool,double>;
struct ColdCard {
#define STR(n) std::string n;
    PVZ72_COLD_REQUIRED_STRINGS(STR)
#undef STR
#define NUM(n) double n=0.;
    PVZ72_COLD_REQUIRED_NUMBERS(NUM)
#undef NUM
#define BOOL(n) bool n=false;
    PVZ72_COLD_REQUIRED_FLAGS(BOOL)
#undef BOOL
#define STR(n) Field<std::string> n;
    PVZ72_COLD_OPTIONAL_STRINGS(STR)
#undef STR
#define NUM(n) Field<double> n;
    PVZ72_COLD_OPTIONAL_NUMBERS(NUM)
#undef NUM
#define BOOL(n) Field<bool> n;
    PVZ72_COLD_OPTIONAL_FLAGS(BOOL)
#undef BOOL
    Field<ColdNumber> slow;
    Field<std::vector<std::string>> targets,native_secret_names;
};
struct ColdReplacement {std::string base,secret,resolved;};
struct ColdSecretNumbers {std::string secret;std::vector<std::pair<std::string,double>> values;};
struct ColdCatalogData {
    std::vector<ColdCard> cards;
    std::vector<ColdReplacement> replacements;
    std::unordered_map<std::string,std::string> derived_bases;
    std::vector<std::string> protected_cards,boss_names,deathmatch_allowed_producers;
    std::unordered_map<std::string,double> costs,health,plant_cooldowns,zombie_cooldowns;
    std::vector<ColdSecretNumbers> zombie_cost_set,zombie_cost_add,zombie_hp_factor;
    double fast_plant_cooldown_factor=.75,hardening_min_base_hp=6.,hardening_hp_factor=1.25;
    double starfruit_cost=0.,sea_shroom_surcharge=0.,imitate_cooldown_factor=.5,rush_cooldown=.75;
    std::string imitate_secret,rage_torch_art,catalog_hash,rules_hash;
};
const ColdCatalogData& compiled_cold_catalog();
class ColdCatalog {
public:
    explicit ColdCatalog(const ColdCatalogData& data=compiled_cold_catalog());
    const ColdCard* find(std::string_view)const;
    const ColdCard& at(const std::string&)const;
    const ColdCatalogData& data()const{return data_;}
    bool allowed(const std::string&,std::span<const std::string> bans={},bool for_spawn=false,
                 std::span<const std::string> secrets={})const;
    std::vector<std::string> native_secrets(std::span<const std::string>,std::span<const std::string> bans={})const;
    ColdCard actual(const std::string&,std::span<const std::string> secrets={},bool night=false)const;
    ColdCard resolve(const std::string&,std::span<const std::string> secrets={},std::span<const std::string> bans={},bool night=false)const;
    ColdCard player_card(const std::string&,std::span<const std::string> secrets,std::span<const std::string> bans,
                         bool night,const std::string& last_copy_card={})const;
    ColdCard unit_card(const std::string&,std::span<const std::string> secrets,std::span<const std::string> bans,
                       bool night,const std::string& last_copy_card={})const;
    bool deathmatch_blocked(const ColdCard&)const;
    static double initial_cooldown(double);
    static double deployment_cooldown(double,bool deathmatch);
private:
    const ColdCatalogData& data_;
    std::unordered_map<std::string,const ColdCard*> by_id_;
    std::unordered_map<std::string,const ColdReplacement*> replacements_;
};
} // namespace pvz::typed72
