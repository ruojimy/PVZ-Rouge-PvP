"""Lightweight contracts: Python only, no generator run, files written or C++ build.

Run: python -B tools/typed72/test_production_observers.py
Real reference sources are read only for narrow, in-memory transformations.
The generator CLI and output filesystem tests use mocks/an in-memory tree.
"""
import contextlib
import io
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
if __package__:
    from . import make_app_composition as app
    from . import production_observers as obs
else:
    # Embedded Python 3.8 -I deliberately omits the script directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import make_app_composition as app
    import production_observers as obs


def method(text, signature):
    start, end = obs.body_span(text, signature)
    return text[start:end]


class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {name: (app.DRIVER / name).read_text(encoding='utf8') for name in obs.RULES}
        cls.driver = (app.DRIVER / 'match_probe.cpp').read_text(encoding='utf8')
        cls.strip = staticmethod(app.load_legacy_strip(app.DRIVER / 'make_stripped.py'))

    def production(self, name):
        transformed, records = obs.transform(name, self.sources[name])
        final, removed = self.strip(transformed)
        obs.validate_observers(name, final, after_legacy=True)
        return final, records, removed

    def test_all_pinned_bodies_and_manifest_records(self):
        count = 0
        for name, rules in obs.RULES.items():
            transformed, records = obs.transform(name, self.sources[name])
            self.assertEqual(len(records), len(rules))
            for rule, row in zip(rules, records):
                with self.subTest(path=name, signature=rule.signature):
                    original = method(self.sources[name], rule.signature)
                    result = method(transformed, rule.signature)
                    self.assertEqual(row['source_body_sha256'], obs.sha256(original))
                    self.assertEqual(row['source_body_sha256'], rule.source_body_sha256)
                    self.assertEqual(row['observer_result_body_sha256'], obs.sha256(result))
                    self.assertEqual(row['expected_count'], 1)
                    if rule.statements is None:
                        self.assertEqual(result, '{}')
                    else:
                        expected = original
                        for statement in rule.statements:
                            self.assertEqual(expected.count(statement), 1)
                            expected = expected.replace(statement, ';', 1)
                        # Byte-level assertion, not just token presence: EVERY
                        # other statement, exception and ordering is preserved.
                        self.assertEqual(result, expected)
                    count += 1
        self.assertEqual(count, 46)

    def test_known_phase_residuals_are_zero(self):
        text, _, _ = self.production(obs.PHASE)
        for token in ('p.calls.push_back', 'p.before(', 'p.after(',
                      'phase_events.push_back', 'phase_draws.push_back',
                      'J water=J::array()', 'J found=J::array()', 'J cells=J::array()'):
            self.assertNotIn(token, text)

    def test_known_controller_fixture_calls_and_json_are_zero(self):
        for name in (obs.ZOMBIES, obs.CONTROLLERS):
            text, _, _ = self.production(name)
            # The helper declaration remains; not a single event call does.
            self.assertNotRegex(text, r'\bevent\s*\(\s*"')
            for token in ('content_events.push_back', 'controller_events.push_back', 'factory_events.push_back'):
                self.assertNotIn(token, text)

    def test_real_damage_and_surface_exception_order_are_exact(self):
        text, _, _ = self.production(obs.PHASE)
        hit = method(text, obs.RULES[obs.PHASE][0].signature)
        self.assertIn('const auto result=p.content_lower_hit(i,f,a);;return result;', hit)
        surface = method(text, obs.RULES[obs.PHASE][1].signature)
        self.assertIn('const auto saved=p.surface_index;p.surface_index=i;', surface)
        self.assertIn('HitResult result;try{result=actual.surface_hit(i,f,a);}catch(...){p.surface_index=saved;throw;}p.surface_index=saved;;return result;', surface)
        self.assertIn('actual.knock(i,a);', method(text, obs.RULES[obs.PHASE][2].signature))
        self.assertIn('HitResult ash(size_t i)override{return actual.ash(i);}', text)
        self.assertIn('return actual.player_damage(amount);', text)

    def test_real_gate_cart_bite_and_barrel_calls_survive(self):
        text, _, _ = self.production(obs.CONTROLLERS)
        for statement in ('return concrete.bite_damage(unit,target);', 'september.gate(unit);',
                          'september.wave_chase(unit);', 'september.finish(unit);',
                          'zombies56.gate(unit);', 'zombies56.finish(unit);', 'zombies70.gate(unit);',
                          'barrels.correct_pair(unit);', 'barrels.detach(unit,hp);',
                          'barrels.break_barrel(unit);', 'barrels.move(unit,factor);', 'barrels.contact(unit,factor);'):
            self.assertIn(statement, text)
        zombies, _, _ = self.production(obs.ZOMBIES)
        self.assertIn('carts.before(unit);', zombies)
        self.assertIn('carts.animate(unit,active,fired);', zombies)

    def test_registration_and_factory_returns_are_not_empty_observers(self):
        text, _, _ = self.production(obs.CONTROLLERS)
        registration = method(text, 'void register_barrel(const ZombieRef& unit,const Field<std::string>& parent)override')
        for statement in ('ids.push_back(battle.units.order().back());units.push_back(unit);',
                          '++orphan_sequence', 'unit->source.id.set(id);unit->source.owner.set("zombie");',
                          'unit->protection.card.set("zombie:滚桶僵尸");battle.native_objects.set(id,unit);'):
            self.assertIn(statement, registration)
        for rule in obs.RULES[obs.CONTROLLERS]:
            if rule.signature.startswith(('ZombieRef spawn_bone_', 'PlantRef spawn_bone_')):
                self.assertIn('return {};', method(text, rule.signature))
        phase, _, _ = self.production(obs.PHASE)
        self.assertIn('battle.native_objects.set(id,plant);', phase)
        self.assertIn('plant_original(battle,cell,"坚果",facing);all_plants.push_back(plant);return plant;', phase)

    def test_match_business_events_and_real_registration_are_byte_identical(self):
        # The production observer pass cannot touch match_probe at all.
        self.assertEqual(obs.transform('match_probe.cpp', self.driver), (self.driver, []))
        stripped, _ = self.strip(self.driver)
        transformed, records = app.transform_driver(stripped)
        signatures = (
            'void plant70_event(const Plant70Event& v)override',
            'void zombie56_event(const Zombie56Event& v)override',
            'void zombie64_event(const Zombie64Event& v)override',
            'void zombie70_event(const Zombie70Event& v)override',
            'void grenade_event(const GrenadeEvent& v)override',
            'void mortar_event(const MortarPlantEvent& v)override',
            'void reed_event(const ReedEvent& v)override',
            'void september_event(const SeptemberPlantEvent& v)override',
            'void event(PveEvent e)override',
            'void register_tentacle(const PlantRef& plant,const Field<std::string>& parent)override',
            'HitResult content_lower_hit(size_t i,double facing,double amount)override',
            'void log_event(J fields)',
        )
        for signature in signatures:
            with self.subTest(signature=signature):
                self.assertEqual(method(transformed, signature), method(self.driver, signature))
        self.assertEqual(transformed.count('log_event('), self.driver.count('log_event('))
        self.assertIn('ContentPhaseProbe::plant70_event(v);', transformed)
        self.assertIn('J water=J::array();', method(transformed, signatures[0]))
        self.assertEqual([record['transform'] for record in records], ['release_fixture_retention', 'report_app_composition'])

    def test_paths_are_an_exact_allowlist_not_basename_or_event_pattern(self):
        source = self.sources[obs.ZOMBIES]
        for path in ('content_zombies_probe.cpp', 'other/content_zombies_probe.cpp',
                     'probes/../probes/content_zombies_probe.cpp', 'probes/business.cpp', 'match_probe.cpp'):
            self.assertEqual(obs.transform(path, source), (source, []))
        source = 'void event(PveEvent e){damage();register_unit();log_event(e);}'
        self.assertEqual(obs.transform('probes/business.cpp', source), (source, []))

    def test_unrelated_business_method_in_allowlisted_file_is_not_deleted(self):
        addition = '\nvoid real_event(){damage();register_unit();log_event(payload);}\n'
        result, _ = obs.transform(obs.CONTROLLERS, self.sources[obs.CONTROLLERS] + addition)
        self.assertTrue(result.endswith(addition))

    def test_real_side_effect_added_to_any_observer_body_fails_closed(self):
        for name, rules in obs.RULES.items():
            for rule in rules:
                with self.subTest(path=name, signature=rule.signature):
                    text = self.sources[name]
                    start, _ = obs.body_span(text, rule.signature)
                    changed = text[:start + 1] + 'damage();register_unit();log_event(payload);' + text[start + 1:]
                    with self.assertRaisesRegex(obs.ObserverContractError, 'unreviewed body'):
                        obs.transform(name, changed)

    def test_side_effect_in_fixture_argument_is_not_silently_erased(self):
        text = self.sources[obs.CONTROLLERS].replace('event("bite",unit,J::array({content_label(target)}));',
                                                     'event("bite",unit,J::array({damage(target)}));', 1)
        with self.assertRaisesRegex(obs.ObserverContractError, 'unreviewed body'):
            obs.transform(obs.CONTROLLERS, text)

    def test_missing_duplicate_or_changed_signature_fails_closed(self):
        name = obs.PHASE
        rule = obs.RULES[name][0]
        text = self.sources[name]
        for changed in (text.replace(rule.signature, rule.signature.replace('hit(', 'hit_changed('), 1),
                        text + '\n' + rule.signature + method(text, rule.signature)):
            with self.assertRaisesRegex(obs.ObserverContractError, 'expected one signature'):
                obs.transform(name, changed)

    def test_new_unreviewed_call_outside_pinned_bodies_is_rejected(self):
        for name, extra in ((obs.PHASE, 'void extra(){p.calls.push_back({"new"});}'),
                            (obs.PHASE, 'void extra(){event("new",unit);}'),
                            (obs.CONTROLLERS, 'void extra(){event("new",unit);}'),
                            (obs.ZOMBIES, 'void extra(){content_events.emplace_back("new");}')):
            with self.subTest(path=name):
                with self.assertRaisesRegex(obs.ObserverContractError, 'unexpected'):
                    obs.transform(name, self.sources[name] + extra)

    def test_empty_statement_preserves_if_else_and_loop_slots(self):
        call = 'event("fixture",unit);'
        text = 'if(flag)' + call + 'else damage();for(;;)' + call + 'registration();'
        # Counts are part of the contract, so repeated calls need separate rules.
        with self.assertRaises(obs.ObserverContractError):
            obs.remove_statements(text, (call,))
        text = 'if(flag)' + call + 'else damage();registration();'
        self.assertEqual(obs.remove_statements(text, (call,)), 'if(flag);else damage();registration();')
        self.assertEqual(obs.remove_statements('for(;;)' + call + 'damage();', (call,)), 'for(;;);damage();')

    def test_historical_strip_preserves_newline_if_else_structure(self):
        source = 'if(flag)\n    calls.push_back({"fixture"});\nelse\n    damage();\nregister_unit();log_event(event);'
        transformed, removed = self.strip(source)
        self.assertEqual(transformed, 'if(flag)\n    ;\nelse\n    damage();\nregister_unit();log_event(event);')
        self.assertEqual(len(removed), 1)
        business = 'void event(PveEvent e){log_event(e);damage();register_unit();}'
        self.assertEqual(self.strip(business), (business, []))

    def test_historical_stripper_source_change_is_rejected(self):
        with patch.object(Path, 'read_bytes', return_value=b'changed strip implementation'):
            with self.assertRaisesRegex(obs.ObserverContractError, 'unreviewed make_stripped'):
                app.load_legacy_strip(Path('unused'))

    def test_body_matching_handles_comments_and_strings(self):
        source = 'void example(){const char* s="}\\\"{";/* } */ if(ok){damage();}// }\n}'
        self.assertEqual(method(source, 'void example()'), source[len('void example()'):])
        with self.assertRaises(obs.ObserverContractError):
            obs.body_span('void example(){/* unterminated', 'void example()')
        with self.assertRaises(obs.ObserverContractError):
            obs.body_span('void example(){R"x(raw)x";}', 'void example()')

    def test_crlf_has_documented_hash_normalization(self):
        for name in obs.RULES:
            self.assertEqual(obs.transform(name, self.sources[name]),
                             obs.transform(name, self.sources[name].replace('\n', '\r\n')))

    def test_report_patch_is_one_exact_position_only(self):
        other = '\nJ unrelated={{"production_composition",false}};\n'
        transformed, records = app.transform_driver(self.driver + other)
        self.assertTrue(transformed.endswith(other))
        self.assertIn(app.APP_REPORT_PREFIX, transformed)
        self.assertEqual(records[1]['source'], app.REPORT_PREFIX)
        self.assertEqual(records[1]['source_text_sha256'], obs.sha256(app.REPORT_PREFIX))
        for text in (self.driver.replace(app.REPORT_PREFIX, 'changed_report', 1), self.driver + app.REPORT_PREFIX):
            with self.assertRaises(obs.ObserverContractError):
                app.transform_driver(text)


