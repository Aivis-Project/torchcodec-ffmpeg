# Collect TorchCodec's native libraries, which PyInstaller does not pick up on
# its own.
#
# TorchCodec ships one set of libraries for each FFmpeg major version
# (libtorchcodec_core4 to libtorchcodec_core9 and so on) and loads the first
# set that works. Only the set that works with the bundled FFmpeg is collected.
# Collecting the others would make PyInstaller look for their FFmpeg on the
# build machine, and bundle whatever FFmpeg it finds there.

import re
from pathlib import Path

from PyInstaller.depend.bindepend import get_imports
from PyInstaller.log import logger
from PyInstaller.utils.hooks import PY_DYLIB_PATTERNS, collect_dynamic_libs

from torchcodec_ffmpeg import LIBRARY_DIR

# Matches the file names of the FFmpeg libraries TorchCodec links against:
# libavcodec.so.62 on Linux, libavcodec.62.dylib on macOS and avcodec-62.dll on
# Windows
_FFMPEG_LIBRARY = re.compile(
    r"^(lib)?(avutil|swresample|swscale|avcodec|avformat|avfilter|avdevice)[.-]",
    re.IGNORECASE,
)

bundled = {path.name.lower() for path in LIBRARY_DIR.iterdir()}
# TorchCodec's pybind module is libtorchcodec_pybind_ops.pyd on Windows, which
# the default patterns miss
libraries = collect_dynamic_libs(
    "torchcodec", search_patterns=[*PY_DYLIB_PATTERNS, "*.pyd"]
)
imports = {
    Path(source).name.lower(): {
        Path(name).name.lower() for name, _ in get_imports(source)
    }
    for source, _ in libraries
}

# Leave out the libraries that need an FFmpeg other than the bundled one, and
# then the libraries that need a library left out (libtorchcodec_custom_ops8
# needs libtorchcodec_core8), until nothing changes
left_out: set[str] = set()
changed = True
while changed:
    changed = False
    for name, names in imports.items():
        if name in left_out:
            continue
        if any(
            (_FFMPEG_LIBRARY.match(dependency) and dependency not in bundled)
            or dependency in left_out
            for dependency in names
        ):
            left_out.add(name)
            changed = True

binaries = [
    (source, destination)
    for source, destination in libraries
    if Path(source).name.lower() not in left_out
]

if not any(
    _FFMPEG_LIBRARY.match(dependency)
    for name, names in imports.items()
    if name not in left_out
    for dependency in names
):
    logger.warning(
        "torchcodec-ffmpeg: none of TorchCodec's libraries work with the "
        "bundled FFmpeg, so TorchCodec will not be able to use FFmpeg"
    )
