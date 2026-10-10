"""Run with the built spi_replay package on PYTHONPATH."""
import unittest

import spi_replay as spi


class AutomaticGenerator(spi.TestGenerator):
    pass


class ClassNameTests(unittest.TestCase):
    def test_explicit_registration(self):
        obj = spi.TestGenerator()
        self.assertEqual(obj.typename, 'py.TestGenerator')
        self.assertIsInstance(spi.Object.from_string(obj.to_string()), spi.TestGenerator)

    def test_automatic_registration(self):
        obj = AutomaticGenerator()
        self.assertEqual(obj.typename, 'py.AutomaticGenerator')


if __name__ == '__main__':
    unittest.main()
