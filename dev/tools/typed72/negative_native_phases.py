"""Inject real native-phase faults into a separately compiled source tree."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cmake',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--only',action='append')
    ap.add_argument('--group',choices=('native','seat_paths','maintenance','plant_actions','content_aim','september','flying','reeds','mortars','scarecrows','scripted_spawn','grenadiers','zombies64','native_summons'),default='native')
    args=ap.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'src/sim/typed';clone=out/'source/src/sim/typed';shutil.copytree(source,clone)
    pinned={str(p):sha(p) for p in source.glob('*.*')}
    manifest=out/'pinned.json';manifest.write_text(json.dumps(pinned,indent=2),encoding='utf8')
    cmake=(clone/'CMakeLists.txt').read_text(encoding='utf8')
    anchor='get_filename_component(PVZ_TYPED_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)'
    assert cmake.count(anchor)==1
    cmake=cmake.replace(anchor,'set(PVZ_TYPED_ROOT "'+ROOT.as_posix()+'")')
    anchor='target_include_directories(pvztyped72 PUBLIC "${PVZ_TYPED_ROOT}/src")'
    assert cmake.count(anchor)==1
    cmake=cmake.replace(anchor,'target_include_directories(pvztyped72 BEFORE PUBLIC "'+(out/'source/src').as_posix()+'" "${PVZ_TYPED_ROOT}/src")')
    (clone/'CMakeLists.txt').write_text(cmake,encoding='utf8')
    faults=[
        ('charmed_bite_loses_attribution','zombie_motion.cpp','source,{}});','{}, {}});','verify_zombie_interactions','reciprocal-source-callback-'),
        ('gravebuster_weak_bite','zombie_motion.cpp','*.5?6.:3.','*.5?3.:3.','verify_zombie_interactions','half-health-bite-'),
        ('dance_skip_reinforcements','zombie_actions.cpp','slot<4','slot<3','verify_zombie_actions','dance-summon-order-'),
        ('vehicle_no_snow_expiry','zombie_actions.cpp','snow.snow_gone.set(0.)','snow.snow_gone.set(1.)','verify_zombie_actions','vehicles-armor-and-ammo-'),
        ('cart_unlimited_ammo','zombie_actions.cpp','--n.basketball_total.get()','n.basketball_total.get()','verify_zombie_actions','vehicles-armor-and-ammo-'),
        ('triple_jump_loses_boost','hero_physics.cpp','p.vy*=1.25','p.vy*=1.','verify_hero_physics','seat-environment-and-jumps-'),
        ('recovery_revives_early','hero_physics.cpp','++g.recovery.get()>2000.','++g.recovery.get()>=2000.','verify_hero_physics','recovery-chili-and-balloon-'),
        ('tail_no_projectile','hero_physics.cpp','++g.tail.get()==50.','++g.tail.get()==51.','verify_hero_physics','two-seat-ability-order-'),
        ('seat_ignores_stun','hero_phase.cpp',' || stun>0.',' || stun>1000.','verify_hero_phase','native-seat-loop-'),
        ('seat_jumps_not_consumed','hero_phase.cpp','if(pressed)--player.jump_presses;','if(pressed)player.jump_presses=player.jump_presses;','verify_hero_phase','native-seat-loop-'),
        ('floating_corpse_sinks','hero_phase.cpp','p.y-tile*2./250.','p.y+tile*2./250.','verify_hero_phase','native-seat-loop-'),
        ('fire_loses_secondary_seat','hero_phase.cpp','if(side!=team)source.seat=side;','if(side!=team)source.seat=team;','verify_hero_phase','native-seat-loop-'),
        ('gravebuster_confuses_max_hp','zombie_motion.cpp','value(u->max_hp,300.)','value(u->patch.observed_max_hp,300.)','verify_zombie_interactions','independent-public-and-observed-max-hp-'),
        ('shared_sky_wrong_income','resources.cpp','income(copy,seat,15.,true)','income(copy,seat,25.,true)','verify_resources','collection-coins-and-shared-sky-'),
        ('merge_ignores_velocity','resources.cpp','std::abs(m.vy-om.vy)>.05','std::abs(m.vy-om.vy)>.5','verify_resources','sun-merge-order-and-compatibility-'),
        ('merge_keeps_older_clock','resources.cpp','std::max(keep->born,drop->born)','std::min(keep->born,drop->born)','verify_resources','sun-merge-order-and-compatibility-'),
        ('path_targets_sleeping_plants','path_tracking.cpp',' || p.sleep.present()','','verify_path_tracking','tracking-queues-targets-and-map-edits-'),
        ('sturdy_repeats_cooldown_cut','hero_recovery.cpp',' || a.sturdy_down.or_missing(false)','','verify_hero_recovery','room-recovery-order-and-boundaries-'),
        ('recovery_heals_before_delay','hero_recovery.cpp','std::min(elapsed,quiet-rules.delay)','elapsed','verify_hero_recovery','room-recovery-order-and-boundaries-'),
        ('economy_uses_native_rng','economy.cpp','world_.room_rng.uniform(0.,width)','world_.runtime.rng.uniform(0.,width)','verify_economy','native-day-clock-subsidy-and-sky-'),
        ('economy_repeats_day_income','economy.cpp','state_.previous_tick=now','state_.previous_tick=previous','verify_economy','native-day-clock-subsidy-and-sky-'),
        ('grave_first_yield_wrong_clock','economy.cpp','truth(u.produced)?card.period.get():6.','card.period.get()','verify_economy','native-grave-growth-and-payment-'),
        ('small_sun_wrong_income','economy.cpp','sun->size==0.?15.:25.','sun->size==0.?25.:25.','verify_economy','native-sun-attribution-and-amounts-'),
        ('producer_healing_restarts_rest','economy.cpp','hp<p->rest_hp.get()','hp!=p->rest_hp.get()','verify_economy','native-producer-rest-and-animation-'),
        ('producer_burst_repeats','economy.cpp','p->burst.set(123.)','p->burst.set(124.)','verify_economy','native-producer-rest-and-animation-'),
    ]
    if args.group=='seat_paths':
        faults=[
            ('seat_bank_copies_matrix','seat_path_tracking.cpp','bank=capture();','bank=independent(capture());','verify_seat_paths','seat-and-rally-'),
            ('seat_bank_drops_scalar_commit','seat_path_tracking.cpp','seats_[seat_index(*selected_)]=capture();','selected_.reset();','verify_seat_paths','seat-and-rally-'),
            ('phase_commits_final_bank','seat_path_tracking.cpp','restore(*phase_baseline_);phase_baseline_.reset();',
             'if(selected_)seats_[seat_index(*selected_)]=capture();restore(*phase_baseline_);phase_baseline_.reset();','verify_seat_paths','seat-and-rally-'),
            ('rally_controls_charmed','seat_path_tracking.cpp','unit.source.charmed.present() || !flags_.for_owner','false || !flags_.for_owner','verify_seat_paths','seat-and-rally-'),
            ('rally_discards_persistent_queue','seat_path_tracking.cpp','if(!bank.goal || !same(*bank.goal,goal))','if(true)','verify_seat_paths','seat-and-rally-'),
            ('destination_ignores_revision','seat_path_tracking.cpp','cache->revision==revision','cache->revision==cache->revision','verify_seat_paths','seat-and-rally-'),
            ('flood_reuses_aliased_queue','flood.cpp','state.frontier.use_count()!=1','false','verify_seat_paths','retained-path-queue-'),
        ]
    if args.group=='maintenance':
        faults=[
            ('grave_status_threshold','grave_clock.cpp','ice>1000.','ice>=1000.','verify_grave_clock','native-grave-status-'),
            ('grave_phantom_progress','grave_clock.cpp','if(!yes(grave->producer))continue;','','verify_grave_clock','native-grave-status-'),
            ('grave_scarecrow_ignores_owner','grave_clock.cpp','if(world_.heroes.owner(source_ref(target.unit))!=owner)continue;','','verify_grave_clock','grave-scarecrow-'),
            ('grave_touch_closed_lower_edge','grave_clock.cpp','point.y-tile<position.y','point.y-tile<=position.y','verify_grave_clock','grave-hero-touch-'),
            ('grave_repeats_wake_event','grave_clock.cpp','if(was){','if(true){','verify_grave_clock','grave-wake-input-'),
            ('plant_repeats_death_reward','plant_death_rules.cpp',' || yes(plant->secret_killed)','','verify_plant_maintenance','death-reward-'),
            ('plant_reverse_cleanup_order','plant_maintenance.cpp','const auto index=remaining-1;','const auto index=size_t(0);','verify_plant_maintenance','reverse-death-roster-'),
            ('plant_primal_circle_too_small','plant_maintenance.cpp','<=2.4*tile+1e-9','<=2.0*tile+1e-9','verify_plant_maintenance','primal-mine-'),
            ('plant_supplement_ignores_conversion','plant_death_rules.cpp',' && !yes(plant->transform_succeeded)','','verify_plant_maintenance','death-reward-'),
        ]
    if args.group=='plant_actions':
        faults=[
            ('plant_sleep_wrap','plant_region.cpp','++plant(index).sleep.get()==400.','++plant(index).sleep.get()==401.','verify_plant_region','sleeping-support-'),
            ('lantern_heal_chain','plant_region.cpp','amount/=2;','amount=3;','verify_plant_region','native-plant-family-27-'),
            ('plant_burst_clock','plant_region.cpp','if(++plant(index).burst.get()==125.) {\n            const double facing=','if(++plant(index).burst.get()==126.) {\n            const double facing=','verify_plant_region','native-plant-family-37-'),
            ('star_tail_count','shooter.cpp','offset<2','offset<1','verify_plant_region','constructor-replaces-entity-tail-'),
            ('sea_contact_lower_edge','sea_shroom.cpp','grave.y-tile*.85<point.y','grave.y-tile*.85<=point.y','verify_plant_utilities','sea-bubble-boundaries-'),
            ('sea_allied_grave','sea_shroom.cpp','world_.heroes.owner(source_ref(target.unit))==owner','false','verify_plant_utilities','sea-row-allegiance-'),
            ('umbrella_closed_threshold','owner_umbrella.cpp','position.vy>200.*plk','position.vy>=200.*plk','verify_plant_utilities','owner-umbrella-mode-'),
            ('umbrella_null_scratch','owner_umbrella.cpp','if(!saved_x.present())heroes.globals.xx.set_null();','','verify_plant_utilities','owner-umbrella-mode-'),
            ('grave_identity_replaced','grave_binding.cpp','target!=link.target','!target','verify_grave_binding_identity','grave-binding-valid-object-replacement-'),
            ('grave_reward_not_removed','grave_binding.cpp','actions_.coins.pop_back();','(void)actions_;','verify_grave_binding','grave-binding-nested-scope-'),
        ]
    if args.group=='content_aim':
        faults=[
            ('tripea_wrong_first_tie','plant_aim.cpp','score<nearest_score','score<=nearest_score','verify_plant_aim','tripea-periodic-'),
            ('tripea_closed_back_edge','plant_aim.cpp','dx*direction < -1.','dx*direction <= -1.','verify_plant_aim','tripea-periodic-'),
            ('hybrid_wrong_interpolation','plant_aim.cpp','            angle.set(old+difference(desired,old)*.3);','            angle.set(old+difference(desired,old)*.5);','verify_plant_aim','hybrid-split-'),
            ('hybrid_zero_vx_wrong_head','plant_aim.cpp','motion.vx>=0.?0:1','motion.vx>0.?0:1','verify_plant_aim','hybrid-split-'),
            ('route_narrow_interception','content_queries.cpp','world_.runtime.tile*.65','world_.runtime.tile*.64','verify_content_queries','content-route-'),
            ('query_omits_second_hero','content_queries.cpp','if(team_of(seat)!=enemy)continue;',
             'if(team_of(seat)!=enemy || seat==Seat::plant2 || seat==Seat::zombie2)continue;','verify_content_queries','content-nearest-'),
            ('taunt_ignores_cached_roster','sweet_taunts.cpp',
             'const auto fresh=dirty_?potatoes():std::vector<PlantRef>{};\n    const auto& candidates=dirty_?fresh:potatoes_;',
             'const auto fresh=potatoes();\n    const auto& candidates=fresh;','verify_content_queries','sweet-taunt-persistent-'),
            ('taunt_new_field_delayed','sweet_taunts.cpp','field.flood[0].cooldown=0;','field.flood[0].cooldown=4;','verify_content_queries','sweet-taunt-persistent-'),
            ('taunt_hides_goal_cell','sweet_taunts.cpp','!(potato->cell.y==y && potato->cell.x==wrapped)','true','verify_content_queries','sweet-taunt-hidden-'),
            ('taunt_loses_tracking_restore','sweet_taunts.cpp','banks_.restore_chase(*saved_);','(void)saved_;','verify_content_queries','sweet-taunt-persistent-'),
            ('taunt_wrong_identifier_tie','sweet_taunts.cpp','id.or_missing("")<old.or_missing("")','id.or_missing("")>old.or_missing("")','verify_content_queries','sweet-taunt-persistent-'),
            ('taunt_baseline_from_current','sweet_taunts.cpp','saved_=baseline_?baseline_->chase:banks_.capture_chase();',
             'saved_=banks_.capture_chase();','verify_content_queries','sweet-taunt-baseline-'),
        ]
    if args.group=='september':
        faults=[
            ('bloom_one_tick_late','september_plants.cpp','plant->content_age.get()<125.','plant->content_age.get()<126.','verify_september_plants','gold-bloom-'),
            ('bloom_income_boundary','september_plants.cpp','now<120*250?15.:25.','now<=120*250?15.:25.','verify_september_plants','gold-bloom-'),
            ('ghost_grave_activation','september_plants.cpp','!body->is_hero() && body->unit->protection.grave','false','verify_september_plants','ghost-activation-'),
            ('ghost_open_blast_edge','september_plants.cpp','std::abs(wrap_delta(origin.x,point.x,width))<=horizontal*tile',
             'std::abs(wrap_delta(origin.x,point.x,width))<horizontal*tile','verify_september_plants','ghost-pulse-'),
            ('ghost_pulse_damage','september_plants.cpp','attack(plant,25.,5.,.85,2.5);','attack(plant,26.,5.,.85,2.5);','verify_september_plants','ghost-pulse-'),
            ('ghost_aura_floor','september_plants.cpp','std::max(.01,plant->aura_factor.or_missing(1.))','std::max(1.,plant->aura_factor.or_missing(1.))','verify_september_plants','ghost-pulse-'),
            ('ghost_delayed_expiry','september_plants.cpp','if(elapsed>=2500.)','if(elapsed>2500.)','verify_september_plants','ghost-pulse-'),
        ]
    if args.group=='flying':
        faults=[
            ('turnip_early_volley','flying_plants.cpp','state.clock.get()+1e-8>=250.','state.clock.get()+1e-8>=249.','verify_flying_plants','turnip-periodic-'),
            ('turnip_omits_periodic_images','flying_plants.cpp','const auto wraps=int64_t(std::ceil(64.*tile/width))+1;',
             'const auto wraps=int64_t(0);','verify_flying_plants','turnip-distant-'),
            ('asparagus_rest_ignores_aura','flying_plants.cpp','state.rest.get()-advance','state.rest.get()-1.','verify_flying_plants','asparagus-sweep-'),
            ('asparagus_wrong_sweep_rate','flying_plants.cpp','angle-facing*60./750.','angle-facing*45./750.','verify_flying_plants','asparagus-sweep-'),
            ('asparagus_wrong_speed','flying_plants.cpp','turnip?12.:48.','turnip?12.:12.','verify_flying_plants','asparagus-sweep-'),
            ('flight_expired_at_closed_limit','flying_plants.cpp','entity->flying.distance.get()>world_.runtime.tile*limit',
             'entity->flying.distance.get()>=world_.runtime.tile*limit','verify_flying_plants','flight-contact-'),
            ('flight_wall_skips_start','flying_plants.cpp','for(int64_t step=0;step<=steps;++step)',
             'for(int64_t step=1;step<=steps;++step)','verify_flying_plants','flight-wall-'),
            ('flight_repeats_piercing_hit','flying_plants.cpp','hits.push_back(uid);','(void)uid;','verify_flying_plants','flight-contact-'),
            ('flight_reuses_dead_roster','flying_plants.cpp','rosters.clear();','(void)rosters;','verify_flying_plants','flight-contact-'),
            ('flight_retains_hidden_roster','flying_plants.cpp','shots.clear();','(void)shots;','verify_flying_plants','flight-captured-'),
        ]
    if args.group=='reeds':
        faults=[
            ('reed_wrong_id_tie','reed_plants.cpp','closest?candidate<best:candidate>best',
             'closest?candidate>best:candidate<best','verify_reed_plants','reed-cone-'),
            ('reed_short_range','reed_plants.cpp','distance>12.*world_.runtime.tile','distance>11.*world_.runtime.tile',
             'verify_reed_plants','reed-cone-'),
            ('reed_narrow_cone','reed_plants.cpp','>40.+1e-9','>39.9+1e-9','verify_reed_plants','reed-cone-'),
            ('reed_early_clock','reed_plants.cpp','plant->reed_clock.get()+1e-8<375.','plant->reed_clock.get()+1e-8<374.',
             'verify_reed_plants','reed-continuous-'),
            ('reed_missing_last_jump','reed_plants.cpp','jump<5','jump<4','verify_reed_plants','reed-chain-'),
            ('reed_loses_jump_tolerance','reed_plants.cpp','distance<=world_.runtime.tile+1e-6','distance<=world_.runtime.tile',
             'verify_reed_plants','reed-chain-'),
            ('reed_wrong_direct_stun','reed_plants.cpp','stun.set(std::max(stun.or_missing(0.),188.));',
             'stun.set(std::max(stun.or_missing(0.),187.));','verify_reed_plants','reed-chain-'),
            ('reed_wrong_hero_event','reed_plants.cpp','false,HeroHit::lightning','false,HeroHit::content',
             'verify_reed_plants','reed-overload-'),
            ('overload_skips_dead_direct_contact','reed_plants.cpp','hp(other,0.)>0. || other==target','hp(other,0.)>0.',
             'verify_reed_plants','reed-overload-'),
            ('overload_wrong_contact_packet','reed_plants.cpp','strike(plant,other,12.);','strike(plant,other,11.);',
             'verify_reed_plants','reed-overload-'),
        ]
    if args.group=='mortars':
        faults=[
            ('spring_distance_rounding','mortar_plants.cpp','const double distance=py::hypot(delta.x,delta.y);',
             'const double distance=std::hypot(delta.x,delta.y);','verify_mortar_plants','spring-fan-'),
            ('mortar_uses_low_arc','mortar_plants.cpp','lead(target),speed_,gravity_,2000.,BallisticArc::high',
             'lead(target),speed_,gravity_,2000.,BallisticArc::low','verify_mortar_plants','mortar-high-'),
            ('mortar_four_shots','mortar_plants.cpp','shot<5','shot<4','verify_mortar_plants','mortar-volley-'),
            ('mortar_short_range','mortar_plants.cpp','std::abs(dx)>16.*tile','std::abs(dx)>15.9*tile','verify_mortar_plants','mortar-high-'),
            ('mortar_short_retry','mortar_plants.cpp','plant->attack_clock.set(period-50.)','plant->attack_clock.set(period-49.)',
             'verify_mortar_plants','mortar-spring-continuous-'),
            ('mortar_keeps_blue_boost','mortar_plants.cpp','entity->mortar.tripea_blue.erase();','entity->mortar.tripea_blue.set(true);',
             'verify_mortar_plants','mortar-red-'),
            ('mortar_gravity_twice','mortar_plants.cpp','entity->motion.get().vy+=gravity_;','entity->motion.get().vy+=2.*gravity_;',
             'verify_mortar_plants','mortar-volley-'),
            ('mortar_bonus_repeats','mortar_plants.cpp','shot.bonus_done.set(true);','shot.bonus_done.set(false);',
             'verify_mortar_plants','mortar-volley-'),
            ('spring_wrong_body_damage','mortar_plants.cpp','hero?3.:6.','hero?3.:5.','verify_mortar_plants','spring-fan-'),
            ('spring_narrow_fan','mortar_plants.cpp','<=30.+1e-9','<=29.9+1e-9','verify_mortar_plants','spring-fan-'),
            ('spring_wrong_hero_kind','mortar_plants.cpp','true,HeroHit::spring','true,HeroHit::content','verify_mortar_plants','spring-fan-'),
            ('spring_weak_flyer_blow','mortar_plants.cpp','(max_speed?max_speed:10.)*50.','(max_speed?max_speed:10.)*10.',
             'verify_mortar_plants','spring-fan-'),
            ('mortar_reflects_twice','mortar_plants.cpp','if(sourced)state.umbrella_reflected=mark;else state.umbrella_reflected.set_null();',
             'state.umbrella_reflected.erase();','verify_mortar_plants','mortar-umbrella-'),
        ]
    if args.group=='scarecrows':
        faults=[
            ('scarecrow_native_walk_speed','scarecrow.cpp','unit->native.move_speed.set(.001);','unit->native.move_speed.set(.01);',
             'verify_scarecrow','scarecrow-config-'),
            ('scarecrow_ash_aura','scarecrow.cpp','!target.unit->body.ash.present()','true','verify_scarecrow','scarecrow-config-'),
            ('scarecrow_smaller_aura','scarecrow.cpp','for(int y=-3;y<=3;++y)for(int x=-3;x<=3;++x)',
             'for(int y=-2;y<=2;++y)for(int x=-2;x<=2;++x)','verify_scarecrow','scarecrow-config-'),
            ('scarecrow_wrong_slow','scarecrow.cpp','?1.15:1.','?1.1:1.','verify_scarecrow','scarecrow-config-'),
            ('scarecrow_omits_suspended_graves','scarecrow.cpp','for(const auto& grave:world_.suspended_graves)if(grave->protection.grave',
             'for(const auto& grave:world_.suspended_graves)if(false && grave->protection.grave','verify_scarecrow','scarecrow-live-'),
            ('scarecrow_early_hop','scarecrow.cpp','unit->hop_clock.get()>=230.','unit->hop_clock.get()>=229.',
             'verify_scarecrow','scarecrow-ground-'),
            ('scarecrow_ignores_slow_walk','scarecrow.cpp','unit->walk_speed.or_missing(0.)*factor','unit->walk_speed.or_missing(0.)',
             'verify_scarecrow','scarecrow-live-'),
            ('crow_leaks_ban_exemption','scarecrow.cpp','~SpawnBanExemption(){--world_.spawn_ban_exempt;}',
             '~SpawnBanExemption(){}','verify_scarecrow','crow-echo-'),
        ]
    if args.group=='scripted_spawn':
        faults=[
            ('spawn_limit_199','scripted_spawn_budget.cpp','raw.get(),1,200','raw.get(),1,199','verify_scripted_spawn','scripted-live-'),
            ('spawn_counts_graves','scripted_spawn_budget.cpp','!target.unit->protection.grave','true','verify_scripted_spawn','scripted-live-'),
            ('spawn_counts_ash','scripted_spawn_budget.cpp','!target.unit->body.ash.present()','true','verify_scripted_spawn','scripted-live-'),
            ('spawn_charm_loses_exemption','scripted_spawn_budget.cpp','(source && source->charmed.present())','false','verify_scripted_spawn','scripted-live-'),
            ('spawn_duplicate_admitted','scripted_spawn_budget.cpp','if(index_.contains(key))return false;','if(index_.contains(key))return true;',
             'verify_scripted_spawn','scripted-retained-'),
            ('spawn_failed_constructor_counted','scripted_spawn_budget.cpp','if(!request.create())break;','if(!request.create()){++admitted;break;}',
             'verify_scripted_spawn','scripted-retained-'),
            ('spawn_drain_flag_leaks','scripted_spawn_budget.cpp','~Reset(){flag=false;}','~Reset(){flag=true;}',
             'verify_scripted_spawn','scripted-retained-'),
            ('spawn_provenance_loses_wave','scripted_spawn_budget.cpp','copy.wave_index=source.wave_index;','copy.wave_index.erase();',
             'verify_scripted_spawn','scripted-provenance-'),
            ('dancer_entry_wrong','scripted_spawn_budget.cpp','child->native.entry.set(300.);','child->native.entry.set(301.);',
             'verify_scripted_spawn','scripted-deferred-'),
            ('dancer_context_wrong','scripted_spawn_budget.cpp','CombatPhase::summon,parent.source','CombatPhase::content,parent.source',
             'verify_scripted_spawn','scripted-deferred-'),
            ('native_dance_ignores_budget','zombie_actions.cpp','actions_.hold_dance()','false','verify_scripted_spawn','scripted-installed-'),
            ('native_sled_ignores_budget','zombie_actions.cpp','!actions_.hold_sled()','true','verify_scripted_spawn','scripted-installed-'),
            ('native_giant_ignores_budget','zombie_actions.cpp','!actions_.hold_giant()','true','verify_scripted_spawn','scripted-installed-'),
            ('spawn_hard_ceiling_exceeded','scripted_spawn_budget.cpp','ordered_.size()>=3200','ordered_.size()>3200',
             'verify_scripted_spawn','scripted-hard-'),
        ]
    if args.group=='grenadiers':
        faults=[
            ('grenade_windup_late', 'grenadiers.cpp', 'state.clock.get()>=250.', 'state.clock.get()>=251.', 'verify_grenadiers', 'grenadier-windup-'),
            ('grenade_ignores_first_damage', 'grenadiers.cpp', 'hp<state.seen_hp.or_missing(hp)-1e-9', 'hp<state.seen_hp.or_missing(hp)-1.', 'verify_grenadiers', 'grenadier-windup-'),
            ('grenade_does_not_hold_position', 'grenadiers.cpp', 'position.x=state.hold_x.or_missing(position.x);', 'position.x=position.x;', 'verify_grenadiers', 'grenadier-windup-'),
            ('grenade_death_does_not_cancel', 'grenadiers.cpp', 'state.phase.set(GrenadierPhase::cancelled);', 'state.phase.set(GrenadierPhase::thrown);', 'verify_grenadiers', 'grenadier-windup-'),
            ('grenade_selects_cheaper_plant', 'grenadiers.cpp', 'std::tuple{-cost,distance,id}<', 'std::tuple{cost,distance,id}<', 'verify_grenadiers', 'grenadier-priced-'),
            ('grenade_loses_firing_secret', 'grenadiers.cpp', 'grenade->instant.set(empowered);', 'grenade->instant.set(false);', 'verify_grenadiers', 'grenadier-lob-'),
            ('grenade_umbrella_square_shrinks', 'grenadiers.cpp', '>tile*1.5 || std::abs(p.y-center.y)>tile*1.5', '>tile*1.49 || std::abs(p.y-center.y)>tile*1.49', 'verify_grenadiers', 'grenadier-umbrella-'),
            ('grenade_mobile_damage_unscaled', 'grenadiers.cpp', 'zombie_vs_zombie(target)?10.:1.', 'zombie_vs_zombie(target)?1.:1.', 'verify_grenadiers', 'grenadier-explosion-'),
            ('grenade_execution_ignores_anchor', 'grenadiers.cpp', 'if(double(world_.heroes.tick)<protection.anchor_until.or_missing(0.))continue;', '', 'verify_grenadiers', 'grenadier-explosion-'),
            ('grenade_defused_expires_late', 'grenadiers.cpp', 'grenade->age<900', 'grenade->age<=900', 'verify_grenadiers', 'grenadier-projectile-'),
            ('grenade_skips_callback_appended_shot', 'grenadiers.cpp', 'index<original->size()', 'index<std::min(size_t(1),original->size())', 'verify_grenadiers', 'grenadier-target-cell-'),
            ('grenade_discards_legacy_seat', 'grenadiers.cpp', 'if(origin)std::visit([&](const auto& unit){seat=unit->source.seat.value_or(owner);', 'if(origin)std::visit([&](const auto& unit){seat=owner;', 'verify_grenadiers', 'grenadier-frozen-'),
        ]
    if args.group=='zombies64':
        faults=[
            ('redeye_throw_cooldown_late', 'content_zombies64.cpp', 'const double period=2000.*', 'const double period=2500.*', 'verify_content_zombies64', 'zombie64-red-eye-'),
            ('redeye_grab_range_shrinks', 'content_zombies64.cpp', 'distance>3.*world_.runtime.tile', 'distance>2.99*world_.runtime.tile', 'verify_content_zombies64', 'zombie64-grab-'),
            ('redeye_launch_late', 'content_zombies64.cpp', 'grab->ticks>=75.', 'grab->ticks>=76.', 'verify_content_zombies64', 'zombie64-red-eye-'),
            ('slime_entry_clock_wrong', 'content_zombies64.cpp', 'child->native.entry.set(500.);', 'child->native.entry.set(501.);', 'verify_content_zombies64', 'zombie64-slime-'),
            ('slime_sticky_loses_children', 'content_zombies64.cpp', 'count=yes(state.sticky)?4:2', 'count=yes(state.sticky)?2:2', 'verify_content_zombies64', 'zombie64-slime-'),
            ('slime_swallow_boundary_closed', 'content_zombies64.cpp', '-1026.<unit->body.hp', '-1026.<=unit->body.hp', 'verify_content_zombies64', 'zombie64-slime-'),
            ('slime_charm_clock_wrong', 'content_zombies64.cpp', 'child->source.charmed.set(200.);', 'child->source.charmed.set(0.);', 'verify_content_zombies64', 'zombie64-slime-'),
            ('slime_reads_stale_parent_after_constructor', 'content_zombies64.cpp', 'live.position.set(unit->body.motion.get());', 'live.position.set(point);', 'verify_content_zombies64', 'zombie64-split-callbacks-'),
            ('slime_spawn_exemption_leaks', 'content_zombies64.cpp', '~BanExemption(){--count;}', '~BanExemption(){}', 'verify_content_zombies64', 'zombie64-split-callbacks-'),
            ('belt_control_not_cleared', 'content_zombies64.cpp', 'field->set(0.);', 'field->set(1.);', 'verify_content_zombies64', 'zombie64-belt-'),
            ('belt_velocity_cap_wrong', 'content_zombies64.cpp', '-world_.runtime.plk*700.', '-world_.runtime.plk*600.', 'verify_content_zombies64', 'zombie64-belt-'),
            ('zombie64_gate_omits_taunt', 'content_zombies64.cpp', 'taunts_.apply(unit);', '', 'verify_content_zombies64', 'zombie64-gate-taunt-'),
            ('belt_publish_omitted', 'content_zombies64.cpp', 'services_.publish_terrain();', '', 'verify_content_zombies64', 'zombie64-installed-belt-'),
        ]
    if args.group=='scripted_spawn':
        faults.append(('spawn_fractional_slots_coalesce','scripted_spawn_budget.cpp','ScriptedSpawnKey key{id,std::move(kind),slot};','ScriptedSpawnKey key{id,std::move(kind),double(int64_t(slot))};','verify_scripted_spawn','scripted-fractional-'))
    if args.group=='native_summons':
        faults=[
            ('content_summon_bypasses_admission', 'native_summons.cpp', 'if(!budget_.can_spawn(1,fields))', 'if(false && !budget_.can_spawn(1,fields))', 'verify_native_summons', 'native-summon-deferred-'),
            ('content_summon_deferred_source_stays_live', 'native_summons.cpp', 'const auto saved=snapshot(source);', 'const Source saved=source;', 'verify_native_summons', 'native-summon-deferred-'),
            ('content_summon_wrong_context', 'native_summons.cpp', 'CombatPhase::summon,fields', 'CombatPhase::content,fields', 'verify_native_summons', 'native-summon-immediate-'),
            ('content_summon_charm_wrong_clock', 'native_summons.cpp', 'child->source.charmed.set(200.);', 'child->source.charmed.set(0.);', 'verify_native_summons', 'native-summon-immediate-'),
            ('content_summon_imp_launch_weak', 'native_summons.cpp', 'point.vx=direction*plk*800.;', 'point.vx=direction*plk*700.;', 'verify_native_summons', 'native-summon-immediate-'),
            ('content_summon_barrel_offset_lost', 'native_summons.cpp', 'barrel.x+direction*offset*tile', 'barrel.x', 'verify_native_summons', 'native-summon-immediate-'),
            ('content_summon_owner_changes_after_constructor', 'native_summons.cpp', 'if(owner==Seat::plant)child->source.charmed.set(200.);', 'if(world_.heroes.owner(fields)==Seat::plant)child->source.charmed.set(200.);', 'verify_native_summons', 'native-summon-live-source-'),
            ('content_summon_exemption_leaks', 'native_summons.cpp', '~Exemption(){--count;}', '~Exemption(){}', 'verify_native_summons', 'native-summon-live-source-'),
            ('content_summon_uses_new_launch_y', 'native_summons.cpp', 'point.y=start.y-1.5*tile;', 'point.y=position(source).y-1.5*tile;', 'verify_native_summons', 'native-summon-live-source-'),
        ]
    if args.only:
        faults=[f for f in faults if f[0] in args.only]
        if set(args.only)!={f[0] for f in faults}:raise ValueError('unknown requested fault')
    build=out/'build';env=dict(os.environ,_CL_='/MP1 /FS');results=[]
    base={f:(source/f).read_text(encoding='utf8') for _,f,_,_,_,_ in faults}
    configure=[args.cmake,'-S',str(clone),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64']
    with (out/'configure.log').open('wb') as log:subprocess.run(configure,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    for name,file,old,new,module,prefix in faults:
        target='resources72_probe' if module in ('verify_resources','verify_path_tracking','verify_hero_recovery','verify_economy') else 'world_rules72_probe'
        if module=='verify_seat_paths':target='seat_paths72_probe'
        if module in ('verify_grave_clock','verify_plant_maintenance'):target='maintenance72_probe'
        if module in ('verify_plant_region','verify_plant_utilities','verify_grave_binding'):target=module[7:]+'72_probe'
        if module=='verify_grave_binding_identity':target='grave_binding72_probe'
        if module in ('verify_plant_aim','verify_content_queries','verify_september_plants','verify_flying_plants','verify_reed_plants','verify_mortar_plants','verify_scarecrow','verify_scripted_spawn','verify_grenadiers','verify_content_zombies64','verify_native_summons'):target=module[7:]+'72_probe'
        assert base[file].count(old)==1,(name,old,base[file].count(old))
        (clone/file).write_text(base[file].replace(old,new),encoding='utf8')
        mutant=out/(name+'.cpp');shutil.copy2(clone/file,mutant)
        with (out/(name+'-build.log')).open('wb') as log:
            subprocess.run([args.cmake,'--build',str(build),'--config','Release','--target',target,'--parallel','1'],
                env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        run_dir=out/name
        wrapper=out/(name+'.py')
        oracle_paths='m.paths()+[Path(__file__)]' if module in ('verify_plant_region','verify_plant_utilities','verify_grave_binding','verify_grave_binding_identity','verify_plant_aim','verify_content_queries','verify_september_plants','verify_flying_plants','verify_reed_plants','verify_mortar_plants','verify_scarecrow','verify_scripted_spawn','verify_grenadiers','verify_content_zombies64','verify_native_summons') else '[Path(m.__file__)]'
        wrapper.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(ROOT/'tools/typed72'))+')\nimport '+module+' as m\n'
            'cases=lambda:[c for c in m.cases() if c[0].startswith('+repr(prefix)+')]\n'
            'raise SystemExit(m.shooting.main('+oracle_paths+',m.'+('build_ref' if module=='verify_zombie_motion' else 'reference')+',cases,m.'+
            {'verify_zombie_interactions':'InteractionExtension','verify_zombie_motion':'MotionExtension','verify_zombie_actions':'ActionExtension','verify_hero_physics':'HeroPhysicsExtension','verify_hero_phase':'HeroPhaseExtension',
             'verify_resources':'ResourceExtension','verify_path_tracking':'PathExtension','verify_hero_recovery':'RecoveryExtension','verify_economy':'EconomyExtension',
             'verify_seat_paths':'SeatPathExtension','verify_grave_clock':'GraveClockExtension','verify_plant_maintenance':'MaintenanceExtension',
             'verify_plant_region':'PlantRegionExtension','verify_plant_utilities':'PlantUtilitiesExtension','verify_grave_binding':'GraveBindingExtension',
             'verify_grave_binding_identity':'GraveBindingExtension','verify_plant_aim':'PlantAimExtension',
             'verify_content_queries':'ContentQueriesExtension','verify_september_plants':'SeptemberPlantsExtension',
             'verify_flying_plants':'FlyingPlantsExtension','verify_reed_plants':'ReedPlantsExtension',
             'verify_mortar_plants':'MortarPlantsExtension','verify_scarecrow':'ScarecrowExtension','verify_scripted_spawn':'ScriptedSpawnExtension','verify_grenadiers':'GrenadierExtension','verify_content_zombies64':'ContentZombie64Extension','verify_native_summons':'NativeSummonsExtension'}[module]+
            ',"negative-native-phase"))\n',encoding='utf8')
        with (out/(name+'.log')).open('wb') as log:
            process=subprocess.run([sys.executable,str(wrapper),'--exe',str(build/'Release'/(target+'.exe')),'--out',str(run_dir)],
                env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        report=json.loads((run_dir/'summary.json').read_text(encoding='utf8'))
        differences=[r for r in report['results'] if not r['passed'] and r.get('first_difference')]
        caught=process.returncode==1 and report['process_exit_code']==0 and not report['changed_inputs'] and bool(differences)
        row=dict(name=name,caught=caught,original=str(source/file),original_sha256=pinned[str(source/file)],mutant=str(mutant),
                 mutant_sha256=sha(mutant),replaced=old,replacement=new,cases=report['cases'],failed_cases=len(differences),
                 failures=differences,evidence=str(run_dir/'summary.json'))
        results.append(row);print(json.dumps(dict(name=name,caught=caught,failed_cases=len(differences))),flush=True)
        (clone/file).write_text(base[file],encoding='utf8')
    drift=[p for p,digest in pinned.items() if sha(Path(p))!=digest]
    report=dict(passed=all(r['caught'] for r in results) and not drift,results=results,source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())
