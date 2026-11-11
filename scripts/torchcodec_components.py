"""What torchcodec-ffmpeg changes on top of the upstream pyav-ffmpeg scripts.

torchcodec-ffmpeg builds the FFmpeg that TorchCodec loads. TorchCodec opens
whatever FFmpeg can open and encodes with any encoder given by name, so the
upstream build is kept as it is, and only what TorchCodec cannot reach is left
out. The package definitions in pkg.py and the configure arguments in
build-ffmpeg.py are not edited, so that upstream updates merge cleanly.
build-ffmpeg.py skips the packages and appends the configure arguments listed
here, and builds x265 with the Builder below.
"""

import platform
import shutil
from dataclasses import replace
from pathlib import Path

import cibuildpkg
from cibuildpkg import Package, log_group, run

# Packages from pkg.py that TorchCodec cannot use: libass and its font libraries
# (the subtitles filter), libvmaf (the libvmaf filter) and ALSA (capture and
# playback devices). TorchCodec builds its filter graphs from a fixed set of
# filters and never opens devices.
SKIPPED_PACKAGES = {
    "alsa-lib",
    "freetype",
    "fribidi",
    "harfbuzz",
    "libass",
    "libunibreak",
    "libvmaf",
}

# The filters TorchCodec's FilterGraph builds. CPU decoding passes frames
# through "copy" when no conversion is needed.
FILTERS = [
    "buffer",
    "buffersink",
    "copy",
    "crop",
    "format",
    "hflip",
    "scale",
    "transpose",
    "vflip",
]


# libheif, which TorchCodec's HEIC decoder (TorchCodec 0.17 and later) links
# against and does not bundle. It is built after FFmpeg and decodes HEVC with
# the bundled libavcodec, so it needs no decoder library of its own. TorchCodec
# only decodes HEIC, so libheif is built without encoders and plugin loading.
libheif_package = Package(
    name="libheif",
    requires=["ffmpeg"],
    source_url="https://github.com/strukturag/libheif/releases/download/v1.23.7/libheif-1.23.7.tar.gz",
    sha256="f7483e818503ea6224c8863e4a56ac02c7089021a98472c811c12aa19faf2475",
    build_system="cmake",
    build_arguments=[
        # libheif builds without optimization unless a build type is given
        "-DCMAKE_BUILD_TYPE=Release",
        "-DWITH_FFMPEG_DECODER=ON",
        "-DWITH_FFMPEG_DECODER_PLUGIN=OFF",
        "-DENABLE_PLUGIN_LOADING=OFF",
        # x264 and x265 are in the vendor directory and would be found
        "-DWITH_X264=OFF",
        "-DWITH_X265=OFF",
        "-DWITH_LIBDE265=OFF",
        "-DWITH_OpenH264_DECODER=OFF",
        "-DWITH_AOM_DECODER=OFF",
        "-DWITH_AOM_ENCODER=OFF",
        "-DWITH_LIBSHARPYUV=OFF",
        "-DWITH_EXAMPLES=OFF",
        "-DWITH_GDK_PIXBUF=OFF",
        "-DBUILD_TESTING=OFF",
    ],
)

# Packages built in addition to those of pkg.py, after FFmpeg
EXTRA_PACKAGES = [libheif_package]


def configure_arguments(upstream_arguments: list[str], use_cuda: bool) -> list[str]:
    """Configure arguments: the upstream ones, then the overrides below.

    FFmpeg's configure applies its arguments in order, so the overrides win over
    the upstream arguments they contradict.
    """
    arguments = upstream_arguments + [
        # The libraries of SKIPPED_PACKAGES
        "--disable-alsa",
        "--disable-libass",
        "--disable-libvmaf",
        # Devices (also the X11 screen capture behind libxcb)
        "--disable-devices",
        "--disable-libxcb",
        "--disable-filters",
        "--enable-filter=" + ",".join(FILTERS),
    ]

    # TorchCodec's CUDA decoding converts colors with hwdownload or scale_cuda.
    # scale_cuda's kernels are compiled with clang (--enable-cuda-llvm), so the
    # CUDA Toolkit is not needed.
    if use_cuda:
        arguments += ["--enable-cuda-llvm", "--enable-filter=hwdownload,scale_cuda"]

    return arguments


def install_clang() -> None:
    """Install clang in the manylinux container for --enable-cuda-llvm.

    The wheels are built in the manylinux_2_28 container, which is AlmaLinux 8.
    """
    if shutil.which("clang") is not None:
        return
    with log_group("install clang"):
        run(["dnf", "-y", "install", "clang"])


class Builder(cibuildpkg.Builder):
    """The upstream Builder, building libheif against the bundled FFmpeg and
    x265 with 8-bit support only.

    Upstream builds x265 three times and links the 8-bit library with the 10-bit
    and 12-bit ones, which more than triples its size. TorchCodec encodes 8-bit
    frames (its video encoders take uint8 tensors), and 10-bit HEVC can still be
    encoded with the hardware encoders (NVENC, AMF, QSV and VideoToolbox).
    """

    def _build_with_cmake(self, package: Package, for_builder: bool) -> None:
        # libheif finds FFmpeg with find_library and find_path, which look in
        # the system's directories (/usr/local, Homebrew) before the paths it
        # lists, so it could compile against the vendor headers and link
        # against another FFmpeg. CMAKE_PREFIX_PATH is searched first.
        if package.name == "libheif":
            prefix = Path(self._prefix(for_builder=for_builder)).as_posix()
            package = replace(
                package,
                build_arguments=[
                    *package.build_arguments,
                    f"-DCMAKE_PREFIX_PATH={prefix}",
                ],
            )
        super()._build_with_cmake(package=package, for_builder=for_builder)

    def _build_x265(self, package: Package) -> None:
        # Upstream builds x265 three times: the 12-bit and 10-bit static
        # libraries, and then the 8-bit shared library, which links them in
        # with -DEXTRA_LIB, -DLINKED_10BIT and -DLINKED_12BIT. Only the 8-bit
        # shared library is built here, without them. It gets the flag upstream
        # gives it on Linux aarch64; upstream's -DCPU_HAS_NEON for 32-bit ARM is
        # not needed, as no 32-bit ARM wheel is built.
        if platform.system() == "Linux" and platform.machine() == "aarch64":
            package.build_arguments = ["-DENABLE_SVE2=OFF"]
        self._build_with_cmake(package=package, for_builder=False)
