"""Build the torchcodec-ffmpeg wheel around the FFmpeg built by scripts/build-ffmpeg.py.

cibuildwheel runs scripts/build-ffmpeg.py before the build (CIBW_BEFORE_BUILD),
which installs FFmpeg and its dependencies into the vendor directory below. The
build copies their shared libraries into torchcodec_ffmpeg/lib under the names
they are loaded by. On Linux and macOS each library gets an rpath to its own
directory, so that FFmpeg's libraries find their dependencies there.

The wheel contains no Python extension, so it works with any Python 3 version,
but it is specific to one platform: it is tagged py3-none-<platform>.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py

if sys.platform == "win32":
    VENDOR_DIR = Path("C:\\cibw\\vendor")
else:
    VENDOR_DIR = Path("/tmp/vendor")


# The FFmpeg libraries TorchCodec links against
FFMPEG_LIBRARIES = (
    "avcodec",
    "avdevice",
    "avfilter",
    "avformat",
    "avutil",
    "swresample",
    "swscale",
)


def patchelf(*args: str) -> str:
    return subprocess.run(
        ["patchelf", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def copy_linux_libraries(lib_dir: Path) -> None:
    # Copy FFmpeg's libraries and the vendor libraries they depend on, each
    # under its SONAME, which is the name the dynamic loader looks for. The
    # vendor directory also holds libraries nothing links against.
    vendor_libraries = {
        path.name: path for path in (VENDOR_DIR / "lib").glob("*.so*") if path.is_file()
    }
    pending = [f"lib{name}.so" for name in FFMPEG_LIBRARIES]
    copied: set[str] = set()
    while pending:
        name = pending.pop()
        # Dependencies outside the vendor directory are system libraries
        if name not in vendor_libraries:
            continue
        # Resolve the symlink to copy the real file
        source = vendor_libraries[name].resolve()
        soname = patchelf("--print-soname", str(source))
        if soname in copied:
            continue
        copied.add(soname)
        target = lib_dir / soname
        shutil.copy2(source, target)
        patchelf("--set-rpath", "$ORIGIN", str(target))
        pending.extend(patchelf("--print-needed", str(source)).split())


def otool(*args: str) -> list[str]:
    output = subprocess.run(
        ["otool", *args], check=True, capture_output=True, text=True
    ).stdout
    # The first line names the file
    return [line.strip().split(" ")[0] for line in output.splitlines()[1:]]


def copy_macos_libraries(lib_dir: Path) -> None:
    # Copy FFmpeg's libraries and the vendor libraries they depend on, each
    # under the file name of its install name (libavcodec.62.dylib), which is
    # the name TorchCodec loads as @rpath/libavcodec.62.dylib. The vendor
    # directory also holds libraries nothing links against.
    vendor_libraries = {
        path.name: path
        for path in (VENDOR_DIR / "lib").glob("*.dylib")
        if path.is_file()
    }
    pending = [f"lib{name}.dylib" for name in FFMPEG_LIBRARIES]
    copied: set[str] = set()
    while pending:
        name = pending.pop()
        # Dependencies outside the vendor directory are system libraries
        if name not in vendor_libraries:
            continue
        # Resolve the symlink to copy the real file
        source = vendor_libraries[name].resolve()
        install_name = os.path.basename(otool("-D", str(source))[0])
        if install_name in copied:
            continue
        copied.add(install_name)
        target = lib_dir / install_name
        shutil.copy2(source, target)
        # Name the library and its dependencies on the other vendor libraries
        # @rpath/<file name>, and add an rpath to its own directory
        arguments = ["-id", f"@rpath/{install_name}", "-add_rpath", "@loader_path"]
        for dependency in otool("-L", str(source)):
            dependency_name = os.path.basename(dependency)
            if dependency_name in vendor_libraries and dependency_name != install_name:
                arguments += ["-change", dependency, f"@rpath/{dependency_name}"]
                pending.append(dependency_name)
        subprocess.run(["install_name_tool", *arguments, str(target)], check=True)
        # install_name_tool invalidates the ad-hoc signature that arm64 requires
        subprocess.run(["codesign", "--force", "--sign", "-", str(target)], check=True)


def copy_windows_libraries(lib_dir: Path) -> None:
    for path in sorted((VENDOR_DIR / "bin").glob("*.dll")):
        shutil.copy2(path, lib_dir / path.name)


class BuildPy(build_py):
    def run(self) -> None:
        super().run()
        lib_dir = Path(self.build_lib) / "torchcodec_ffmpeg" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            copy_windows_libraries(lib_dir)
        elif sys.platform == "darwin":
            copy_macos_libraries(lib_dir)
        else:
            copy_linux_libraries(lib_dir)


class BinaryDistribution(Distribution):
    # The wheel contains native libraries, so the package goes to platlib
    def has_ext_modules(self) -> bool:
        return True


class BdistWheel(bdist_wheel):
    def get_tag(self) -> tuple[str, str, str]:
        _, _, platform_tag = super().get_tag()
        # Inside a manylinux container, AUDITWHEEL_PLAT names the platform the
        # libraries were built for. The wheel is not repaired with auditwheel,
        # which would rename the libraries.
        if sys.platform.startswith("linux") and "AUDITWHEEL_PLAT" in os.environ:
            platform_tag = os.environ["AUDITWHEEL_PLAT"]
        return "py3", "none", platform_tag


setup(
    cmdclass={"build_py": BuildPy, "bdist_wheel": BdistWheel},
    distclass=BinaryDistribution,
)
