#include "cold_placement.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
template<class T>bool has(const T& values,std::string_view key){return std::find(values.begin(),values.end(),key)!=values.end();}
bool yes(const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();}
std::string text(const Field<std::string>& value){return value.present()&&!value.is_null()?value.get():"";}
double number(const Field<double>& value,double fallback){return value.present()?value.get():fallback;}
double mod(double value,double width){return py::mod(value,width);}
double delta(double from,double to,double width){return mod(to-from+width/2.,width)-width/2.;}
bool overlap(Point a,double aw,double ah,Point b,double bw,double bh,double width){return std::abs(delta(a.x,b.x,width))<(aw+bw)/2.-1.&&a.y>b.y-bh+1.&&b.y>a.y-ah+1.;}
bool harmless(std::string_view behavior){return behavior=="spike"||behavior=="mine"||behavior=="pot"||behavior=="lily";}
}
bool ColdPlacement::present(Seat seat)const{return world_.heroes.players[seat_index(seat)].has_value();}
bool ColdPlacement::deck_has(Seat seat,const std::string& key)const{return has(state_.players[seat_index(seat)].deck,key);}
std::span<const std::string> ColdPlacement::secrets(Seat seat)const{return world_.heroes.players.at(seat_index(seat)).value().secrets;}
double ColdPlacement::facing(Seat seat)const{return published_.heroes.at(seat_index(seat)).value().visible.facing;}
double ColdPlacement::cooldown(Seat seat,const std::string& key)const{
    for(const auto& [name,value]:world_.heroes.players.at(seat_index(seat)).value().cooldowns)if(name==key)return value;return 0.;
}
ColdCard ColdPlacement::player_card(Seat seat,const std::string& key)const{
    return catalog_.player_card(key,secrets(seat),state_.bans,economy_.night,state_.players[seat_index(seat)].last_copy_card.value_or(""));
}
ColdCard ColdPlacement::unit_card(Seat seat,const std::string& key)const{
    return catalog_.unit_card(key,secrets(seat),state_.bans,economy_.night,state_.players[seat_index(seat)].last_copy_card.value_or(""));
}
const RoomPublishedUnit* ColdPlacement::find(const std::string& id)const{for(const auto& u:published_.units)if(u.id==id)return &u;return nullptr;}
RoomPublicCell ColdPlacement::cell(Point p)const{
    const double row=std::floor(p.y/world_.runtime.tile);
    if(row<0.){RoomPublicCell c;c.kind="空";return c;}
    if(row>=published_.terrain.tiles.size()){RoomPublicCell c;c.kind="石";c.solid=true;return c;}
    const auto& line=published_.terrain.tiles.at(size_t(row));const auto col=size_t(std::floor(mod(p.x,width())/world_.runtime.tile));return line.at(col%line.size());
}
bool ColdPlacement::overlaps(Point p,double w,double h,const RoomPublishedUnit& u)const{return overlap(p,w,h,u.position,u.w,u.h,width());}
bool ColdPlacement::blocked(Point p,double w,double h)const{
    const int rows=std::max(1,int(h/(world_.runtime.tile*.5)));
    for(int i=0;i<=rows;++i){const double y=p.y-h+.001+(h-.002)*i/rows;
        for(double x:{p.x-w/2.+.001,p.x+w/2.-.001})if(cell({x,y}).solid)return true;
    }return false;
}
std::optional<ColdPlacement::Surface> ColdPlacement::surface(Point p,bool grave)const{
    const double tile=world_.runtime.tile;const double x=(std::floor(mod(p.x,width())/tile)+.5)*tile;
    // Clamp before integer conversion; hostile finite coordinates may exceed int64.
    const double candidate=grave?std::floor(p.y/tile):std::trunc(p.y/tile)-1.;
    if(candidate>=published_.terrain.tiles.size())return {};
    int start=candidate<0?0:int(candidate);
    if(grave&&cell({x,start*tile+1.}).water)while(start>0&&cell({x,(start-1)*tile+1.}).water)--start;
    for(int row=start;row<std::min(start+4,int(published_.terrain.tiles.size()));++row){const auto c=cell({x,row*tile+1.});if(c.solid||c.water)return Surface{{x,row*tile},c.water};}
    return {};
}
std::optional<Point> ColdPlacement::soldier_exit(const ColdCard& card,Seat side,Point p)const{
    p.x=mod(p.x,width());const double h=number(card.height,44.);const bool flying=yes(card.flying);if(flying)p.y-=100.;
    for(size_t level=0;level<=published_.units.size();++level){
        if(blocked(p,34.,h))return {};
        std::optional<double> ally_top;
        for(const auto& u:published_.units)if(u.hp>0.&&overlaps(p,34.,h,u)){
            if(u.side!=side&&!harmless(u.card->behavior))return {};
            if(u.side==side&&u.mobile&&!u.card->flying&&!u.burrowed)ally_top=ally_top?std::min(*ally_top,u.position.y-u.h):u.position.y-u.h;
        }
        if(flying||!ally_top){if(flying)p.y+=100.;return p;}p.y=*ally_top;
    }return {};
}
std::optional<Point> ColdPlacement::grave_soldier_exit(const ColdCard& card,Seat side,const RoomPublishedUnit& grave,double direction)const{
    if(auto point=soldier_exit(card,side,{grave.position.x+direction*42.,grave.position.y}))return point;
    return soldier_exit(card,side,grave.position);
}
std::optional<Point> ColdPlacement::aquatic_exit(const ColdCard& card,Seat side,const RoomPublishedUnit& grave,double direction)const{
    const double tile=world_.runtime.tile,h=number(card.height,44.);
    for(double distance:{42.,42.+tile}){
        const auto spot=surface({grave.position.x+direction*distance,grave.position.y});if(!spot||!spot->water)continue;
        const Point p=spot->position;const double drop=p.y-grave.position.y,dx=delta(grave.position.x,p.x,width());
        if(drop<-.01||drop>tile*2.+.01||dx*direction<=0.||std::abs(dx)>tile*2.+.01)continue;
        const auto clear=[&](Point at){if(blocked(at,34.,h))return false;
            for(const auto& u:published_.units)if(u.hp>0.&&u.side!=side&&!harmless(u.card->behavior)&&overlaps(at,34.,h,u))return false;return true;};
        bool allowed=true;int count=std::max(1,int(std::abs(dx)/8.)+1);
        for(int i=0;i<=count&&allowed;++i)allowed=clear({mod(grave.position.x+dx*i/count,width()),grave.position.y});
        count=std::max(1,int(drop/8.)+1);for(int i=1;i<=count&&allowed;++i)allowed=clear({p.x,grave.position.y+drop*i/count});
        if(allowed)if(auto result=soldier_exit(card,side,p))return result;
    }return {};
}
ColdPlacementResult ColdPlacement::thief(Seat seat,const std::string& key,Point p)const{
    if(team_of(seat)!=Seat::zombie||!present(seat)||!deck_has(seat,key))return "卡牌不在本方卡槽";
    if(room_.result)return "对局已结束";
    if(!std::isfinite(p.x)||!std::isfinite(p.y)||p.x<0||p.x>=width()||p.y<0||p.y>=height())return "放置坐标无效";
    ColdCard card;try{card=catalog_.resolve(key,secrets(seat),state_.bans);}catch(const std::invalid_argument& e){return std::string(e.what());}
    if(cooldown(seat,key)>world_.heroes.time)return "卡牌冷却中";
    if(balance(seat)<card.cost)return "脑光不足";
    if(published_.units.size()>=700)return "战场单位达到上限";
    const double tile=world_.runtime.tile;const auto row=std::floor(p.y/tile),col=std::floor(p.x/tile);
    const RoomPublishedUnit* target=nullptr;
    for(const auto& u:published_.units)if(u.side==Seat::plant&&u.hp>0.&&u.card->id!="plant:幽灵辣椒"&&u.copy_card!="plant:幽灵辣椒"&&u.card->id!="plant:抓人草触手"&&
        std::floor(u.position.x/tile)==col&&py::round0(u.position.y/tile)-1.==row&&(!target||u.id<target->id))target=&u;
    if(!target)return "请选择存活的敌方植物";
    ColdPlacementPlan plan;plan.charge=card.cost;plan.card=std::move(card);plan.position=target->position;plan.slot=key;plan.thief_target=target->id;return plan;
}
ColdPlacementResult ColdPlacement::plant(Seat seat,const std::string& key,Point p,const ColdPlacementRules& native,std::optional<std::string> copied_id)const{
    if(team_of(seat)!=Seat::plant||!present(seat))return "未知植物玩家";
    if(room_.result)return "对局已结束";
    if(!std::isfinite(p.x)||!std::isfinite(p.y))return "放置坐标无效";
    if(!deck_has(seat,key))return "卡牌不在本方卡槽";
    ColdCard card;try{card=catalog_.resolve(key,secrets(seat),state_.bans,economy_.night);}catch(const std::invalid_argument& e){return std::string(e.what());}
    if(cooldown(seat,key)>world_.heroes.time)return "卡牌冷却中";
    std::optional<ColdCard> copied;
    if(card.behavior=="copy"){
        if(!copied_id)copied_id=state_.players[seat_index(seat)].last_copy_card;
        if(!copied_id||*copied_id==key||!deck_has(seat,*copied_id))return "请先种下一株可复制植物，或通过模仿目标按键选择复制目标（默认 V）";
        try{copied=catalog_.resolve(*copied_id,secrets(seat),state_.bans,economy_.night);}catch(const std::invalid_argument& e){return std::string(e.what());}
        if(copied->category=="secret"||copied->category=="tool"||copied->behavior=="gravebuster")return "不能复制工具、秘籍或墓碑吞噬者";
    }else if(copied_id)return "仅模仿者可以指定复制目标";
    if(room_.deathmatch&&(card.producer||(copied&&copied->producer)))return "死斗期间不能新增生产单位";
    double charge=card.cost;if(copied&&has(secrets(seat),"secret:肆意模仿"))charge=copied->cost-100.;
    if(card.native_input_name=="地刺")charge=native.spike_cost;
    if(!std::isfinite(balance(seat)))return "等待本方资源状态";
    if(balance(seat)<charge)return "阳光不足";
    if(published_.units.size()>=700)return "战场单位达到上限";
    const double tile=world_.runtime.tile,raw_row=std::floor(p.y/tile);
    if(raw_row<0.||raw_row>=world_.terrain.rows())return "放置位置超出地图";
    const int row=int(raw_row),col=int(std::floor(mod(p.x,width())/tile));const auto& placed=copied?*copied:card;
    bool special_legal=false;
    if(text(placed.content)=="水盆"){
        if(!native.plants_at(row,col).empty()||!native.accepts("花盆",row,col))return "水盆需要符合花盆放置要求的空格";special_legal=true;
    }else if(text(placed.content)=="冰冻生菜"){
        const auto here=native.plants_at(row,col);const bool occupied=std::any_of(here.begin(),here.end(),[](auto* u){return !u->basin;});
        if(native.water(row,col)&&(!occupied||native.dense()))special_legal=true;
    }
    const bool shell=placed.behavior=="vine"||(!copied&&card.native_input_name=="南瓜头");
    const auto limit=native.dense_error(shell?"南瓜头":placed.native_input_name,row,col);if(!limit.empty())return limit;
    ColdPlacementPlan plan;plan.card=card;plan.charge=charge;plan.position={(col+.5)*tile,(row+1)*tile};plan.cell=Cell{row,col};plan.slot=key;
    if(card.behavior=="gravebuster"){
        const RoomPublishedUnit* target=nullptr;
        for(const auto& u:published_.units)if(u.card->behavior=="grave"&&u.side==Seat::zombie&&u.hp>0.&&
            std::floor(mod(u.position.x,width())/tile)==col&&std::floor((u.position.y-.001)/tile)==row)target=&u;
        if(!target)return "请选择存活的敌方实体墓碑";if(native.marker(row,col))return "墓碑位置已有植物";
        plan.grave_target=target->id;return plan;
    }
    if(card.behavior=="grass"){
        if(!native.grass_cell(row,col))return "草坪需要闲置格，周围八格至少一格实体方块";
        for(const auto& u:published_.units)if(u.hp>0.&&overlaps(plan.position,tile,tile,u))return "草坪位置被单位占用";
        for(const auto& hero:published_.heroes)if(hero&&hero->visible.hp>0.&&overlap(plan.position,tile,tile,hero->visible.position,hero->visible.w,hero->visible.h,width()))return "草坪位置被单位占用";
    }else if(yes(placed.allow_air)){
        if(!native.idle_cell(row,col))return "此处不是闲置空格";
        if(!native.dense())for(const auto& u:published_.units)if(u.hp>0.&&!u.mobile&&std::floor(u.position.x/tile)==col&&std::floor((u.position.y-.001)/tile)==row)return "位置已有单位";
    }else if(shell){if(!native.shell_cell(row,col,placed.behavior=="vine"))return "此处不能放置南瓜头或藤蔓（每格限一个保护壳）";
    }else if(copied&&!special_legal&&!native.accepts(copied->native_input_name,row,col))return "此处不符合复制目标的原版种植条件";
    if(!special_legal&&card.behavior!="grass"&&!yes(placed.allow_air)&&!shell&&!(copied&&yes(copied->aquatic))&&!native.accepts(card.native_input_name,row,col))return "此处不符合原版种植条件";
    plan.copied=std::move(copied);plan.copy_id=copied_id;plan.temporary=plan.copied.has_value();return plan;
}
ColdPlacementResult ColdPlacement::zombie(Seat seat,const std::string& key,Point p,std::optional<std::string> grave_id,std::optional<std::string> copied_id)const{
    if(!present(seat))return "未知玩家";if(room_.result)return "对局已结束";
    if(!std::isfinite(p.x)||!std::isfinite(p.y))return "坐标无效";
    if(!deck_has(seat,key)||!catalog_.allowed(key,state_.bans))return "未携带此卡";
    auto card=player_card(seat,key);if(card.category=="secret")return "秘籍为常驻效果";
    if(cooldown(seat,key)>world_.heroes.time)return "正在冷却";
    double charge=card.cost;
    if(card.behavior=="copy"){
        if(!copied_id||!deck_has(seat,*copied_id)||*copied_id==key||!catalog_.allowed(*copied_id,state_.bans))return "请选择已携带的合法复制目标";
        auto other=player_card(seat,*copied_id);if(other.category=="secret"||other.category=="tool")return "不能复制工具或秘籍";card=std::move(other);charge+=card.cost;
    }
    if(room_.deathmatch&&catalog_.deathmatch_blocked(card))return "死斗禁止新增生产者";
    const auto team=team_of(seat);if(balance(seat)<charge)return team==Seat::plant?"阳光不足":"脑光不足";
    if(published_.units.size()>=700)return "战场单位达到上限";
    ColdPlacementPlan plan;plan.card=card;plan.charge=charge;plan.slot=key;plan.temporary=copied_id&& !copied_id->empty();
    if(team==Seat::zombie&&card.behavior!="grave"){
        const auto* grave=grave_id?find(*grave_id):nullptr;
        if(!grave||grave->side!=team||grave->card->behavior!="grave"||grave->hp<=0.)return "请选择存活的己方脑光墓碑";
        const auto exit=yes(card.aquatic)?aquatic_exit(card,team,*grave,facing(seat)):grave_soldier_exit(card,team,*grave,facing(seat));
        if(!exit)return yes(card.aquatic)?"水生僵尸需要墓碑前方两格内可达的水面出兵口":"墓碑出兵口被地形或敌方单位阻挡";
        plan.position=*exit;plan.position.x=mod(plan.position.x,width());return plan;
    }
    const auto spot=surface(p,card.behavior=="grave");if(!spot)return "需要可放置的地面";
    p=spot->position;const bool water=spot->water;plan.position=p;
    if(card.behavior=="grave"&&cell({p.x,p.y-1.}).water)return "不能在水下地面布置墓碑，请选择水面或陆地";
    std::vector<const RoomPublishedUnit*> vines,occupants;
    for(const auto& u:published_.units)if(u.hp>0.&&overlaps(p,32.,40.,u)){
        if(u.side==team&&u.card->behavior=="grave"&&yes(unit_card(u.original_owner,u.card->id).shell))vines.push_back(&u);
        if(!u.mobile)occupants.push_back(&u);
    }
    if(yes(card.shell)&&!vines.empty())return "此处已有石化藤蔓";
    if(text(card.grave_surface)=="land"&&water&&vines.empty())return "地面墓碑不能放在水面，请选择水上墓碑";
    if(text(card.grave_surface)=="water"&&!water)return "水上墓碑只能放在水面";
    if(yes(card.shell))std::erase_if(occupants,[&](auto* u){return u->side==team&&u->card->behavior=="grave";});
    else if(!vines.empty()&&std::none_of(occupants.begin(),occupants.end(),[&](auto* u){return std::find(vines.begin(),vines.end(),u)==vines.end()&&u->side==team&&u->card->behavior=="grave";}))
        std::erase_if(occupants,[&](auto* u){return std::find(vines.begin(),vines.end(),u)!=vines.end();});
    std::erase_if(occupants,[&](auto* u){return u->card->id=="plant:南瓜头"&&u->side==team;});
    if(yes(card.aquatic)&&!water)return "水生植物需要水面";
    if(!occupants.empty())return "位置已有单位";
    if(blocked(p,32.,40.))return "地面上方空间不足";return plan;
}
std::string ColdPlacement::ring_error(const ColdCard& card,Seat seat,Point point)const{
    double inner=0.,outer=8.;const auto either=[&](std::string_view key){return card.base_id==key||card.id==key;};
    if(either("plant:黄金蓓蕾"))inner=4.;
    else if(either("plant:火爆辣椒")||either("plant:寒冰辣椒")||either("plant:幽灵辣椒")||either("plant:墓碑吞噬者"))outer=4.;
    else if(!either("zombie:坚固脑光墓碑")&&!either("zombie:石化火炬")&&card.behavior=="grave")outer=4.;
    const auto hero=world_.heroes.hero(seat).frame.position.get();const double tile=world_.runtime.tile;
    const double distance=py::hypot(delta(hero->x,point.x,width())/1.5,point.y-(hero->y-tile))/tile;
    if(distance>outer+1e-6)return outer==4.?"计入胜率对局：只能在己方戴夫 4 格内放置":"计入胜率对局：只能在己方戴夫 8 格内放置";
    if(distance<inner-1e-6)return "计入胜率对局：黄金蓓蕾只能放在戴夫 4 到 8 格之间";return {};
}
ColdPlacementResult ColdPlacement::placement(Seat seat,const std::string& key,Point p,const ColdPlacementRules& native,std::optional<std::string> grave,std::optional<std::string> copied)const{
    if(team_of(seat)==Seat::zombie&&secrets_.last_stand()&&deck_has(seat,key)&&catalog_.deathmatch_blocked(player_card(seat,key)))return "最后攻势期间不能新增生产单位";
    auto result=team_of(seat)==Seat::plant?plant(seat,key,p,native,copied):key=="zombie:飞贼僵尸"?thief(seat,key,p):zombie(seat,key,p,grave,copied);
    if(!result.error.empty()||!result.plan)return result;
    auto& plan=*result.plan;
    if(key=="zombie:乌鸦")if(const double extra=secrets_.crow_surcharge(seat);extra!=0.){plan.charge+=extra;if(balance(seat)<plan.charge)return "脑光不足（鸦群：每只稻草人 +50）";}
    if(state_.ranked&&plan.card.category!="secret"&&!(team_of(seat)==Seat::zombie&&plan.card.behavior!="grave"&&secrets_.unsealed(seat))){const auto error=ring_error(plan.card,seat,p);if(!error.empty())return error;}
    return result;
}
} // namespace pvz::typed72
