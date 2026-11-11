"""What torchcodec-ffmpeg changes on top of the upstream pyav-ffmpeg scripts.

torchcodec-ffmpeg builds the FFmpeg that TorchCodec loads. TorchCodec opens
whatever FFmpeg can open and encodes with any encoder given by name, so the
upstream build is kept as it is, and only what TorchCodec cannot reach is left
out. The package definitions in pkg.py and the configure arguments in
build-ffmpeg.py are not edited, so that upstream updates merge cleanly.
build-ffmpeg.py skips the packages and appends the configure arguments listed
here.
"""

import shutil

from cibuildpkg import log_group, run

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
