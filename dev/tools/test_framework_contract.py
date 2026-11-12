"""Independent CPython checks for the translated-test assertion adapter; no game imports."""
import importlib.util
import unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location("native_unittest_adapter", Path(__file__).parent / "testshim/pvzunit.py")
shim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shim)

class Contract(unittest.TestCase):
    def setUp(self):
        self.tc = shim.TestCase()

    def test_equal_rejects_wrong_value(self):
        with self.assertRaises(AssertionError): self.tc.assertEqual(1, 2)

    def test_list_rejects_tuple(self):
        with self.assertRaises(AssertionError): self.tc.assertListEqual([1], (1,))

    def test_tuple_rejects_list(self):
        with self.assertRaises(AssertionError): self.tc.assertTupleEqual((1,), [1])

    def test_dict_requires_dict(self):
        with self.assertRaises(AssertionError): self.tc.assertDictEqual(1, 1)

    def test_sequence_honors_type(self):
        with self.assertRaises(AssertionError): self.tc.assertSequenceEqual((1,), (1,), seq_type=list)

    def test_sequence_accepts_equal_sequences(self):
        self.tc.assertSequenceEqual([1], (1,))

    def test_context_regex_uses_regex(self):
        with self.tc.assertRaisesRegex(ValueError, "^boom[0-9]+$"): raise ValueError("boom12")

    def test_raises_requires_exception(self):
        with self.assertRaises(AssertionError):
            with self.tc.assertRaises(ValueError): pass

    def test_raises_rejects_wrong_exception(self):
        with self.assertRaises(TypeError):
            with self.tc.assertRaises(ValueError): raise TypeError("bad")

    def test_skip_sets_unittest_metadata(self):
        @shim.skip("why")
        def test(): pass
        self.assertTrue(test.__unittest_skip__)
        self.assertEqual(test.__unittest_skip_why__, "why")

    def test_cleanup_is_lifo(self):
        seen=[]
        self.tc.addCleanup(seen.append, 1)
        self.tc.addCleanup(seen.append, 2)
        self.tc.doCleanups()
        self.assertEqual(seen,[2,1])

    def test_almost_equal_preserves_tolerance(self):
        self.tc.assertAlmostEqual(1, 1.001, delta=.01)
        with self.assertRaises(AssertionError): self.tc.assertAlmostEqual(1, 1.1, delta=.01)

if __name__ == "__main__": unittest.main(verbosity=2)
