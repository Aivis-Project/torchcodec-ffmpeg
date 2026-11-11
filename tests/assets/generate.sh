#!/bin/sh
# Generate the test assets with the ffmpeg command line tool.
# The assets are synthetic (a sine tone and FFmpeg's test pattern) and short,
# so that they can be committed. Generating them needs an ffmpeg built with
# libopencore-amrnb, libtheora and libvorbis, and the HEIC image needs
# ImageMagick with libheif.
set -eu
cd "$(dirname "$0")"

audio="-f lavfi -i sine=frequency=440:sample_rate=48000:duration=0.5"
video="-f lavfi -i testsrc=size=128x96:rate=25:duration=0.4"
ff="ffmpeg -nostdin -loglevel error -y"

# Audio
$ff $audio -c:a pcm_s16be aiff.aiff
$ff $audio -c:a pcm_s16be au.au
$ff $audio -c:a pcm_s16le caf.caf
$ff $audio -c:a pcm_s16le w64.w64
$ff $audio -c:a aac adts.aac
$ff $audio -c:a ac3 ac3.ac3
$ff $audio -c:a eac3 eac3.eac3
$ff $audio -c:a alac alac.m4a
$ff $audio -c:a mp2 mp2.mp2
$ff $audio -c:a tta tta.tta
$ff $audio -c:a wavpack wavpack.wv
$ff $audio -c:a wmav2 -b:a 64k wmav2.wma
$ff $audio -c:a libvorbis vorbis.mka
$ff $audio -c:a flac -f ogg flac.oga
$ff $audio -c:a dca -strict -2 dts.dts
$ff $audio -ar 8000 -ac 1 -c:a libopencore_amrnb amrnb.amr

# Video
$ff $video -c:v prores_ks -pix_fmt yuv422p10le prores.mov
$ff -f lavfi -i testsrc=size=256x128:rate=25:duration=0.2 -c:v dnxhd -profile:v dnxhr_lb -pix_fmt yuv422p dnxhr.mov
$ff $video -c:v ffv1 ffv1.mkv
$ff $video -c:v huffyuv -pix_fmt yuv422p huffyuv.avi
$ff $video -c:v utvideo utvideo.avi
$ff $video -c:v msmpeg4 msmpeg4.avi
$ff $video -c:v wmv1 wmv1.wmv
$ff $video -c:v wmv2 wmv2.wmv
$ff $video -c:v h263 h263.3gp
# TorchCodec cannot count the frames of a shorter MPEG-TS file
$ff -f lavfi -i testsrc=size=128x96:rate=25:duration=1 -c:v mpeg2video mpeg2.ts
$ff $video -c:v mpeg2video mpeg2.mxf
$ff $video -c:v libvpx vp8.webm
$ff $video -c:v libtheora theora.ogv
$ff $video -c:v mjpeg mjpeg.mov
$ff $video -c:v gif gif.gif
$ff $video -c:v apng -f apng apng.apng
$ff $video -c:v rawvideo -pix_fmt yuv420p rawvideo.y4m

# Image (TorchCodec 0.17 and later decode HEIC with libheif)
$ff -f lavfi -i testsrc=size=128x96 -frames:v 1 heic.png
convert heic.png -quality 50 heic.heic
rm heic.png
