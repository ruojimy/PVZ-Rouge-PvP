#include "sim/typed/command_actions.h"
#include "core/pymath.h"
#include <cstdio>

namespace pvz::typed72 {
namespace {
bool text(const Field<std::string>& value,std::string_view expected){return value.present()&&!value.is_null()&&value.get()==expected;}
std::string one_decimal(double value){char out[64];std::snprintf(out,sizeof(out),"%.1f",value);return out;}
bool published_solid(const TargetSight& map,Point point,double tile,double width){
    const auto row=std::floor(point.y/tile);if(row<0.)return false;if(row>=double(map.solid.size()))return true;
    const auto& cells=map.solid.at(size_t(row));if(cells.empty())throw std::logic_error("empty published command row");
    return cells.at(size_t(std::floor(py::mod(point.x,width)/tile))%cells.size())!=0;
}
}
bool NativeRoomCommands::secret(Seat seat,std::string_view key)const{
    const auto& secrets=world_.heroes.players.at(seat_index(seat))->secrets;
    return std::find(secrets.begin(),secrets.end(),key)!=secrets.end();
}
bool NativeRoomCommands::coordinates(const NativeCommand& c)const{
    return c.x.valid()&&c.y.valid()&&std::isfinite(c.x.value)&&std::isfinite(c.y.value)&&c.x.value>=0.&&c.x.value<world_.world_width.get()&&c.y.value>=0.&&c.y.value<world_.world_height.get();
}
std::string NativeRoomCommands::turn(Seat seat,const NativeCommand& c){
    if(team_of(seat)!=Seat::plant||!secret(seat,"secret:转向"))return "需要植物方携带转向秘籍";
    if(!c.facing.valid()||(c.facing.value!=-1&&c.facing.value!=1))return "转向方向无效";
    const auto record=c.target.valid()?world_.native_objects.get(c.target.value):std::nullopt;
    const auto* ptr=record?std::get_if<PlantRef>(&*record):nullptr;
    if(!ptr||!text((*ptr)->source.owner,"plant")||(*ptr)->hp.or_missing(0.)<=0.||(*ptr)->dead.present())return "请选择己方存活植物";
    std::vector<std::string> ids;
    for(const auto& p:*world_.plant_roster){
        if(!text(p->source.owner,"plant")||p->hp.or_missing(0.)<=0.||p->dead.present()||p->cell!=(*ptr)->cell)continue;
        p->facing=double(c.facing.value);if(text(p->flying.mode,"sweep"))p->flying.sweep_facing.set(double(c.facing.value));
        ids.push_back(p->source.id.get());
    }
    RoomActionEvent event{RoomActionKind::plant_turned,seat,c.target.value};event.entities=std::move(ids);event.facing=double(c.facing.value);
    services_.emit(std::move(event));services_.sync_public();return {};
}
std::string NativeRoomCommands::select_grave(Seat seat,const NativeCommand& c){
    if(team_of(seat)!=Seat::zombie||!world_.protection.secrets.seat_has(seat,DamageSecret::seal))return "需要携带解除封印秘籍";
    const auto* target=c.grave.valid()?services_.published_target(c.grave.value):nullptr;
    if(!target||!target->grave||target->hp<=0.||team_of(target->side)!=Seat::zombie)return "请选择己方存活的墓碑";
    auto& selected=world_.protection.selected_grave[seat_index(seat)];
    if(selected!=c.grave.value){selected=c.grave.value;services_.emit(RoomActionEvent{RoomActionKind::select_grave,seat,c.grave.value});}
    return {};
}
std::string NativeRoomCommands::detonate(Seat seat,const NativeCommand& c){
    if(!c.target.valid())return "目标编号无效";
    const auto record=world_.native_objects.get(c.target.value);const auto* ptr=record?std::get_if<ZombieRef>(&*record):nullptr;
    if(record&&(!ptr||(*ptr)->body.kind!="小丑僵尸")&&team_of(seat)==Seat::zombie&&services_.has_self_destruct(seat))return services_.self_destruct(seat,c.target.value);
    if(!ptr||(*ptr)->body.kind!="小丑僵尸"||(*ptr)->body.hp<=0.||(*ptr)->body.ash.present())return "只能引爆存活的小丑僵尸";
    if(world_.heroes.owner(source_ref(*ptr))!=team_of(seat))return "只能引爆己方小丑僵尸";
    if((*ptr)->body.hand!="玩偶匣")return "这只小丑僵尸已没有玩偶匣";
    (*ptr)->body.hp=-299.;services_.emit(RoomActionEvent{RoomActionKind::clown_detonate,seat,c.target.value});services_.sync_public();return {};
}
std::string NativeRoomCommands::teleport(Seat seat,const NativeCommand& c){
    auto& avatar=world_.heroes.hero(seat);if(avatar.frame.hp.get()<=0.)return "戴夫已阵亡";
    if(avatar.ice.or_missing(0.)>1000.||avatar.butter.or_missing(0.)>0.||avatar.stun.or_missing(0.)>0.)return "冰冻、黄油或眩晕期间无法传送";
    auto& player=state_.players[seat_index(seat)];const auto remaining=player.teleport_ready_at-world_.heroes.time;
    if(remaining>0.)return "传送冷却中："+one_decimal(remaining)+"秒";
    const auto* target=c.target.valid()?services_.published_target(c.target.value):nullptr;const auto team=team_of(seat);
    if(!target||target->hp<=0.||target->side!=team)return "请选择己方存活的植物或墓碑";
    if((team==Seat::plant&&(target->card_side!=Seat::plant||target->tentacle))||(team==Seat::zombie&&!target->grave))return "植物方只能传送至植物，僵尸方只能传送至墓碑";
    const auto tile=world_.runtime.tile,width=world_.world_width.get(),height=world_.world_height.get();std::optional<Point> spot,air;
    for(const double up:{0.,1.,2.,3.,-1.,-2.}){
        for(const double dx:{0.,-1.,1.,-2.,2.}){
            const double x=py::mod(target->position.x+dx*tile,width),y=target->position.y-up*tile;
            if(y<1.5*tile||y>=height)continue;
            bool blocked=false;
            for(int64_t col=int64_t(std::floor((x-.3*tile)/tile));col<=int64_t(std::floor((x+.3*tile)/tile));++col)
                for(int64_t row=int64_t(std::floor((y-1.5*tile)/tile));row<=int64_t(std::floor((y-.01)/tile));++row)
                    if(published_solid(map_,{(col+.5)*tile,(row+.5)*tile},tile,width))blocked=true;
            if(blocked)continue;
            bool supported=false;for(const double offset:{-.2*tile,0.,.2*tile})
                if(published_solid(map_,{x+offset,y+1.},tile,width)||map_.water_at({x+offset,y+1.},tile,width))supported=true;
            if(!supported){if(target->airborne&&!air)air=Point{x,y};continue;}
            spot=Point{x,y};break;
        }
        if(spot)break;
    }
    if(!spot)spot=air;if(!spot)return "目标附近没有安全落点，未消耗传送冷却";
    *avatar.frame.position.get()={spot->x,spot->y,0.,0.};if(team==Seat::zombie)services_.zombie_teleport(seat);
    auto cooldown=rules_.teleport_cooldown;
    if(team==Seat::plant&&secret(seat,"secret:闪现")){
        cooldown*=.5;avatar.frame.hp.get()+=4.;RoomActionEvent heal{RoomActionKind::blink_heal,seat};heal.amount=4.;services_.emit(std::move(heal));
    }
    if(team==Seat::zombie&&rally_.for_owner(world_.mode,seat))cooldown*=.5;
    player.teleport_ready_at=world_.heroes.time+cooldown;RoomActionEvent event{RoomActionKind::teleport,seat,c.target.value};event.position=*spot;
    services_.emit(std::move(event));services_.sync_public();return {};
}
std::string NativeRoomCommands::cannon(Seat seat,const NativeCommand& c){
    if(team_of(seat)!=Seat::plant)return "只有植物方可操作玉米炮";
    auto& aim=state_.players[seat_index(seat)].cannon_aim;
    if(c.kind==NativeCommandKind::cannon_cancel){plants_.selected_cannon.reset();aim.reset();return {};}
    if(!coordinates(c))return "炮击坐标无效";
    world_.heroes.globals.overlay(world_.heroes.hero(seat).frame,true);world_.heroes.globals.mode.set("正常模式");world_.heroes.globals.secrets.set(native_secrets_);
    plants_.pointer={int(py::floordiv(c.y.value,world_.runtime.tile)),int64_t(py::floordiv(c.x.value,world_.runtime.tile))};
    if(plants_.selected_cannon){
        PlantRef cannon;for(const auto& p:*world_.plant_roster)if(p->cell==*plants_.selected_cannon&&p->kind=="玉米加农炮"&&p->hp.get()>0.){cannon=p;break;}
        if(!cannon||cannon->cannon_cd.get()!=0.||cannon->cannon_animation.get()!=0.){plants_.selected_cannon.reset();aim.reset();return "玉米炮已失效或未装填完成";}
        // The original fire region performs a second plant lookup, so a
        // layered stack can select a different record than the guard above.
        const auto index=lookup_pvp_plant(world_,*plants_.selected_cannon,true);
        const auto fired=world_.plant_roster->at(index.value_or(world_.plant_roster->size()-1));
        fired->cannon_cd.set(9000.);fired->cannon_animation.set(1.);fired->cannon_column.set(double(plants_.pointer.x));plants_.selected_cannon.reset();
        RoomActionEvent event{RoomActionKind::cannon_fire,seat,cannon->source.id.get()};event.position={c.x.value,c.y.value};services_.emit(std::move(event));
    }else{
        const auto& cell=plants_.pointer;
        if(!world_.terrain.outside(cell.y,cell.x)&&world_.terrain.native_at(cell.y,cell.x).plant.present()){
            const auto index=lookup_pvp_plant(world_,cell,true);const auto p=world_.plant_roster->at(index.value_or(world_.plant_roster->size()-1));
            if(p->kind=="玉米加农炮"&&p->cannon_cd.get()==0.&&p->cannon_animation.get()==0.)plants_.selected_cannon=cell;
        }
        if(!plants_.selected_cannon)return "此处没有装填完成的玉米炮";
    }
    aim=plants_.selected_cannon;return {};
}
std::string NativeRoomCommands::shovel(Seat seat,const NativeCommand& c){
    if(team_of(seat)!=Seat::plant)return "只有植物方可使用铲子";
    if(!coordinates(c)||(!c.right.absent()&&!c.right.valid()))return "铲除坐标无效";
    const bool right=c.right.valid()&&c.right.value;const auto tile=world_.runtime.tile;
    const Cell cell{int(py::floordiv(c.y.value,tile)),int64_t(py::floordiv(c.x.value,tile))};
    const auto index=lookup_pvp_plant(world_,cell,right);
    if(!index||world_.plant_roster->at(*index)->dead.present())return "这里没有可铲除的植物";
    const auto p=world_.plant_roster->at(*index);
    if(p->source.owner.present()&&!text(p->source.owner,"plant"))return "只能铲除己方植物";
    const bool basin=text(p->source.content,"水盆");
    if(basin){
        p->hp.set(0.);p->dead.set(DeathMarker(0.));services_.remove_basin(p);
        if(right){const auto id=services_.basin_to_pot(p,cell,p->facing);if(id.empty())throw std::runtime_error("水盆转换花盆失败");services_.emit(RoomActionEvent{RoomActionKind::basin_to_pot,seat,id,p->source.id.or_missing(std::string{})});}
    }else{
        HeroContext scope(world_.heroes,{Seat::zombie,Seat::plant,CombatPhase::plants,source_ref(p),{}});
        const auto again=lookup_pvp_plant(world_,cell,right);
        if(again){auto& target=*world_.plant_roster->at(*again);target.dead.set(DeathMarker(0.));target.shovel_dead.set(DeathMarker(0.));}
    }
    NativeCommand cancel{NativeCommandKind::cannon_cancel};cannon(seat,cancel);
    RoomActionEvent event{RoomActionKind::shovel,seat,p->source.id.or_missing(std::string{})};event.right=right;services_.emit(std::move(event));
    if(basin)services_.sync_public();return {};
}
std::string NativeRoomCommands::apply(Seat seat,const NativeCommand& c){
    switch(c.kind){
    case NativeCommandKind::turn:return turn(seat,c);
    case NativeCommandKind::detonate:return detonate(seat,c);
    case NativeCommandKind::select_grave:return select_grave(seat,c);
    case NativeCommandKind::teleport:return teleport(seat,c);
    case NativeCommandKind::cannon:case NativeCommandKind::cannon_cancel:return cannon(seat,c);
    case NativeCommandKind::shovel:return shovel(seat,c);
    case NativeCommandKind::deploy:return services_.deploy(seat,c);
    case NativeCommandKind::wake:
        switch(graves_.wake_input(seat,c.grave.valid()?std::optional<std::string>(c.grave.value):std::nullopt)){
        case GraveWakeResult::success:return {};case GraveWakeResult::wrong_team:return "只有僵尸方可唤醒墓碑";
        case GraveWakeResult::invalid_id:return "墓碑编号无效";case GraveWakeResult::missing:return "墓碑不存在";
        case GraveWakeResult::nonproducer:return "墓碑不需要照料";
        }
    }
    throw std::logic_error("invalid native command kind");
}
} // namespace pvz::typed72
