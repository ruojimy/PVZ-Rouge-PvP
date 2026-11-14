#include "core/function_profile.h"
// The typed composition (generated into composition/ from build/typed72-match-v1 by
// tools/typed72/make_app_composition.py) wrapped as a Session.
#define TYPED72_NO_MAIN
#include "match_probe.cpp"
#include "sim/typed72_app/session.h"
#include "sim/typed72_app/ai/layers19.h"
#include <deque>
#include <map>
#include <algorithm>
#include <array>
#include <optional>
#include <stdexcept>
namespace pvz::typed72app {
namespace {
class TypedSession final:public Session {
public:
    TypedSession(ColdExport cold,const std::string& map_name){
        const auto& c=cold.cold;const auto seed=int64_t(c.at("seed").get<double>());
        match_=std::make_unique<MatchProbe>(seed,c.at("battle").at("width").get<double>(),c.at("battle").at("rules").at("melon_splash_damage").get<double>());
        auto& m=*match_;m.no_trace=true;m.release_fixtures=true;
        // NativeBattle._perf_counter: the shipped game measures real native cost (pve pacing).
        m.wall_clock=[]{return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();};
        auto& atlas=m.battle.runtime.presentation.atlas;
        for(auto& [name,p]:cold.atlas){
            SpritePixels s;s.width=p.width;s.height=p.height;s.pixels.reserve(p.rgba.size());
            for(const auto& px:p.rgba)s.pixels.push_back(Color{px[0],px[1],px[2],px[3]});
            atlas.emplace(name,std::move(s));
        }
        cold.atlas.clear();
        m.install_frames_json(cold.draw_atlas,c);
        m.log.push_back({{"event","battle_start"},{"map",map_name},{"seed",seed},{"tick",0},{"time",0}});
        m.setup(c,J::object());
        // The old builder keeps the room map's initial night flag even when a
        // cooperative cycle changes the battle's current daylight later.
        initial_map_night_=m.battle.placement.day=="黑天";
        // AISeat builds its Field from room.map.to_dict(): the construction terrain.
        initial_tiles_=public_tiles();
        if(c.at("battle").contains("ai_zombie_points"))for(const auto& x:c.at("battle").at("ai_zombie_points"))zombie_points_.push_back(x.get<double>());
        if(const auto& rules=c.at("battle").at("rules");rules.contains("hero_lock_range"))hero_lock_range_=rules.at("hero_lock_range").get<double>();
        births_.emplace(m.battle.runtime,static_cast<PlantRegionServices&>(m));
    }
    std::string command(const std::string& side,const nlohmann::json& payload)override{
        auto& m=*match_;const auto seat=parse_seat(side);
        const auto error=m.inputs.apply(seat,decode_command(payload));
        if(error.empty())m.log_event(m.input_record(seat,side,payload));
        return error;
    }
    void clear_input(const std::string& side)override{match_->scheduler.clear_input(parse_seat(side));}
    void step()override{
        auto& m=*match_;
        // A result may settle before the caller's requested batch ends. Keep
        // every room step's final native frame; draw hooks carry state and
        // cannot safely be replayed later merely to recover that ending frame.
        m.scheduler.step();m.flush_journal();++m.current_room;
    }
    nlohmann::json snapshot(bool include_frame=true)override{PVP_PROFILE_SCOPE("MatchProbe::snapshot_json");return match_->snapshot_json(include_frame);}
    const typed72::NativeFrame& native_frame()const override{return match_->canvas.frames.frame();}
    nlohmann::json reference_native_frame()const override{return match_->canvas.frame_json(native_frame());}
    size_t log_size()const override{return match_->log.size();}
    nlohmann::json log_entry(size_t index)const override{return nlohmann::json(match_->log.at(index));}
    int64_t tick()const override{return match_->room.tick;}
    SessionClock clock()const override{
        const auto& m=*match_;
        return {m.room.tick,m.battle.heroes.tick,m.published.terrain.revision,m.world.time,m.room.deathmatch};
    }
    AiObservationPacket ai_observe(typed72::Seat owner,int64_t match_id=0)override{
        // Const authority: only the observer's own history is changed below.
        // In particular, never sync/publish, serialize, or inspect peer inputs.
        const MatchProbe& m=*match_;const auto i=ai_owner_index(owner);
        const Seat side=team_of(owner),enemy=side==Seat::plant?Seat::zombie:Seat::plant;
        const double width=m.battle.world_width.get(),height=m.battle.world_height.get(),tile=m.battle.runtime.tile;
        const auto hero=[&](Seat seat){return ai_hero(seat);};
        // local_perspective swaps the own main/sub-seat only. The opponent is
        // still its main seat and unit side/seat labels are never relabelled.
        const auto mine=hero(owner),theirs=hero(enemy);
        auto& slot=ai_observers_[i];
        if(!slot)slot.emplace(side,width,height,tile,initial_map_night_);
        const bool current_night=m.battle.placement.day=="黑天";
        const bool night=current_night||initial_map_night_;
        const auto units=ai_units();
        std::vector<AiPublicResource> resources;resources.reserve(m.resources.records().size());
        for(const auto& value:m.resources.records()){
            auto resource_side=value.side;
            const bool shared=value.shared.present()&&!value.shared.is_null()&&value.shared.get();
            if(owner!=side&&!shared&&(resource_side==side||resource_side==owner))resource_side=resource_side==side?owner:side;
            resources.push_back({value.id,resource_side,value.position,value.amount,value.source});
        }
        const auto& player=*m.world.players[i];const auto& deck=m.deployment.players[i].deck;
        std::vector<AiDeckCardView> cards;cards.reserve(deck.size());
        const auto flag=[](const Field<bool>& value){return value.present()&&!value.is_null()&&value.get();};
        for(const auto& key:deck){
            if(!m.catalog.find(key))continue;
            // Observation uses actual_card, not deployment's resolve/player_card
            // (which applies bans, copy state and other placement-only rules).
            const auto card=m.catalog.actual(key,player.secrets,night);
            AiDeckCardView view;view.id=key;view.name=card.name;view.behavior=card.behavior;
            view.cost=card.cost;view.range=card.range;view.producer=card.producer;view.mushroom=flag(card.mushroom);view.secret=card.category=="secret";
            view.aquatic=flag(card.aquatic);view.lob=flag(card.lob);view.star=flag(card.star);view.homing=flag(card.homing);
            for(const auto& [name,ready]:player.cooldowns)if(name==key)view.cooldown_ready=ready;
            cards.push_back(std::move(view));
        }
        AiObservationPacket packet;
        // Native speed/gravity are inferred by the existing position-difference
        // algorithm. Do not read physical vx/vy, real damage or hidden aim data.
        slot->native_shots.sample(*m.battle.runtime.entities.list(),m.world.time,width);
        packet.visible_shots=slot->native_shots.visible(mine.position,width);
        packet.shots_seen=slot->native_shots.seen();
        // NativeBattle's public top-level projectiles is empty. Hook/bone shots
        // belong to pvp70.projectiles, which the legacy observation never merges.
        // All spans below refer to local owned values and die before returning.
        AiObservationFrame frame;frame.mine=&mine;frame.enemy=&theirs;
        frame.units=units;frame.shots=packet.visible_shots;frame.resources=resources;frame.cards=cards;
        frame.time=m.world.time;frame.tick=m.room.tick;frame.night=current_night;frame.deathmatch=m.room.deathmatch;
        frame.enemy_input_present=false; // A typed public projection has no input field.
        packet.observation=slot->builder.build(frame,0,match_id,0);
        last_observation_[i]=packet.observation;
        packet.own_counts=ai_own_counts(units,side,m.battle.mode==MatchMode::duo?std::optional<Seat>(owner):std::nullopt);
        packet.team_counts=ai_own_counts(units,side);
        return packet;
    }
    void reset_ai_observation(typed72::Seat owner)override{ai_observers_[ai_owner_index(owner)].reset();}
    AiPlanR22 ai_plan(typed72::Seat owner,bool recovering)override{
        // Same const authority and perspective as ai_observe: "me" is the owner seat,
        // the foe is the enemy team's main seat; units are the published list.
        const MatchProbe& m=*match_;const auto i=ai_owner_index(owner);
        const Seat side=team_of(owner),enemy=side==Seat::plant?Seat::zombie:Seat::plant;
        const auto facts=[&](Seat seat){
            const auto h=ai_hero(seat);return AiPlannerHero{h.position.x,h.position.y,h.hp,h.max_hp,h.resource};
        };
        const auto units=ai_units();
        AiPlannerInput in;in.side=side;in.time=m.world.time;in.width=m.battle.world_width.get();
        in.me=facts(owner);in.foe=facts(enemy);in.deck=m.deployment.players[i].deck;in.units=units;in.recovering=recovering;
        auto& slot=ai_planners_[i];
        if(!slot)slot.emplace(side);
        auto plan=slot->plan(in);
        last_plan_[i]=plan_dict(plan);
        return plan;
    }
    void reset_ai_planner(typed72::Seat owner)override{ai_planners_[ai_owner_index(owner)].reset();}
    // ------------------------------------------------------------ r22 controller
    const std::map<std::string,double>& ai_control(typed72::Seat owner,const std::string& layer,AiSend send)override{
        const auto i=ai_owner_index(owner);const Seat side=team_of(owner);
        if(!last_observation_[i])throw std::logic_error("ai_control before ai_observe for this seat");
        if(!last_plan_[i])throw std::logic_error("ai_control before ai_plan for this seat");
        auto& slot=controllers_[i];
        if(!slot||slot->layer!=layer){
            slot.emplace();slot->layer=layer;
            if(layer=="v7"&&side==Seat::plant)slot->controller=std::make_unique<ai::PlantV7>();
            else if(layer=="z7"&&side==Seat::zombie)slot->controller=std::make_unique<ai::ZombieT7>();
            else if(layer=="p11"&&side==Seat::plant)slot->controller=std::make_unique<ai::Plant11>();
            else if(layer=="z11"&&side==Seat::zombie)slot->controller=std::make_unique<ai::Zombie11>();
            else if(layer=="r22"&&side==Seat::plant)slot->controller=std::make_unique<ai::Plant19>();
            else if(layer=="r22"&&side==Seat::zombie)slot->controller=std::make_unique<ai::Zombie19>();
            else throw std::invalid_argument("unknown controller layer "+layer+" for this seat");
        }
        if(!field_)field_.emplace(initial_tiles_,match_->battle.world_width.get(),match_->battle.world_height.get(),match_->battle.runtime.tile);
        const auto view=ai_control_view(owner);
        AiServices services(*this,owner,view);
        slot->send=std::move(send);
        auto* ctl=slot->controller.get();
        if(!slot->bound){ControllerSlot* s=&*slot;ctl->bind([s](const std::string& k,const ai::Args& a){return s->send(k,a);});slot->bound=true;}
        ctl->step(view,*last_observation_[i],*last_plan_[i],*field_,services);
        return ctl->log.v;
    }
    void reset_ai_controller(typed72::Seat owner)override{controllers_[ai_owner_index(owner)].reset();}
    bool ai_controller_recovering(typed72::Seat owner)const override{
        const auto& slot=controllers_[ai_owner_index(owner)];return slot&&slot->controller&&slot->controller->is_recovering();
    }
    ai::View ai_control_view(typed72::Seat owner)override{
        const MatchProbe& m=*match_;const Seat team=team_of(owner);
        ai::View v;v.team=team;v.seat=owner;v.time=m.world.time;v.width=m.battle.world_width.get();v.height=m.battle.world_height.get();
        v.tile=m.battle.runtime.tile;v.deathmatch=m.room.deathmatch;v.map_night=initial_map_night_;
        if(m.battle.mode!=MatchMode::duel)v.mode=m.battle.mode==MatchMode::duo?"duo":m.battle.mode==MatchMode::coop?"coop":"pve";
        v.command=m.commands.shared==PathMode::follow_hero?"follow":"attack";
        if(m.hero_flags.shared)v.rally_point=std::pair<double,double>{m.hero_flags.shared->x,m.hero_flags.shared->y};
        if(m.battle.mode!=MatchMode::duel){
            v.has_team=true;
            for(const auto s:m.seated_seats)if(m.room.down_since[seat_index(s)])v.fallen.push_back(std::string(seat_name(s)));
            std::sort(v.fallen.begin(),v.fallen.end());
        }
        for(const auto s:m.seated_seats){
            const auto idx=seat_index(s);const auto& p=*m.world.players[idx];const auto& rp=m.room.players[idx];const auto& view=m.published.heroes[idx]->visible;
            ai::Player row;row.key=row.seat=std::string(seat_name(s));
            row.x=view.position.x;row.y=view.position.y;row.hp=p.hp;row.max_hp=p.max_hp;row.resource=m.resources.accounts[idx].balance;
            row.facing=double(view.facing);row.grounded=view.grounded;
            row.deck=m.deployment.players[idx].deck;row.secrets=p.secrets;
            for(const auto& [k,t]:p.cooldowns)row.cooldowns.emplace_back(k,t);
            if(rp.teleport_ready_at>0.)row.teleport_ready_at=rp.teleport_ready_at;
            if(rp.collect_locked_until>0.)row.collect_locked_until=rp.collect_locked_until;
            row.cannon_aim_written=m.cannon_aim_written[idx];row.cannon_aim_set=m.cannon_aim_written[idx]&&rp.cannon_aim.has_value();
            if(const auto& g=m.battle.protection.selected_grave[idx])row.selected_grave=*g;
            row.absent=std::find(m.tick_state.present.begin(),m.tick_state.present.end(),s)==m.tick_state.present.end();
            v.players.push_back(std::move(row));
        }
        for(const auto& u:m.published.units){
            ai::Unit out;out.id=u.id;out.card_id=u.card->id;out.behavior=u.card->behavior;out.side=u.side;
            if(u.seat)out.seat=std::string(seat_name(*u.seat));
            if(u.copy_card)out.copy_card_id=*u.copy_card;
            out.x=u.position.x;out.y=u.position.y;out.hp=u.hp;out.max_hp=u.max_hp;out.w=u.w;out.h=u.h;out.facing=double(u.facing);
            out.drowsy_level=double(u.drowsy_level);out.mobile=u.mobile;out.flying=bool(u.card->flying);out.awake=u.awake;out.mature=u.mature;out.drowsy=u.drowsy;
            out.card=unit_card(u.original_owner,u.card->id);
            v.units.push_back(std::move(out));
        }
        for(const auto& r:m.resources.records()){
            ai::Resource row;row.id=r.id;row.side=std::string(seat_name(r.side));row.source=r.source;row.x=r.position.x;row.y=r.position.y;row.amount=r.amount;
            if(r.shared.present()&&!r.shared.is_null())row.shared=r.shared.get();
            v.resources.push_back(std::move(row));
        }
        v.tiles=public_tiles();
        v.zombie_points=zombie_points_;
        if(m.zsecrets.enabled()){
            v.has_zsecrets=true;
            for(const auto& item:m.zruntime.pickups)v.pickups.push_back({item.id,item.kind.empty()?item.name:item.kind,item.position.x,item.position.y});
            for(const auto s:m.battle.heroes.last_stand_order)if(m.battle.heroes.last_stand[seat_index(s)])v.last_stand.push_back(std::string(seat_name(s)));
        }
        v.bans=m.deployment.bans;
        v.hero_lock_range=hero_lock_range_;
        // AISeat applies local_perspective only for a secondary seat (seat != team).
        if(owner!=team){
            const std::string seat_key(seat_name(owner)),team_key(seat_name(team));
            if(team==Seat::zombie&&m.battle.mode==MatchMode::duo){
                v.command=m.commands.by_seat[seat_index(owner)]==PathMode::follow_hero?"follow":"attack";
                v.rally_point.reset();
                if(const auto& flag=m.hero_flags.by_seat[seat_index(owner)])v.rally_point=std::pair<double,double>{flag->x,flag->y};
                v.local_seat=seat_key;
            }
            ai::Player* mine=nullptr;ai::Player* main=nullptr;
            for(auto& p:v.players){if(p.key==seat_key)mine=&p;if(p.key==team_key)main=&p;}
            // dict(players) keeps key order; the two values trade places.
            if(mine&&main){std::swap(*mine,*main);std::swap(mine->key,main->key);v.local_seat=seat_key;}
            for(auto& r:v.resources)if((r.side==team_key||r.side==seat_key)&&!r.shared.value_or(false))r.side=r.side==team_key?seat_key:team_key;
        }
        return v;
    }

