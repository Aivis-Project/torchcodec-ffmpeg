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
    """The upstream Builder, building x265 with 8-bit support only.

    Upstream builds x265 three times and links the 8-bit library with the 10-bit
    and 12-bit ones, which more than triples its size. TorchCodec encodes 8-bit
    frames (its video encoders take uint8 tensors), and 10-bit HEVC can still be
    encoded with the hardware encoders (NVENC, AMF, QSV and VideoToolbox).
    """

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
