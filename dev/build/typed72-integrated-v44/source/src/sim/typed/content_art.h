#pragma once
#include "sim/typed/native_content_phase.h"
#include "sim/typed/expansion_art.h"
namespace pvz::typed72 {
// Concrete content rendering. Frames retain immutable image snapshots from
// the same atlas/alias store as the ordinary native and expansion renderers.
class ContentArt final:public ContentPhasePresentation,public DartPresentation {
public:
    ContentArt(TypedBattleState& world,NativeArtStore& store,ExpansionArt& expansion,std::vector<NativeArtDraw>& frame)
        :world_(world),store_(store),expansion_(expansion),frame_(frame){}
    void draw_dart(const EntityRef&,Point,double angle)override;
    void draw_mortar_projectile(const EntityRef&,double,const std::optional<Point>&,std::string_view)override;
    void draw_ghost_effect(const GhostBlast&)override;
    void draw_reed_effect(const ReedBolt&)override;
    void draw_spring_effect(const SpringSwipe&)override;
    void draw_grenade_effect(const GrenadeBlast&)override;
    void draw_grenade_projectile(const GrenadeRef&,double,double)override;
    void draw_hook_rope(Point)override;
    void draw_zombie_projectile(const ContentProjectileRef&,std::string_view,double,double)override;
    void draw_lettuce_flash(const LettuceFlash&)override;
    void restore_content_art()override{expansion_.restore();}
    void alias_content_art(const std::string& first,const std::string& second)override{expansion_.alias(first,second);}
    bool has_content_sprite(const std::string& key)const override{return bool(store_.find(key));}
private:
    TypedBattleState& world_;NativeArtStore& store_;ExpansionArt& expansion_;std::vector<NativeArtDraw>& frame_;
    NativeArt required(const std::string&)const;
    void emit(const NativeArt&,Point);
    void center(const NativeArt&,Point,double angle);
    void frost(Point,int count,double radius,int seed,double age);
};
} // namespace pvz::typed72
