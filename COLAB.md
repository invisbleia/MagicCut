# PeakCut on Colab with a Tesla T4

The T4 is used for the **video encode**. Before this, every clip was made by the CPU (`libx264`)
even on Colab, because PeakCut only knew how to ask Intel's QuickSync for hardware encoding.
Now it asks ffmpeg what the machine really has — NVENC on the T4, QuickSync / AMF on a PC — and
uses that, falling back to the CPU only when there is nothing else.

Your notebook clones `haziqahmedqasmi/PeakCut` into Drive once, so the new code reaches Colab only
after a `git push` from your GitHub account. Then the two cells below do the rest: the install cell
puts an ffmpeg **with NVENC** on the PATH (Colab's own build usually has none), and the start cell
writes the fresh ngrok URL into `.env` every run — or keeps one fixed URL if you give it your free
static ngrok domain.

## 0. Getting the new code into the clone

The notebook clones your GitHub repo into Drive, so the clone only changes when the repo does. Either:

- **Push from your own GitHub account** (the account that owns `haziqahmedqasmi/PeakCut`):
  ```
  cd C:\peakcut
  git add -A
  git commit -m "GPU render core (NVENC), hook text switch, readable selected states"
  git push
  ```
  Cell 1 then does `git pull --ff-only` on every run.
- **Or upload `peakcut-gpu.patch`** (in `C:\peakcut`) to Drive, then once in Colab:
  ```
  !cd /content/drive/MyDrive/peakcut && git apply /content/drive/MyDrive/peakcut-gpu.patch
  ```

## Cell 1 — dependencies (mount, pull, ffmpeg with NVENC, wheels)

```python
# 1. Mount Google Drive first to ensure we can clone into it
from google.colab import drive
import os, subprocess

drive.mount('/content/drive')

REPO_PATH = '/content/drive/MyDrive/peakcut'

# 2. Clone once; on later runs just update it (your new GPU code arrives this way)
if not os.path.exists(REPO_PATH):
    print(f"Cloning PeakCut into Google Drive: {REPO_PATH}...")
    !git clone https://github.com/haziqahmedqasmi/peakcut "{REPO_PATH}"
else:
    print(f"Already cloned at {REPO_PATH}, updating...")
    !cd "{REPO_PATH}" && git pull --ff-only

# 3. Is there really a GPU?
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                      "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
      or "No NVIDIA GPU: Runtime > Change runtime type > T4 GPU")

# 4. ffmpeg that HAS NVENC. Colab's apt ffmpeg usually does not, and without it every clip
#    silently renders on the CPU. Static build from johnvansickle.com has NVENC + NVDEC.
enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
if "h264_nvenc" not in enc:
    print("Installing a static ffmpeg build with NVENC...")
    !curl -fsSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ff.tar.xz
    !tar -xJf /tmp/ff.tar.xz -C /tmp
    !install -m 0755 /tmp/ffmpeg-*-static/ffmpeg /usr/local/bin/ffmpeg
    !install -m 0755 /tmp/ffmpeg-*-static/ffprobe /usr/local/bin/ffprobe
enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
print("NVENC:", "yes" if "h264_nvenc" in enc else "NO (clips will use the CPU)")
# one real probe of the card, the same three-frame test PeakCut runs
probe = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=320x240:d=0.2:r=30", "-frames:v", "3",
                        "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, text=True)
print("NVENC encode test:", "works" if probe.returncode == 0 else "failed: " + probe.stderr.strip()[-300:])

# 5. Dependencies
!pip install -q -r "{REPO_PATH}/requirements.txt"
!pip install -q pyngrok

# 6. Speech: CUDA wheel instead of the CPU one
print("Forcing installation of CUDA 12-optimized sherpa-onnx wheel...")
!pip uninstall -y sherpa-onnx
!pip install sherpa-onnx -f https://k2-fsa.github.io/sherpa/onnx/cuda.html
```

## Cell 2 — start the server (fresh URL, or one fixed URL)

`ngrok.connect(8765)` gives a new address on every run, which is why the URL keeps changing. Two
things here: the server always writes the **current** address into `.env` before it starts, and if you
copy your free static domain from the ngrok dashboard into a Colab secret named `NGROK_DOMAIN`
(for example `quiet-fox-123.ngrok-free.app`), the address never changes again.

```python
import subprocess, time, os, sys
from pyngrok import ngrok, exception
from google.colab import userdata

# Token from Colab Secrets (Tools > Secrets), name: NGROK_AUTH_TOKEN
try:
    NGROK_TOKEN = userdata.get('NGROK_AUTH_TOKEN')
except Exception:
    NGROK_TOKEN = os.environ.get('NGROK_AUTH_TOKEN', '')
if not NGROK_TOKEN:
    raise ValueError("Add NGROK_AUTH_TOKEN to Colab Secrets (Tools > Secrets).")

try:
    ngrok.set_auth_token(NGROK_TOKEN)
except exception.PyngrokNgrokError as e:
    if "already set" not in str(e):
        raise

# Optional: one permanent URL. Copy the free static domain from dashboard.ngrok.com
# (Domains) and save it as a secret named NGROK_DOMAIN.
try:
    STATIC_DOMAIN = userdata.get('NGROK_DOMAIN') or ""
except Exception:
    STATIC_DOMAIN = ""

ngrok.kill()                       # a dead tunnel from the last run would hold the port/domain
public_url = (ngrok.connect(8765, domain=STATIC_DOMAIN) if STATIC_DOMAIN else ngrok.connect(8765)).public_url
print(f"Ngrok tunnel: {public_url}")

repo_path = '/content/drive/MyDrive/peakcut'
if not os.path.exists(repo_path):
    raise FileNotFoundError(f"Repository not found at {repo_path}. Run the install cell first.")

# PeakCut reads .env before it starts, so the address must be written first.
DATA_DIR = '/content/drive/MyDrive/peakcut_data'
os.makedirs(DATA_DIR, exist_ok=True)
env_content = f"""
PEAKCUT_DATA={DATA_DIR}
PEAKCUT_ACCOUNTS=1
PEAKCUT_HOST=0.0.0.0
PEAKCUT_PUBLIC_URL={public_url}
PEAKCUT_ASR_PROVIDER=cuda
"""
with open(os.path.join(repo_path, '.env'), 'w') as f:
    f.write(env_content.strip())
print("Wrote .env with the current public URL and CUDA speech.")

env_config = os.environ.copy()
env_config["CUDA_VISIBLE_DEVICES"] = "0"
env_config["PEAKCUT_ASR_PROVIDER"] = "cuda"

print("Starting PeakCut in the background from:", repo_path)
process = subprocess.Popen(
    ["python", "-m", "studio.server"], cwd=repo_path,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env_config,
)

# Wait until it answers, then say which encoder it picked.
import json, urllib.request
for _ in range(30):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=3) as r:
            st = json.load(r)
        print("Render core:", st.get("render", {}).get("auto", "?"),
              "| cards:", ", ".join(st.get("render", {}).get("gpus", [])) or "none")
        break
    except Exception:
        time.sleep(1)

print(f"\nPeakCut is running: {public_url}\n")

try:
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(line.strip()); sys.stdout.flush()
except KeyboardInterrupt:
    print("\nStopped watching logs. The server is still running.")
```

## What changed for the GPU

- `studio/hw.py` (new): asks ffmpeg to encode three frames with NVENC / QuickSync / AMF /
  VideoToolbox and remembers what worked. A card that claims an encoder but fails costs one clip,
  never every clip.
- `studio/render.py`: picks the encoder per clip — Auto = the best hardware here, CPU if none.
- `studio/jobs.py`, `studio/creators.py`, `studio/live.py`: the options `render` and `hook_text`
  travel with every job and clip.
- `web/index.html`: **Options → Render core** shows what this machine can do (greyed out cards carry
  the reason on hover), plus the **Hook text** switch and the **GTA 6 preset** chip.
- `studio/config.py`: `PEAKCUT_BASE_URL` is accepted as another name for `PEAKCUT_PUBLIC_URL`, so an
  older `.env` keeps working.

## Checking it is really on the T4

1. Dashboard → **Options → Render core** should read `Auto (NVENC · Tesla T4)`.
2. Make one 1080p clip: roughly **5–15 s** for 60 seconds of output on the T4, a minute or more on
   the CPU.
3. `!nvidia-smi` in Colab shows the `ffmpeg` process on the card while a clip renders.

## Things Colab does not change

- Free Colab disconnects after a few hours and the machine is wiped: the clone and `peakcut_data`
  survive only because they are on Drive. Keep them there.
- Live clipping needs a server that stays up; a dropped runtime ends the recording.
- `PEAKCUT_ASR_PROVIDER=cuda` needs the CUDA sherpa wheel from cell 1. If startup complains about
  CUDA, remove that line and transcription falls back to the CPU while the encode stays on the T4.
