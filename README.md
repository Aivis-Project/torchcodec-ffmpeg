# torchcodec-ffmpeg

[![PyPI](https://img.shields.io/pypi/v/torchcodec-ffmpeg?color=blue)](https://pypi.org/project/torchcodec-ffmpeg/)
[![Python](https://img.shields.io/pypi/pyversions/torchcodec-ffmpeg)](https://pypi.org/project/torchcodec-ffmpeg/)
[![build-ffmpeg](https://github.com/Aivis-Project/torchcodec-ffmpeg/actions/workflows/build-ffmpeg.yml/badge.svg)](https://github.com/Aivis-Project/torchcodec-ffmpeg/actions/workflows/build-ffmpeg.yml)

**The FFmpeg that [TorchCodec](https://github.com/meta-pytorch/torchcodec) refuses to ship, as a wheel you can `pip install` or `uv add`.**

TorchCodec cannot decode or encode a single audio or video file without FFmpeg, yet **it does not ship FFmpeg, and leaves you to find one on your own.**
Since torch 2.9 this is everyone's problem: `torchaudio.load()` and `torchaudio.save()` now go through TorchCodec, torchvision has removed its own video decoding and encoding, and libraries such as transformers and datasets pick TorchCodec up whenever it is installed.
Code that used to load a WAV file now fails at import time with `RuntimeError: Could not load libtorchcodec`.

torchcodec-ffmpeg bundles FFmpeg 8 (with NVDEC and NVENC), and libheif for TorchCodec's HEIC decoder, inside the wheel.
**Install it, call `torchcodec_ffmpeg.install()` before importing TorchCodec, and TorchCodec just works** — on Linux, macOS and Windows, in any virtual environment, with no system-wide FFmpeg, no `PATH` editing and no conda.

> [!NOTE]  
> torchcodec-ffmpeg is not an officially supported Aivis Project product.

## Why this exists

TorchCodec's installation guide asks you to install FFmpeg yourself, and the only installation method it offers is **`conda install ffmpeg`**.
For everyone else, it is on their own:

- On **Windows**, a typical FFmpeg build (the "essentials" build) does not work.
  You need the "shared" build, and even then TorchCodec does not find its DLLs on `PATH` unless you call `os.add_dll_directory()` yourself before importing it.
  Windows support arrived only in [TorchCodec 0.7](https://github.com/meta-pytorch/torchcodec/issues/640#issuecomment-3266672732), [five months after it was requested](https://github.com/meta-pytorch/torchcodec/issues/640), **as BETA and CPU only**, with GPU users sent to conda-forge.
  Before that, Windows users were asked [whether they had considered WSL](https://github.com/meta-pytorch/torchcodec/issues/640#issuecomment-2830057962), and [the README of TorchCodec 0.8](https://github.com/meta-pytorch/torchcodec/blob/v0.8.1/README.md) said: **"On Windows (experimental support), you'll need to rely on `conda` to install both pytorch and TorchCodec"**.
- On **macOS**, [TorchCodec could not find the FFmpeg installed by Homebrew at all](https://github.com/meta-pytorch/torchcodec/issues/570) until 0.10, and the workarounds were setting `DYLD_FALLBACK_LIBRARY_PATH` (which macOS strips from GUI apps) or patching TorchCodec's libraries with `install_name_tool`.
  Since 0.10, **the only place it looks is hard-coded into its libraries: `/opt/homebrew/opt/ffmpeg/lib`**.
  That is Homebrew's current `ffmpeg`, which is now FFmpeg 9, so [TorchCodec 0.15 and older cannot load it](https://github.com/pollen-robotics/grabette-policy/issues/4), while Homebrew's `ffmpeg@8` lives in a directory TorchCodec never looks at.
- On **Linux**, the FFmpeg your distribution ships may be too old, too new, or missing entirely in containers.
- **An application that ships to end users cannot count on any of these.**
  Asking every user of a Windows desktop app built on torch to install conda, or a particular FFmpeg build, is not a solution.

When a user asked for wheels that bundle FFmpeg ([#1149](https://github.com/meta-pytorch/torchcodec/issues/1149)), [the answer](https://github.com/meta-pytorch/torchcodec/issues/1149#issuecomment-3718446777) was that bundling raises licensing concerns, and that avoiding conflicts with the user's environment **"is a hard problem - that's the problem package managers like `conda` are there to solve"**, so shipping FFmpeg binaries **"isn't in scope at the moment"**.

**TorchCodec is built for Meta's own environment first.**
The function that searches for FFmpeg and produces the infamous `Could not load libtorchcodec`, [`load_core_libraries()`](https://github.com/meta-pytorch/torchcodec/blob/v0.16.0/src/torchcodec/_internally_replaced_utils.py#L98-L139), lives in a file named `_internally_replaced_utils.py`, because Meta's internal build replaces that file with its own (its import is even annotated with the internal build target `//pytorch/torchcodec/src:internally_replaced_utils`).
The CUDA decoder says it plainly: [**"No need to do anything on fbcode. NVCUVID is available there, we can take a hard dependency on it."**](https://github.com/meta-pytorch/torchcodec/blob/v0.16.0/src/torchcodec/_core/NVCUVIDRuntimeLoader.cpp#L7-L13)

Inside Meta, TorchCodec is built with Buck inside fbcode, where the library loader is swapped out and NVCUVID is simply there.
**The code path every outside user depends on is the one Meta itself does not run.**

We can only guess from these facts, but the conclusion is hard to avoid: **the problem does not exist inside Meta, so it has never been treated as one.**
The way Windows and macOS users have been handled points the same way.

Meanwhile, the failure has spread to every project that touches audio or video through torch.
A few of the many reports:

- [huggingface/transformers#42499](https://github.com/huggingface/transformers/issues/42499): the speech recognition pipeline fails **merely because TorchCodec is installed** without a working FFmpeg
- [pytorch/audio#4121](https://github.com/pytorch/audio/issues/4121): `torchaudio.load` fails on non-shared Python builds since 2.9.0
- [ROCm/TheRock#1490](https://github.com/ROCm/TheRock/issues/1490): torchaudio 2.9 relies on TorchCodec, but there is no TorchCodec wheel to go with it
- [meta-pytorch/torchcodec#912](https://github.com/meta-pytorch/torchcodec/issues/912), [#1006](https://github.com/meta-pytorch/torchcodec/issues/1006), [#1131](https://github.com/meta-pytorch/torchcodec/issues/1131), [#1147](https://github.com/meta-pytorch/torchcodec/issues/1147): `Could not load libtorchcodec`, again and again
- [SWivid/F5-TTS#1234](https://github.com/SWivid/F5-TTS/issues/1234), [m-bain/whisperX#1360](https://github.com/m-bain/whisperX/issues/1360), [QwenLM/Qwen3-VL#1468](https://github.com/QwenLM/Qwen3-VL/issues/1468), [deepbeepmeep/WanGP#1702](https://github.com/deepbeepmeep/WanGP/issues/1702), [rakuri255/UltraSinger#306](https://github.com/rakuri255/UltraSinger/issues/306), [Aratako/Irodori-TTS#40](https://github.com/Aratako/Irodori-TTS/issues/40), [RVC-Boss/GPT-SoVITS#2789](https://github.com/RVC-Boss/GPT-SoVITS/issues/2789): the same failure in text-to-speech, speech recognition, vision-language and video generation projects
- [How to fix the FFmpeg error of torchaudio 2.9.1 (torchcodec 0.8.1) on Windows](https://zenn.dev/litagin/articles/a55e6cfe506677) (in Japanese), by the author of Style-Bert-VITS2: the shared build, the manual `os.add_dll_directory()`, and the README's advice to use conda

TorchCodec 0.16 finally stopped failing at import time when FFmpeg is missing.
**That does not help torch 2.9 and 2.10 users**: each of them can only use TorchCodec 0.8 to 0.10, which are tied to their torch version and still fail.

TorchCodec itself is a good library.
**Its distribution is the problem**, and it is the problem of every developer who ships an AI application built on torch to Windows and macOS.
torchcodec-ffmpeg is the all-in-one package that should have existed from the start, and we hope it helps the community until TorchCodec solves this itself.

## Installation

```bash
pip install torch torchcodec torchcodec-ffmpeg
```

or

```bash
uv add torch torchcodec torchcodec-ffmpeg
```

Wheels are provided for the platforms TorchCodec publishes wheels for:

- Linux x86_64 and aarch64 (manylinux_2_28)
- macOS arm64 (macOS 14 or later)
- Windows x86_64

Each wheel works with Python 3.10 to 3.14, including the free-threaded build, because it contains no Python extension.

## Usage

Call `torchcodec_ffmpeg.install()` once, **before importing TorchCodec** or anything that imports it (torchaudio, transformers, datasets and so on).
The top of your application's entry point is the right place:

```python
import torchcodec_ffmpeg

torchcodec_ffmpeg.install()

from torchcodec.decoders import AudioDecoder, VideoDecoder
```

Nothing else changes.
TorchCodec uses the bundled FFmpeg as if it were installed on the system, even when another FFmpeg is installed there.
Calling `install()` again does nothing.
Calling it after TorchCodec has been imported raises an error, because TorchCodec loads FFmpeg when it is imported and cannot switch afterwards.

### PyInstaller

Apps frozen with [PyInstaller](https://pyinstaller.org/) work without any option, and **nothing from the build machine ends up in the app because of TorchCodec**.
The wheel ships PyInstaller hooks for itself and for TorchCodec:

- **The bundled FFmpeg and libheif** are collected as is.
  PyInstaller alone misses them on Linux, because it only picks up shared libraries named like `lib*.so` and these are named `libavcodec.so.62` and so on.
- **TorchCodec** is collected with only the libraries that work with the bundled FFmpeg.
  PyInstaller alone does not collect TorchCodec's libraries at all.
  Collecting all of them would also be wrong: TorchCodec ships a set of libraries for each FFmpeg major version, and PyInstaller would bundle whatever FFmpeg it finds on the build machine for each of them.
- **The libraries TorchCodec links against resolve to the bundled ones.**
  PyInstaller looks for a library's dependencies where the library itself would at run time.
  TorchCodec's libraries look in `/opt/homebrew/opt/ffmpeg/lib` on macOS and in the system's library directories on Linux, so a Homebrew or system FFmpeg, and everything it links against, would otherwise be bundled next to the one that is actually loaded.

The libraries are collected as binaries, so on macOS PyInstaller signs them along with the rest of the app, with the identity given by `--codesign-identity` for apps that are notarized.

Hooks shipped by a package take priority over those of [pyinstaller-hooks-contrib](https://github.com/pyinstaller/pyinstaller-hooks-contrib), so the TorchCodec hook stays in effect even if pyinstaller-hooks-contrib adds one.

## Compatibility

| TorchCodec | torch | Tested with |
|---|---|---|
| 0.8, 0.9 | 2.9 | torch 2.9.1 |
| 0.10 | 2.10 | torch 2.10.0 |
| 0.11 | 2.11 | torch 2.11.0 |
| 0.12 to 0.17 | 2.11 and later | torch 2.11.0 and 2.15.0 |

CI tests every row above on Linux x86_64, and the latest TorchCodec on every platform and Python version.

**torchcodec-ffmpeg ships FFmpeg 8.x, and will keep doing so for the foreseeable future.**
TorchCodec 0.15 and older can load FFmpeg 4 to 8 only, and only TorchCodec 0.16 and later can load FFmpeg 9.
FFmpeg 8 is the newest version that every TorchCodec since 0.8 (torch 2.9) can load.
The version of torchcodec-ffmpeg is the version of the bundled FFmpeg, with a `.postN` suffix for releases that change only the packaging.
If you use TorchCodec 0.15 or older (torch 2.9 or 2.10), require `torchcodec-ffmpeg<9`, so that a future release with FFmpeg 9 is not installed.

## How it works

TorchCodec's native libraries depend on FFmpeg's libraries and libheif by name (`libavcodec.so.62`, `libheif.so.1` and so on) and leave it to the operating system to find them.
`install()` loads the bundled libraries into the process first, so that the operating system resolves those names to them:

- On Linux and macOS, each library is loaded by its absolute path with `RTLD_GLOBAL`.
  The bundled libraries find their own dependencies through an rpath to their directory.
- On Windows, the directory of the bundled DLLs is also added to the DLL search path with `os.add_dll_directory()`.

TorchCodec 0.16 and later try their libraries for each FFmpeg major version from 9 down, so an FFmpeg 9 on the system, such as Homebrew's on macOS, would be used instead of the bundled FFmpeg 8.
`install()` makes TorchCodec try its libraries for the bundled FFmpeg first, so that your environment and an app frozen with PyInstaller use the same FFmpeg.
If they fail to load, TorchCodec falls back to its own order.

PyAV's wheels also contain FFmpeg, but TorchCodec cannot use them: `auditwheel`, `delocate` and `delvewheel` rename the bundled libraries (for example to `libavcodec-d61378e8.so.63`), so the operating system never matches them to the names TorchCodec asks for.
torchcodec-ffmpeg keeps the original names instead.

**torchcodec-ffmpeg does not conflict with PyAV.**
PyAV keeps loading its own renamed copy of FFmpeg, and both can be used in the same process.
No environment variable, system-wide installation or change to `site-packages` is needed.

## What is included

TorchCodec opens whatever FFmpeg can open, including URLs, and encodes with any encoder given by name.
torchcodec-ffmpeg therefore keeps what the upstream pyav-ffmpeg build provides, including **NVDEC, NVENC and the `scale_cuda` filter** for TorchCodec's CUDA decoding and encoding on Linux and Windows x86_64 (the CUDA Toolkit is not needed, only the NVIDIA driver).
It leaves out only what TorchCodec cannot reach:

- filters other than those TorchCodec's filter graphs use
- capture and playback devices (ALSA, X11 screen capture)
- libass and its font libraries, used only by the subtitles filter
- libvmaf, used only by the libvmaf filter

TorchCodec 0.17 and later decode HEIC images with libheif, which TorchCodec does not ship either: it tells you to install it with conda, apt or Homebrew.
torchcodec-ffmpeg bundles libheif, built to decode HEVC with the bundled libavcodec, so it adds no decoder library of its own (about 2 MB).

x265 is built with 8-bit support only.
The 10-bit and 12-bit libraries that upstream links in would more than triple its size, while TorchCodec encodes 8-bit frames; 10-bit HEVC can still be encoded with the hardware encoders.

## Caveats

- **`install()` must run before TorchCodec is imported.**
  If a library imports TorchCodec first, TorchCodec loads whatever FFmpeg it finds, or fails as before.
- If another FFmpeg with the same library names is already loaded into the process (for example by an extension linked against the system FFmpeg) before `install()` runs, the operating system may keep using it.
  Wheels that bundle renamed copies of FFmpeg, such as PyAV's, are not affected.
- The wheel adds about 22 MB to download (about 56 MB installed on Linux x86_64).
  If PyAV is installed too, the environment holds two copies of FFmpeg.
- Only FFmpeg 8.x is provided, so features that only FFmpeg 9 has are not available.

**If torchcodec-ffmpeg does not work for the way you use TorchCodec, please [open an issue](https://github.com/Aivis-Project/torchcodec-ffmpeg/issues)** with the details: what you call, the files or streams you pass, your platform and the versions of torch, TorchCodec and torchcodec-ffmpeg.
torchcodec-ffmpeg aims to cover everything TorchCodec can do, and we will look into whether the build can support it.

## Relation to pyav-ffmpeg

This repository is a fork of [pyav-ffmpeg](https://github.com/PyAV-Org/pyav-ffmpeg), which builds FFmpeg and its dependencies for PyAV.
pyav-ffmpeg is very well made and keeps up with FFmpeg and its dependencies closely, so torchcodec-ffmpeg builds on it and merges its changes to stay up to date.

To keep those merges simple, the upstream build scripts are changed as little as possible.
The package definitions in `scripts/pkg.py` and the configure arguments in `scripts/build-ffmpeg.py` are kept as upstream has them.
What torchcodec-ffmpeg changes lives in `scripts/torchcodec_components.py`, and every other change is marked with a `torchcodec-ffmpeg:` comment.
The main differences are:

- FFmpeg 8 instead of 9, so that TorchCodec 0.15 and older can load it
- `setup.py` builds the torchcodec-ffmpeg wheel instead of a dummy extension, and the wheel is not repaired with `auditwheel`, `delocate` or `delvewheel`
- x265 with 8-bit support only
- builds only for the platforms TorchCodec publishes wheels for

## Development

`scripts/build-ffmpeg.py` builds FFmpeg and `setup.py` builds the wheel around it, both run by cibuildwheel in CI (`.github/workflows/build-ffmpeg.yml`).
CI then tests the wheel with the latest TorchCodec on every platform and Python version, and with each TorchCodec version from 0.8 on Linux x86_64.

To run the tests locally, install the wheel with TorchCodec, torch and pytest, and run pytest from the repository:

```bash
uv venv .venv-test
uv pip install --python .venv-test torch torchcodec pytest dist/torchcodec_ffmpeg-*.whl
uv run --no-project --python .venv-test pytest
```

The test assets in `tests/assets` are generated by `tests/assets/generate.sh`.

The wheels that pass the tests are published to TestPyPI on every push, and to PyPI when a tag is pushed.
To release, set `version` in `pyproject.toml` and push a tag named after it: `v8.1.3` for a new FFmpeg version, `v8.1.3-post1` for a release that changes only the packaging (`version = "8.1.3-post1"`, published as `8.1.3.post1`).
Publishing needs the `PYPI_API_TOKEN` and `TEST_PYPI_API_TOKEN` secrets.

The README of pyav-ffmpeg follows.

---


# pyav-ffmpeg

This project provides binary builds of FFmpeg and its dependencies for [PyAV](https://github.com/PyAV-Org/PyAV). These builds are used in order to provide binary wheels of PyAV, allowing users to easily install PyAV without perform error-prone compilations.

The builds are provided for several platforms:

- Linux (x86_64, aarch64, armv7l, ppc64le, riscv64)
- macOS (x86_64, arm64)
- Windows (x86_64, aarch64)

Features
--------

Currently FFmpeg 9.0.2 is built with the following packages enabled for all platforms:

- [bwlame](https://github.com/basswood-io/bwlame) 4.1.0
- opus 1.6.1
- dav1d 1.5.4
- libsvtav1 4.3.0
- vpx 1.17.0
- webp 1.6.0
- libvmaf 3.2.1
- x264 b35605ace3ddf7c1a5d67a2eb553f034aef41d55 (except armv7l)
- x265 4.3
- freetype 2.15.0
- fribidi 1.0.18
- harfbuzz 15.1.0
- libunibreak 8.0
- libass 0.17.5

The following additional packages are also enabled on Linux:

- gnutls 3.8.13
- nettle 4.0
- unistring 1.5
