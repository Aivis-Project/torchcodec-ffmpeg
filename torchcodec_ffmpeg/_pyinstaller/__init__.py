"""PyInstaller hooks for torchcodec-ffmpeg and TorchCodec.

PyInstaller finds them through the pyinstaller40 entry point in pyproject.toml.
Hooks shipped by a package take priority over those of
pyinstaller-hooks-contrib, so hook-torchcodec.py is used even if
pyinstaller-hooks-contrib adds its own.
"""

from pathlib import Path


def get_hook_dirs() -> list[str]:
    return [str(Path(__file__).parent)]
