# CI verification

`python ci/run.py` builds and runs the existing tests on Linux, Windows and
macOS. Linux needs GCC, make, libcurl and UUID development headers; macOS needs
Xcode command-line tools; Windows needs Visual Studio 2022 and its Windows SDK.
The Windows job uses the bundled Cygwin utilities and discovers compiler versions.
CI builds the version-specific Python 3.9 and 3.14 targets on each OS, and the
existing `3-abi` target with Python 3.12. The latter binaries are also tested
unchanged on Python 3.13 and 3.14. All targets run the bridge regression tests.
The opt-in `3-abi3t` target requires Python 3.15+ and does not replace those
older targets; its binaries cannot be loaded on older Python versions. The new
bridge lock is active only in abi3t builds; older targets retain GIL-based
synchronization.

The harness supplies the legacy tests' fixtures and directory layout, and a
local HTTP proxy answers the curl test's fixed URL. It runs each test separately
and uses `sh -e` so recursive make failures cannot be hidden. Build/test logs and
a JSON summary are written to `test-results/` and uploaded by GitHub Actions.

The optional `makeXLAddin` Office COM automation helper needs installed Excel
and is omitted. Native Excel bindings still build on Windows.

Use `--skip-build` to reuse existing libraries, `--jobs 2` to control concurrency,
and `--make-arg NAME=value` for site-specific build settings.

Stable ABI builds use `python ci/run.py --python-tag 3-abi` (Python 3.12+)
or `python ci/run.py --python-tag 3-abi3t` (Python 3.15+ headers). The latter
builds one binary for regular and free-threaded Python 3.15 and later. On Unix
its extension suffix is `.abi3t.so`; Windows links against `python3t.lib`.
Both targets regenerate the bindings and run the Python bridge regression tests.
The abi3t CI job also runs those same binaries with the GIL enabled and with a
regular interpreter, without rebuilding them. Import must not enable the GIL.
CI installs the official Python 3.15.0 final release, verifies its checksum and
version, and never falls back to a prerelease. Linux builds both interpreters
from source; Windows and macOS use the official binary distributions.

The abi3t Python bridge serializes SPI calls, object access, and destruction through
one recursive lock in the shared Python runtime library. Waiting for this lock
releases the Python thread state. Python callbacks can re-enter SPI on the same
thread and can release the GIL. A callback must not wait for another thread to
finish an SPI call: that thread would be waiting for the callback's lock.

This provides safe concurrent entry from Python, not parallel execution of SPI
operations. Direct C/C++ callers and background work inside wrapped libraries
still need their own synchronization. Individual calls are protected; a series
of calls (such as read/modify/write) is not a transaction. Mutable Python lists
and dictionaries are copied during conversion; nested containers are copied
when visited, not as one atomic snapshot of the entire object graph.

Generated abi3t modules explicitly reject subinterpreters and a second module
instance in the same process because SPI's service/type registries are global.
Rebuild the Python runtime and regenerate all bindings together when switching
ABI targets; do not mix older generated bindings with this runtime.
