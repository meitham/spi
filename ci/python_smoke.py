"""Exercise generated extensions, conversions and Python class delegation."""
import argparse
import datetime
import os
from pathlib import Path
import sys
import filecmp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--abi', required=True)
    parser.add_argument('--python-tag', required=True)
    parser.add_argument('--thread-tests', action='store_true')
    parser.add_argument('--require-free-threaded', action='store_true')
    args = parser.parse_args()
    gil_before = getattr(sys, '_is_gil_enabled', lambda: True)()
    if args.require_free_threaded:
        assert not gil_before, 'Expected a free-threaded interpreter with the GIL disabled'
    root = args.root.resolve()
    initial_directory = os.getcwd()

    def import_from(directory, module):
        sys.path.insert(0, str(directory))
        result = __import__(module)
        assert os.getcwd() == initial_directory, 'Import changed the working directory'
        print('PASS import', module, flush=True)
        return result

    spi = import_from(root / 'replay' / args.abi / ('py' + args.python_tag), 'spi_replay')
    values = {
        'integer': (42, 'INT'), 'float': (3.125, 'DOUBLE'),
        'boolean': (True, 'BOOL'), 'string': ('hello world', 'STRING'),
        'date': (datetime.date(2024, 2, 29), 'DATE'),
        'datetime': (datetime.datetime(2024, 2, 29, 12, 34, 56), 'DATETIME'),
    }
    sample = {name: value for name, (value, _) in values.items()}
    assert set(spi.MapFieldNames(sample)) == set(values)
    for name, (expected, expected_type) in values.items():
        actual, value_type = spi.MapGetValue(sample, name)
        assert actual == expected, (name, actual, expected)
        assert type(actual) is type(expected), (name, type(actual), type(expected))
        assert value_type == expected_type, (name, value_type, expected_type)
        print('PASS roundtrip', name, flush=True)
    original = spi.TestGenerator()
    restored = spi.Object.from_string(original.to_string())
    assert isinstance(restored, spi.TestGenerator), type(restored)
    assert restored.to_dict(True) == {}
    print('PASS Python subclass serialization', flush=True)
    spdoc = import_from(root / 'svo/spdoc/bin' / args.abi / ('py' + args.python_tag), 'spdoc')
    assert spi.Object is spdoc.Object, 'Extensions loaded separate SPI runtimes'
    if args.thread_tests:
        from python_threads import run
        run(spi, spdoc, args.python_tag)
    assert getattr(sys, '_is_gil_enabled', lambda: True)() == gil_before, 'Import enabled the GIL'
    spdoc = import_from(root / 'svo/spdoc/bin' / args.abi / ('py' + args.python_tag), 'spdoc')
    test_svo = str(root / 'test/config/test.svo')

    svc = spdoc.Service.from_file(test_svo)
    print('PASS read service object', test_svo)

    print("Summary of service object:\n")
    print("\n".join(svc.Summary(True)))
    print("\n")

    print('PASS summarize service object', test_svo)

    spi_replay = spi

    ifn = str(root / 'ci/a.log')
    ofn = str(root / 'test-results/a.out')
    baseline = str(root / 'ci/a.out')

    replayLog = spi_replay.ReplayLog.Read(ifn)
    generator = spi_replay.TestGenerator(ofn)
    replayLog.generateCode(generator)
    del generator
    
    assert filecmp.cmp(ofn, baseline, shallow=False)
    print('PASS spi_replay.generateCode')

    print('ALL PYTHON CHECKS PASSED:', sys.version, flush=True)


if __name__ == '__main__':
    main()
