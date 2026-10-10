#
# specific information for running python scripts
#

G_PY_MAJOR_VERSION=$(shell $(G_PYTHON) -c "import sys; print(sys.version_info.major)")
G_PY_MINOR_VERSION=$(shell $(G_PYTHON) -c "import sys; print(sys.version_info.minor)")

info::
	@echo "G_PYTHON=$(G_PYTHON)"
	@echo "G_PY_MAJOR_VERSION=$(G_PY_MAJOR_VERSION)"
	@echo "G_PY_MINOR_VERSION=$(G_PY_MINOR_VERSION)"


ifeq ($(G_PY_VERSION),3-abi)
G_PY_LIMITED_API_CFLAGS=-DPy_LIMITED_API=0x030C0000
G_PYTHON_INCLUDES=-I$(shell $(G_PYTHON) -c "import sysconfig; print(sysconfig.get_path('include'))")
endif

# The free-threaded Stable ABI also runs on regular CPython 3.15+.
ifeq ($(G_PY_VERSION),3-abi3t)
G_PY_LIMITED_API_CFLAGS=-DPy_LIMITED_API=0x030F0000 -DPy_TARGET_ABI3T=0x030F0000
G_PYTHON_INCLUDES=-I$(shell $(G_PYTHON) -c "import sysconfig; print(sysconfig.get_path('include'))")
ifeq ($(G_PLATFORM),win32)
G_PYTHON_LIBS=$(shell $(G_PYTHON) -c "import sys; print(sys.base_prefix.replace(chr(92), '/'))")/libs/python3t.lib
endif
endif
