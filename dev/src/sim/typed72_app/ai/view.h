#pragma once
// Frozen per-control-tick view for the typed r22 controller port. Every field
// mirrors one key of the V room snapshot the controller reads (after the seat's
// local_perspective), including whether the key is present, so dict.get(k, d)
// semantics are kept. Values are copied from typed authorities at tick start;
// the controller's own sends during the tick never change this view (as in V,
// where it reads one snapshot per tick).
#include "sim/typed/cold_catalog.h"
#include "sim/typed/ai_observation_builder.h"
#include <cstdint>
#include <functional>
#include <array>
#include <map>
#include <stdexcept>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <variant>
#include <vector>

namespace pvz::typed72app::ai {
using typed72::Seat;
using typed72::ColdCard;

// ---- plan dict: closed value set, insertion-ordered like a Python dict ----
using Quotas=std::vector<std::pair<std::string,double>>;
using PlanValue=std::variant<std::monostate,double,bool,std::string,std::vector<std::string>,Quotas>;   // monostate = None
class PlanDict {
public:
    bool has(const std::string& k)const{return find(k)!=nullptr;}
    const PlanValue* find(const std::string& k)const{for(const auto& [key,v]:items_)if(key==k)return &v;return nullptr;}
    void set(const std::string& k,PlanValue v){for(auto& [key,old]:items_)if(key==k){old=std::move(v);return;}items_.emplace_back(k,std::move(v));}
    // plan.get(k, d) for numbers (bools count as 0/1, as in Python arithmetic).
    double num(const std::string& k,double d)const{
        const auto* v=find(k);if(!v)return d;
        if(const auto* n=std::get_if<double>(v))return *n;if(const auto* b=std::get_if<bool>(v))return *b?1.:0.;
        throw std::invalid_argument("plan value is not a number: "+k);
    }
    bool flag(const std::string& k,bool d)const{
        const auto* v=find(k);if(!v)return d;
        if(const auto* b=std::get_if<bool>(v))return *b;if(const auto* n=std::get_if<double>(v))return *n!=0.;
        if(const auto* s=std::get_if<std::string>(v))return !s->empty();
        throw std::invalid_argument("plan value is not a flag: "+k);
    }
    std::string str(const std::string& k,const std::string& d)const{
        const auto* v=find(k);if(!v)return d;if(const auto* s=std::get_if<std::string>(v))return *s;
        throw std::invalid_argument("plan value is not text: "+k);
    }
    const std::vector<std::string>* list(const std::string& k)const{const auto* v=find(k);return v?std::get_if<std::vector<std::string>>(v):nullptr;}
    const Quotas* quotas()const{const auto* v=find("quotas");return v?std::get_if<Quotas>(v):nullptr;}
    double quota(const std::string& card,double d)const{
        if(const auto* q=quotas())for(const auto& [k,n]:*q)if(k==card)return n;return d;
    }
    const std::vector<std::pair<std::string,PlanValue>>& items()const{return items_;}
private:
    std::vector<std::pair<std::string,PlanValue>> items_;
};

// The command arguments AISeat.send forwards (insertion-ordered kwargs).
using Args=std::vector<std::pair<std::string,PlanValue>>;

// One unit dict of snapshot["units"] (encode_public_unit). All keys below are
// always present there except seat / copy_card_id.
struct Unit {
    std::string id,card_id,behavior;
    Seat side=Seat::plant;                 // team
    std::optional<std::string> seat,copy_card_id;
    double x=0.,y=0.,hp=0.,max_hp=0.,w=0.,h=0.,facing=1.,drowsy_level=0.;
    bool mobile=false,flying=false,awake=true,mature=false,drowsy=false;
    const ColdCard* card=nullptr;          // u['card'] (owner-resolved); nullptr when V held the bare id
};
// One players[...] row (seat key after local_perspective).
struct Player {
    std::string key,seat;                  // dict key, real seat
    double x=0.,y=0.,hp=0.,max_hp=0.,resource=0.,facing=1.;
    bool grounded=false,absent=false;
    std::vector<std::string> deck,secrets;
    std::vector<std::pair<std::string,double>> cooldowns;
    std::optional<double> teleport_ready_at,collect_locked_until;
    bool cannon_aim_written=false;bool cannon_aim_set=false;   // key present / value not None
    std::optional<std::string> selected_grave;
    double cooldown(const std::string& k,double d)const{for(const auto& [key,v]:cooldowns)if(key==k)return v;return d;}
    bool has_secret(const std::string& s)const{for(const auto& v:secrets)if(v==s)return true;return false;}
    bool in_deck(const std::string& s)const{for(const auto& v:deck)if(v==s)return true;return false;}
};
struct Resource {std::string id,side,source;double x=0.,y=0.,amount=0.;std::optional<bool> shared;};
struct Cell {bool solid=false,water=false,ladder=false;std::string kind;};
struct Pickup {std::string id,name;double x=0.,y=0.;};

struct View {
    Seat team=Seat::plant,seat=Seat::plant;
    double time=0.,width=0.,height=0.,tile=48.;
    bool deathmatch=false,map_night=false;
    std::optional<std::string> mode,local_seat;     // b.get('mode'), b.get('local_seat')
    std::string command="follow";
    std::optional<std::pair<double,double>> rally_point;
    bool has_team=false;std::vector<std::string> fallen;
    std::vector<Player> players;                    // snapshot dict order
    std::vector<Unit> units;
    std::vector<Resource> resources;
    std::vector<std::vector<Cell>> tiles;           // b.map tiles (current published cells)
    std::vector<double> zombie_points;
    bool has_zsecrets=false;std::vector<Pickup> pickups;std::vector<std::string> last_stand;
    std::vector<std::string> bans;
    std::optional<double> hero_lock_range;          // snap['rules'].get('hero_lock_range')
    const Player* player(const std::string& key)const{for(const auto& p:players)if(p.key==key)return &p;return nullptr;}
};

// The services the controller reaches through, never the authority itself.
class Services {
public:
    virtual ~Services()=default;
    // PreviewBattle.placement(side, key, x, y, grave) on the tick's state; unbounded clones the
    // player with resource>=10000 and no cooldowns (ztactics7 aquatic legality).
    virtual std::string preview(const std::string& key,double x,double y,const std::optional<std::string>& grave,bool unbounded)=0;
    // resolve_card(key, secrets, bans, night): throws for a card that cannot be resolved.
    virtual const ColdCard& card(const std::string& key)=0;
    virtual bool air_plant(const std::string& key)const=0;   // pvp56 AIR_PLANTS membership
};

// Field: standing spots per zone, built once from the room map (rv_field.Field).
struct Spot {double x=0.,y=0.;bool water=false;};
class Field {
public:
    static constexpr int ZONES=6;
    Field(const std::vector<std::vector<Cell>>& tiles,double width,double height,double tile);
    std::vector<Spot> candidates(int zone,double hero_x,std::optional<double> hero_y,int64_t limit)const;
    std::array<std::vector<Spot>,ZONES> spots;
    double width,height,tile;
};
} // namespace pvz::typed72app::ai
