#pragma once
#include "sim/typed/zombie_motion.h"
#include "sim/typed/entity_region.h"

namespace pvz::typed72 {
struct NativeCoin {
    double age;
    Motion motion;
    double cooldown;
    std::string kind;
};
struct ZombieActionState {
    int coin_count=0;
    bool drawing=false;
    std::vector<NativeCoin> coins;
    std::vector<std::string> large_zombies;
};
class ZombieActionServices {
public:
    virtual ~ZombieActionServices()=default;
    virtual void zombie_gate(size_t)=0;
    virtual void summon_zombie(std::string,Motion,double)=0;
    virtual bool hold_dance()=0;
    virtual bool defer_dancer(Point,double facing,int64_t slot)=0;
    virtual bool hold_sled()=0;
    virtual bool hold_giant()=0;
    virtual void ash_zombie(size_t)=0;
    virtual void line(Point screen_start,Point screen_end)=0;
    virtual void crop(std::string sprite,Point position,bool mirrored,Point extent)=0;
    virtual uint64_t flat_sprite(std::string sprite,Point extent,bool mirrored)=0;
    virtual bool has_sprite(const std::string&)const=0;
};
class ZombieActions {
public:
    ZombieActions(TypedBattleState& world,ZombieMotion& motion,ZombieNavigation& nav,ZombieActionState& state,
                  ZombieMotionServices& move,ZombieActionServices& actions,PlantLifecycle& plants,EntityRenderer& renderer)
        :world_(world),motion_(motion),nav_(nav),state_(state),move_(move),actions_(actions),plants_(plants),renderer_(renderer){}
    void run();
    // Continue a live body's updates immediately after the displacement call.
    void finish(ZombieMotionFrame frame);
    // NativeContent barrel crushing calls the same original flatten entry.
    bool flatten_plant(Cell cell){return crush(cell);}
private:
    enum class Layer { body,ice,charm,ash_body,head,ice_head,charm_head,ash_head,armor,ice_armor,hand };
    struct Art {
        std::array<std::pair<std::string,Layer>,9> layers;
        size_t size=0;
        double ash_height=0.;
        void add(std::string sprite,Layer layer){layers.at(size++)={std::move(sprite),layer};}
    };
    TypedBattleState& world_;
    ZombieMotion& motion_;
    ZombieNavigation& nav_;
    ZombieActionState& state_;
    ZombieMotionServices& move_;
    ZombieActionServices& actions_;
    PlantLifecycle& plants_;
    EntityRenderer& renderer_;
    ZombieRef unit(size_t index)const;
    void dance(const ZombieMotionFrame&);
    void waking(const ZombieMotionFrame&);
    void locomotion(const ZombieMotionFrame&);
    void vehicle(const ZombieMotionFrame&);
    void body_art(const ZombieMotionFrame&,Art&);
    bool death(const ZombieMotionFrame&);
    void explode(const ZombieRef&,Point,Cell,bool car);
    void miner(const ZombieMotionFrame&,Art&);
    void giant(const ZombieMotionFrame&);
    void render(const ZombieRef&,const Art&);
    void cart(const ZombieMotionFrame&);
    void pole(const ZombieRef&);
    void blast_terrain(Cell);
    bool crush(Cell);
    void player_hit(double);
    void draw(std::string,Point,bool mirrored=false,std::optional<double> angle={});
    void alpha(const std::string&,double);
};
} // namespace pvz::typed72
