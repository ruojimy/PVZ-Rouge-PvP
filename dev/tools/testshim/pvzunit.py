"""unittest replacement for the C++ build of the old test suite.

The old tests (next-pvp71/tests/test_pvp_*.py) are translated unchanged by tools/pvp2cpp.py; `import unittest`
resolves here. Only the assertion / fixture surface is provided; semantics follow CPython 3.8 unittest
(messages are simplified). The runner lives in C++ (src/cpptests/runner.cpp): it creates one instance per test
method, then calls setUp / the test / tearDown / doCleanups and classifies the outcome.
"""
import math
import re


class SkipTest(Exception):
    pass


class _AssertRaisesContext:
    def __init__(self, expected, test, regex=None):
        self.expected = expected
        self.test = test
        self.regex = regex
        self.exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            raise AssertionError('%s not raised' % (getattr(self.expected, '__name__', self.expected),))
        if not _exc_matches(exc_value, self.expected):
            return False
        self.exception = exc_value
        if self.regex is not None and not re.search(self.regex, str(exc_value)):
            raise AssertionError('"%s" does not match "%s"' % (self.regex, exc_value))
        return True


def _exc_matches(exc, expected):
    if isinstance(expected, tuple):
        for item in expected:
            if _exc_matches(exc, item):
                return True
        return False
    return isinstance(exc, expected)


class _SubTest:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        return False


def _fmt(msg, default):
    return default if msg is None else '%s : %s' % (default, msg)


