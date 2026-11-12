"""Reject truncated and empty recordings before declaring parity."""
import contextlib,importlib.util,io,json,sys,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("oracle_diff_contract_target",Path(__file__).parent/"oracle_diff.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class Capture(io.StringIO):
    def reconfigure(self, **kwargs): pass

class OracleContract(unittest.TestCase):
    def run_diff(self,a,b):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for folder,rows in (("oracle",a),("oracle_cpp",b)):
                path=root/"extract"/folder;path.mkdir(parents=True)
                (path/"case.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
            old_root,old_argv=mod.ROOT,sys.argv
            mod.ROOT=root;sys.argv=["oracle_diff.py","case"]
            try:
                with contextlib.redirect_stdout(Capture()):return mod.main()
            finally:mod.ROOT=old_root;sys.argv=old_argv
    def test_empty_is_failure(self):self.assertEqual(self.run_diff([],[]),1)
    def test_cpp_truncation_is_failure(self):self.assertEqual(self.run_diff([{"t":1},{"t":2}],[{"t":1}]),1)
    def test_extra_cpp_ticks_are_failure(self):self.assertEqual(self.run_diff([{"t":1}],[{"t":1},{"t":2}]),1)
    def test_changed_value_is_failure(self):self.assertEqual(self.run_diff([{"t":1,"hp":10}],[{"t":1,"hp":9}]),1)
    def test_missing_key_is_failure(self):self.assertEqual(self.run_diff([{"t":1,"hp":10}],[{"t":1}]),1)
    def test_matching_nonempty_passes(self):self.assertEqual(self.run_diff([{"t":1}],[{"t":1}]),0)
if __name__=="__main__":unittest.main(verbosity=2)
