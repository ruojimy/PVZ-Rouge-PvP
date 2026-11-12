#include "cold_catalog.h"
#include <algorithm>
#include <set>
namespace pvz::typed72 {
namespace {
bool has(std::span<const std::string> values,std::string_view key){return std::find(values.begin(),values.end(),key)!=values.end();}
template<class T> bool value(const Field<T>& v){return v.present()&&!v.is_null();}
bool truth(const Field<bool>& v){return value(v)&&v.get();}
std::string text(const Field<std::string>& v){return value(v)?v.get():std::string{};}
std::string prefix80(const std::string& text){size_t end=0,count=0;while(end<text.size()){
    if((static_cast<unsigned char>(text[end])&0xc0)!=0x80&&count++==80)break;++end;
}return text.substr(0,end);}
}
ColdCatalog::ColdCatalog(const ColdCatalogData& data):data_(data){
    for(const auto& card:data.cards)if(!by_id_.emplace(card.id,&card).second)throw std::logic_error("Duplicate compiled card");
    for(const auto& replacement:data.replacements)if(!replacements_.emplace(replacement.base,&replacement).second)throw std::logic_error("Duplicate compiled replacement");
}
const ColdCard* ColdCatalog::find(std::string_view key)const {const auto it=by_id_.find(std::string(key));return it==by_id_.end()?nullptr:it->second;}
const ColdCard& ColdCatalog::at(const std::string& key)const {const auto* card=find(key);if(!card)throw std::out_of_range(key);return *card;}
bool ColdCatalog::allowed(const std::string& key,std::span<const std::string> bans,bool spawn,std::span<const std::string> secrets)const {
    const auto* card=find(key);if(!card)return false;
    if(!truth(card->pvp_regular_unit))for(const auto& boss:data_.boss_names)if(card->name.find(boss)!=std::string::npos)return false;
    if(!card->selectable&&!(spawn&&truth(card->spawn_only)))return false;
    if(has(data_.protected_cards,key))return true;
    if(has(bans,key)||has(bans,card->family))return false;
    const auto dependency=text(card->dependency);
    if(!dependency.empty()&&(has(bans,dependency)||has(bans,at(dependency).family)))return false;
    const auto required=text(card->required_secret);
    return required.empty()||(has(secrets,required)&&allowed(required,bans));
}
std::vector<std::string> ColdCatalog::native_secrets(std::span<const std::string> secrets,std::span<const std::string> bans)const {
    std::set<std::string> names;
    for(const auto& key:secrets){const auto* card=find(key);
        if(!allowed(key,bans)||!card||card->category!="secret")throw std::invalid_argument("秘籍不可用："+prefix80(key));
        if(card->side=="plant")names.insert(card->native_secret_name.get());
    }
    return {names.begin(),names.end()};
}
ColdCard ColdCatalog::actual(const std::string& key,std::span<const std::string> secrets,bool night)const {
    const auto& source=at(key);const auto derived=data_.derived_bases.find(key);
    const auto& base=derived==data_.derived_bases.end()?key:derived->second;
    const auto replacement=replacements_.find(base);
    ColdCard c=source;
    if(replacement!=replacements_.end()&&(derived!=data_.derived_bases.end()||has(secrets,replacement->second->secret))){
        c=at(replacement->second->resolved);c.id=base;c.base_id=base;
        c.category=at(base).category;c.selectable=at(base).selectable;
    }
    const auto secret=[&](std::string_view name){return has(secrets,name);};
    if(c.side=="plant"&&c.category!="secret"){
        if(secret("secret:咖啡")&&base=="plant:咖啡豆"){c.cost=50.;c.native_cost.set(50.);c.native_cd.set(750.);}
        if(secret("secret:三向蓝火")&&base=="plant:三向射手"){c.native_cost.set(450.);c.projectile_asset.set("火豆");}
        if(secret("secret:速植")&&value(c.native_cd))c.native_cd.get()*=data_.fast_plant_cooldown_factor;
        if(secret("secret:硬化")&&value(c.native_hp)){
            if(c.native_hp.get()>data_.hardening_min_base_hp)c.native_hp.get()*=data_.hardening_hp_factor;
            else if(c.native_hp.get()==data_.hardening_min_base_hp)c.native_hp.get()+=3.;
        }
    }
    if(value(c.native_cd)){
        c.native_deploy_cd.set(c.side=="zombie"&&text(c.expansion).empty()?0.:c.native_cd.get());
        c.cooldown=c.native_deploy_cd.get()/250.;
    }
    if(value(c.native_hp))c.hp.set(c.native_hp.get());
    if((data_.health.contains(base)&&c.resolved_id==base)||c.resolved_id=="plant:石果子"){
        c.hp.set(data_.health.at(c.resolved_id));
        if(base=="plant:路灯花"&&secret("secret:光疗"))c.hp.get()*=2.;
        if(c.side=="plant"&&secret("secret:硬化"))c.hp.set(c.hp.get()>data_.hardening_min_base_hp?c.hp.get()*data_.hardening_hp_factor:c.hp.get()+3.);
    }
    if(data_.costs.contains(base)&&c.resolved_id==base)c.cost=data_.costs.at(base);
    if(secret("secret:三向蓝火")&&(base=="plant:三向射手"||base=="plant:裂荚射手"||base=="plant:豌豆迫击炮"))c.cost+=50.;
    if(base=="plant:胆小菇"&&secret("secret:胆大"))c.cost+=25.;
    if(base=="plant:杨桃"&&secret("secret:大帝"))c.cost=data_.starfruit_cost;
    if(c.resolved_id=="plant:龙蒺藜")c.hp.set(18.);
    if(base=="plant:海蘑菇"&&secret("secret:水兵")){
        c.allow_air.set(true);c.cost+=data_.sea_shroom_surcharge;
        c.description+="水兵：无法选中，种植冷却翻倍。";
        c.native_description.set(text(c.native_description)+"水兵：无法选中，种植冷却翻倍。");
    }
    if(base=="plant:小喷菇"&&secret("secret:小喷"))c.cost+=25.;
    if(base=="plant:抓人草"&&secret("secret:触手"))c.cost+=50.;
    if(data_.plant_cooldowns.contains(base))c.cooldown=data_.plant_cooldowns.at(base)*(secret("secret:速植")?data_.fast_plant_cooldown_factor:1.);
    if(base=="plant:海蘑菇"&&secret("secret:水兵"))c.cooldown*=2.;
    if((base=="plant:土豆地雷"||base=="plant:原始土豆地雷")&&secret("secret:地雷"))c.cooldown*=.75;
    if(base=="plant:魅惑菇"&&secret("secret:魅惑"))c.cooldown*=.25;
    if(base=="plant:模仿者"&&secret(data_.imitate_secret))c.cooldown*=data_.imitate_cooldown_factor;
    if(data_.zombie_cooldowns.contains(base))c.cooldown=data_.zombie_cooldowns.at(base);
    if(night&&c.side=="plant"&&truth(c.mushroom))c.cost+=25.;
    if(night&&(base=="plant:向日葵"||base=="plant:双子向日葵"||base=="zombie:脑光墓碑"||base=="zombie:双生脑光墓碑"||base=="zombie:水上脑光墓碑"||base=="zombie:水上双生脑光墓碑"))c.period.set(20.);
    if(c.side=="zombie"&&c.category!="secret"){
        for(const auto& table:data_.zombie_cost_set)if(secret("zsecret:"+table.secret))for(const auto& [id,amount]:table.values)if(id==base)c.cost=amount;
        for(const auto& table:data_.zombie_cost_add)if(secret("zsecret:"+table.secret))for(const auto& [id,amount]:table.values)if(id==base)c.cost=std::max(0.,c.cost+amount);
        for(const auto& table:data_.zombie_hp_factor)if(secret("zsecret:"+table.secret))for(const auto& [id,factor]:table.values)if(id==base&&value(c.hp))c.hp.get()*=factor;
        if(secret("zsecret:加急")&&c.behavior!="grave"&&c.cooldown)c.cooldown*=data_.rush_cooldown;
        if(secret("zsecret:暴怒")&&base=="zombie:石化火炬")c.asset=data_.rage_torch_art;
        if(secret("zsecret:黏糊糊")&&(base=="zombie:史莱姆僵尸"||base=="zombie:中型史莱姆"||base=="zombie:小型史莱姆"))c.slime_sticky.set(true);
        if(secret("zsecret:萝卜伞")&&base=="zombie:萝卜伞僵尸"){c.hp.get()*=2.;c.umbrella_secret.set(true);}
        if(secret("zsecret:手雷")&&base=="zombie:掷弹兵僵尸"){c.cooldown*=.5;c.grenade_secret.set(true);}
        if(secret("zsecret:空输")&&base=="zombie:飞贼僵尸"){c.cost=100.;c.cooldown*=.5;}
    }
    if(base=="plant:火爆辣椒")c.damage=750.;
    std::set<std::string> ordered(secrets.begin(),secrets.end());std::vector<std::string> names;
    for(const auto& id:ordered)if(const auto* s=find(id);s&&s->category=="secret"&&s->side=="plant")names.push_back(s->native_secret_name.get());
    c.native_secret_names.set(std::move(names));return c;
}
ColdCard ColdCatalog::resolve(const std::string& key,std::span<const std::string> secrets,std::span<const std::string> bans,bool night)const {
    auto names=native_secrets(secrets,bans);
    if(!allowed(key,bans,true,secrets))throw std::invalid_argument("生成卡牌不可用");
    if(at(key).category=="secret")throw std::invalid_argument("秘籍为常驻卡槽，不能生成实体");
    auto card=actual(key,secrets,night);
    if(!allowed(card.base_id,bans,true,secrets))throw std::invalid_argument("基础卡牌已被禁用");
    if(card.resolved_id!=card.base_id&&!allowed(card.resolved_id,bans,true,secrets))throw std::invalid_argument("派生形态缺少秘籍或已被禁用");
    card.native_secret_names.set(std::move(names));return card;
}
ColdCard ColdCatalog::player_card(const std::string& key,std::span<const std::string> secrets,std::span<const std::string> bans,bool night,const std::string& copied)const {
    auto card=resolve(key,secrets,bans,night);
    if(key=="plant:模仿者"&&has(secrets,"secret:肆意模仿")&&!copied.empty())card.cost=resolve(copied,secrets,bans,night).cost-100.;
    return card;
}
ColdCard ColdCatalog::unit_card(const std::string& key,std::span<const std::string> secrets,std::span<const std::string> bans,bool night,const std::string& copied)const {
    try{return player_card(key,secrets,bans,night,copied);}catch(const std::invalid_argument&){return actual(key,secrets,night);}
}
bool ColdCatalog::deathmatch_blocked(const ColdCard& c)const{return c.producer&&!has(data_.deathmatch_allowed_producers,c.base_id);}
double ColdCatalog::initial_cooldown(double value){return value<=12.?0.:value<=48.?value/2.:value;}
double ColdCatalog::deployment_cooldown(double value,bool deathmatch){return deathmatch?value*(value<=12.?.5:value<=48.?2./3.:.75):value;}
} // namespace pvz::typed72
