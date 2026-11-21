#pragma once
#include "sim/typed72_app/snapshot_sink.h"
#include "sim/typed/pvp75_content.h"
#include <nlohmann/json.hpp>
namespace pvz::typed72app {
// Projection only; mirrors the unchanged reference snapshot's field presence,
// nulls and order. Differential checks compare complete output in real modes.
// M is the production composition. It has no dependency on UI V values.
template<class M> void project_metadata(M& m,SnapshotSink& w){
    using namespace typed72;
    const auto residual=m.snapshot_json(false,false,false);
    for(auto i=residual.begin();i!=residual.end();++i){
        if(i.key()=="players"||i.key()=="native_placement_state"||i.key()=="resources"||i.key()=="pvp70")continue;
        w.json(i.key(),i.value());
    }
    w.object("players");
    auto seats=m.seated_seats;
    std::sort(seats.begin(),seats.end(),[](Seat a,Seat b){return seat_name(a)<seat_name(b);});
    for(const auto seat:seats){
        const auto i=seat_index(seat);const auto& p=*m.world.players[i];const auto& rp=m.room.players[i];
        const auto& v=m.published.heroes[i]->visible;const auto& account=m.resources.accounts[i];
        const auto s=seat_name(seat),team=seat_name(team_of(seat));
        w.object(s);
        w.put("x",v.position.x);w.put("y",v.position.y);w.put("vx",v.velocity.x);w.put("vy",v.velocity.y);
        w.put("w",m.battle.runtime.tile*.8);w.put("h",m.battle.runtime.tile*1.9);
        w.put("hp",p.hp);w.put("max_hp",p.max_hp);w.put("resource",account.balance);
        w.object("cooldowns");for(const auto& [k,x]:p.cooldowns)w.put(k,x);w.end();
        w.object("cooldown_spans");for(const auto& [k,x]:rp.cooldown_spans)w.put(k,x);w.end();
        w.put("seq",rp.sequence);w.put("last_input_tick",rp.last_input_tick);w.put("marked_until",p.marked_until);w.put("immune_until",rp.immune_until);
        w.put("facing",v.facing);w.put("frozen",v.frozen);w.put("slowed",v.slowed);w.put("buttered",v.buttered);
        w.put("jumps",v.jumps);w.put("jump_cap",v.jump_cap);w.put("grounded",v.grounded);w.put("poison_level",v.poison);w.put("jump_held",p.jump_held);
        w.object("stats");w.put("spent",m.deployment.players[i].spent);w.put("earned",account.earned);w.put("hero_damage",p.hero_damage);w.put("producer_lost",rp.producer_lost);w.end();
        w.put("id",s);w.put("side",team);w.put("native_side",team);
        for(const char* k:{"owner","current_owner","original_owner","source_entity","root_source","root_original_owner"})w.put(k,team);
        w.null("parent_entity");w.null("parent_attack");
        w.strings("deck",m.deployment.players[i].deck);w.strings("secrets",p.secrets);if(m.battle.local_test_mode)w.put("test_slots",true);
        w.object("input");w.put("move",p.move);w.end();
        if(m.published_pose[i].is_null())w.json("native_pose",m.frame_json(m.battle.heroes.hero(seat)));
        else w.json("native_pose",m.published_pose[i]);
        if(const auto& g=m.battle.protection.selected_grave[i])w.put("selected_grave",*g);
        for(const char* k:{"control_until","tail_cd","knock_until","knock_vx"})w.put(k,0);
        if(m.deployment.players[i].last_copy_card)w.put("last_copy_card",*m.deployment.players[i].last_copy_card);
        if(seat!=team_of(seat))w.put("seat",s);
        if(rp.gift_ready_at>0.)w.put("gift_ready_at",rp.gift_ready_at);
        if(rp.teleport_ready_at>0.)w.put("teleport_ready_at",rp.teleport_ready_at);
        if(rp.collect_locked_until>0.)w.put("collect_locked_until",rp.collect_locked_until);
        if(m.cannon_aim_written[i]){if(rp.cannon_aim){w.array("cannon_aim");w.put("",rp.cannon_aim->y);w.put("",rp.cannon_aim->x);w.end();}else w.null("cannon_aim");}
        // PvP75: same fields as snapshot_layer.inc (the metadata view builds player rows here).
        if(const auto& aim=rp.laser_aim)if(const auto record=m.battle.native_objects.get(*aim))if(const auto* bean=std::get_if<PlantRef>(&*record)){
            const auto eye=pvp75::laser_eye(**bean,m.battle.runtime.tile);
            w.json("laser_aim",nlohmann::json{{"id",*aim},{"x",eye.x},{"y",eye.y},{"facing",(*bean)->facing<0.?-1:1},
                {"min",pvp75::kLaserMinCells},{"max",pvp75::kLaserMaxCells},{"angle",pvp75::kLaserHalfAngle}});
        }
        if(rp.test_zero_cooldown)w.put("test_zero_cooldown",true);
        if(std::find(m.tick_state.present.begin(),m.tick_state.present.end(),seat)==m.tick_state.present.end())w.put("absent",true);
        w.end();
    }
    w.end();
    w.object("native_placement_state");w.put("version",1);w.array("plants");
    for(const auto& p:*m.battle.plant_roster){
        const std::string content=p->source.content.present()&&!p->source.content.is_null()?p->source.content.get():std::string{};
        if(content=="抓人草触手")continue;
        const std::string copy=p->copy_card.present()&&!p->copy_card.is_null()?p->copy_card.get():std::string{};
        const bool shell=p->kind=="南瓜头"||content=="阳光藤蔓"||content=="忧郁藤蔓"||content=="抓人草"||(p->kind=="模仿者"&&copy=="plant:抓人草");
        w.object("");w.put("植物",shell?std::string("南瓜头"):p->kind);w.array("坐标");w.put("",p->cell.y);w.put("",p->cell.x);w.end();
        if(content=="水盆")w.put("basin",true);
        if(p->sleep.present())w.put("睡觉",true);
        if(content=="阳光藤蔓"||content=="忧郁藤蔓"||content=="抓人草")w.put("vine",true);
        if(content=="旋转芜菁"||content=="芦笋战机"||(p->kind=="模仿者"&&(copy=="plant:旋转芜菁"||copy=="plant:芦笋战机")))w.put("air",true);
        w.end();
    }
    w.end();w.strings("secrets",*m.tick_state.native_secrets);w.strings("empty_blocks",m.battle.terrain.empty_blocks);
    w.put("spike_cost",m.deployment.spike_cost.or_missing(100.));w.end();
    w.array("resources");for(const auto& r:m.resources.records()){
        w.object("");w.put("id",r.id);w.put("side",seat_name(r.side));w.put("amount",r.amount);
        w.put("x",r.position.x);w.put("y",r.position.y);w.put("born",r.born);w.put("source",r.source);
        if(r.shared.present())w.optional("shared",r.shared);if(r.coin.present())w.optional("coin",r.coin);w.end();
    }w.end();
    w.object("pvp70");w.json("projectiles",m.pvp70_projectiles());w.array("tentacles");
    for(const auto& p:*m.battle.plant_roster){
        if(!p->source.content.present()||p->source.content.is_null()||p->source.content.get()!="抓人草触手")continue;
        if(!(p->hp.present()&&!p->hp.is_null()&&p->hp.get()>0.)||p->dead.present())continue;
        const auto& c=p->content70;w.object("");w.optional("id",p->source.id);w.optional("parent",c.parent);
        w.optional("phase",c.head_phase);w.optional("clock",c.head_clock);w.optional("target",c.head_target);w.end();
    }w.end();w.end();
}
}
