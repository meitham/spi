"""
Defines the simplified types arising from the first phase of the
code generation process.

This is designed to provide enough information for all phase two
code generation.

You no longer need to know anything about the inner library or how
data is translated into the inner library.
"""

import os
_dll_dir = (os.add_dll_directory(os.path.dirname(os.path.abspath(__file__)))
            if hasattr(os, 'add_dll_directory') else None)
try:
    if __package__:
        from .py_spdoc import *
    else:
        from py_spdoc import *
finally:
    if _dll_dir is not None: _dll_dir.close()
del os, _dll_dir
