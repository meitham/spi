#!/usr/bin/env python3
"""Install official Python 3.15.0 final runtimes on disposable CI runners."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

BASE = 'https://www.python.org/ftp/python/3.15.0/'


def download(root, name, sha256):
    path = root / name
    urllib.request.urlretrieve(BASE + name, path)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != sha256:
        raise RuntimeError(f'Checksum mismatch for {name}: {actual}')
    return path


def install(root):
    if sys.platform == 'win32':
        hashes = {
            'regular': ('', '6b1a3f885ce416cf3a68af203e62203664eb5224d8d0c1d2a1945fddec5c500b'),
            'threaded': ('t', 'ef22f32d3370a499273016d2233a964edc4e0cce7906a5ecfa3131c264518fcd'),
        }
        for mode, (suffix, checksum) in hashes.items():
            archive = download(root, f'python-3.15.0{suffix}-amd64.zip', checksum)
            with zipfile.ZipFile(archive) as package:
                package.extractall(root / mode)
        return {mode: root / mode / 'python.exe' for mode in hashes}
    if sys.platform == 'darwin':
        package = download(root, 'python-3.15.0-macos11.pkg',
                           '7c7e7eca61cbfa5f0c6f80cd594cddbfd492f4e8b3fb87e3d9fa1efebaec43ed')
        subprocess.run(['sudo', 'installer', '-pkg', str(package), '-target', '/'], check=True)
        frameworks = Path('/Library/Frameworks')
        return {
            'regular': frameworks / 'Python.framework/Versions/3.15/bin/python3.15',
            'threaded': frameworks / 'PythonT.framework/Versions/3.15/bin/python3.15t',
        }
    if sys.platform != 'linux':
        raise RuntimeError(f'Unsupported CI platform: {sys.platform}')
    archive = download(root, 'Python-3.15.0.tar.xz',
                       'ba4bed1ba346b916890b76d9e320451420aa69f6408997d33c66482eeae3d575')
    with tarfile.open(archive) as package:
        package.extractall(root, filter='data')
    runtimes = {}
    for mode, suffix in [('regular', ''), ('threaded', 't')]:
        prefix = root / mode
        build = root / ('build-' + mode)
        build.mkdir()
        command = [str(root / 'Python-3.15.0/configure'), f'--prefix={prefix}',
                   '--enable-shared', '--without-ensurepip', '--disable-test-modules',
                   'CFLAGS=-O1', f'LDFLAGS=-Wl,-rpath,{prefix}/lib']
        if suffix:
            command.append('--disable-gil')
        subprocess.run(command, cwd=build, check=True)
        subprocess.run(['make', '-j2'], cwd=build, check=True)
        subprocess.run(['make', 'install'], cwd=build, check=True)
        runtimes[mode] = prefix / 'bin' / ('python3.15' + suffix)
    return runtimes


def main():
    # macOS installation changes system frameworks; this helper is CI-only.
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Run this installer only on a disposable GitHub Actions runner')
    root = Path(os.environ['RUNNER_TEMP']) / 'spi-python315'
    root.mkdir()
    runtimes = install(root)
    for mode, executable in runtimes.items():
        subprocess.run([str(executable), '-c',
                        'import sys, sysconfig; print(sys.version); '
                        'assert sys.version_info == (3, 15, 0, "final", 0); '
                        f'assert bool(sysconfig.get_config_var("Py_GIL_DISABLED")) == {mode == "threaded"}; '
                        f'assert sys._is_gil_enabled() == {mode == "regular"}'], check=True)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for mode, executable in runtimes.items():
            output.write(f'{mode}={executable.as_posix()}\n')


if __name__ == '__main__':
    main()
