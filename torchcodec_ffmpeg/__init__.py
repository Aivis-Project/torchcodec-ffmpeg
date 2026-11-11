"""FFmpeg shared libraries for TorchCodec.

Call install() before importing TorchCodec:

    import torchcodec_ffmpeg

    torchcodec_ffmpeg.install()

    from torchcodec.decoders import VideoDecoder
"""

import ctypes
import functools
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

__all__ = ["install"]

# The bundled FFmpeg, libheif and their dependencies, with the file names they
# were built with
LIBRARY_DIR = Path(__file__).parent / "lib"

# The libraries TorchCodec links against, dependencies first: FFmpeg's, and
# libheif for TorchCodec's HEIC decoder, which decodes HEVC with libavcodec
_LIBRARIES = (
    "avutil",
    "swresample",
    "swscale",
    "avcodec",
    "avformat",
    "avfilter",
    "avdevice",
    "heif",
)

# The major version of the bundled FFmpeg, which is the version of this package
_FFMPEG_MAJOR_VERSION = 8

# Keeps the loaded libraries (and on Windows the DLL directory) alive
_loaded: list[object] = []


def _library_path(name: str) -> Path:
    if sys.platform == "win32":
        # avcodec-62.dll and so on, and heif.dll without a version
        pattern = f"{name}*.dll"
    elif sys.platform == "darwin":
        pattern = f"lib{name}.*.dylib"
    else:
        pattern = f"lib{name}.so.*"
    matches = sorted(LIBRARY_DIR.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {pattern} in {LIBRARY_DIR}, found {len(matches)}"
        )
    return matches[0]


def _prefer_bundled_ffmpeg(module: ModuleType) -> None:
    # TorchCodec 0.16 and later try the libraries for each FFmpeg major
    # version from 9 down in load_core_libraries(), so an FFmpeg 9 on the
    # system (Homebrew's on macOS, the distribution's on Linux) would be used
    # instead of the bundled one. Try the libraries for the bundled FFmpeg
    # first, and TorchCodec's own order if they fail to load. TorchCodec 0.15
    # and older try FFmpeg 8 first and have no load_core_libraries().
    original = getattr(module, "load_core_libraries", None)
    if original is None:
        return

    @functools.cache
    def load_core_libraries() -> tuple[int, str]:
        try:
            core_library_path = module._get_extension_path(
                f"libtorchcodec_core{_FFMPEG_MAJOR_VERSION}"
            )
            module.torch.ops.load_library(core_library_path)
            module.torch.ops.load_library(
                module._get_extension_path(
                    f"libtorchcodec_custom_ops{_FFMPEG_MAJOR_VERSION}"
                )
            )
        except Exception:
            return original()
        return (_FFMPEG_MAJOR_VERSION, core_library_path)

    setattr(module, "load_core_libraries", load_core_libraries)


class _LoaderPreferringBundledFFmpeg(importlib.abc.Loader):
    """Runs a module with its own loader, then _prefer_bundled_ffmpeg()."""

    def __init__(self, loader: importlib.abc.Loader) -> None:
        self._loader = loader

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        return self._loader.create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        self._loader.exec_module(module)
        _prefer_bundled_ffmpeg(module)


class _FinderPreferringBundledFFmpeg(importlib.abc.MetaPathFinder):
    """Wraps the loader of the TorchCodec module that loads FFmpeg.

    The module is changed right after it runs, before torchcodec._core.ops
    imports load_core_libraries() from it when TorchCodec is imported.
    """

    _MODULE = "torchcodec._internally_replaced_utils"

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname != self._MODULE:
            return None
        # Find the module with the other finders, once
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(fullname)
        if spec is not None and spec.loader is not None:
            spec.loader = _LoaderPreferringBundledFFmpeg(spec.loader)
        return spec


def install() -> None:
    """Make TorchCodec use the bundled FFmpeg and libheif.

    TorchCodec's native libraries depend on FFmpeg's libraries and libheif by
    name (libavcodec.so.62, libheif.so.1 and so on) and leave it to the
    operating system to find them. This loads the bundled libraries into the
    process first, so that the operating system resolves those names to them,
    and makes TorchCodec try its libraries for the bundled FFmpeg first.

    Call it before importing TorchCodec. Calling it again does nothing.
    """
    if _loaded:
        return
    if "torchcodec" in sys.modules:
        raise RuntimeError(
            "torchcodec_ffmpeg.install() must be called before torchcodec is imported"
        )

    loaded: list[object] = []
    if sys.platform == "win32":
        # Lets Windows find the bundled DLLs that FFmpeg's DLLs depend on
        loaded.append(os.add_dll_directory(str(LIBRARY_DIR)))

    # RTLD_GLOBAL makes the libraries' symbols available to TorchCodec, which
    # is loaded later. On Linux and macOS the libraries find their own
    # dependencies through an rpath relative to their directory.
    for name in _LIBRARIES:
        loaded.append(ctypes.CDLL(str(_library_path(name)), mode=ctypes.RTLD_GLOBAL))
    sys.meta_path.insert(0, _FinderPreferringBundledFFmpeg())
    _loaded.extend(loaded)
