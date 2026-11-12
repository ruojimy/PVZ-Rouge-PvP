#pragma once
#include "sim/typed/targets.h"

namespace pvz::typed72 {
using CartImage=uint64_t;
enum class CartBlend {rgb_max,rgb_multiply};
class CartDrawing {
public:
    virtual ~CartDrawing()=default;
    virtual CartImage art(std::string_view)=0;
    virtual CartImage saved_art(std::string_view,CartImage fallback)=0;
    virtual CartImage copy(CartImage)=0;
    virtual Point dimensions(CartImage)=0;
    virtual void fill(CartImage,int red,int green,int blue,CartBlend)=0;
    virtual void alpha(CartImage,int)=0;
    virtual void blit(CartImage destination,CartImage source,Point)=0;
    virtual CartImage rotate(CartImage,double degrees)=0;
    virtual CartImage scale(CartImage,Point)=0;
    virtual CartImage mirror(CartImage)=0;
    virtual CartImage tint_poison(CartImage,int level)=0;
    virtual void display(CartImage,Point)=0;
};
class CartLifecycleServices {
public:
    virtual ~CartLifecycleServices()=default;
    virtual void cart_expired(const Field<std::string>& entity,const Field<std::string>& card,double seconds)=0;
};
class CartLifecycle {
public:
    CartLifecycle(TypedBattleState& world,CartLifecycleServices& services):world_(world),services_(services){}
    void configure(const ZombieRef&,std::string_view card);
    void before(const ZombieRef&);
    void animate(const ZombieRef&,bool active,bool fired);
    void draw(const ZombieRef&,CartDrawing&);
    static double action_rate(const CombatZombie&);
private:
    TypedBattleState& world_;
    CartLifecycleServices& services_;
};
} // namespace pvz::typed72
