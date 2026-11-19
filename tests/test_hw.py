"""The render core: which encoder a clip is made with, the fallback when a card is not there, and the switch
for the big hook text.

Runs against the code directly, with its own empty data folder, and makes real clips with ffmpeg."""
import os, sys, tempfile, subprocess
from pathlib import Path
os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="pc-hw-")
sys.path.insert(0, ".")
from studio import hw, jobs, render

fails = []
def check(n, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"   got {got!r}")); ok or fails.append(n)


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


# ---- what the machine says it can do
info = hw.detect()
ids = [e["id"] for e in info["encoders"]]
check("the CPU encoder is always there", any(e["id"] == "cpu" and e["available"] for e in info["encoders"]), True)
check("every encoder is listed with a name and a state", all(e.get("label") and isinstance(e.get("available"), bool) for e in info["encoders"]), True)
check("auto names an encoder that exists", info["auto"] in ids, True)
check("the cards are named, not guessed", isinstance(info["gpus"], list), True)
check("choosing the CPU tries only the CPU", hw.candidates("cpu"), ["cpu"])
auto = hw.candidates("auto")
check("auto ends on the CPU", auto[-1], "cpu")
check("auto tries each encoder once", len(auto) == len(set(auto)), True)
check("asking for the GPU keeps the CPU as the last resort", hw.candidates("gpu")[-1], "cpu")
check("a nonsense choice still has somewhere to go", hw.candidates("banana")[-1], "cpu")
check("the summary the dashboard reads has the same shape", sorted(hw.summary()) == ["auto", "checked", "encoders", "gpus"], True)
check("the summary explains itself in one line", isinstance(hw.explain("auto"), str) and len(hw.explain("auto")) > 10, True)

# ---- the two new options
check("hook text is on unless it is switched off", jobs.DEFAULTS["hook_text"], True)
check("the render core defaults to auto", jobs.DEFAULTS["render"], "auto")
check("hook text can be turned off", jobs.clean_options({"hook_text": False}), {"hook_text": False})
check("the render core is kept", jobs.clean_options({"render": "cpu"}), {"render": "cpu"})
check("an unknown render core becomes auto", jobs.clean_options({"render": "banana"}), {"render": "auto"})
check("a non-boolean hook text is refused", raises(lambda: jobs.clean_options({"hook_text": "no"})), True)
check("a creator remembers both", ("hook_text" in jobs.creators.DEFAULTS and jobs.creators.DEFAULTS["render"] == "auto"), True)

# ---- a real clip, with the heading on and off
src_dir, out = Path(tempfile.mkdtemp(prefix="pc-hw-src-")), Path(tempfile.mkdtemp(prefix="pc-hw-out-"))
src = src_dir / "src.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
base = {"start": 0.0, "end": 3.0, "style": "hype", "layout": "crop", "captions": False, "hook": "THE TEST",
        "hook_text": True, "render": "cpu"}

render.render_clip(src, out, "withhook", dict(base), [], 640, 360)
ass = (out / "withhook.ass").read_text(encoding="utf-8")
check("the heading is drawn when it is on", "THE TEST" in ass, True)
check("the clip is made", (out / "withhook.mp4").is_file(), True)
check("the clip is vertical 1080x1920", subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
      "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out / "withhook.mp4")],
      capture_output=True, text=True).stdout.strip(), "1080,1920")

render.render_clip(src, out, "nohook", dict(base, hook_text=False), [], 640, 360)
ass2 = (out / "nohook.ass").read_text(encoding="utf-8")
check("the heading is left out when it is off", "THE TEST" not in ass2, True)
check("no heading line is drawn at all", "Dialogue: 4," not in ass2, True)
check("the rest of the clip is still made", (out / "nohook.mp4").is_file(), True)

# ---- a card that is not there costs nothing: the next encoder makes the clip
render.render_clip(src, out, "forced", dict(base, render="nvenc", hook_text=False), [], 640, 360)
check("a missing GPU still renders the clip", (out / "forced.mp4").is_file(), True)

import shutil
shutil.rmtree(src_dir, ignore_errors=True); shutil.rmtree(out, ignore_errors=True)
if fails:
    print("FAILED: " + ", ".join(fails)); sys.exit(1)
