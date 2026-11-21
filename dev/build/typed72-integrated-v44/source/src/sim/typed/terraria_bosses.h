#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/cold_catalog.h"
#include "sim/typed/native_canvas.h"
#include <functional>
namespace pvz::typed72 {
struct TerrariaDefinition {int type;const char* name;double hp,damage,defense,width,height;int sprite_width,sprite_height,frames;};
const TerrariaDefinition& terraria_definition(int type);
int terraria_type(std::string_view key);
bool terraria_summon(int type);
const ColdCatalogData& terraria_catalog();
// Classic 1.4.5.8 behavior at 60 Hz, independent of the native 250 Hz tick.
// Positions use world pixels; AI velocities and distances use Terraria pixels.
class TerrariaBosses {
public:
    using Factory=std::function<ZombieRef(int,Point,const ZombieRef&)>;
    TerrariaBosses(TypedBattleState& world,ContentTargets& hits,Factory factory):world_(world),hits_(hits),factory_(std::move(factory)){}
    ZombieRef summon(int type,Point center);
    // PvP75: the 克苏鲁之仆 card, in every mode; facing gives its first drift.
    ZombieRef summon_servant(Point center,double facing);
    void advance();
    void draw(NativeCanvas&);
    int accumulator()const{return accumulator_;}
    int64_t frames()const{return frames_;}
    const std::map<std::string,int64_t>& contacts_state()const{return contact_until_;}
private:
    TypedBattleState& world_;ContentTargets& hits_;Factory factory_;
    int accumulator_=0;int64_t frames_=0;
    std::map<std::string,int64_t> contact_until_;
    std::map<int,NativeArt> sheets_;
    std::map<uint64_t,double> observed_hp_;
    std::map<uint64_t,int64_t> dig_until_;
    struct Debris {int sprite=0,age=0;Point point,velocity;double rotation=0.;Color color{};};
    std::vector<Debris> debris_;
    uint64_t visual_serial_=0;
    double scale()const{return world_.runtime.tile/16.;}
    Point center(const ZombieRef&)const;
    Point delta(Point,Point)const;
    std::vector<ContentTarget> enemies()const;
    std::optional<ContentTarget> target(const ZombieRef&,bool closest=false);
    std::string id(const ContentTarget&)const;
    void step(const ZombieRef&);
    void eye(const ZombieRef&,Point);
    void skeleton(const ZombieRef&,Point);
    void hand(const ZombieRef&,Point);
    void worm(const ZombieRef&,Point);
    bool solid(const ZombieRef&)const;
    void contacts(const ZombieRef&);
    void reap();
    void sound(const ZombieRef&,const char*);
    void feedback(const ZombieRef&,double damage,bool death=false,bool transform=false);
    void advance_debris();
    void draw_debris(NativeCanvas&);
};
}
