"""Which video encoders this computer really has.

Making a clip is an ffmpeg encode, and most graphics cards carry a hardware encoder: NVIDIA's
NVENC (a Colab T4, a gaming PC), Intel's QuickSync, AMD's AMF, Apple's VideoToolbox. They are
several times faster than the CPU's x264 and leave the processor free for the transcript and the
AI. PeakCut cannot ask a card what it is, so it asks ffmpeg instead: a three-frame encode of a
black picture with that encoder — it either works on this machine or it does not. The answer is
kept for a couple of minutes, so a dashboard polling every few seconds costs nothing.

The job's option `render` decides: "auto" (the best hardware here, CPU when there is none), "cpu",
"gpu" (any hardware), or one encoder by name. They are tried in that order, and a broken one is
remembered, so a card that claims NVENC but cannot open it costs one failed clip, never every clip.
"""
import re
import shutil
import subprocess
import sys
import threading
import time

CACHE_SECONDS = 120
_lock = threading.Lock()
_cache = {"at": 0.0, "info": None, "broken": set()}

CPU = {"id": "cpu", "label": "CPU", "kind": "cpu", "gpu": "", "available": True,
       "detail": "libx264 · works everywhere"}

# id, short name, the ffmpeg arguments that ask for it, words that name its maker in a card's name
ENCODERS = (
    ("nvenc", "NVENC", ["-c:v", "h264_nvenc"], ("nvidia", "geforce", "quadro", "tesla", "rtx", "gtx")),
    ("qsv", "QuickSync", ["-pix_fmt", "nv12", "-c:v", "h264_qsv"], ("intel",)),
    ("amf", "AMF", ["-c:v", "h264_amf"], ("amd", "radeon")),
    ("videotoolbox", "VideoToolbox", ["-c:v", "h264_videotoolbox"], ("apple",)),
)
IDS = ("auto", "cpu", "gpu") + tuple(e[0] for e in ENCODERS)


def _run(args, timeout=25):
    """Run a program and return (return code, its output). A missing program is code 127, not an exception."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, ""
    except Exception as e:  # noqa: BLE001 - a timeout or a refused card: the text is what gets shown
        return 1, str(e)


def _probe(args) -> bool:
    """Can this machine encode three frames with that encoder right now?"""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    code, _out = _run([ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi",
                       "-i", "color=c=black:s=320x240:d=0.2:r=30", "-frames:v", "3",
                       *args, "-f", "null", "-"])
    return code == 0


def _gpu_names():
    """What the cards are called, best source first: NVIDIA's own tool, then Windows, then lspci."""
    names = []
    smi = shutil.which("nvidia-smi")
    if smi:
        code, out = _run([smi, "--query-gpu=name,memory.total", "--format=csv,noheader"])
        if code == 0:
            for line in out.splitlines():
                name = line.split(",")[0].strip()
                if name:
                    names.append(name)
    if not names and sys.platform == "win32":
        ps = shutil.which("powershell") or "powershell"
        code, out = _run([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                          "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"])
        if code == 0:
            names = [l.strip() for l in out.splitlines() if l.strip()]
    if not names and sys.platform.startswith("linux") and shutil.which("lspci"):
        code, out = _run(["lspci"])
        if code == 0:
            names = [re.sub(r"^[^:]*:\s*", "", l).strip() for l in out.splitlines() if "VGA" in l or "3D controller" in l]
    return [n for n in names if "microsoft basic" not in n.lower()][:6]


def _maker_card(names, vendors):
    """The card that belongs to an encoder's maker, e.g. the name with "nvidia" in it for NVENC."""
    for n in names:
        low = n.lower()
        if any(v in low for v in vendors):
            return n
    return ""


def detect(force: bool = False) -> dict:
    """The encoders that really work here, the cards found, and which one "auto" would use."""
    with _lock:
        if not force and _cache["info"] and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["info"]
        names = _gpu_names()
        encoders = []
        for eid, short, args, vendors in ENCODERS:
            works = eid not in _cache["broken"] and _probe(args)
            card = _maker_card(names, vendors)
            encoders.append({"id": eid, "label": short, "kind": "gpu", "gpu": card,
                             "available": works, "detail": (card or short) if works else "not found"})
        encoders.append(dict(CPU))
        best = next((e["id"] for e in encoders if e["available"] and e["kind"] == "gpu"), "cpu")
        info = {"encoders": encoders, "gpus": names, "auto": best, "checked": round(time.time()),
                "ffmpeg": shutil.which("ffmpeg") or ""}
        _cache.update(at=time.time(), info=info)
        return info


def candidates(choice: str = "auto") -> list:
    """The encoders to try, in order, for one clip: what was asked for first, then the rest, CPU last."""
    info = detect()
    here = [e["id"] for e in info["encoders"] if e["available"] and e["id"] != "cpu"]
    choice = (choice or "auto").strip().lower()
    if choice == "cpu":
        return ["cpu"]
    wanted = [choice] if choice in here else []
    rest = [e for e in here if e not in wanted]
    return wanted + rest + ["cpu"]


def mark_broken(eid: str):
    """An encoder that failed is not asked again until the next restart (or a rescan)."""
    if eid == "cpu":
        return
    with _lock:
        _cache["broken"].add(eid)
        if _cache["info"]:
            for e in _cache["info"]["encoders"]:
                if e["id"] == eid:
                    e["available"] = False
                    e["detail"] = "failed, using the next one"


def summary() -> dict:
    """What the dashboard needs: the cards, the encoders that work, and what Auto picked."""
    info = detect()
    return {"auto": info["auto"], "gpus": info["gpus"], "checked": info["checked"],
            "encoders": [{"id": e["id"], "label": e["label"], "kind": e["kind"], "gpu": e["gpu"],
                          "detail": e["detail"], "available": e["available"]} for e in info["encoders"]]}


def explain(choice: str = "auto") -> str:
    """One plain sentence for a person: what this machine will encode with."""
    info = detect()
    if choice == "cpu":
        return "Rendering on the CPU (libx264)."
    if choice in ("auto", "gpu"):
        pick = info["auto"]
    else:
        pick = choice
    name = next((f"{e['label']} · {e['gpu']}" if e["gpu"] else e["label"] for e in info["encoders"]
                 if e["id"] == pick), pick)
    return f"Rendering with {name}." if pick != "cpu" else "No hardware encoder found: rendering on the CPU."
