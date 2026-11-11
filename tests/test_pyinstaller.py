"""Check that an app frozen with PyInstaller uses the bundled FFmpeg.

The hooks in torchcodec_ffmpeg/_pyinstaller should collect the bundled FFmpeg
and TorchCodec without any option, and nothing from the build machine. Skipped
when PyInstaller is not installed.
"""

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyInstaller")

import torchcodec  # noqa: E402
import torchcodec.decoders  # noqa: E402

import torchcodec_ffmpeg  # noqa: E402

TESTS_DIR = Path(__file__).parent
ASSETS_DIR = TESTS_DIR / "assets"

APP = """
import json
import sys
from pathlib import Path

import torchcodec_ffmpeg

torchcodec_ffmpeg.install()

import torchcodec
from torchcodec.decoders import AudioDecoder, VideoDecoder

from loaded_libraries import loaded_libraries

samples = AudioDecoder(sys.argv[1]).get_samples_played_in_range(0)
frame = VideoDecoder(sys.argv[2])[0]
# decode_heic was added in TorchCodec 0.17
heic_shape = None
if hasattr(torchcodec.decoders, "decode_heic"):
    heic_shape = list(torchcodec.decoders.decode_heic(sys.argv[3]).shape)
print(
    json.dumps(
        {
            "ffmpeg_major_version": getattr(torchcodec, "ffmpeg_major_version", None),
            "libavcodec": sorted(
                {path for path in loaded_libraries() if "avcodec" in Path(path).name}
            ),
            "samples": samples.data.shape[-1],
            "channels": frame.shape[0],
            "heic_shape": heic_shape,
        }
    )
)
"""

# An app with torch only, to tell which binaries TorchCodec brings in
BASELINE_APP = """
import torch
"""

# Analyses both apps, records the binaries each one collects and builds the app
SPEC = """
import json

app = Analysis([{app!r}], pathex=[{tests_dir!r}])
baseline = Analysis([{baseline_app!r}])
with open({binaries!r}, "w") as file:
    json.dump(
        {{
            "app": list(app.binaries),
            "baseline": list(baseline.binaries),
        }},
        file,
    )

pyz = PYZ(app.pure)
exe = EXE(pyz, app.scripts, [], exclude_binaries=True, name="app")
coll = COLLECT(exe, app.binaries, app.datas, name="app")
"""


def test_frozen_app_uses_bundled_ffmpeg(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(APP)
    (tmp_path / "baseline.py").write_text(BASELINE_APP)
    (tmp_path / "app.spec").write_text(
        SPEC.format(
            app=str(tmp_path / "app.py"),
            baseline_app=str(tmp_path / "baseline.py"),
            tests_dir=str(TESTS_DIR),
            binaries=str(tmp_path / "binaries.json"),
        )
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--log-level",
            "WARN",
            "--distpath",
            str(tmp_path / "dist"),
            "--workpath",
            str(tmp_path / "build"),
            str(tmp_path / "app.spec"),
        ],
        check=True,
        # python -m puts the working directory first on sys.path, so running
        # from a checkout would import its torchcodec_ffmpeg, which has no lib
        cwd=tmp_path,
    )

    # Every binary that TorchCodec brings in comes from TorchCodec or
    # torchcodec-ffmpeg, and none from the build machine, such as another
    # FFmpeg or the libraries it depends on
    binaries = json.loads((tmp_path / "binaries.json").read_text())
    baseline = {destination for destination, _, _ in binaries["baseline"]}
    package_dirs = [
        Path(torchcodec.__file__).parent.resolve(),
        Path(torchcodec_ffmpeg.__file__).parent.resolve(),
    ]
    # auditwheel puts the libraries TorchCodec bundles on Linux next to the
    # package, in torchcodec.libs
    package_dirs.append(package_dirs[0].with_name("torchcodec.libs"))
    foreign = [
        f"{destination} from {source}"
        for destination, source, typecode in binaries["app"]
        # The source of a symbolic link is the file it points to in the app
        if destination not in baseline
        and typecode != "SYMLINK"
        and not any(
            directory in Path(source).resolve().parents for directory in package_dirs
        )
    ]
    assert not foreign, foreign

    app_dir = tmp_path / "dist" / "app"
    library_dir = (app_dir / "_internal" / "torchcodec_ffmpeg" / "lib").resolve()
    executable = app_dir / ("app.exe" if sys.platform == "win32" else "app")
    output = subprocess.run(
        [
            str(executable),
            str(ASSETS_DIR / "alac.m4a"),
            str(ASSETS_DIR / "vp8.webm"),
            str(ASSETS_DIR / "heic.heic"),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    result = json.loads(output.splitlines()[-1])

    assert len(result["libavcodec"]) == 1, result["libavcodec"]
    assert Path(result["libavcodec"][0]).resolve().parent == library_dir
    # The package version is the FFmpeg version. TorchCodec 0.8 has no
    # ffmpeg_major_version.
    ffmpeg_major = int(importlib.metadata.version("torchcodec-ffmpeg").split(".")[0])
    if result["ffmpeg_major_version"] is not None:
        assert result["ffmpeg_major_version"] == ffmpeg_major
    assert result["samples"] > 0
    assert result["channels"] == 3
    if hasattr(torchcodec.decoders, "decode_heic"):
        assert result["heic_shape"] == [3, 96, 128]
