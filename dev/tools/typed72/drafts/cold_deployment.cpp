#include "cold_deployment.h"
#include <algorithm>
#include <unordered_set>
namespace pvz::typed72 {
namespace {
std::string_view text(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
bool one(std::string_view value,std::initializer_list<std::string_view> list){return std::find(list.begin(),list.end(),value)!=list.end();}
void set(std::vector<std::pair<std::string,double>>& items,const std::string& key,double value){for(auto& item:items)if(item.first==key){item.second=value;return;}items.emplace_back(key,value);}
}
std::vector<ColdPlacementPlant> ColdDeployment::placement_roster()const{
    std::vector<ColdPlacementPlant> result;result.reserve(world_.plant_roster->size());
    for(const auto& p:*world_.plant_roster){const auto content=text(p->source.content);if(content=="抓人草触手")continue;
        const bool vine=one(content,{"阳光藤蔓","忧郁藤蔓","抓人草"});const bool shell=p->kind=="南瓜头"||vine||(p->kind=="模仿者"&&text(p->copy_card)=="plant:抓人草");
        const bool air=one(content,{"旋转芜菁","芦笋战机"})||(p->kind=="模仿者"&&one(text(p->copy_card),{"plant:旋转芜菁","plant:芦笋战机"}));
        // Serialized native placement state writes True whenever 睡觉 exists.
        result.push_back({shell?"南瓜头":p->kind,p->cell,p->sleep.present(),content=="水盆",vine,air,p->sleep.present()});
    }return result;
}
ColdPlacementResult ColdDeployment::placement(Seat seat,const std::string& key,Point point,std::optional<std::string> grave,std::optional<std::string> copy)const{
    const auto roster=placement_roster();ColdPlacementRules native(world_.terrain,roster,*native_secrets_,state_.map_source,state_.spike_cost.or_missing(100.));return placement_.placement(seat,key,point,native,std::move(grave),std::move(copy));
}
bool ColdDeployment::campaign_allowed(const std::string& initial)const{
    std::unordered_set<std::string> seen;std::string key=initial;
    do{const auto* card=catalog_.find(key);if(!card||!seen.emplace(key).second||one(key,{"plant:甜薯","zombie:稻草人","zombie:垃圾桶僵尸"}))return false;
        key=std::string(text(card->dependency));
    }while(!key.empty());return true;
}
void ColdDeployment::coffee(Cell cell,double facing){
    auto target=vines_.coffee_target(cell);if(!target)target=find_plant(*world_.plant_roster,cell,true);if(!target)return;
    auto& plant=*world_.plant_roster->at(*target);if(!plant.sleep.present())throw std::out_of_range("coffee target has no sleep field");plant.sleep.erase();
    const bool aquatic=plant.kind=="海蘑菇"&&std::find(native_secrets_->begin(),native_secrets_->end(),"水兵")==native_secrets_->end();const double tile=world_.runtime.tile;
    world_.runtime.native_constructor->add_entity("咖啡豆",facing,{cell.x*tile+tile,cell.y*tile+(aquatic?0.:tile*.5),0.,0.});
    world_.runtime.entities.list()->back()->expires.set(800.);
}
std::string ColdDeployment::deploy(Seat seat,const std::string& key,Point point,std::optional<std::string> grave,std::optional<std::string> copy,std::optional<double> facing){
    if(seat!=team_of(seat)||world_.mode!=MatchMode::duel){
        const bool team_mode=world_.mode==MatchMode::duo||world_.mode==MatchMode::coop;
        if(team_mode&&world_.heroes.players[seat_index(seat)]&&world_.heroes.players[seat_index(seat)]->hp<=0.)return "戴夫已阵亡，等待队友复活";
        state_.acting_seat=seat;struct Clear{std::optional<Seat>& seat;~Clear(){seat.reset();}} clear{state_.acting_seat};return perform(seat,key,point,std::move(grave),std::move(copy),facing);
    }return perform(seat,key,point,std::move(grave),std::move(copy),facing);
}
std::string ColdDeployment::perform(Seat seat,const std::string& key,Point point,std::optional<std::string> grave,std::optional<std::string> copy,std::optional<double> facing){
    if(world_.mode==MatchMode::pve||world_.mode==MatchMode::coop)if(catalog_.find(key)&&(!campaign_allowed(key)||(key=="plant:模仿者"&&copy&&catalog_.find(*copy)&&!campaign_allowed(*copy))))return world_.mode==MatchMode::coop?"合作模式禁用此卡":"闯关模式禁用此卡";
    auto result=placement(seat,key,point,grave,copy);if(!result.error.empty())return result.error;if(!result.plan)throw std::logic_error("placement returned neither plan nor error");
    const auto plan=std::move(*result.plan);const auto& card=plan.card;const Seat side=team_of(seat);const size_t index=seat_index(seat);
    const double direction=facing.value_or(double(published_.heroes.at(index).value().visible.facing));cold_select_hero(world_.heroes,seat,native_secrets_);
    if(plan.copied)world_.placement.imitation=plan.copied->native_input_name;
    std::optional<std::string> entity;
    if(side==Seat::plant&&card.behavior=="grass"){
        const auto cell=plan.cell.value();world_.terrain.native_at(cell.y,cell.x).block=card.terrain_kind;services_.sync_terrain();services_.terrain_grass(cell);
    }else if(side==Seat::plant&&card.behavior=="coffee")coffee(plan.cell.value(),direction);
    else{
        entity=admission_.spawn(card.id,side,plan.position,direction,plan.temporary);
        if(side==Seat::zombie&&!entity)return "未能生成该单位，未扣除脑光或冷却";
        if(side==Seat::plant&&!text(card.content).empty()&&!entity)return "未能生成该植物，未扣除阳光或冷却";
        if(entity&&plan.grave_target){const auto object=world_.native_objects.get(*entity);if(!object)throw std::out_of_range("missing deployed gravebuster");graves_.attach(std::get<PlantRef>(*object),*plan.grave_target);}
        if(entity&&plan.copied){const auto object=world_.native_objects.get(*entity);if(!object)throw std::out_of_range("missing deployed imitater");std::get<PlantRef>(*object)->copy_card.set(plan.copied->id);}
    }
    resources_.accounts[index].balance-=plan.charge;state_.players[index].spent+=plan.charge;
    if(side==Seat::plant&&entity&&card.category!="tool"&&card.category!="secret"&&card.behavior!="gravebuster"&&card.behavior!="copy")state_.players[index].last_copy_card=key;
    if(side==Seat::plant&&entity&&card.base_id=="plant:地刺"&&card.native_secret_names.present()&&!card.native_secret_names.is_null()&&std::find(card.native_secret_names.get().begin(),card.native_secret_names.get().end(),"地刺")!=card.native_secret_names.get().end())state_.spike_cost.set(std::max(15.,state_.spike_cost.or_missing(plan.charge)-10.));
    const auto current=placement_.player_card(seat,key);const double cooldown=ColdCatalog::deployment_cooldown(current.cooldown,room_.deathmatch||(side==Seat::zombie&&secrets_.last_stand()));const double ready=world_.heroes.time+cooldown;
    set(world_.heroes.players[index]->cooldowns,key,ready);set(room_.players[index].cooldown_spans,key,ready-world_.heroes.time);
    services_.deploy_event({seat,key,plan.charge,entity,plan.position,grave,direction});
    if(entity&&one(key,{"zombie:旗帜僵尸","zombie:黑旗帜僵尸"}))flag_reinforcements(*entity);
    if(key=="plant:黄金蓓蕾"&&entity&&state_.ranked)room_.players[index].collect_locked_until=std::max(room_.players[index].collect_locked_until,world_.heroes.time+12.);
    if(side==Seat::zombie&&entity){secrets_.on_deployed(*entity,grave);if(grave&&!grave->empty()&&secrets_.unsealed(seat))services_.select_grave(seat,*grave);}
    if(key=="zombie:乌鸦"&&entity){if(secrets_.seat_has(seat,"鸦群"))secrets_.crow_flock(*entity,seat);else{const auto* unit=placement_.find(*entity);if(!unit)throw std::out_of_range("missing crow projection");scarecrows_.crow_echo(unit->position,*entity);}}
    services_.sync_public();return {};
}
void ColdDeployment::flag_reinforcements(const std::string& flag_id){
    const auto* flag=placement_.find(flag_id);if(!flag)throw std::out_of_range("missing deployed flag");
    const auto key=secrets_.flag_summon(flag->card->id).value_or(flag->card->id=="zombie:黑旗帜僵尸"?"zombie:黑普通僵尸":"zombie:普通僵尸");
    // This query intentionally bypasses card bans; each spawn still performs
    // the actual internal-handout resolution and budget guard.
    const auto actual=placement_.unit_card(Seat::zombie,key);std::vector<RoomPublishedUnit> graves;
    for(const auto& u:published_.units)if(u.side==Seat::zombie&&u.card->behavior=="grave"&&u.hp>0.)graves.push_back(u);
    std::sort(graves.begin(),graves.end(),[](const auto& a,const auto& b){return a.id<b.id;});
    ColdParent parent;parent.id=flag_id;parent.card=flag->card->id;
    for(const auto& grave:graves){const double facing=published_.heroes.at(seat_index(Seat::zombie)).value().visible.facing;const auto position=placement_.grave_soldier_exit(actual,Seat::zombie,grave,facing);
        if(!position||published_.units.size()>=700){services_.flag_event({grave.id,flag_id,{},true});continue;}
        struct Exemption{int& count;Exemption(int& c):count(c){++count;}~Exemption(){--count;}} exemption(world_.spawn_ban_exempt);
        if(auto child=admission_.spawn(actual.id,Seat::zombie,*position,facing,true,&parent))services_.flag_event({grave.id,flag_id,*child,false});
    }
}
} // namespace pvz::typed72
