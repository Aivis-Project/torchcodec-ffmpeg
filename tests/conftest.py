import torchcodec_ffmpeg

# TorchCodec loads FFmpeg when it is imported, so install the bundled FFmpeg
# before the test modules import TorchCodec
torchcodec_ffmpeg.install()