    const AiPlannerR22* ai_planner(typed72::Seat owner)const override{
        const auto& slot=ai_planners_[ai_owner_index(owner)];return slot?&*slot:nullptr;
    }
    bool finished()const override{return match_->room.result.has_value();}
    nlohmann::json result_json()const override{
        const auto& m=*match_;if(!m.room.result)return nullptr;
        J result={{"winner",m.room.result->winner==RoomWinner::plant?"plant":m.room.result->winner==RoomWinner::zombie?"zombie":"draw"},
            {"reason",m.room.result->reason==RoomResultReason::hero_death?"hero_death":m.room.result->reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"},{"tick",m.room.result->tick}};
        m.scripted_result_fields(result,*m.room.result);
        return nlohmann::json(result);
    }
    nlohmann::json surrender_requests_json()const override{
        const auto& m=*match_;J requests=J::object();
        if(m.battle.mode==MatchMode::duel||!m.team_mode)return nlohmann::json::object();
        const double now=m.world.time;
        for(const auto& r:m.room.surrender_requests)if(r&&r->expires>now)
            requests[std::string(seat_name(team_of(r->seat)))]={{"id",r->id},{"seat",std::string(seat_name(r->seat))},{"expires",r->expires}};
        return nlohmann::json(requests);
    }
    void set_ai_subsidy_seats(const std::vector<std::string>& seats)override{
        auto& v=match_->room.ai_subsidy_seats;v.clear();for(const auto& s:seats)v.push_back(parse_seat(s));
    }
    nlohmann::json placement(const std::string& side,const std::string& key,double x,double y,const nlohmann::json& grave,const nlohmann::json& copy)override{
        auto& m=*match_;
        std::optional<std::string> g,k;if(grave.is_string())g=grave.get<std::string>();if(copy.is_string())k=copy.get<std::string>();
        const auto r=m.cold_deployment.placement(parse_seat(side),key,{x,y},g,k);
        if(!r.plan)return J::array({r.error.empty()?J(nullptr):J(r.error),nullptr});
        // The plan dict shapes of native_placement.py (cell plans), native_placement.py:48
        // (thief) and simulation.py (free placements), key for key.
        const auto& p=*r.plan;J plan={{"card",MatchProbe::card_json(p.card)},{"charge",p.charge},{"x",p.position.x},{"y",p.position.y}};
        if(p.cell){
            plan["row"]=p.cell->y;plan["col"]=p.cell->x;plan["slot"]=p.slot;
            if(p.grave_target){plan["grave_target"]=*p.grave_target;plan["copy_card"]=nullptr;plan["copy_id"]=nullptr;plan["temporary"]=false;}
            else{plan["copy_card"]=p.copied?MatchProbe::card_json(*p.copied):J(nullptr);plan["copy_id"]=p.copy_id?J(*p.copy_id):J(nullptr);plan["temporary"]=p.temporary;}
        }else if(p.thief_target){plan["slot"]=p.slot;plan["thief_target"]=*p.thief_target;}
        else{plan["slot"]=p.slot;plan["temporary"]=p.temporary;}
        return J::array({J(r.error),plan});   // ("", plan) on success, as NativeBattle.placement
    }
    bool tutorial_sleep_grave(const std::string& id,double idle_seconds)override{
        const auto object=match_->battle.native_objects.get(id);if(!object)return false;
        const auto* grave=std::get_if<ZombieRef>(&*object);if(!grave||!*grave)return false;
        const auto& producer=(*grave)->producer;if(!(producer.present()&&!producer.is_null()&&producer.get()))return false;
        (*grave)->idle.set(idle_seconds);return true;
    }
    bool grave_awake(const std::string& id)override{
        const auto object=match_->battle.native_objects.get(id);if(!object)return true;
        const auto* grave=std::get_if<ZombieRef>(&*object);if(!grave||!*grave)return true;
        return (*grave)->body.hp<=0.||!match_->grave_clock.drowsy(**grave);
    }
    nlohmann::json native_view()override{return nlohmann::json(match_->native_view());}
    std::optional<double> native_cost_ratio()const override{return match_->room.native_cost_ratio;}
    bool fixture_place_zombie(const std::string& id,double x,double y,double facing)override{return match_->fixture_place_zombie(id,x,y,facing);}
    void fixture_set_avatar(const std::string& side,const nlohmann::json& state)override{match_->fixture_set_avatar(parse_seat(side),J(state));}
    void sync_public()override{match_->fixture_sync();}
    void native_set(bool avatar,const std::string& id,const nlohmann::json& fields)override{match_->native_set(avatar,id,J(fields));}
    void fixture_entity(size_t index,const nlohmann::json& fields,bool keep_only)override{match_->fixture_entity(index,J(fields),keep_only);}
    std::optional<std::string> spawn(const std::string& key,const std::string& side,double x,double y,double facing,bool temporary)override{
        return match_->spawn_unit(key,side,x,y,facing,temporary);
    }
    nlohmann::json rng_state()const override{return nlohmann::json(match_->rng_state());}
    std::string create_resource(const std::string& side,double amount,double x,double y,const std::string& source)override{
        return match_->resources.create(parse_seat(side),amount,{x,y},source);
    }
    nlohmann::json players()override{return nlohmann::json(match_->snapshot_players());}
    void fixture_player(const std::string& side,const nlohmann::json& fields)override{match_->fixture_player(parse_seat(side),J(fields));}
    void fixture_clock(const nlohmann::json& fields)override{match_->fixture_clock(J(fields));}
    void fixture_tile(int64_t row,int64_t col,const nlohmann::json& cell)override{match_->fixture_tile(row,col,J(cell));}
    nlohmann::json map_tiles()override{return nlohmann::json(match_->map_tiles_json());}
    void fixture_ditu(int64_t row,int64_t col,const nlohmann::json& cell)override{match_->fixture_ditu(row,col,J(cell));}
    int64_t terrain_revision()const override{return match_->published.terrain.revision;}
    std::optional<bool> coop_map_night()const override{
        if(!match_->director.coop_cycle())return {};
        return match_->battle.placement.day=="黑天";
    }
    nlohmann::json fixture_retention()const override{return nlohmann::json(match_->fixture_retention());}
    nlohmann::json performance_counters()const override{
        const auto& c=match_->contacts;const auto entities=match_->battle.runtime.entities.list();
        const auto t=match_->owner_phase.tracking_counters();const auto& chart=match_->chart;
        const auto& p=match_->peas;const auto& heads=match_->bonus_projectiles;const auto aim=match_->shooting.aim_counters();const auto& f=match_->navigation.flood;const auto& legal=match_->path_banks.destination_field();const auto path=match_->path_banks.target_work();
        nlohmann::json functions=nlohmann::json::object();for(const auto& [name,row]:function_profile::snapshot())functions[name]={{"calls",row.calls},{"total_ms",row.total_ms},{"max_ms",row.max_ms}};
        return {{"function_profile",std::move(functions)},{"fixture_retention",fixture_retention()},{"nearest_queries",t[0]+chart.nearest_queries},{"nearest_candidates",t[1]+chart.nearest_candidates},{"nearest_full_scan",t[2]+chart.nearest_full_scan},{"zombie_collision_queries",p.spatial_queries},{"zombie_collision_candidates",p.spatial_candidates},{"zombie_collision_full_scan",p.full_scan_pairs},{"zombie_exact_tests",p.exact_tests},{"spatial_bytes",c.spatial_bytes()+p.spatial_bytes()},
            {"primal_knock_targets",match_->content_damage.primal_knock_targets},{"primal_knock_velocity",match_->content_damage.primal_knock_velocity},
            {"content_queries",match_->queries.local_queries},{"content_candidates",match_->queries.local_candidates},{"point_grid_builds",match_->queries.moving_index().rebuilds},{"point_grid_moves",match_->queries.moving_index().moves},{"point_grid_cell_changes",match_->queries.moving_index().cell_changes},
            {"range_queries",match_->queries.range_queries},{"range_candidates",match_->queries.range_candidates},{"range_full_scan",match_->queries.range_full_scan},{"range_exact_tests",match_->queries.range_exact_tests},
            {"seeking_plant_ticks",match_->queries.seeking_plant_ticks},{"max_seeking_plants",match_->queries.max_seeking_plants},
            {"range_cache_hits",match_->queries.coverage_index().cache_hits},{"range_grid_resets",match_->queries.coverage_index().resets},{"range_cell_changes",match_->queries.coverage_index().cell_changes},{"range_index_bytes",match_->queries.range_storage_bytes()},
            {"aim_queries",aim[0]},{"aim_candidates",aim[1]},{"aim_full_scan",aim[2]},{"head_queries",heads.head_queries},{"head_candidates",heads.head_candidates},{"head_full_scan",heads.head_full_scan},{"head_exact_tests",heads.head_exact_tests},{"head_spatial_bytes",heads.spatial_bytes()},
            {"flood_calls",f[0].calls+f[1].calls},{"flood_expansions",f[0].expansions+f[1].expansions},{"flood_cycles",f[0].cycles+f[1].cycles},{"flood_neighbors",f[0].neighbours+f[1].neighbours},
            {"destination_queries",legal.queries},{"destination_rebuilds",legal.rebuilds},{"destination_reuses",legal.reused},{"plant_target_scans",path[0]+match_->paths.target_scans},{"plant_target_candidates",path[1]+match_->paths.target_candidates},{"plant_target_reuses",path[2]+match_->paths.target_cache_hits},
            {"torch_scans",match_->torches.roster_scans},{"torch_candidates",match_->torches.roster_candidates},{"torch_batch_reuses",match_->torches.batch_reuses},{"collision_queries",c.queries},{"find_contact_calls",c.narrow_queries},{"empty_cell_skips",c.empty_cell_skips},{"occupied_cells",c.occupied_cells()},{"collision_candidates",c.candidates},{"full_scan_equivalent",c.full_scan_equivalent},{"index_builds",c.index_builds},{"native_entities",entities->size()}};
    }
    nlohmann::json events(size_t n)const override{return nlohmann::json(match_->recent_events(n));}
private:
    // Owner-seat hero as snapshot_players publishes it: physics/status from the
    // published view; HP/account/action facts from their own typed authorities.
    AiPublicHero ai_hero(Seat seat)const{
        const MatchProbe& m=*match_;const auto index=seat_index(seat);const double tile=m.battle.runtime.tile;
        if(index>=4||!m.world.players[index]||!m.published.heroes[index])throw std::invalid_argument("AI view has no battle player");
        const auto& player=*m.world.players[index];const auto& room_player=m.room.players[index];
        auto out=m.published.heroes[index]->visible;
        out.hp=player.hp;out.max_hp=player.max_hp;out.w=tile*.8;out.h=tile*1.9;
        out.resource=m.resources.accounts[index].balance;
        out.teleport_ready=std::max(0.,room_player.teleport_ready_at);
        out.cannon_aimed=m.cannon_aim_written[index]&&room_player.cannon_aim.has_value();
        out.absent=std::find(m.tick_state.present.begin(),m.tick_state.present.end(),seat)==m.tick_state.present.end();
        return out;
    }
    std::vector<AiUnitView> ai_units()const{
        std::vector<AiUnitView> units;units.reserve(match_->published.units.size());
        for(const auto& unit:match_->published.units)units.push_back(ai_public_unit(unit));
        return units;
    }
    struct AiObserver {
        AiNativeShotView native_shots;
        AiObservationBuilder builder;
        AiObserver(Seat side,double width,double height,double tile,bool night):builder(side,width,height,tile,night){}
    };
    static size_t ai_owner_index(Seat owner){
        const auto index=seat_index(owner);
        if(index>=4)throw std::invalid_argument("invalid AI observation owner seat");
        return index;
    }
    std::unique_ptr<MatchProbe> match_;
    std::optional<NativeBirthScope> births_;
    bool initial_map_night_=false;
    std::array<std::optional<AiObserver>,4> ai_observers_;
    std::array<std::optional<AiPlannerR22>,4> ai_planners_;
    std::array<std::optional<AiObservation>,4> last_observation_;
    std::array<std::optional<ai::PlanDict>,4> last_plan_;
    struct ControllerSlot{std::string layer;std::unique_ptr<ai::Controller> controller;AiSend send;bool bound=false;};
    std::array<std::optional<ControllerSlot>,4> controllers_;
    std::vector<std::vector<ai::Cell>> initial_tiles_;
    std::optional<ai::Field> field_;
    std::optional<double> hero_lock_range_;
    std::vector<double> zombie_points_;
    std::deque<ColdCard> card_store_;std::map<std::string,const ColdCard*> card_index_;
    static bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
    std::vector<std::vector<ai::Cell>> public_tiles()const{
        std::vector<std::vector<ai::Cell>> out;
        for(const auto& row:match_->published.terrain.tiles){std::vector<ai::Cell> line;for(const auto& c:row)line.push_back({c.solid,c.water,c.ladder,c.kind});out.push_back(std::move(line));}
        return out;
    }
    // u['card'] = placement_view.unit_card(original_owner, id); V keeps the bare id on failure.
    const ColdCard* unit_card(Seat owner,const std::string& id){
        try{return keep(match_->placement_view.unit_card(owner,id));}catch(const std::exception&){return nullptr;}
    }
    // Stable addresses for resolved cards, deduplicated by the facts the controller reads.
    const ColdCard* keep(ColdCard card){
        char cost[40];std::snprintf(cost,sizeof cost,"%.17g",card.cost);
        const std::string key=card.id+"\x1f"+card.resolved_id+"\x1f"+card.side+"\x1f"+cost+"\x1f"+card.behavior+"\x1f"+card.name+"\x1f"+card.category;
        auto f=card_index_.find(key);if(f!=card_index_.end())return f->second;
        card_store_.push_back(std::move(card));card_index_.emplace(key,&card_store_.back());return &card_store_.back();
    }
    // The AISeat plan: validate_plan(raw) keeps keys, order and values of the typed plan.
    static ai::PlanDict plan_dict(const AiPlanR22& p){
        ai::PlanDict d;d.set("priority",p.priority);d.set("quotas",p.quotas);
        if(p.side==Seat::plant){
            d.set("mode",*p.mode);d.set("econ_goal",p.econ_goal);d.set("wall_goal",p.wall_goal);d.set("reserve",p.reserve);d.set("siege_gap",p.siege_gap);
            d.set("teleport_hp",p.teleport_hp);d.set("panic_value",p.panic_value);d.set("bomb_value",p.bomb_value);d.set("siege_step",p.siege_step);
            d.set("siege_dwell",p.siege_dwell);d.set("siege_lobs",p.siege_lobs);d.set("rich",p.rich);d.set("vine_reserve",p.vine_reserve);d.set("global_collect",p.global_collect);
        }else{
            d.set("grave_start",p.grave_start);d.set("grave_max",p.grave_max);d.set("grave_every",p.grave_every);d.set("save_horizon",p.save_horizon);
            d.set("wave_base",p.wave_base);d.set("wave_growth",p.wave_growth);d.set("wave_cap",p.wave_cap);d.set("wave_hold_max",p.wave_hold_max);
            d.set("teleport_hp",p.teleport_hp);d.set("tend_every",p.tend_every);d.set("detonate_value",p.detonate_value);
            if(p.save)d.set("save",*p.save);
            if(p.mode)d.set("mode",*p.mode);
        }
        return d;
    }
    // PreviewBattle.placement for the controller: the tick's state without the live
    // battle's ranked ring rule; optionally the cloned unbounded player (ztactics7).
    class AiServices final:public ai::Services {
    public:
        AiServices(TypedSession& s,Seat owner,const ai::View& v):s_(s),owner_(owner),view_(v){}
        std::string preview(const std::string& key,double x,double y,const std::optional<std::string>& grave,bool unbounded)override{
            auto& m=*s_.match_;const auto i=seat_index(owner_);
            struct Restore{MatchProbe& m;size_t i;bool ranked;std::optional<double> balance;std::optional<std::vector<std::pair<std::string,double>>> cds;
                ~Restore(){m.deployment.ranked=ranked;if(balance)m.resources.accounts[i].balance=*balance;if(cds)m.world.players[i]->cooldowns=*cds;}} restore{m,i,m.deployment.ranked,{},{}};
            m.deployment.ranked=false;
            if(unbounded){
                restore.balance=m.resources.accounts[i].balance;m.resources.accounts[i].balance=std::max(10000.,*restore.balance);
                restore.cds=m.world.players[i]->cooldowns;m.world.players[i]->cooldowns.clear();
            }
            const auto r=m.cold_deployment.placement(owner_,key,{x,y},grave,{});
            if(r.error.empty()&&!r.plan)return "no placement";
            return r.error;
        }
        const ColdCard& card(const std::string& key)override{
            auto f=cache_.find(key);if(f!=cache_.end())return *f->second;
            const ai::Player* me=view_.player(std::string(seat_name(team_of(owner_))));
            const auto* c=s_.keep(s_.match_->catalog.resolve(key,me->secrets,view_.bans,view_.map_night));
            cache_.emplace(key,c);return *c;
        }
        bool air_plant(const std::string& name)const override{return name=="幽灵辣椒"||name=="旋转芜菁"||name=="芦笋战机";}
    private:
        TypedSession& s_;Seat owner_;const ai::View& view_;std::map<std::string,const ColdCard*> cache_;
    };

};
}
std::unique_ptr<Session> Session::create(ColdExport cold,const std::string& map_name){
    return std::make_unique<TypedSession>(std::move(cold),map_name);
}
} // namespace pvz::typed72app
