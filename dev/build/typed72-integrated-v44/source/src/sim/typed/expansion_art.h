#pragma once
#include "sim/typed/native_art.h"
#include "sim/typed/targets.h"
#include <set>
namespace pvz::typed72 {
class ExpansionArt {
public:
    explicit ExpansionArt(NativeArtStore& store):store_(store){}
    void gate(const ZombieRef&);
    void clear();
    void restore();
    void alias_one(const std::string&,const std::string&);
    void alias(const std::string&,const std::string&);
    bool has(const std::string& name)const{return bool(store_.find(name));}
    NativeArt armor_art(const std::string&,const std::string& wearer="小鬼僵尸");
    // Produces zero, one or two concrete layers at the same synchronous call
    // boundary as 摄像显示, including suppression of a composited headgear.
    std::vector<NativeArtDraw> seated(const NativeArt&,Point);
    static NativeArt retrace(const NativeArt&,const NativeArt& replacement);
    static std::optional<Point> seat(const std::string& armor,const NativeArt& head,const NativeArt& plate);
    static double overlap(const std::string&,NativeArtBox head,NativeArtBox plate);
    const ZombieRef& wearer()const{return wearer_;}
private:
    struct Body {std::string name,armor;NativeArt plate;};
    NativeArtStore& store_;
    std::map<std::string,NativeArt> saved_atlas_;
    std::optional<Body> body_;
    ZombieRef wearer_;
    std::optional<std::pair<NativeArt,Point>> imp_;
    std::set<std::string> suppress_;
    std::map<std::string,std::optional<Point>> imp_seats_;
    std::map<std::string,NativeArt> imp_composites_;
    std::map<std::pair<std::string,std::string>,NativeArt> carrier_heads_;
    bool imp_armored()const;
    std::string worn_name(const std::string&)const;
    std::optional<Point> imp_seat(const std::string& armor);
    NativeArt imp_composite(const std::string& armor,Point seat);
    std::optional<std::pair<NativeArt,Point>> imp_headgear();
    NativeArt carrier_headgear(const std::string&,const NativeArt&,const std::string&,const NativeArt&);
};
}