class MemoryPath:
    """Small filesystem double: tests never create temporary/on-disk files."""
    def __init__(self, tree, path='/output', writes=None):
        self.tree = tree
        self.path = PurePosixPath(path)
        self.writes = [] if writes is None else writes

    def __str__(self):
        return str(self.path)

    def __lt__(self, other):
        return str(self) < str(other)

    def __truediv__(self, child):
        return MemoryPath(self.tree, self.path / child, self.writes)

    @property
    def name(self):
        return self.path.name

    @property
    def parent(self):
        return MemoryPath(self.tree, self.path.parent, self.writes)

    @property
    def parents(self):
        return tuple(MemoryPath(self.tree, path, self.writes) for path in self.path.parents)

    def exists(self):
        return str(self) in self.tree

    def is_dir(self):
        return self.exists() and self.tree[str(self)] is None

    def is_file(self):
        return isinstance(self.tree.get(str(self)), bytes)

    def is_symlink(self):
        return self.tree.get(str(self)) == 'symlink'

    def lstat(self):
        if not self.exists():
            raise FileNotFoundError(str(self))
        linked = self.tree.get(str(self)) in ('symlink', 'junction', 'reparse')
        return SimpleNamespace(st_file_attributes=0x400 if linked else 0)

    def iterdir(self):
        return [MemoryPath(self.tree, path, self.writes) for path in self.tree
                if PurePosixPath(path).parent == self.path and PurePosixPath(path) != self.path]

    def read_bytes(self):
        return self.tree[str(self)]

    def mkdir(self, **kwargs):
        self.writes.append(('mkdir', str(self)))
        self.tree[str(self)] = None

    def write_bytes(self, data):
        self.writes.append(('write', str(self)))
        self.tree[str(self)] = data


