from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('    J zombie_json(const ZombieRef& unit)const {\n','''    // Key names come from the probes' verified field readers for each state struct.
    static void zombie_extra(J& j,const CombatZombie& u){
        const auto& pa=u.patch;const auto& c=u.content;const auto& a=u.content56;const auto& b=u.content70;const auto& s=u.content64;const auto& e=u.expansion;const auto& f=u.factory;const auto& r=u.registration;
        write(j,"植物僵尸",pa.plant_zombie);write(j,"植物僵尸名",pa.plant_name);write(j,"植物僵尸鸭子",pa.duck);write(j,"植物僵尸发射动画",pa.fire_animation);write(j,"植物僵尸角",pa.aim_angle);write(j,"射",pa.shoot);
        write(j,"植物僵尸抗击退",pa.knockback);write(j,"植物僵尸头",f.plant_head);write(j,"植物僵尸基础体",f.plant_base);write(j,"植物僵尸显示",f.plant_display);
        write(j,"植物僵尸射cd",pa.shooting_cooldown);write(j,"植物僵尸连发",pa.burst_left);write(j,"植物僵尸连发cd",pa.burst_cooldown);write(j,"__pvz_sb_plant_zombie_jump_cd",pa.jump_assist_cooldown);
        write(j,"__pvz_sb_plant_zombie_max_hp",pa.plant_max_hp);write(j,"__pvz_sb_blover_zombie_cd",pa.blover_cooldown);write(j,"__pvz_sb_blover_zombie_wind_tick",pa.blover_wind_tick);write(j,"__pvz_sb_lantern_zombie_cd",pa.lantern_cooldown);
        write(j,"__pvz_sb_fumeshroom_zombie_cd",pa.fume_cooldown);write(j,"__pvz_sb_fumeshroom_zombie_attack_angle",pa.fume_attack_angle);write(j,"__pvz_sb_fumeshroom_zombie_damage_done",pa.fume_damage_done);write(j,"__pvz_sb_fumeshroom_zombie_bubble_tick",pa.fume_bubble_tick);
        write(j,"__pvz_sb_umbrella_zombie_cd",pa.umbrella_cooldown);write(j,"__pvz_sb_gold_magnet_zombie_cd",pa.magnet_cooldown);write(j,"_pvp_umbrella_secret",pa.umbrella_secret);write(j,"_pvp_umbrella_initialized",pa.umbrella_initialized);
        write(j,"__pvz_sb_doom_zombie_life_ticks",pa.doom_life_ticks);write(j,"__pvz_sb_doom_zombie_life_time",pa.doom_life_time);write(j,"_pvp_bite_plant",pa.bite_plant);write(j,"_pvp_no_attack",pa.no_attack);write(j,"_pvp_zs_volley",pa.shotgun_volley);write(j,"_pvp_torch_brain",pa.torch_brain);write(j,"_pvp_torch_sleep_until",pa.torch_sleep_until);
        write(j,"_pvp_no_hero_attack",u.source.no_hero_attack);write(j,"_pvp_base_speed",u.base_speed);write(j,"_pvp_walk_speed",u.walk_speed);write(j,"_pvp_hop_clock",u.hop_clock);write(j,"_pvp_flight",u.flight);write(j,"_pvp_mature",u.mature);
        if(u.source.seat)j["_pvp_seat"]=seat_name(*u.source.seat);
        write(j,"_pvp_saved_basketball_cd",c.saved_basketball_cd);write(j,"_pvp_summon_clock",c.summon_clock);write(j,"_pvp_cannon_rate",c.cannon_rate);write(j,"_pvp_cart_deadline",c.cart_deadline);write(j,"_pvp_cannon_anim",c.cannon_animation);write(j,"_pvp_cannon_recoil",c.cannon_recoil);write(j,"_pvp_cart_expired",c.cart_expired);write(j,"_pvp_cannon_loaded",c.cannon_loaded);
        write(j,"_pvp_barrel_direction",c.barrel_direction);write(j,"_pvp_barrel_remaining",c.barrel_remaining);write(j,"_pvp_barrel_broken",c.barrel_broken);write(j,"_pvp_barrel_discarded",c.barrel_discarded);write(j,"_pvp_barrel_detached",c.barrel_detached);write(j,"_pvp_target",c.target);write(j,"_pvp_zs_headhunt",c.headhunt);
        if(u.barrel_position.present()&&!u.barrel_position.is_null())j["_pvp_barrel_position"]=as_json(*u.barrel_position.get());if(u.orphan_barrel)j["_pvp_orphan_barrel"]=true;
        write(j,"_pvp_dance_owner",a.dance_owner);write(j,"_pvp_zs_dance_parent",a.wild_parent);write(j,"_pvp_squad_owner",a.squad_owner);write(j,"_pvp_dance_slot",a.dance_slot);write(j,"_pvp_dance_saved_speed",a.saved_speed);write(j,"_pvp_dance_clock",a.dance_clock);write(j,"_pvp_dance_rate",a.dance_rate);write(j,"_pvp_dancing",a.dancing);write(j,"_pvp_dance_impulse",a.impulse);
        if(a.dance_side.present())j["_pvp_dance_side"]=a.dance_side.is_null()?J(nullptr):J(seat_name(a.dance_side.get()));
        write(j,"_pvp70_clock",b.clock);write(j,"_pvp_reaper_idle",b.reaper_idle);write(j,"_pvp_airdrop_used",b.airdrop_used);write(j,"_pvp_bone_grave",b.bone_grave);write_point(j,"_pvp_hook_pull",b.hook_pull);
        write(j,"_pvp_throw_clock",s.throw_clock);write(j,"_pvp_grabbed_by",s.grabbed_by);write(j,"_pvp_thrown_by",s.thrown_by);write(j,"_pvp_split",s.split);write(j,"_pvp_slime_sticky",s.sticky);write(j,"_pvp_zs_hand_kind",s.hand_kind);
        if(s.grab.present()){if(s.grab.is_null())j["_pvp_grab"]=nullptr;else{J g={{"ticks",s.grab.get()->ticks}};write(g,"id",s.grab.get()->id);j["_pvp_grab"]=g;}}
        const auto& gr=u.grenadier;write(j,"_pvp_grenade_clock",gr.clock);write(j,"_pvp_seen_hp",gr.seen_hp);write(j,"_pvp_hold_x",gr.hold_x);
        if(gr.phase.present()){static const char* phases[]={"ready","wind","thrown","cancelled"};j["_pvp_grenade"]=gr.phase.is_null()?J(nullptr):J(phases[int(gr.phase.get())]);}
        write(j,"_pvp_black_armor",e.black_armor);write(j,"_pvp_before_vy",e.before_vy);write(j,"_pvp_charge_until",e.charge_until);write(j,"_pvp_charge_ready",e.charge_ready);write(j,"_pvp_charge_cd",e.charge_cd);write(j,"_pvp_charging",e.charging);write(j,"_pvp_paralysis_until",e.paralysis_until);write(j,"_pvp_paralysis_started",e.paralysis_started);write(j,"_pvp_paralysis_garlic",e.paralysis_garlic);
        write(j,"_pvp_poison_killed",u.poison.killed);write(j,"_pvp_armor_triggered",u.poison.armor_triggered);write(j,"_pvp_imp_armor",u.poison.imp_armor);write(j,"_pvp_imp_armor_hp",u.poison.imp_armor_hp);
        write(j,"_pvp72_health",r.health72);write(j,"_pvp_zs_hand",r.secret_hand);write(j,"_pvp_zs_hand_max",u.hand_max);write(j,"_pvp_zs_pole",r.secret_pole);write(j,"_pvp_zs_crowd",r.secret_crowd);write(j,"_pvp_coop_dormant",r.coop_dormant);
        if(!pa.speed_factors.empty()){J speed=J::object();for(const auto& [key,value]:pa.speed_factors)speed[key]=value;j["_pvp_zs_speed"]=speed;}
        const auto& pr=u.protection;write(j,"_pvp_zs_hurt",pr.hurt_tick);write(j,"_pvp_reaper_hurt",pr.reaper_hurt);write(j,"_pvp_anchor_until",pr.anchor_until);write(j,"_pvp_zs_crowd_factor",pr.crowd_factor);write(j,"_pvp_zs_relic_until",pr.relic_until);write(j,"_pvp_zs_locked",pr.locked);
    }
    static void plant_extra(J& j,const CombatPlant& p){
        const auto& c=p.content_state;const auto& s=p.content70;const auto& fl=p.flying;
        write(j,"_pvp_interval",c.interval);write(j,"_pvp_before_shot",c.before_shot);write(j,"_pvp_before_cd",c.before_cd);write(j,"_pvp_vine_clock",c.vine_clock);write(j,"_pvp_vine_produced",c.vine_produced);write(j,"_pvp_lantern_timer",c.lantern_timer);write(j,"_pvp_hardening_form",c.hardening_form);write(j,"_pvp_awake_forever",c.awake_forever);
        write(j,"_pvp70_clock",s.clock);write(j,"_pvp_head_clock",s.head_clock);write(j,"_pvp_head_age",s.head_age);write(j,"_pvp_head_phase",s.head_phase);write(j,"_pvp_parent",s.parent);write(j,"_pvp_head_target",s.head_target);write(j,"_pvp_head_color",s.head_color);write(j,"_pvp_head_hits",s.head_hits);write(j,"_pvp_heads",s.heads);write(j,"_pvp_was_asleep",s.was_asleep);
        write_point(j,"_pvp_head_aim",s.head_aim);write_point(j,"_pvp_head_goal",s.head_goal);write_point(j,"_pvp_head_start",s.head_start);
        if(s.basin_terrain.present()&&!s.basin_terrain.is_null()){auto saved=tile_state(s.basin_terrain.get());write(saved,"_pvp_basin",s.basin_terrain.get()->basin);j["_pvp_basin_terrain"]=saved;}
        write(j,"_pvp_health_form",p.registration.health_form);write(j,"_pvp_content_age",p.content_age);write(j,"_pvp_one_shot",p.one_shot);write(j,"_pvp_effect_done",p.effect_done);write(j,"_pvp_attack_clock",p.attack_clock);write(j,"_pvp_reed_clock",p.reed_clock);write(j,"_pvp_last_fired",p.last_fired);write(j,"_pvp_ghost_started",p.ghost_started);write(j,"_pvp_ghost_clock",p.ghost_clock);write(j,"_pvp_ghost_pulse",p.ghost_pulse);
        write(j,"_pvp_flying_clock",fl.clock);write(j,"_pvp_flying_rest",fl.rest);write(j,"_pvp_flying_mode",fl.mode);write(j,"_pvp_flying_sweep_age",fl.sweep_age);write(j,"_pvp_flying_sweep_angle",fl.sweep_angle);write(j,"_pvp_flying_sweep_facing",fl.sweep_facing);write(j,"_pvp_flying_shots",fl.shots);
        const auto& angles=p.bonus.tripea_angles;if(angles.present()){J values=nullptr;if(!angles.is_null()){values=J::array();for(const auto& a:angles.get())values.push_back(a.is_null()?J(nullptr):J(a.get()));}j["三向角"]=values;}
        const auto clock=[&](const char* key,const Field<ExpansionClockValues>& f){if(!f.present()||f.is_null())return;J d=J::object();constexpr std::array<const char*,10> names{"射cd","射","吃","发射cd","发射动画","埋藏","滚蛋","吸","爆了","路灯"};for(size_t i=0;i<names.size();++i)write(d,names[i],f.get()[i]);j[key]=d;};
        clock("_pvp_clock_credit",p.expansion_clock.credit);clock("_pvp_clock_debt",p.expansion_clock.debt);
    }
    static void entity_extra(J& j,const Entity& e){
        write(j,"牛顿",e.gravity);write(j,"旋转",e.rotation);write(j,"穿墙",e.through_wall);write(j,"追踪",e.tracking);write(j,"__pvz_sb_zombie_pea_fire",e.source.zombie_fire);
        if(e.expires.boolean_encoding())j["消亡"]=e.expires.get()!=0.;else write(j,"消亡",e.expires);
        write(j,"__pvz_sb_smart_projectile_skip",e.service.smart_skip);
        const auto& pe=e.pea;write(j,"x",pe.x);write(j,"y",pe.y);write(j,"prev_x",pe.previous_x);write(j,"prev_y",pe.previous_y);write(j,"vx",pe.vx);write(j,"vy",pe.vy);write(j,"age",pe.age);write(j,"僵尸豌豆弹",pe.zombie_pea);write(j,"__pvz_sb_native_move",pe.native_move);write(j,"__pvz_sb_charmed_plant_zombie_pea",pe.charmed_pea);
        const auto& c=e.chili;write(j,"智能辣椒火",c.patched);write(j,"智能火行",c.row);write(j,"智能火列",c.col);write(j,"智能火地面行",c.ground_row);write(j,"智能火地面",c.ground_y);write(j,"__pvz_sb_chili_zombie_fire",c.zombie_fire);write(j,"__pvz_sb_chili_zombie_friendly_fire",c.friendly_fire);write(j,"__pvz_sb_chili_fire_no_hero",c.no_hero);write(j,"__pvz_sb_chili_fire_damage_mode",c.damage_mode);
        const auto& m=e.mortar;write(j,"_pvp_mortar",m.mortar);write(j,"_pvp_mortar_speed",m.speed);write(j,"_pvp_mortar_target",m.target);write(j,"_pvp_mortar_bonus_done",m.bonus_done);write(j,"_pvp_multi_red",m.multi_red);write(j,"三向蓝火弹",m.tripea_blue);
        const auto& b=e.bonus;write(j,"智能杨桃",b.star_patched);write(j,"上次制导",b.last_guide);write(j,"制导次数",b.guide_count);
    }
    J zombie_json(const ZombieRef& unit)const {
''')
sub('if(u.protection.grave)j["_pvp_grave"]=true;','zombie_extra(j,u);if(u.protection.grave)j["_pvp_grave"]=true;')
sub('for(const auto& p:*battle.plant_roster)plants.push_back(plant_state(*p));','for(const auto& p:*battle.plant_roster){J row=plant_state(*p);plant_extra(row,*p);plants.push_back(std::move(row));}')
sub('''        write_point(j,"_pvp_torch_previous",e.flight.torch_previous);return j;''','''        write_point(j,"_pvp_torch_previous",e.flight.torch_previous);entity_extra(j,e);return j;''')
# Real services instead of stubs.
sub('    int jump_cap(Seat)const override{return 2;}\n','''    int jump_cap(Seat seat)const override{
        // Source _jump_cap: secret:疾行 gives plants three jumps; the zombie secret 豌豆 limits to one. 0 keeps the default.
        const auto& secrets=world.players[seat_index(seat)]->secrets;
        if(team_of(seat)==Seat::plant)return std::find(secrets.begin(),secrets.end(),"secret:疾行")!=secrets.end()?3:0;
        return zsecrets.seat_has(seat,"豌豆")?1:0;
    }
''')
sub('    bool rage()const override{return false;}\n    bool first_soldier()const override{return false;}\n','    bool rage()const override{return battle.protection.secrets.team.test(size_t(DamageSecret::rage));}\n    bool first_soldier()const override{return zsecrets.has("首发士兵");}\n')
sub('    void select_grave(Seat,const std::string&)override{unsupported.push_back("select_grave");}\n','''    void select_grave(Seat seat,const std::string& grave)override{
        auto& chosen=battle.protection.selected_grave[seat_index(seat)];
        if(chosen!=grave){chosen=grave;log_event({{"event","zsecret_select_grave"},{"side",seat_name(seat)},{"grave",grave}});}
    }
''')
p.write_text(t,encoding='utf8')
