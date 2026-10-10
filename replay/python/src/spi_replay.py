"""
No description
"""

import os
_dll_dir = (os.add_dll_directory(os.path.dirname(os.path.abspath(__file__)))
            if hasattr(os, 'add_dll_directory') else None)
try:
    if __package__:
        from .py_replay import *
    else:
        from py_replay import *
finally:
    if _dll_dir is not None: _dll_dir.close()
del os, _dll_dir


import sys
class TestGenerator(ReplayCodeGenerator):
    def __init__(self, ofn=None):
        self.ofn = ofn
        self.fp = None
    def __del__(self):
        if self.fp:
            sys.stdout.write("Closing %s\n" % self.ofn)
            self.fp.close()
            self.fp = None
    def _write(self, txt):
        if self.ofn and self.fp is None:
            sys.stdout.write("Opening %s\n" % self.ofn)
            self.fp = open(self.ofn, "w", newline='\n')
        fp = sys.stdout if self.fp is None else self.fp
        fp.write("%s\n" % txt)
        if not txt: fp.flush()
    def GenerateFunction(self, action):
        self._write("FUNCTION: %s" % MapClassName(action.inputs))
        self._write(action.to_string())
        self._write("")
    def GenerateObject(self, action):
        self._write("OBJECT: %s" % MapClassName(action.inputs))
        self._write(action.to_string())
        self._write("")
    def to_dict(self, publicOnly):
        dict = {}
        if self.ofn: dict["ofn"] = self.ofn
        return dict
    @staticmethod
    def from_dict(dict):
        ofn = dict.get("ofn", None)
        return TestGenerator(ofn = ofn)

# Object is automatically provided by py_spi_replay
Object.register_class(TestGenerator)


