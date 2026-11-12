#include "cold_zombie_secrets.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
bool one(std::string_view s,std::initializer_list<std::string_view> list){return std::find(list.begin(),list.end(),s)!=list.end();}
bool water(std::string_view s){return one(s,{"zombie:潜水僵尸","zombie:海豚僵尸","zombie:鸭子普通僵尸","zombie:鸭子路障僵尸","zombie:鸭子铁桶僵尸","zombie:滚桶僵尸","zombie:钩索僵尸","zombie:海盗船长","zombie:小鬼炮"});}
bool air(std::string_view s){return one(s,{"zombie:海盗鹦鹉","zombie:乌鸦","zombie:气球僵尸","zombie:飞贼僵尸"});}
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
}
bool ColdZombieSecrets::seat_has(Seat seat,std::string_view key)const{
    if(team_of(seat)!=Seat::zombie)return false;const auto& player=world_.heroes.players[seat_index(seat)];if(!player)return false;
    return std::find(player->secrets.begin(),player->secrets.end(),"zsecret:"+std::string(key))!=player->secrets.end();
}
bool ColdZombieSecrets::has(std::string_view key)const{for(Seat seat:seats_for(world_.mode))if(seat_has(seat,key))return true;return false;}
bool ColdZombieSecrets::enabled()const{for(Seat seat:seats_for(world_.mode))if(team_of(seat)==Seat::zombie)if(const auto& p=world_.heroes.players[seat_index(seat)])for(const auto& key:p->secrets)if(key.starts_with("zsecret:"))return true;return false;}
bool ColdZombieSecrets::last_stand()const{for(const auto& until:world_.heroes.last_stand)if(until)return true;return false;}
void ColdZombieSecrets::configure_locked(){
    trinity_.fill(false);
    for(Seat seat:seats_for(world_.mode))if(seat_has(seat,"海陆空")){
        bool land_found=false,water_found=false,air_found=false;
        for(const auto& key:deployment_.players[seat_index(seat)].deck){const auto& card=catalog_.at(key);if(card.category=="secret"||card.behavior=="grave")continue;
            water_found=water_found||water(key);air_found=air_found||air(key);land_found=land_found||(!water(key)&&!air(key));
        }trinity_[seat_index(seat)]=land_found&&water_found&&air_found;
    }
}
void ColdZombieSecrets::scale_hp(const ZombieRef& z,double factor){z->body.hp*=factor;z->max_hp.set(z->max_hp.or_missing(z->body.hp)*factor);}
bool ColdZombieSecrets::scale_speed(const ZombieRef& z,std::string tag,double bonus){
    auto& values=z->patch.speed_factors;double before=1.;for(const auto& [key,value]:values){if(key==tag)return false;before+=value;}
    values.emplace_back(std::move(tag),bonus);double after=1.;for(const auto& pair:values)after+=pair.second;
    if(before==0.)throw std::domain_error("zero zombie speed bonus denominator");const double factor=after/before;
    z->native.move_speed.set(z->native.move_speed.or_missing(0.)*factor);if(z->base_speed.present())z->base_speed.get()*=factor;return true;
}
void ColdZombieSecrets::on_spawn(const ZombieRef& z,const ColdCard& card,const ColdParent* parent){
    if(!enabled()||card.side!="zombie"||z->protection.grave)return;const auto& key=card.base_id;const Seat seat=z->source.seat.value_or(Seat::zombie);
    if(key=="zombie:萝卜伞僵尸"&&seat_has(seat,"萝卜伞")){scale_hp(z,2.);z->patch.umbrella_secret.set(true);}
    if(has("散弹攻击")&&key=="zombie:机枪僵尸")scale_hp(z,2.);
    if(has("大运！小子")&&one(key,{"zombie:雪橇车僵尸","zombie:滚桶僵尸"}))scale_speed(z,"大运",1.);
    if(has("体育生")&&one(key,{"zombie:撑杆跳僵尸","zombie:橄榄球僵尸","zombie:黑撑杆僵尸","zombie:黑橄榄僵尸"})){
        scale_hp(z,1.25);scale_speed(z,"体育生",.25);if(key=="zombie:黑橄榄僵尸")z->expansion.charge_cd.set(750.);
    }
    if(has("斩首行动")&&key=="zombie:雪人僵尸"){scale_hp(z,2.);z->source.no_hero_attack.erase();z->content.headhunt.set(true);}
    z->protection.hurt_tick.set(double(world_.heroes.tick));
    if(has("僵王出品")){if(z->body.armor_hp>0.)z->body.armor_hp*=1.25;if(z->body.hand_hp>0.)z->body.hand_hp*=1.25;if(z->armor_max.present()&&!z->armor_max.is_null()&&z->armor_max.get()!=0.)z->armor_max.get()*=1.25;}
    if(one(z->body.hand,{"报纸","钢门","梯子","铁栅门","传送带"})){z->registration.secret_hand.set(z->body.hand);z->hand_max.set(z->body.hand_hp);}
    if(has("立棍！小子")&&one(key,{"zombie:撑杆跳僵尸","zombie:黑撑杆僵尸"}))z->registration.secret_pole.set(z->body.hand=="撑杆");
    if(trinity_[seat_index(seat)]&&(water(key)||air(key))){scale_hp(z,1.5);scale_speed(z,"海陆空",.25);}
    if(has("三五成群")&&one(key,{"zombie:普通僵尸","zombie:鸭子普通僵尸","zombie:黑普通僵尸"}))z->registration.secret_crowd.set(!(parent&&parent->card&&one(*parent->card,{"zombie:旗帜僵尸","zombie:黑旗帜僵尸"})));
}
void ColdZombieSecrets::on_deployed(const std::string& entity,const std::optional<std::string>& grave){
    if(!has("头兵")||!grave||grave->empty())return;const auto g=world_.native_objects.get(*grave),u=world_.native_objects.get(entity);if(!g||!u)return;
    const auto* gz=std::get_if<ZombieRef>(&*g);const auto* uz=std::get_if<ZombieRef>(&*u);if(!gz||!uz)throw std::logic_error("zombie deployment did not resolve a zombie record");
    if(yes((*gz)->registration.first_soldier_used))return;(*gz)->registration.first_soldier_used.set(true);scale_hp(*uz,1.5);services_.first_soldier_event({*grave,entity});
}
std::optional<std::string> ColdZombieSecrets::flag_summon(const std::string& card)const{
    if(card=="zombie:旗帜僵尸"&&has("一大波僵尸"))return "zombie:路障僵尸";return {};
}
std::vector<ZombieRef> ColdZombieSecrets::own_scarecrows()const{
    auto result=scarecrows_.living();std::erase_if(result,[&](const auto& z){return world_.heroes.owner(source_ref(z))!=Seat::zombie||z->body.hp<=0.;});return result;
}
double ColdZombieSecrets::crow_surcharge(Seat seat)const{return seat_has(seat,"鸦群")?50.*own_scarecrows().size():0.;}
std::vector<std::string> ColdZombieSecrets::crow_flock(const std::string& crow,Seat seat){
    auto sources=own_scarecrows();std::stable_sort(sources.begin(),sources.end(),[](const auto& a,const auto& b){return a->source.id.or_missing("")<b->source.id.or_missing("");});
    std::vector<std::string> made;
    for(const auto& z:sources){const auto& p=z->body.motion.get();struct Exemption{int& value;Exemption(int& v):value(v){++value;}~Exemption(){--value;}} scope(world_.spawn_ban_exempt);
        ColdParent parent;parent.id=crow;if(auto child=services_.spawn_flock({p.x,p.y-world_.runtime.tile},z->body.facing,parent))made.push_back(*child);
    }services_.crow_flock_event({seat,crow,made});return made;
}
} // namespace pvz::typed72
