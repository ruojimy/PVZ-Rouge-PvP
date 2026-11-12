"""Regression controls for exact waivers, memory admission and fixture isolation."""
import copy,json,os,sys,tempfile,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_test_waivers import detail_sha256,evaluate_module,load_waivers
from native_test_scheduling import MIB,can_start,memory_snapshot,run_modules
from run_cpp_suite import clone_fixture


class WaiverPolicyTests(unittest.TestCase):
    def setUp(self):
        self.cases=load_waivers();self.case=next(iter(self.cases.values()))
        module,cls,test=self.case['id'].split('.')
        self.row=dict(module=module,**{'class':cls},test=test,outcome=self.case['outcome'],detail=self.case['baseline_detail'])

    def evaluate(self,rows=None,rc=1,**kwargs):
        return evaluate_module(self.row['module'],[self.case['id']],rows if rows is not None else [self.row],rc,waivers=self.cases,**kwargs)

    def test_exact_case_is_waived_without_rewriting_raw_outcome(self):
        before=copy.deepcopy(self.row);result=self.evaluate()
        self.assertTrue(result['accepted']);self.assertFalse(result['success'])
        self.assertEqual(len(result['waived']),1);self.assertEqual(before,self.row)

    def test_all_18_cases_have_exact_pinned_failures(self):
        self.assertEqual(len(self.cases),18)
        self.assertEqual(sum(case['outcome']=='FAIL' for case in self.cases.values()),6)
        for case in self.cases.values():self.assertEqual(detail_sha256(case['baseline_detail']),case['detail_sha256'])

    def test_changed_detail_for_same_case_is_rejected(self):
        self.row['detail']+=' new failure';self.assertFalse(self.evaluate()['accepted'])

    def test_changed_outcome_for_same_case_is_rejected(self):
        self.row['outcome']='ERROR' if self.row['outcome']=='FAIL' else 'FAIL'
        self.assertFalse(self.evaluate()['accepted'])

    def test_new_failure_is_rejected(self):
        row=dict(self.row,test='test_new_failure')
        result=evaluate_module(row['module'],['.'.join(row[k] for k in ('module','class','test'))],[row],1,waivers=self.cases)
        self.assertFalse(result['accepted'])

    def test_fixed_case_passes_and_is_reported_resolved(self):
        self.row.update(outcome='PASS',detail='');result=self.evaluate(rc=0)
        self.assertTrue(result['accepted']);self.assertTrue(result['success'])
        self.assertEqual(result['resolved_waivers'],[self.case['id']]);self.assertEqual(result['waived'],[])

    def test_strict_mode_rejects_the_known_failure(self):
        result=evaluate_module(self.row['module'],[self.case['id']],[self.row],1,waivers={})
        self.assertFalse(result['accepted'])

    def test_missing_case_is_rejected(self):self.assertFalse(self.evaluate(rows=[])['accepted'])
    def test_duplicate_case_is_rejected(self):self.assertFalse(self.evaluate(rows=[self.row,self.row])['accepted'])
    def test_extra_case_is_rejected(self):self.assertFalse(self.evaluate(rows=[self.row,dict(self.row,test='test_extra')])['accepted'])
    def test_timeout_is_not_waived(self):self.assertFalse(self.evaluate(rc='TIMEOUT')['accepted'])
    def test_crash_is_not_waived(self):self.assertFalse(self.evaluate(rc=3221225477)['accepted'])
    def test_zero_exit_with_failure_report_is_rejected(self):self.assertFalse(self.evaluate(rc=0)['accepted'])
    def test_hero_violation_is_not_waived(self):self.assertFalse(self.evaluate(hero_violations=1)['accepted'])
    def test_report_error_is_not_waived(self):self.assertFalse(self.evaluate(report_error='truncated report')['accepted'])
    def test_malformed_report_is_rejected(self):self.assertFalse(self.evaluate(rows=[{}])['accepted'])

    def test_skipping_a_waived_case_is_rejected(self):
        self.row.update(outcome='SKIP',detail='skip');self.assertFalse(self.evaluate(rc=0)['accepted'])

    def test_invalid_policy_cannot_broaden_the_waiver(self):
        variants=[dict(self.case,id='test_pvp_*.Case.test_any'),dict(self.case,outcome='PASS'),dict(self.case,detail_sha256='')]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json'
            for case in variants:
                path.write_text(json.dumps(dict(schema_version=1,status='temporary',cases=[case])),encoding='utf-8')
                with self.assertRaises(ValueError):load_waivers(path)
            path.write_text(json.dumps(dict(schema_version=1,status='temporary',cases=[self.case,self.case])),encoding='utf-8')
            with self.assertRaises(ValueError):load_waivers(path)


class SchedulingTests(unittest.TestCase):
    def test_both_physical_and_commit_headroom_limit_dispatch(self):
        for snapshot in [dict(physical_available=16000*MIB,commit_available=2000*MIB),dict(physical_available=2000*MIB,commit_available=16000*MIB)]:
            self.assertFalse(can_start(snapshot,[],1536*MIB,1024*MIB))

    def test_running_worker_future_growth_is_reserved(self):
        snapshot=dict(physical_available=3800*MIB,commit_available=3800*MIB)
        self.assertFalse(can_start(snapshot,[0],1536*MIB,1024*MIB))
        self.assertTrue(can_start(snapshot,[1024*MIB],1536*MIB,1024*MIB))

    def test_unknown_memory_permits_only_one_worker(self):
        self.assertTrue(can_start(None,[],1536*MIB,1024*MIB))
        self.assertFalse(can_start(None,[0],1536*MIB,1024*MIB))

    def test_available_memory_runs_two_workers_at_once(self):
        barrier=threading.Barrier(2);events=[]
        def work(name):barrier.wait(timeout=5);return name
        rows,summary=run_modules(['a','b','c','d'],work,2,1536,1024,lambda:{},events.append,
                                 probe=lambda:dict(physical_available=8192*MIB,commit_available=8192*MIB))
        self.assertEqual(rows,['a','b','c','d']);self.assertEqual(summary['peak_workers'],2)

    def test_unknown_memory_scheduler_falls_back_to_serial(self):
        rows,summary=run_modules(['a','b'],lambda name:name,4,1536,1024,lambda:{},lambda row:None,probe=lambda:None)
        self.assertEqual(rows,['a','b']);self.assertEqual(summary['peak_workers'],1)

    def test_actual_host_memory_can_be_read(self):
        snapshot=memory_snapshot()
        if os.name=='nt':
            self.assertIsNotNone(snapshot);self.assertGreater(snapshot['physical_available'],0);self.assertGreater(snapshot['commit_available'],0)

    def test_parallel_fixture_writes_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=root/'base';(base/'tests').mkdir(parents=True)
            (base/'input.json').write_text('{}',encoding='utf-8')
            a=clone_fixture(base,root/'a');b=clone_fixture(base,root/'b')
            (a/'tests/result.json').write_text('private',encoding='utf-8')
            self.assertFalse((base/'tests/result.json').exists());self.assertFalse((b/'tests/result.json').exists())
            self.assertEqual((b/'input.json').read_text('utf-8'),'{}')

if __name__=='__main__':unittest.main(verbosity=2)
