# Collect the bundled FFmpeg and libheif. PyInstaller only picks up shared
# libraries named like lib*.so, so the versioned names on Linux
# (libavcodec.so.62 and so on) are listed here. They are collected as binaries,
# so that PyInstaller signs them on macOS.

from collections.abc import Iterable
from pathlib import Path

import PyInstaller.depend.bindepend as bindepend

from torchcodec_ffmpeg import LIBRARY_DIR

binaries = [
    (str(path), "torchcodec_ffmpeg/lib")
    for path in sorted(LIBRARY_DIR.iterdir())
    if path.is_file()
]

# PyInstaller resolves the libraries a binary depends on by looking where the
# binary itself would at run time. TorchCodec's libraries look in
# /opt/homebrew/opt/ffmpeg/lib on macOS and in the system's library directories
# on Linux, so PyInstaller would bundle the FFmpeg or libheif installed on the
# build machine, and the libraries they depend on, next to the bundled ones.
# Resolve the bundled libraries to the bundled files instead, which is where
# they are loaded from at run time.
#
# get_imports() is not a public API of PyInstaller. tests/test_pyinstaller.py
# checks that nothing from the build machine is bundled because of TorchCodec,
# with the latest PyInstaller.
_bundled = {Path(source).name.lower(): source for source, _ in binaries}
_get_imports = bindepend.get_imports


def _names(imports: Iterable[tuple[str, str | None]]) -> set[str]:
    return {Path(name).name.lower() for name, _ in imports}


def get_imports_preferring_bundled_ffmpeg(
    filename: str, search_paths: list[str] | None = None
) -> set[tuple[str, str | None]]:
    imports = _get_imports(filename, search_paths)
    # On Linux, PyInstaller lists the dependencies with ldd, which also lists
    # the dependencies of the dependencies. Those that come only with a copy
    # found on the build machine (libde265 and libaom for a system libheif) are
    # left out, and the bundled copy is analyzed for its own.
    only_elsewhere: set[str] = set()
    for name, path in imports:
        bundled = _bundled.get(Path(name).name.lower())
        if bundled is None or path is None:
            continue
        if Path(path).resolve() != Path(bundled).resolve():
            only_elsewhere |= _names(_get_imports(path, search_paths)) - _names(
                _get_imports(bundled, search_paths)
            )
    # x265 links against libmvec on Linux x86_64. It is part of glibc, like
    # libm, so the one of the system the app runs on is used, as the upstream
    # build does by excluding it from auditwheel.
    if Path(filename).resolve().parent == LIBRARY_DIR.resolve():
        only_elsewhere.add("libmvec.so.1")
    return {
        (name, _bundled.get(Path(name).name.lower(), path))
        for name, path in imports
        if Path(name).name.lower() not in only_elsewhere
    }


# The hook runs once for each Analysis in a spec file, so wrap get_imports()
# only once
if _get_imports.__name__ != get_imports_preferring_bundled_ffmpeg.__name__:
    bindepend.get_imports = get_imports_preferring_bundled_ffmpeg
