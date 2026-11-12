# relay 相关测试归属（自动生成：tools/relay_ownership.py relay-ownership-src）

分类依据见脚本说明；`server-implementation` 不计入原生覆盖。

| 模块 | 类.用例 | 归属 | 原生结果 | 说明 |
| --- | --- | --- | --- | --- |
| test_pvp_51_ui | Controls51.test_slot_keys_rebind_persist_and_match_visible_page | native-client | PASS |  |
| test_pvp_51_ui | SpectatorBP51.test_bp_updates_decks_bans_stage_and_remains_read_only | native-client | ERROR | NotImplementedError: patch target requires a mutable production binding: object.text |
| test_pvp_53_features | Editor53.test_background_cancels_drag_and_preserves_placed_flag | native-client | PASS |  |
| test_pvp_53_features | Editor53.test_desktop_drag_cancel_and_read_only | native-client | PASS |  |
| test_pvp_53_features | Editor53.test_touch_drag_rally_does_not_jump_or_scroll | native-client | PASS |  |
| test_pvp_53_features | Editor53.test_weather_and_wall_tools_render_and_save | native-client | PASS |  |
| test_pvp_53_features | Map53.test_all_templates_keep_original_walls_and_invalid_data_rejected | native-client | PASS |  |
| test_pvp_53_features | Map53.test_original_rain_variants_safe_spawns_and_clear_switch | native-client | PASS |  |
| test_pvp_53_features | Map53.test_walls_persist_undo_and_never_change_collision | native-client | PASS |  |
| test_pvp_53_features | Rally53.test_charmed_native_movement_is_independent_of_rally | native-client | PASS |  |
| test_pvp_53_features | Rally53.test_rally_move_arrive_clear_and_dave_is_not_moved | native-client | PASS |  |
| test_pvp_53_features | Rally53.test_rally_special_mobile_units_and_charmed_parrot | native-client | PASS |  |
| test_pvp_53_features | Rally53.test_rally_validation_charm_and_solid_target | native-client | PASS |  |
| test_pvp_53_features | Rally53.test_recording_replays_place_replace_and_clear | native-client | PASS |  |
| test_pvp_53_features | Sync53.test_three_clients_share_walls_weather_and_rally | native-client | ERROR | setUpClass: NotImplementedError: untranslated: unresolved name classmethod (test_pvp_53_features.py:153) |
| test_pvp_56_ui | ProfileNetwork56Tests.test_names_roundtrip_and_result_count_only_connected_participants | native-client | PASS |  |
| test_pvp_56_ui | ProfileTests.test_participant_deduplication_persistence_draw_and_name | native-client | PASS |  |
| test_pvp_56_ui | Replay56Tests.test_real_native_high_speed_preserves_elapsed_time_and_backlog | native-client | PASS |  |
| test_pvp_56_ui | Replay56Tests.test_scaled_finger_scrub_resumes_and_speed_button_changes_native_ticks | native-client | PASS |  |
| test_pvp_56_ui | UI56Tests.test_action_binding_rebind_and_toggle | native-client | ERROR | NotImplementedError: patch target requires a mutable production binding: object.begin_rally |
| test_pvp_56_ui | UI56Tests.test_compact_map_footer_and_draft_map_label | native-client | ERROR | NotImplementedError: patch target requires a mutable production binding: object.text |
| test_pvp_56_ui | UI56Tests.test_music_and_effects_have_independent_saved_controls | native-client | ERROR | NotImplementedError: patch target requires a mutable production binding: object.update |
| test_pvp_56_ui | UI56Tests.test_name_and_room_profile_snapshot_and_immutable_participants | native-client | PASS |  |
| test_pvp_56_ui | UI56Tests.test_profile_and_keys_controls_fit_mobile_logical_display | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_draft_loading_and_battle_cannot_be_reset_by_requests | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_map_weather_seed_and_swap_need_authenticated_host_approval | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_proposals_cannot_smuggle_host_commands_or_invalid_custom_data | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_replace_cancel_reject_stale_and_departed_requests | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_tcp_guest_click_observing_host_approves_and_declines | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_tcp_guest_custom_colored_map_requires_host_acceptance | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_tcp_spectator_policy_request_updates_transport | native-client | PASS |  |
| test_pvp_57_room_requests | RoomRequestTests.test_tcp_two_remote_players_same_deck_rematch_with_observing_host | native-client | PASS |  |
| test_pvp_59_features | PvP59SweepTests.test_sweeping_the_pointer_over_a_drowsy_grave_wakes_it | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_a_planted_flower_pot_no_longer_changes_the_map_every_tick | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_blover_wind_reaches_projectiles_only_within_8_tiles | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_blover_zombie_pushes_plant_dave_inside_8_tiles_only | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_coffee_without_dense_is_unchanged | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_dense_coffee_wakes_every_sleeper_in_the_cell | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_gloom_pulse_hits_zombie_dave_for_4 | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_imitater_copies_aquatic_plants_in_the_water | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_masochist_dave_rises_after_3_seconds_instead_of_8 | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_parrots_eat_snow_blocks_without_breaking_the_match | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_plant_clover_blows_zombie_dave_twice_as_far_and_onto_a_mine | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_producing_graves_turn_drowsy_after_20_seconds_at_half_rate | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_sea_shroom_attacks_graves_on_the_water | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_sweep_input_tends_awake_or_drowsy_zombie_graves | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_turnip_ball_hits_zombie_dave_for_2_5 | native-client | PASS |  |
| test_pvp_59_features | PvP59Tests.test_zombie_dave_touching_a_drowsy_grave_wakes_it | native-client | PASS |  |
| test_pvp_59_features | RelayExpiryTests.test_room_with_a_watch_lane_player_outlives_the_waiting_timeout | native-client+relay | PASS |  |
| test_pvp_59_stack_care | CareInputTests.test_mouse_sweep_refreshes_all_awake_producers_in_a_shared_cell | native-client | PASS |  |
| test_pvp_59_stack_care | CareInputTests.test_sleep_state_is_visible_with_low_effects_and_survives_public_snapshot | native-client | ERROR | NotImplementedError: patch target requires a mutable production binding: object.blit |
| test_pvp_59_stack_care | CareInputTests.test_touch_hover_uses_the_same_care_path_without_a_tap | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_awake_sweep_refreshes_the_whole_20_second_interval_and_preserves_ice | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_card_descriptions_include_the_cap_and_awake_care | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_full_stack_coffee_wakes_all_sleepers_under_a_pumpkin | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_guest_preview_matches_authority_for_body_shell_and_coffee | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_hero_contact_refreshes_an_awake_grave_including_horizontal_wrap | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_pending_imitater_occupies_one_body_slot_through_transformation | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_shovel_releases_a_body_slot_without_removing_the_shell | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_three_bodies_plus_one_shared_shell_and_no_charge_on_rejection | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_three_flying_plants_and_one_vine_without_ground_support | native-client | PASS |  |
| test_pvp_59_stack_care | StackCareTests.test_water_vine_carries_three_bodies_and_uses_only_the_shell_slot | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyApplicationTests.test_app_polls_rtt_without_room_commands_and_clears_on_close | native-client | ERROR | NotImplementedError: patch target requires a mutable production binding: object.command |
| test_pvp_66_latency_oct15 | LatencySocketTests.test_direct_full_host_round_trip | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencySocketTests.test_relay_round_trip_reaches_authoritative_host_not_relay | native-client+relay | PASS |  |
| test_pvp_66_latency_oct15 | LatencySocketTests.test_spectator_diagnostics_work_without_allowing_game_commands | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencySocketTests.test_transport_filters_bad_diagnostics_and_keeps_next_game_sequence | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_failed_queue_send_is_waiting_and_retried_at_bounded_cadence | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_host_summary_is_slowest_and_unknown_peers_are_not_hidden | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_no_fake_zero_before_measurement_or_after_stale_disconnect_and_reconnect | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_oversized_malformed_and_flood_probes_do_not_reflect_or_grant_authority | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_probe_cadence_one_pending_and_timeout_cannot_be_a_success | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_round_trip_uses_only_local_monotonic_time_and_bounded_nonce | native-client | PASS |  |
| test_pvp_66_latency_oct15 | LatencyStateTests.test_unknown_replayed_wrong_peer_and_previous_connection_echoes_do_not_set_rtt | native-client | PASS |  |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_ai_fill_in_live_draft_is_rejected_without_roster_changes | native-client+relay | PASS |  |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_direct_four_players_join_without_spectating_and_fifth_is_rejected | native-client+relay | PASS |  |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_explicit_coop_ai_loads_current_brain_and_acts_for_its_own_seat | native-client+relay | ERROR | NotImplementedError: patch target requires a mutable production binding: object.human_delay |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_host_ai_invite_targets_empty_seat_and_never_autofills_or_replaces_human | native-client+relay | ERROR | NotImplementedError: patch target requires a mutable production binding: object.pending_bytes |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_human_duo_room_ai_seats_load_and_send_only_their_actual_seat | native-client+relay | ERROR | AttributeError: unsupported function attribute: __module__ |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_legacy_relay_automatically_uses_spare_lanes_for_third_and_fourth_players | server-implementation | ERROR | NotImplementedError: untranslated: stmt AsyncFunctionDef (test_pvp_66_room_admission_oct16.py:116) |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_legacy_relay_full_listing_join_button_still_attempts_direct_join | native-client+relay | PASS |  |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_pre_oct16_client_handshake_joins_four_seats_through_legacy_fallback | native-client+relay | ERROR | NotImplementedError: patch target requires a mutable production binding: object.RelayClientTransport |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_relay_four_players_join_without_spectating_and_fifth_is_rejected | native-client+relay | PASS |  |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_relay_observing_host_admits_four_remote_players | native-client+relay | FAIL | AssertionError: network condition failed: [["host","",[]]] |
| test_pvp_66_room_admission_oct16 | AdmissionAndAI.test_rendered_coop_ai_control_fills_and_kicks_only_from_host_preparation | native-client+relay | ERROR | NotImplementedError: patch target requires a mutable production binding: object.label |
| test_pvp_66_room_admission_oct16 | DraftVotes.test_duel_restart_still_requires_both | native-client | PASS |  |
| test_pvp_66_room_admission_oct16 | DraftVotes.test_duo_two_votes_continue_and_third_resets_all_four_seats | native-client | PASS |  |
| test_pvp_66_room_admission_oct16 | DraftVotes.test_duo_withdrawal_and_stale_revision_cannot_double_vote | native-client | PASS |  |
| test_pvp_network_memory67 | QueueMemoryTests.test_backlog_counts_commands_per_seat_and_clears_stale_generations | native-client | ERROR | AttributeError: 'function' object has no attribute '__new__' |
| test_pvp_network_memory67 | QueueMemoryTests.test_non_snapshot_overflow_still_fails_instead_of_losing_inputs | native-client | ERROR | AttributeError: 'function' object has no attribute '__new__' |
| test_pvp_network_memory67 | QueueMemoryTests.test_receive_coalescing_preserves_input_phase_map_and_peer_barriers | native-client | ERROR | AttributeError: 'function' object has no attribute '__new__' |
| test_pvp_network_memory67 | QueueMemoryTests.test_sequence_gap_is_rejected_before_any_state_can_be_coalesced | native-client | ERROR | AttributeError: 'function' object has no attribute '__new__' |
| test_pvp_network_memory67 | QueueMemoryTests.test_stalled_receiver_keeps_latest_state_and_full_map_in_both_modes | native-client | ERROR | AttributeError: 'function' object has no attribute '__new__' |
| test_pvp_network_memory67 | RelayMemoryTests.test_large_frame_is_forwarded_unchanged_with_small_stream_limits | native-client+relay | ERROR | AttributeError: bytearray.__str__ |
| test_pvp_relay | RelayNativeMatchTests.test_authenticated_guest_full_bp_input_economy_and_result | native-client | PASS |  |
| test_pvp_relay | RelayNativeMatchTests.test_unskipped_450_simulated_seconds_snapshots_deathmatch_and_rematch | native-client | ERROR | NotImplementedError: test decorator not yet supported: TENDED_GRAVES |
| test_pvp_relay | RelayNativeMatchTests.test_wire_turn_revision_and_locked_roster_cannot_be_bypassed | native-client | PASS |  |
| test_pvp_relay | RelayTests.test_background_lobby_query | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_capacity_and_rate_limits | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_code_normalization | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_collision_retry_is_bounded | server-implementation | ERROR | NotImplementedError: patch target requires a mutable production binding: object.choice |
| test_pvp_relay | RelayTests.test_control_slowloris_has_absolute_deadline | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_create_code_entropy_and_secret_separation | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_full_bidirectional_game_handshake_and_unicode | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_guest_disconnect_recovers_original_game_session | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_half_close_delivers_complete_final_frame | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_health_counts_wire_bytes_without_payload | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_host_expiration | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_host_resume_keeps_room_code | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_host_wan_disconnect_preserves_room_and_session | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_identity_mismatch_still_rejected | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_invalid_unicode_resume_secret_is_rejected | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_malformed_control_and_version | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_occupied_public_room_visible_but_not_joinable | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_oversized_game_frame_disconnects_pair | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_per_ip_connection_limit | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_playing_room_keeps_its_code_when_the_relay_reclaims_it | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_playing_room_reserves_a_new_code_when_the_registry_is_gone | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_public_listing_excludes_private_and_secrets | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_relay_restart_requires_new_room | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_waiting_room_timeout_is_bounded | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_wrong_code_and_bad_code | native-client+relay | PASS |  |
| test_pvp_relay | RelayTests.test_wrong_host_secret_and_duplicate_host | native-client+relay | PASS |  |
| test_pvp_replay_transfer | ReplayTransferTests.test_corrupt_out_of_order_unsolicited_and_timeout_never_enter_library | native-client | PASS |  |
| test_pvp_replay_transfer | ReplayTransferTests.test_guest_auto_save_without_host_auto_save_and_no_duplicate_requests | native-client | FAIL | AssertionError: '回放已保存' not found in '保存回放失败：回放分段顺序错误，请重试' |
| test_pvp_replay_transfer | ReplayTransferTests.test_lobby_guest_manual_save_list_reopen_and_native_playback | native-client | FAIL | AssertionError: '回放已保存' not found in '保存回放失败：回放分段顺序错误，请重试' |
| test_pvp_room_refill | RoomRefillTests.test_direct_guest_leave_refills_same_room_three_times | native-client | PASS |  |
| test_pvp_room_refill | RoomRefillTests.test_locked_match_disconnect_still_reserves_until_timeout | native-client | PASS |  |
| test_pvp_room_refill | RoomRefillTests.test_public_relay_guest_leave_refills_same_code_three_times | native-client | PASS |  |
| test_pvp_room_roles54 | RoleApplicationTests.test_direct_host_observes_two_remote_players_and_native_forfeit | native-client | PASS |  |
| test_pvp_room_roles54 | RoleApplicationTests.test_host_spectator_shutdown_aborts_without_awarding_either_player | native-client | PASS |  |
| test_pvp_room_roles54 | RoleApplicationTests.test_relay_closed_observer_gate_still_admits_a_second_player | native-client | PASS |  |
| test_pvp_room_roles54 | RoleApplicationTests.test_relay_promoted_spectator_stays_connected_when_watch_gate_closes | native-client | PASS |  |
| test_pvp_room_roles54 | RoleApplicationTests.test_relay_second_player_joins_available_seat_and_listing_tracks_room | native-client | PASS |  |
| test_pvp_room_roles54 | RoleApplicationTests.test_result_role_change_resets_before_reusing_seat | native-client | PASS |  |
| test_pvp_room_roles54 | RoleTransportTests.test_promoted_player_reconnects_with_same_authenticated_seat | native-client | PASS |  |
| test_pvp_room_roles54 | RoleTransportTests.test_server_authorized_promotion_then_demotion_changes_filter_in_place | native-client | PASS |  |
| test_pvp_spectator_ui49 | SpectatorApplicationTests.test_direct_immediate_reenable_revokes_old_sessions_and_refills_all_slots | native-client+relay | ERROR | NotImplementedError: stdlib call contextlib.ExitStack |
| test_pvp_spectator_ui49 | SpectatorApplicationTests.test_direct_spectator_receives_dynamic_terrain_and_new_match | native-client+relay | ERROR | NotImplementedError: patch target requires a mutable production binding: object.render |
| test_pvp_spectator_ui49 | SpectatorApplicationTests.test_full_direct_battle_cameras_touch_and_inputs_are_read_only | native-client+relay | ERROR | NotImplementedError: patch target requires a mutable production binding: object.send |
| test_pvp_spectator_ui49 | SpectatorApplicationTests.test_full_relay_battle_disable_reenable_and_leave_preserve_players | native-client+relay | PASS |  |
| test_pvp_spectator_ui49 | SpectatorApplicationTests.test_relay_immediate_reenable_revokes_old_sessions_and_refills_all_slots | native-client+relay | ERROR | NotImplementedError: stdlib call contextlib.ExitStack |
| test_pvp_spectators49 | SpectatorRelayTests.test_full_relay_room_observers_have_independent_read_only_channels | native-client+relay | PASS |  |
| test_pvp_spectators49 | SpectatorRelayTests.test_legacy_relay_without_capability_does_not_receive_watch_attempts | server-implementation | ERROR | NotImplementedError: untranslated: stmt AsyncFunctionDef (test_pvp_spectators49.py:274) |
| test_pvp_spectators49 | SpectatorRelayTests.test_player_slot_refills_while_existing_spectator_stays_connected | native-client+relay | PASS |  |
| test_pvp_spectators49 | SpectatorRelayTests.test_relay_host_policy_updates_listing_and_disconnects_only_audience | native-client+relay | PASS |  |
| test_pvp_spectators49 | SpectatorRelayTests.test_spectator_relay_cannot_forge_player_handshake | native-client+relay | PASS |  |
| test_pvp_spectators49 | SpectatorRoomTests.test_full_room_admits_read_only_spectator_in_every_phase | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorRoomTests.test_only_host_changes_policy_and_disabling_removes_audience | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorRoomTests.test_spectator_leave_during_native_battle_never_forfeits_or_clears_inputs | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorSocketTests.test_full_direct_room_separate_slots_snapshots_and_authority_filter | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorSocketTests.test_host_disables_existing_audience_without_disconnecting_player | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorSocketTests.test_latest_snapshot_queue_is_bounded_and_does_not_consume_player_budget | native-client | FAIL | AssertionError: 8 != 99 |
| test_pvp_spectators49 | SpectatorSocketTests.test_pending_full_map_cannot_be_replaced_by_mapless_delta | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorSocketTests.test_spectator_session_cannot_resume_as_player | native-client | PASS |  |
| test_pvp_spectators49 | SpectatorSocketTests.test_stalled_spectator_socket_does_not_block_player_snapshots | native-client | PASS |  |

汇总：`{"native-client": {"PASS": 90, "ERROR": 13, "FAIL": 3}, "native-client+relay": {"PASS": 36, "ERROR": 10, "FAIL": 1}, "server-implementation": {"ERROR": 3}}`
