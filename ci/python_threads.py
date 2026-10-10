"""Regression tests for the generated Python bridge, including concurrent entry."""
from concurrent.futures import ThreadPoolExecutor
import copy
import datetime
import gc
import importlib.util
from pathlib import Path
import os
import tempfile
import subprocess
import runpy
import sys
import threading
import time
import unittest
import weakref


class BridgeTests(unittest.TestCase):
    workers = 8
    iterations = 100

    def concurrent(self, operation):
        barrier = threading.Barrier(self.workers)

        def worker(number):
            barrier.wait(timeout=10)
            for iteration in range(self.iterations):
                operation(number, iteration)

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = [pool.submit(worker, number) for number in range(self.workers)]
            for future in futures:
                future.result(timeout=60)

    def test_constructors_and_conversions(self):
        def check(worker, iteration):
            value = worker * self.iterations + iteration
            obj = self.spdoc.IntConstant(value=value)
            self.assertEqual(obj.value, value)
            date = datetime.date(2024, 2, 29)
            self.assertEqual(self.spdoc.DateConstant(date).value, date)
            self.assertEqual(self.spi.MapGetValue({'x': [value, date]}, 'x')[0], [value, date])
        self.concurrent(check)

    def test_object_make(self):
        # ObjectMake initializes the native common-service type registry.
        # Isolate it from tests that register additional Python classes.
        directory = str(Path(importlib.util.find_spec('spdoc').origin).parent)
        code = """
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import spdoc
gil_before = getattr(sys, '_is_gil_enabled', lambda: True)()
barrier = threading.Barrier(8)
def check(worker):
    barrier.wait(timeout=10)
    for iteration in range(100):
        value = worker * 100 + iteration
        obj = spdoc.object_make('IntConstant', ['value'], value)
        assert obj.value == value
with ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(check, range(8)))
assert getattr(sys, '_is_gil_enabled', lambda: True)() == gil_before
"""
        env = dict(os.environ, PYTHONPATH=directory)
        result = subprocess.run([sys.executable, '-c', code], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shared_object_serialization_and_copy(self):
        # The legacy full C API string conversion accepts one-byte strings only.
        value = 'shared ☃' if self.python_tag in ('3-abi', '3-abi3t') else 'shared value'
        obj = self.spdoc.StringConstant(value)
        text = obj.to_string()
        digest = obj.sha_256()

        def check(worker, iteration):
            self.assertEqual(obj.to_string(), text)
            self.assertEqual(obj.sha_256(), digest)
            self.assertEqual(copy.copy(obj).value, obj.value)
            self.assertEqual(copy.deepcopy(obj).value, obj.value)
            self.assertEqual(self.spi.Object.from_string(text).value, obj.value)
        self.concurrent(check)

    def test_shared_object_reinitialization(self):
        obj = self.spdoc.IntConstant(0)

        def check(worker, iteration):
            obj.__init__(worker)
            self.assertIn(obj.value, range(self.workers))
        self.concurrent(check)

    def test_shared_metadata(self):
        obj = self.spdoc.IntConstant(1)

        def check(worker, iteration):
            obj.set_meta_data('worker_' + str(worker), iteration)
            self.assertEqual(obj.value, 1)
        self.concurrent(check)
        for worker in range(self.workers):
            self.assertEqual(self.spi.MapGetValue(obj.meta_data, 'worker_' + str(worker))[0],
                             self.iterations - 1)

    def test_exceptions_do_not_poison_other_threads(self):
        def check(worker, iteration):
            with self.assertRaises(Exception):
                self.spdoc.IntConstant(value=object())
            self.assertEqual(self.spdoc.IntConstant(worker).value, worker)
        self.concurrent(check)

    def test_delegate_callbacks_reenter_and_release_gil(self):
        spi = self.spi

        class ReentrantGenerator(spi.TestGenerator):
            def to_dict(self, publicOnly):
                # Other threads must be able to run while this callback sleeps.
                time.sleep(0.0001)
                self.check_value = spi.MapGetValue({'x': 42}, 'x')[0]
                return {}

            @staticmethod
            def from_dict(values):
                return ReentrantGenerator()

        spi.Object.register_class(ReentrantGenerator)

        def check(worker, iteration):
            obj = ReentrantGenerator()
            restored = spi.Object.from_string(obj.to_string())
            self.assertIsInstance(restored, ReentrantGenerator)
            self.assertEqual(obj.check_value, 42)
        self.concurrent(check)

    def test_slotted_subclass_storage_and_lifetime(self):
        class SlottedGenerator(self.spi.TestGenerator):
            __slots__ = ('marker',)

        def check(worker, iteration):
            obj = SlottedGenerator()
            obj.marker = worker
            self.assertEqual(obj.typename, 'py.SlottedGenerator')
            self.assertEqual(obj.marker, worker)
            ref = weakref.ref(obj)
            del obj
            # Deferred reference counting may wait for collection on 3.15t.
            gc.collect()
            self.assertIsNone(ref())
        self.concurrent(check)

    def test_dictionary_snapshot_during_callback(self):
        if self.python_tag not in ('3-abi', '3-abi3t'):
            self.skipTest('The full C API reads date fields without Python callbacks')
        source = {}

        class MutatingDate(datetime.date):
            def toordinal(self):
                source.clear()
                return super().toordinal()

        source.update(date=MutatingDate(2024, 2, 29), sentinel=42)
        self.assertEqual(set(self.spi.MapFieldNames(source)), {'date', 'sentinel'})
        self.assertEqual(source, {})

    def test_list_snapshot_during_callback(self):
        if self.python_tag not in ('3-abi', '3-abi3t'):
            self.skipTest('The full C API reads date fields without Python callbacks')
        source = []

        class MutatingDate(datetime.date):
            def toordinal(self):
                source.clear()
                return super().toordinal()

        source.extend([MutatingDate(2024, 2, 29), 42])
        self.assertEqual(self.spi.MapGetValue({'x': source}, 'x')[0],
                         [datetime.date(2024, 2, 29), 42])
        self.assertEqual(source, [])

    def test_concurrently_mutated_python_containers(self):
        values = [1, 2, 3]
        mapping = {'x': values}
        stop = threading.Event()

        def mutate():
            while not stop.is_set():
                values[:] = [4, 5]
                mapping['extra'] = 7
                values[:] = [1, 2, 3]
                mapping.pop('extra', None)

        thread = threading.Thread(target=mutate)
        thread.start()
        try:
            for iteration in range(1000):
                result = self.spi.MapGetValue(mapping, 'x')[0]
                self.assertIn(result, ([1, 2, 3], [4, 5]))
        finally:
            stop.set()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())

    def test_timing_counts(self):
        self.spi.clear_timings()
        self.spi.start_timing()
        try:
            self.concurrent(lambda worker, iteration: self.spi.MapGetValue({'x': worker}, 'x'))
        finally:
            self.spi.stop_timing()
        names, counts, failures, durations = self.spi.get_timings()
        self.assertEqual(names, ['spi_replay.MapGetValue'])
        self.assertEqual(counts, [self.workers * self.iterations])
        self.assertEqual(failures, [0])
        self.assertGreaterEqual(durations[0], 0)

    def test_timing_state(self):
        def check(worker, iteration):
            self.spi.start_timing()
            self.spi.MapGetValue({'x': worker}, 'x')
            try:
                self.spi.get_timings()
            except Exception as error:
                self.assertEqual(str(error), 'No functions have been timed')
            self.spi.stop_timing()
            self.spi.clear_timings()
        self.concurrent(check)

    def test_concurrent_imports_preserve_working_directory(self):
        directories = [str(Path(importlib.util.find_spec(name).origin).parent)
                       for name in ('spi_replay', 'spdoc')]
        code = """
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
initial_directory = os.getcwd()
gil_before = getattr(sys, '_is_gil_enabled', lambda: True)()
barrier = threading.Barrier(2)
def load(name):
    barrier.wait(timeout=10)
    return __import__(name)
with ThreadPoolExecutor(max_workers=2) as pool:
    modules = list(pool.map(load, ['spi_replay', 'spdoc']))
assert modules[1].IntConstant(42).value == 42
assert os.getcwd() == initial_directory
assert getattr(sys, '_is_gil_enabled', lambda: True)() == gil_before
"""
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(directories))
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                                    env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_abi3t_module_reimport_rejected(self):
        if 'abi3t' not in self.python_tag:
            self.skipTest('Applies to multi-phase abi3t modules')
        directory = str(Path(importlib.util.find_spec('py_replay').origin).parent)
        code = """
import py_replay
import importlib
import sys
sys.modules.pop('py_replay')
try:
    importlib.import_module('py_replay')
except ImportError as error:
    assert 'once per process' in str(error), error
else:
    raise AssertionError('Second module instance was accepted')
"""
        result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_abi3t_subinterpreter_rejected(self):
        if 'abi3t' not in self.python_tag:
            self.skipTest('Applies to multi-phase abi3t modules')
        directory = str(Path(importlib.util.find_spec('py_replay').origin).parent)
        code = """
from concurrent import interpreters
import os
interpreter = interpreters.create()
try:
    try:
        interpreter.exec('import sys; sys.path.insert(0, ' + repr(os.getcwd()) + '); import py_replay')
    except interpreters.ExecutionFailed as error:
        assert 'subinterpreter' in str(error), error
    else:
        raise AssertionError('Subinterpreter import was accepted')
finally:
    interpreter.close()
"""
        result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def run(spi, spdoc, python_tag):
    BridgeTests.python_tag = python_tag
    BridgeTests.spi = spi
    BridgeTests.spdoc = spdoc
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BridgeTests)
    regression = runpy.run_path(str(Path(__file__).resolve().parents[1]
                                   / 'replay/python/test/test-class-names.py'))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(regression['ClassNameTests']))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError('Python bridge regression tests failed')
