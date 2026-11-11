# torchcodec-ffmpeg

[![PyPI](https://img.shields.io/pypi/v/torchcodec-ffmpeg?color=blue)](https://pypi.org/project/torchcodec-ffmpeg/)
[![Python](https://img.shields.io/pypi/pyversions/torchcodec-ffmpeg)](https://pypi.org/project/torchcodec-ffmpeg/)
[![build-ffmpeg](https://github.com/Aivis-Project/torchcodec-ffmpeg/actions/workflows/build-ffmpeg.yml/badge.svg)](https://github.com/Aivis-Project/torchcodec-ffmpeg/actions/workflows/build-ffmpeg.yml)

**FFmpeg and libheif for [TorchCodec](https://github.com/meta-pytorch/torchcodec), as a wheel you can `pip install` or `uv add`.**

TorchCodec needs FFmpeg to decode or encode audio and video, but it does not ship FFmpeg and leaves you to install one yourself.  
torchcodec-ffmpeg bundles FFmpeg 8 (with NVDEC and NVENC), and libheif for TorchCodec's HEIC decoder, inside the wheel.

Add it to your dependencies and call `torchcodec_ffmpeg.install()` at the top of your entry point script, before anything imports TorchCodec.  
TorchCodec then works on Linux, macOS and Windows, in any virtual environment, with no system-wide FFmpeg, no `PATH` editing and no conda.

> [!NOTE]  
> torchcodec-ffmpeg is not an officially supported Aivis Project product.

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

## Background

### The move to TorchCodec

In April 2025, PyTorch began consolidating its media decoding and encoding into TorchCodec.  
torchvision 0.22 deprecated its video decoding and encoding, and the TorchAudio team [announced](https://github.com/pytorch/audio/issues/3902) that TorchAudio would enter a maintenance phase and leave its audio and video I/O to TorchCodec.  
[datasets 4.0](https://github.com/huggingface/datasets/releases/tag/4.0.0) (July 2025) switched its audio and video decoding to TorchCodec, and since torch 2.9 (October 2025), `torchaudio.load()` and `torchaudio.save()` go through TorchCodec.  
torchvision 0.26 (torch 2.11, March 2026) [removed its video decoding and encoding](https://github.com/pytorch/vision/releases/tag/v0.26.0) altogether.

Every project that loads audio or video through torch was affected, and the transition was confusing for three reasons at once.

**TorchCodec does not ship FFmpeg, and points to conda for it.**  
The only installation command its installation guide gives for FFmpeg is `conda install ffmpeg`.  
That means working in a conda environment, while most projects install torch from PyPI with pip or uv: PyTorch itself [stopped publishing to its Anaconda channel after 2.5](https://github.com/pytorch/pytorch/issues/138506), pointing to the gap between its downloads from PyPI and from conda.  
conda's own documentation [warns that issues may arise when using pip and conda together](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment), and recommends installing as many packages as possible with conda first.

**Windows support came late.**  
[Windows support](https://github.com/meta-pytorch/torchcodec/issues/640) arrived in TorchCodec 0.7 (September 2025), as beta and CPU only, so the release notes of datasets 4.0 asked Windows users to stay on `datasets<4.0` for the time being.  
[The README of TorchCodec 0.8](https://github.com/meta-pytorch/torchcodec/blob/v0.8.1/README.md) said that on Windows "you'll need to rely on `conda` to install both pytorch and TorchCodec".  
Without conda, TorchCodec 0.8 did not find FFmpeg's DLLs even when they were on `PATH`, until users found that they had to call `os.add_dll_directory()` themselves ([meta-pytorch/torchcodec#1014](https://github.com/meta-pytorch/torchcodec/issues/1014)).  
As the author of Style-Bert-VITS2 [put it](https://github.com/huggingface/transformers/issues/42499#issuecomment-3599813095) at the time, "most Windows users (even with ffmpeg installed) run into this issue unless they're using conda".

**Each TorchCodec release worked with a single torch version.**  
Until TorchCodec 0.12, a TorchCodec release had to match the torch version it was built for, and [this cannot be enforced at install time](https://github.com/meta-pytorch/torchcodec/issues/655#issuecomment-2839535090), so pip and uv happily install combinations that do not work.  
A mismatch does not always end with an error message: it can crash the process, with a segmentation fault ([meta-pytorch/torchcodec#995](https://github.com/meta-pytorch/torchcodec/issues/995)), or with `Windows fatal exception: code 0xc0000139` ([yuvraj108c/ComfyUI-Whisper#44](https://github.com/yuvraj108c/ComfyUI-Whisper/issues/44)) or an "Entry Point Not Found" dialog ([ace-step/ACE-Step-1.5#739](https://github.com/ace-step/ACE-Step-1.5/issues/739)) on Windows.  
Libraries started pinning torch to avoid this.  
pyannote.audio 4.0.2 and 4.0.3 required exactly `torch==2.8.0`, `torchaudio==2.8.0` and `torchcodec==0.7.0` "to avoid segmentation fault", which [kept their users off newer hardware and libraries](https://github.com/pyannote/pyannote-audio/issues/1976), WhisperX [pinned TorchCodec for torch 2.8](https://github.com/m-bain/whisperX/pull/1397), and F5-TTS [advised Windows users to stay on torch older than 2.9](https://github.com/SWivid/F5-TTS/issues/1234#issuecomment-3626830518).

Reports of the same failures piled up across the ecosystem:

- [meta-pytorch/torchcodec#912](https://github.com/meta-pytorch/torchcodec/issues/912): `Could not load libtorchcodec` with the torch 2.9 release candidate, the first of many reports of this error
- [huggingface/transformers#42499](https://github.com/huggingface/transformers/issues/42499): the speech recognition pipeline fails merely because a TorchCodec that cannot load is installed
- [pytorch/audio#4121](https://github.com/pytorch/audio/issues/4121): `torchaudio.load()` fails on Python builds without a shared libpython since 2.9.0
- [ROCm/TheRock#1490](https://github.com/ROCm/TheRock/issues/1490): torchaudio 2.9 relies on TorchCodec, but there is no TorchCodec wheel for ROCm to go with it
- [RVC-Boss/GPT-SoVITS#2789](https://github.com/RVC-Boss/GPT-SoVITS/issues/2789): a Docker image whose TorchCodec does not match its torch, so that every text-to-speech request fails
- [vllm-project/vllm#63121](https://github.com/vllm-project/vllm/issues/63121): a TorchCodec wheel for the wrong CUDA version stops `vllm serve` from starting, even when no audio is used
- [How to fix the FFmpeg error of torchaudio 2.9.1 (torchcodec 0.8.1) on Windows](https://zenn.dev/litagin/articles/a55e6cfe506677) (in Japanese), by the author of Style-Bert-VITS2: the shared build of FFmpeg, a manual `os.add_dll_directory()`, and the README's advice to use conda

### What has improved

Much of this has eased since then.  
TorchCodec 0.9.1 (December 2025) finds the DLLs of the shared build of FFmpeg on `PATH` by itself.  
torch 2.11 and later have become common, and libraries such as datasets have finished moving to TorchCodec.  
[TorchCodec 0.12](https://github.com/meta-pytorch/torchcodec/releases/tag/v0.12.0) (May 2026) is ABI stable from torch 2.11, so new TorchCodec releases keep working with torch 2.11 and later; its release notes say that "previously, each new version of torch required a corresponding version of TorchCodec, which made dependency management complex for users".  
TorchCodec 0.16 (August 2026) no longer fails at import time when FFmpeg is missing, so code that never decodes audio or video is no longer broken just because TorchCodec is installed.  
Decoding and encoding still need FFmpeg, though, and TorchCodec 0.16 requires torch 2.11 or later.

### What remains

- **Projects on torch 2.9 or 2.10 are left with TorchCodec 0.8 to 0.10, which receive no further fixes.**  
  For example, decoding a 24-bit WAV with a trailing metadata chunk from memory reads past the end of the buffer and fails ([meta-pytorch/torchcodec#1378](https://github.com/meta-pytorch/torchcodec/issues/1378)).  
  The fix is only in TorchCodec 0.13 and later, which require torch 2.11, so projects such as SGLang [fall back to another library](https://github.com/sgl-project/sglang/pull/24185) when TorchCodec fails.
- **Even with the latest torch and TorchCodec, audio cannot be loaded unless TorchCodec finds a suitable FFmpeg.**  
  Python projects today keep their dependencies in a virtual environment of their own, created with venv or uv.  
  torch itself is the prime example: its CUDA builds bring the CUDA libraries they need into the virtual environment, as pip dependencies on Linux and inside the wheel on Windows, so each project can use its own CUDA version without replacing the one on the system.  
  TorchCodec, on the other hand, expects FFmpeg from outside the virtual environment, installed for the whole system and shared by every project.  
  Finding one is up to you:
  - On Windows, a typical FFmpeg build (the "essentials" build) does not work, because TorchCodec needs FFmpeg's DLLs.  
    You need the "shared" build on `PATH`, and TorchCodec 0.8 and 0.9.0 also need `os.add_dll_directory()` to be called before importing them.
  - On macOS, [TorchCodec could not find the FFmpeg installed by Homebrew](https://github.com/meta-pytorch/torchcodec/issues/570) until 0.10, and since 0.10 the place it looks is hard-coded into its libraries: `/opt/homebrew/opt/ffmpeg/lib`.  
    That is Homebrew's current `ffmpeg`, which is now FFmpeg 9, so [TorchCodec 0.15 and older cannot load it](https://github.com/pollen-robotics/grabette-policy/issues/4), while Homebrew's `ffmpeg@8` lives in a directory TorchCodec does not look at.
  - On Linux, the FFmpeg your distribution ships may be too old, too new, or missing entirely in containers.
- **An application shipped to end users cannot rely on any of these.**  
  Installing FFmpeg for TorchCodec means changing the user's system, and asking every user of a desktop app built on torch to install conda or a particular FFmpeg build is not practical.

When a user asked for wheels that bundle FFmpeg ([meta-pytorch/torchcodec#1149](https://github.com/meta-pytorch/torchcodec/issues/1149)), [the answer](https://github.com/meta-pytorch/torchcodec/issues/1149#issuecomment-3718446777) was that bundling raises licensing concerns and conflicts with the user's environment, which package managers like conda are there to solve, so shipping FFmpeg binaries is not in scope for now.

### Why we made this

More than a year after the move to TorchCodec began, these problems are still there.  
We ran into them ourselves while preparing tools that we develop at Aivis Project for Windows and macOS: the tools load audio through torchaudio and TorchCodec, and we could not ask their users to install FFmpeg, edit `PATH` or set up conda.

torchcodec-ffmpeg is the all-in-one solution we made for this, and we publish it so that anyone facing the same problem can use it.  
It gives every torch version since 2.9 the same FFmpeg, inside the virtual environment, without touching the user's system.  
Add it to your dependencies and call `torchcodec_ffmpeg.install()` at the top of your entry point script, before anything imports TorchCodec; nothing else is needed.  
We hope it helps until TorchCodec addresses this itself.

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
The tags differ from upstream's (such as `9.0.2-1`) on purpose: upstream tags mark the FFmpeg builds that PyAV downloads, while the tags here are versions published to PyPI.  
Push release tags by name (`git push origin v8.1.3`), because the repository also has upstream's tags.

The README of [pyav-ffmpeg](https://github.com/PyAV-Org/pyav-ffmpeg) below is kept unchanged for reference.  
It describes pyav-ffmpeg, and what it says may not apply to torchcodec-ffmpeg.

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
