"""Current user rules applied to individual methods of the frozen 71 collection."""
import ast


REVISIONS = {
    'test_pvp_62_features': {
        'test_dense_zombies_bite_the_shell_first': [
            ('1, vines.lookup(3, 4))  # attacking zombies: the pumpkin',
             '2, vines.lookup(3, 4))  # newest living plant takes the bite'),
            ("b.g['植物'][1]['植物血'] = 0", "b.g['植物'][2]['植物血'] = 0"),
            ('2, vines.lookup(3, 4))  # dead shell: back to the top plant',
             '1, vines.lookup(3, 4))  # middle pumpkin is now exposed')],
    },
    'test_pvp_66_ai_maps_gift_oct16': {
        'test_all_bundled_maps_select_in_duo_and_rotate_in_coop': [
            ('identifier,day%4==3)', 'identifier,day%4==3 or day in (8,16,24))')],
    },
    'test_pvp_67_author_maps': {
        'test_two_complete_map_cycles_are_sequential_for_solo_and_coop': [
            ('day%4==3)', 'day%4==3 or (coop and day in (8,16,24)))')],
    },
    'test_pvp_66_coop_roster_oct15': {
        'test_kick_then_new_player_inherits_saved_seat_but_never_old_confirmation': [
            ("self.assertEqual('',self.confirm(r,'new'));self.assertEqual('config',r.phase)\n"
             "        self.assertEqual('',self.confirm(r,'host'));self.assertEqual('loading',r.phase)",
             "self.assertTrue(r.confirmed['plant']);self.assertFalse(r.confirmed['plant2'])\n"
             "        self.assertEqual('',self.confirm(r,'new'));self.assertEqual('loading',r.phase)")],
    },
    'test_pvp_66_feedback_pve_oct15': {
        'test_tcp_guest_restart_cannot_reset_host_progress_and_does_replace_guest_old_deck': [
            ('self.assertFalse(any(host.room.confirmed.values()))',
             "self.assertEqual({'plant': True, 'plant2': False}, host.room.confirmed)")],
    },
    'test_pvp_68003_balance': {
        'test_human_seat_deck_change_still_asks_everyone_to_confirm_again': [
            ('self.assertFalse(any(r.confirmed.values()))',
             "self.assertEqual({'plant': True, 'plant2': False}, r.confirmed)")],
    },
    'test_pvp_touch': {
        'test_scale_and_reset_actions': [('1.6)', '2.0)')],
        'test_layout_persists_round_trip': [('1.6)  # clamped', '2.0)  # clamped')],
    },
    'test_pvp_native_draft_display': {
        'test_locked_secrets_resolve_bank_grid_and_detail_without_changing_bp_identity': [
            ('self.assertEqual(CARDS, catalog_before)',
             "boss_cards = {'zombie:' + name for name in ('克苏鲁之眼', '克苏鲁之仆', '世界吞噬者', '世界吞噬者体节', '世界吞噬者尾节', '骷髅王', '骷髅王之手')}\n"
             "        for key in CARDS:\n"
             "            self.assertTrue(key in catalog_before or key in boss_cards, key)\n"
             "        for key in catalog_before:\n"
             "            self.assertEqual(catalog_before[key], CARDS[key], key)\n"
             "        for key in boss_cards:\n"
             "            self.assertTrue(CARDS[key]['spawn_only'], key)\n"
             "            self.assertFalse(CARDS[key]['selectable'], key)")],
    },
    'test_pvp_63_features': {
        'test_prices_descriptions_and_export_are_current': [
            ("ROOT/'对战/PvP规则数据.json'", "ROOT/'extract/data/catalog.json'"),
            ("data['build']", "json.loads((ROOT/'extract/data/__init__.json').read_text('utf8'))['BUILD']"),
            ("self.assertEqual(catalog_hash(),data['catalog_hash'])",
             "from pvp.catalog import digest\n        self.assertEqual(catalog_hash(),digest(data['CARDS']))"),
            ("exported=data['cards']", "exported=data['CARDS']")],
        'PLANT_COSTS': [('萝卜伞=60','萝卜伞=100')],
        'ZOMBIE_COSTS': [('橄榄球僵尸=200','橄榄球僵尸=175'),('报纸僵尸=250','报纸僵尸=275'),
                        ('墓碑吞噬者僵尸=300','墓碑吞噬者僵尸=225')],
    },
    'test_pvp_60_features': {
        'test_catalog_hud_almanac_and_export_share_prices': [
            ("ROOT/'对战/PvP规则数据.json'", "ROOT/'extract/data/catalog.json'"),
            ("self.assertEqual(catalog_hash(),data['catalog_hash'])",
             "from pvp.catalog import digest\n        self.assertEqual(catalog_hash(),digest(data['CARDS']))")],
    },
    'test_pvp_61_features': {
        'test_card_numbers_almanac_and_export': [
            ("ROOT/'对战/PvP规则数据.json'", "ROOT/'extract/data/catalog.json'"),
            ("self.assertEqual(catalog_hash(), data['catalog_hash'])",
             "from pvp.catalog import digest\n        self.assertEqual(catalog_hash(),digest(data['CARDS']))")],
    },
    'test_pvp_69002_balance': {
        'PRICES': [('报纸僵尸=250','报纸僵尸=275'),('墓碑吞噬者僵尸=300','墓碑吞噬者僵尸=225'),
                   ('滚桶僵尸=200','滚桶僵尸=225'),('海盗船长=225','海盗船长=250')],
        'test_all_mobile_cards_keep_charm_and_reciprocal_native_bite_values': [
            ("60. if name=='墓碑吞噬者僵尸'", "30. if name=='墓碑吞噬者僵尸'")],
    },
    'test_pvp_balance50': {
        'test_requested_prices_and_cooldowns': [
            ("'plant:萝卜伞':60","'plant:萝卜伞':100"),("'zombie:海盗船长':225","'zombie:海盗船长':250")],
    },
    'test_pvp_66_feedback': {
        'test_new_speed_secrets_change_car_and_air_travel': [
            ("'海陆空',1.5", "'海陆空',1.25", 2)],
        'test_taco_changes_actual_walking_car_and_bird_distance': [
            ("self.assertEqual(1.,b.units","self.assertEqual(.75,b.units"),
            ("self.assertAlmostEqual(2.,distances","self.assertAlmostEqual(1.75,distances")],
        'test_taco_real_twenty_second_timer_and_no_duplicate_buff': [('2*before','1.75*before',2)],
    },
    'test_pvp_66_material_maps_oct16': {
        'test_taco_effect_survives_snapshot_and_does_not_delay_or_duplicate_buff': [('2*speed','1.75*speed',2)],
    },
    'test_pvp_66_zombie_secrets': {
        'test_heal_and_taco_from_the_holder_dave': [('speed * 2','speed * 1.75',2)],
        'test_trinity_needs_land_water_air_in_own_deck': [("1.5, native['移速']","1.25, native['移速']")],
    },
    'test_pvp_57_producer_protection': {
        'test_native_supplemental_bite_scales_desired_total': [
            ("zombie['啃咬']=100","before=plant['植物血']\n        zombie['啃咬']=100"),
            ("self.assertIn(id(plant),b.patch.ns['__pvz_sb_gravebuster_zombie_bite_records'])",
             "self.assertEqual(before,plant['植物血'])"),
            ('self.assertEqual(1.5,','self.assertEqual(.75,',2)],
        'test_ash_500_packet_has_protected_death_threshold_and_no_repeat_fire': [
            ("275.,grave['血量']", "212.5,grave['血量']")],
    },
    'test_pvp_59_features': {
        'test_masochist_dave_rises_after_3_seconds_instead_of_8': [
            ('self.assertLess(quick, 3*250+100)','self.assertGreaterEqual(quick, 4*250)\n        self.assertLess(quick, 4*250+100)'),
            ('self.assertIn("3秒",','self.assertIn("4秒即开始起身",')],
    },
    'test_pvp_balance': {
        'test_native_ashes_and_instant_kills_take_exactly_500_from_a_giant': [
            ('500,giant["血量"],key','250 if key=="plant:火爆辣椒" else 500,giant["血量"],key')],
    },
    'test_pvp_chili_zombie_fire': {
        'test_ash_marked_grave_burns_out': [('775., tough["血量"]','712.5, tough["血量"]')],
    },
    'test_pvp_review_followup': {
        'test_chili_giant_survives_entire_first_fire_but_second_chili_kills': [('500,native["血量"]','250,native["血量"]')],
    },
    'test_pvp_hardening_copy': {
        'test_hardening_reaches_the_pvp_health_override_in_catalogue_and_field': [
            ('"plant:萝卜伞",18.,22.5','"plant:萝卜伞",36.,45.')],
    },
    'test_pvp_hero_damage_balance': {
        'test_bite_damage_by_zombie_kind': [('"zombie:墓碑吞噬者僵尸": 6.','"zombie:墓碑吞噬者僵尸": 3.')],
    },
    'test_pvp_plant_zombie_allegiance': {
        'test_charmed_peas_cross_torch_at_head_height_and_hit_enemy_zombies': [
            ("[1400.,480.,0.,0.]", "[1000.,480.,0.,0.]"),
            ('lit = False','lit = False\n                    seen = set()\n                    closest = (100000.,0.,0.)'),
            ('lit |= any(', "for e in b.g['实体']:\n                            seen.add((e.get('名',''), bool(e.get('__pvz_sb_charmed_plant_zombie_pea'))))\n                            if e.get('__pvz_sb_charmed_plant_zombie_pea'):\n                                px,py=e['位置'][:2]\n                                closest=min(closest,(abs(px-(torch['坐标'][1]+.5)*b.tile),px,py))\n                        lit |= any("),
            ("self.assertTrue(lit,'head-height charmed peas must ignite')",
             "self.assertTrue(lit,(name,secret,sorted(seen),target['血量'],torch['坐标'],closest))")],
    },
    'test_pvp_content_acceptance': {
        'test_actual_native_charm_bites_and_reciprocal_damage': [("('墓碑吞噬者僵尸',60.)","('墓碑吞噬者僵尸',30.)")],
        'test_charmed_units_walk_towards_nearest_enemy_and_bite_dave': [
            ("target=self.obj(b,'zombie:普通僵尸',560)", "target=self.obj(b,'zombie:普通僵尸',800)"),
            ("self.assertLess(a['位置'][0],700,name)", "self.assertGreater(a['位置'][0],700,name)")],
    },
    'test_pvp_ui': {
        'test_deck_version_and_almanac_controls': [
            ('with self.assertRaises(ValueError):\n                load_decks(path, ["plant:豌豆射手"])',
             'self.assertEqual({"plant": ["plant:花盆", "plant:咖啡豆"], "zombie": value["zombie"]}, load_decks(path, ["plant:豌豆射手"]))'),
            ('with self.assertRaises(ValueError):\n                load_decks(path)',
             'self.assertEqual(value, load_decks(path))\n'
             '            bad["format"]="unsupported"\n'
             '            path.write_text(json.dumps(bad), encoding="utf-8")\n'
             '            with self.assertRaises(ValueError):\n                load_decks(path)')],
    },
}


def current_test_source(module, source):
    revisions = REVISIONS.get(module, {})
    if not revisions:
        return source
    lines = source.splitlines(True)
    tree = ast.parse(source)
    blocks = [(n.name,n) for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in revisions]
    blocks.extend((n.targets[0].id,n) for n in tree.body if isinstance(n,ast.Assign) and
                  isinstance(n.targets[0],ast.Name) and n.targets[0].id in revisions)
    if len(blocks) != len(revisions) or {name for name,node in blocks} != set(revisions):
        raise ValueError('Missing or duplicate regression contract in ' + module)
    for name,node in sorted(blocks, key=lambda hit: hit[1].lineno, reverse=True):
        start, end = node.lineno - 1, node.end_lineno
        method = ''.join(lines[start:end])
        for old, new, *count in revisions[name]:
            if method.count(old) != (count[0] if count else 1):
                raise ValueError('Changed source contract in ' + module + '.' + name)
            method = method.replace(old, new)
        lines[start:end] = method.splitlines(True)
    return ''.join(lines)