class TestCase:
    maxDiff = 640
    longMessage = True

    def __init__(self, methodName='runTest'):
        self._testMethodName = methodName
        self._cleanups = []

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def id(self):
        return self._testMethodName

    def addCleanup(self, function, *args, **kwargs):
        self._cleanups.append((function, args, kwargs))

    def doCleanups(self):
        while self._cleanups:
            function, args, kwargs = self._cleanups.pop()
            function(*args, **kwargs)

    def skipTest(self, reason):
        raise SkipTest(reason)

    def subTest(self, msg=None, **params):
        return _SubTest()

    def fail(self, msg=None):
        raise AssertionError(msg)

    # ---- assertions
    def assertTrue(self, expr, msg=None):
        if not expr:
            raise AssertionError(_fmt(msg, '%r is not true' % (expr,)))

    def assertFalse(self, expr, msg=None):
        if expr:
            raise AssertionError(_fmt(msg, '%r is not false' % (expr,)))

    def assertEqual(self, first, second, msg=None):
        if not first == second:
            raise AssertionError(_fmt(msg, '%r != %r' % (first, second)))

    def assertNotEqual(self, first, second, msg=None):
        if not first != second:
            raise AssertionError(_fmt(msg, '%r == %r' % (first, second)))

    def assertIs(self, first, second, msg=None):
        if first is not second:
            raise AssertionError(_fmt(msg, '%r is not %r' % (first, second)))

    def assertIsNot(self, first, second, msg=None):
        if first is second:
            raise AssertionError(_fmt(msg, 'unexpectedly identical: %r' % (first,)))

    def assertIsNone(self, obj, msg=None):
        if obj is not None:
            raise AssertionError(_fmt(msg, '%r is not None' % (obj,)))

    def assertIsNotNone(self, obj, msg=None):
        if obj is None:
            raise AssertionError(_fmt(msg, 'unexpectedly None'))

    def assertIn(self, member, container, msg=None):
        if member not in container:
            raise AssertionError(_fmt(msg, '%r not found in %r' % (member, container)))

    def assertNotIn(self, member, container, msg=None):
        if member in container:
            raise AssertionError(_fmt(msg, '%r unexpectedly found in %r' % (member, container)))

    def assertIsInstance(self, obj, cls, msg=None):
        if not isinstance(obj, cls):
            raise AssertionError(_fmt(msg, '%r is not an instance of %r' % (obj, cls)))

    def assertNotIsInstance(self, obj, cls, msg=None):
        if isinstance(obj, cls):
            raise AssertionError(_fmt(msg, '%r is an instance of %r' % (obj, cls)))

    def assertGreater(self, a, b, msg=None):
        if not a > b:
            raise AssertionError(_fmt(msg, '%r not greater than %r' % (a, b)))

    def assertGreaterEqual(self, a, b, msg=None):
        if not a >= b:
            raise AssertionError(_fmt(msg, '%r not greater than or equal to %r' % (a, b)))

    def assertLess(self, a, b, msg=None):
        if not a < b:
            raise AssertionError(_fmt(msg, '%r not less than %r' % (a, b)))

    def assertLessEqual(self, a, b, msg=None):
        if not a <= b:
            raise AssertionError(_fmt(msg, '%r not less than or equal to %r' % (a, b)))

    def assertAlmostEqual(self, first, second, places=None, msg=None, delta=None):
        if first == second:
            return
        diff = abs(first - second)
        if delta is not None:
            if diff <= delta:
                return
            raise AssertionError(_fmt(msg, '%r != %r within %r delta (%r difference)' % (first, second, delta, diff)))
        if places is None:
            places = 7
        if round(diff, places) == 0:
            return
        raise AssertionError(_fmt(msg, '%r != %r within %r places (%r difference)' % (first, second, places, diff)))

    def assertNotAlmostEqual(self, first, second, places=None, msg=None, delta=None):
        diff = abs(first - second)
        if delta is not None:
            if not (first == second) and diff > delta:
                return
            raise AssertionError(_fmt(msg, '%r == %r within %r delta' % (first, second, delta)))
        if places is None:
            places = 7
        if not (first == second) and round(diff, places) != 0:
            return
        raise AssertionError(_fmt(msg, '%r == %r within %r places' % (first, second, places)))

    def assertCountEqual(self, first, second, msg=None):
        a = list(first)
        b = list(second)
        for item in a:
            if item in b:
                b.remove(item)
            else:
                raise AssertionError(_fmt(msg, 'element counts differ: %r vs %r' % (first, second)))
        if b:
            raise AssertionError(_fmt(msg, 'element counts differ: %r vs %r' % (first, second)))

    def assertListEqual(self, first, second, msg=None):
        self.assertIsInstance(first, list, msg)
        self.assertIsInstance(second, list, msg)
        self.assertEqual(first, second, msg)

    def assertTupleEqual(self, first, second, msg=None):
        self.assertIsInstance(first, tuple, msg)
        self.assertIsInstance(second, tuple, msg)
        self.assertEqual(first, second, msg)

    def assertDictEqual(self, first, second, msg=None):
        self.assertIsInstance(first, dict, msg)
        self.assertIsInstance(second, dict, msg)
        self.assertEqual(first, second, msg)

    def assertSetEqual(self, first, second, msg=None):
        self.assertEqual(set(first), set(second), msg)

    def assertSequenceEqual(self, first, second, msg=None, seq_type=None):
        if seq_type is not None:
            self.assertIsInstance(first, seq_type, msg)
            self.assertIsInstance(second, seq_type, msg)
        self.assertEqual(list(first), list(second), msg)

    def assertRegex(self, text, regex, msg=None):
        import re
        if not re.search(regex, text):
            raise AssertionError(_fmt(msg, "Regex didn't match: %r not found in %r" % (regex, text)))

    def assertNotRegex(self, text, regex, msg=None):
        import re
        if re.search(regex, text):
            raise AssertionError(_fmt(msg, 'Regex matched: %r in %r' % (regex, text)))

    def assertRaises(self, expected, *args, **kwargs):
        context = _AssertRaisesContext(expected, self)
        if not args:
            return context
        function = args[0]
        try:
            function(*args[1:], **kwargs)
        except Exception as exc:
            if _exc_matches(exc, expected):
                context.exception = exc
                return context
            raise
        raise AssertionError('%s not raised by %r' % (getattr(expected, '__name__', expected), function))

    def assertRaisesRegex(self, expected, regex, *args, **kwargs):
        context = _AssertRaisesContext(expected, self, regex)
        if not args:
            return context
        function = args[0]
        try:
            function(*args[1:], **kwargs)
        except Exception as exc:
            if not _exc_matches(exc, expected):
                raise
            import re
            if not re.search(regex, str(exc)):
                raise AssertionError('"%s" does not match "%s"' % (regex, exc))
            context.exception = exc
            return context
        raise AssertionError('%s not raised' % (getattr(expected, '__name__', expected),))

    # deprecated aliases still used by older tests
    def assertEquals(self, first, second, msg=None):
        self.assertEqual(first, second, msg)

    def failUnless(self, expr, msg=None):
        self.assertTrue(expr, msg)


def skip(reason):
    def decorator(item):
        item.__unittest_skip__ = True
        item.__unittest_skip_why__ = reason
        return item
    return decorator


def skipIf(condition, reason):
    return skip(reason) if condition else (lambda item: item)


def skipUnless(condition, reason):
    return skip(reason) if not condition else (lambda item: item)


def main(*args, **kwargs):
    pass
