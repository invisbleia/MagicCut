#!/usr/bin/env bash
# PeakCut on a Google Colab GPU runtime (Tesla T4).
#
#   !git clone https://github.com/<you>/PeakCut.git /content/peakcut
#   %cd /content/peakcut
#   !bash deploy/colab.sh
#
# What it does: checks the GPU, puts an ffmpeg that has NVENC on the PATH (Colab's own build often
# does not), installs the Python requirements, and starts the server. PeakCut finds the T4 by itself:
# Settings > Options > Render core shows "Auto (NVENC)" once it is up.
set -euo pipefail

echo "== GPU =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true
else
  echo "No NVIDIA GPU. In Colab: Runtime > Change runtime type > T4 GPU, then run this again."
fi

echo "== ffmpeg with NVENC =="
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_nvenc; then
  echo "already there: $(ffmpeg -version | head -n1)"
else
  apt-get -qq update >/dev/null 2>&1 || true
  apt-get -qq install -y --no-install-recommends xz-utils curl >/dev/null 2>&1 || true
  echo "installing a static ffmpeg build (has NVENC and NVDEC)..."
  curl -fsSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ff.tar.xz
  tar -xJf /tmp/ff.tar.xz -C /tmp
  install -m 0755 /tmp/ffmpeg-*-static/ffmpeg /usr/local/bin/ffmpeg
  install -m 0755 /tmp/ffmpeg-*-static/ffprobe /usr/local/bin/ffprobe
fi
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_nvenc; then
  echo "NVENC: yes — clips encode on the T4"
else
  echo "NVENC: NO — clips will use the CPU (slower, everything still works)"
fi

echo "== Python =="
python -m pip -q install --upgrade pip
python -m pip -q install -r requirements.txt

# On Colab the app is reached through ngrok, not from this machine, so it must listen on all
# addresses and have sign-in on (PeakCut refuses to expose itself without accounts).
export PEAKCUT_HOST="${PEAKCUT_HOST:-0.0.0.0}"
export PEAKCUT_ACCOUNTS="${PEAKCUT_ACCOUNTS:-1}"
export PEAKCUT_PORT="${PEAKCUT_PORT:-8765}"
# Faster transcription on the same card. Leave it unset if sherpa-onnx complains about CUDA.
# export PEAKCUT_ASR_PROVIDER=cuda

echo "== starting PeakCut on ${PEAKCUT_HOST}:${PEAKCUT_PORT} =="
echo "   open your ngrok address (see COLAB.md), sign in, then Options > Render core"
python -m studio.server
