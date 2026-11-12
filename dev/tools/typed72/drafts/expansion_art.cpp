#include "sim/typed/expansion_art.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
const std::array<const char*,5> suffixes{"","-受伤","-冰冻","-灰烬","-魅惑"};
bool black_marker(const ZombieRef& unit){return unit&&unit->expansion.black_armor.present()&&!unit->expansion.black_armor.is_null()&&!unit->expansion.black_armor.get().empty();}
bool armed(const ZombieRef& unit){return unit&&unit->poison.imp_armor.present()&&!unit->poison.imp_armor.is_null()&&!unit->poison.imp_armor.get().empty()&&unit->poison.imp_armor_hp.present()&&!unit->poison.imp_armor_hp.is_null()&&unit->poison.imp_armor_hp.get()>0.;}
}
void ExpansionArt::clear(){body_.reset();wearer_.reset();imp_.reset();suppress_.clear();}
void ExpansionArt::restore(){for(const auto& [key,image]:saved_atlas_)store_.atlas[key]=image;saved_atlas_.clear();}
void ExpansionArt::alias_one(const std::string& old,const std::string& next){saved_atlas_[old]=store_.atlas.at(old);store_.atlas[old]=store_.atlas.at(next);}
void ExpansionArt::alias(const std::string& old,const std::string& next){for(const auto suffix:suffixes)if(has(old+suffix)&&has(next+suffix))alias_one(old+suffix,next+suffix);}
bool ExpansionArt::imp_armored()const{return armed(wearer_);}
std::string ExpansionArt::worn_name(const std::string& armor)const {
    if(black_marker(wearer_)&&(armor=="路障"||armor=="铁桶"))return "黑"+armor;return armor;
}
NativeArt ExpansionArt::armor_art(const std::string& name,const std::string& wearer) {
    const double scale=store_.factor(wearer);if(scale==1.)return store_.find(name);
    const auto key=wearer+"-"+name;const auto existing=store_.find(key);if(existing)return existing;
    const auto raw=store_.find(name);if(!raw)return {};
    return store_.register_asset(key,store_.shrink(raw,scale));
}
void ExpansionArt::gate(const ZombieRef& unit) {
    clear();if(!unit)return;
    const auto& name=unit->body.kind;const auto& armor=unit->body.armor;
    const bool carrier=name.find("巨人")!=std::string::npos,imp=name.find("小鬼僵尸")!=std::string::npos;
    const bool imp_armed=armed(unit);
    if((armor.empty()&&!imp_armed&&!carrier)||(!carrier&&armor.empty()))return;
    const auto head=store_.find(name+"-首");if(!head)return;
    auto plate=armor.empty()?NativeArt{}:store_.find(armor);
    if(plate&&head->width==plate->width&&!imp)plate.reset();
    wearer_=unit;
    if(plate&&imp)plate=armor_art(worn_name(armor));
    if(!plate&&!imp_armed&&!carrier){wearer_.reset();return;}
    body_=Body{name,armor,plate};
}
double ExpansionArt::overlap(const std::string& armor,NativeArtBox head,NativeArtBox plate) {
    const auto key=NativeArtStore::atlas_name(armor);double cover=.41;
    if(key=="路障"||key=="黑路障")cover=.47;
    else if(key=="铁桶"||key=="黑铁桶")cover=.37;
    else if(key=="橄榄球头盔"||key=="黑橄榄球头盔")cover=1.13;
    return std::min(cover*(head.bottom-head.top+1.),plate.bottom-plate.top+1.);
}
std::optional<Point> ExpansionArt::seat(const std::string& armor,const NativeArt& head,const NativeArt& plate) {
    const auto h=NativeArtStore::bounds(head),p=NativeArtStore::bounds(plate);if(!h||!p)return {};
    return Point{(h->left+h->right-p->left-p->right)/2.,h->top+overlap(armor,*h,*p)-p->bottom};
}
std::optional<Point> ExpansionArt::imp_seat(const std::string& armor) {
    const auto found=imp_seats_.find(armor);if(found!=imp_seats_.end())return found->second;
    return imp_seats_[armor]=seat(armor,store_.find("小鬼僵尸-首"),armor_art(armor));
}
NativeArt ExpansionArt::imp_composite(const std::string& armor,Point point) {
    const auto found=imp_composites_.find(armor);if(found!=imp_composites_.end())return found->second;
    const auto base=store_.find("小鬼僵尸"),plate=armor_art(armor);if(!base||!plate)return {};
    auto composite=NativeArtStore::copy(base);NativeArtStore::blit(composite,plate,point);imp_composites_[armor]=composite;return composite;
}
NativeArt ExpansionArt::retrace(const NativeArt& image,const NativeArt& replacement) {
    using Kind=NativeArtRecipe::Kind;
    std::vector<const NativeArtRecipe*> operations;FrozenArt node=image;
    for(int i=0;i<8&&node;++i) {
        const auto& r=*node->recipe;if(r.kind==Kind::asset)break;
        if(r.kind!=Kind::rotate&&r.kind!=Kind::flip)return {};
        operations.push_back(&r);node=r.source;
    }
    auto out=replacement;
    for(auto i=operations.rbegin();i!=operations.rend();++i)out=(*i)->kind==Kind::rotate?
        NativeArtStore::rotate(out,(*i)->angle):NativeArtStore::flip(out,(*i)->flip_x,(*i)->flip_y);
    return out;
}
std::optional<std::pair<NativeArt,Point>> ExpansionArt::imp_headgear() {
    if(!imp_||!imp_armored())return {};
    const auto& armor=wearer_->poison.imp_armor.get();const auto point=imp_seat(armor);if(!point)return {};
    const auto composite=imp_composite(armor,*point);if(!composite)return {};
    const auto image=retrace(imp_->first,composite);if(!image)return {};
    return std::pair{image,imp_->second};
}
NativeArt ExpansionArt::carrier_headgear(const std::string& key,const NativeArt& image,const std::string& armor,const NativeArt& plate) {
    const auto name=NativeArtStore::atlas_name(key);const auto split=name.find("-首");
    const auto suffix=split==std::string::npos?std::string{}:name.substr(split+std::string("-首").size());
    auto tinted=armor_art(worn_name(armor)+suffix,name.substr(0,name.find('-')));if(!tinted)tinted=plate;
    const auto art=NativeArtStore::art_key(tinted);
    const auto cache=std::pair{key,art?NativeArtStore::atlas_name(*art):armor};
    const auto found=carrier_heads_.find(cache);NativeArt composite;
    if(found!=carrier_heads_.end())composite=found->second;
    else {
        const auto base=store_.find(name);if(!base)return {};
        const auto point=seat(armor,base,tinted);if(!point)return {};
        composite=NativeArtStore::copy(base);NativeArtStore::blit(composite,tinted,*point);carrier_heads_[cache]=composite;
    }
    return retrace(image,composite);
}
std::vector<NativeArtDraw> ExpansionArt::seated(const NativeArt& image,Point position) {
    const auto key=NativeArtStore::art_key(image);std::optional<std::pair<NativeArt,Point>> riding;
    if(body_&&key&&NativeArtStore::atlas_name(*key)=="小鬼僵尸") {
        imp_=std::pair{image,position};riding=imp_headgear();const double lift=store_.rider_lift("小鬼僵尸");
        position.y-=lift;if(riding)riding->second.y-=lift;
    }
    if(body_&&key&&suppress_.contains(NativeArtStore::atlas_name(*key)))return {};
    if(body_&&key&&body_->plate&&key->find("-首")!=std::string::npos&&key->find(body_->name)!=std::string::npos) {
        const auto composite=carrier_headgear(*key,image,body_->armor,body_->plate);
        if(composite) {
            suppress_={NativeArtStore::atlas_name(body_->armor)};
            if(black_marker(wearer_))suppress_.insert(NativeArtStore::atlas_name("黑"+body_->armor));
            return {{NativeArtStore::freeze(composite),position}};
        }
    }
    std::vector<NativeArtDraw> result{{NativeArtStore::freeze(image),position}};
    if(riding)result.push_back({NativeArtStore::freeze(riding->first),riding->second});return result;
}
}