class OutputSafetyTests(unittest.TestCase):
    def test_check_is_read_only_for_missing_changed_and_matching_outputs(self):
        outputs = {'probes/a.cpp': b'new', 'MANIFEST.json': b'{}\n'}
        trees = ({'/': None},
                 {'/': None, '/output': None, '/output/probes': None, '/output/probes/a.cpp': b'old'},
                 {'/': None, '/output': None, '/output/probes': None,
                  '/output/probes/a.cpp': b'new', '/output/MANIFEST.json': b'{}\n'})
        for tree in trees:
            original = dict(tree)
            out = MemoryPath(tree)
            changed = app.sync_output(outputs, out, check=True)
            self.assertEqual(changed, app.output_changes(outputs, {
                key: tree['/output/' + key] for key in outputs if '/output/' + key in tree}))
            self.assertEqual(out.writes, [])
            self.assertEqual(tree, original)

    def test_unknown_old_file_or_directory_refuses_before_any_write(self):
        for extra in ({'/output/zz_notes.txt': b'keep me'}, {'/output/zz_old': None}):
            tree = {'/': None, '/output': None, '/output/a.cpp': b'old', **extra}
            original = dict(tree)
            out = MemoryPath(tree)
            with self.assertRaisesRegex(obs.ObserverContractError, 'unexpected output'):
                app.sync_output({'a.cpp': b'new'}, out)
            self.assertEqual(tree, original)
            self.assertEqual(out.writes, [])

    def test_links_junctions_and_linked_ancestors_refuse(self):
        for location in ('/output/a.cpp', '/output', '/'):
            for kind in ('symlink', 'junction', 'reparse'):
                tree = {'/': None, '/output': None, '/output/a.cpp': b'old'}
                tree[location] = kind
                out = MemoryPath(tree)
                with self.assertRaisesRegex(obs.ObserverContractError, 'linked output'):
                    app.sync_output({'a.cpp': b'new'}, out)
                self.assertEqual(out.writes, [])

    def test_only_changed_known_files_are_written(self):
        out = MemoryPath({'/': None, '/output': None, '/output/a.cpp': b'same', '/output/b.cpp': b'old'})
        outputs = {'a.cpp': b'same', 'b.cpp': b'new', 'probes/c.cpp': b'new too'}
        self.assertEqual(app.sync_output(outputs, out), ['b.cpp', 'probes/c.cpp'])
        self.assertEqual([entry for entry in out.writes if entry[0] == 'write'],
                         [('write', '/output/b.cpp'), ('write', '/output/probes/c.cpp')])

    def test_invalid_names_and_case_collisions_fail_closed(self):
        for outputs in ({'../escape.cpp': b'x'}, {'/absolute.cpp': b'x'}, {'probes\\x.cpp': b'x'},
                        {'a.cpp': b'x', 'A.cpp': b'y'}, {'./a.cpp': b'x'}, {'x:stream': b'x'},
                        {'probes': b'file', 'probes/a.cpp': b'nested'}, {'a.cpp': 'not bytes'}):
            with self.assertRaises(obs.ObserverContractError):
                app.output_changes(outputs, {})
        with self.assertRaisesRegex(obs.ObserverContractError, 'unexpected output files'):
            app.output_changes({'a.cpp': b'new'}, {'old.cpp': b'keep'})

    def test_cli_source_failure_cannot_reach_output_mutation(self):
        with patch.object(app, 'build_outputs', side_effect=obs.ObserverContractError('late source body changed')), \
             patch.object(app, 'sync_output') as sync, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(app.main([]), 2)
            sync.assert_not_called()

    def test_cli_check_out_and_exit_codes_use_mocked_build_only(self):
        # This exercises argument/exit handling, not the actual generator.
        for changed, expected in (([], 0), (['a.cpp'], 1)):
            with patch.object(app, 'build_outputs', return_value={'a.cpp': b'new'}), \
                 patch.object(app, 'sync_output', return_value=changed) as sync, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(['--check', '--out', 'custom-composition']), expected)
                sync.assert_called_once_with({'a.cpp': b'new'}, Path('custom-composition').absolute(), check=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
