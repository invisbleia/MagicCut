# PeakCut on this PC â€” how to clip GTA 6

Installed at `C:\peakcut`. Start it with the **PeakCut** shortcut on the desktop (or
`C:\peakcut\Start PeakCut.bat`). The dashboard opens at http://127.0.0.1:8765 â€”
no sign-in.

## 1. Get footage in

PeakCut clips **video files, links and live streams**. It does not capture your game
window, so record first:

- **PC gameplay:** OBS Studio (`winget install OBSProject.OBSStudio`), NVENC/AMF,
  60 fps, 1080p or 1440p, CQP ~18â€“20, audio track with your mic separate from game audio.
- **Console gameplay (PS5 / Xbox):** capture card into OBS, or the console's own
  share/record feature and copy the file over.
- **Someone else's stream:** paste the Twitch / Kick / YouTube link (live or VOD) â€”
  PeakCut downloads it. Only clip what you have the rights to use.
- Long sessions are fine: no length limit by default, and a one-hour video costs
  about four AI requests.

Big files go straight from the drive you already have them on: **Videos â†’ Add** â†’
"Upload a file".

## 2. Make it behave like GTA 6

PeakCut recognises the game from the creator's Setup `game` field, then the stream or
video title, then the file name. Set it once and it stops guessing:

- Creator â†’ Setup â†’ **game**: `Grand Theft Auto VI` (or `GTA 6`)
- Then every clip gets `#GTA6 #GTA6Game #ViceCity #RockstarGames #GTA6Launch`, the
  hook is written from what the streamer said at that moment, and the AI is told to
  look for plays, deaths, glitches, discoveries and reactions.

Settings that suit a launch-night gaming stream (`GAMING.md`):

```json
{ "style": "hype", "layout": "gameplay", "min_len": 15, "max_len": 60,
  "max_clips": 6, "min_score": 65, "buffer_min": 10, "live_per_hour": 4,
  "ai_every_min": 3, "ai_only_on_spike": true }
```

- `layout: gameplay` fills the 1080x1920 frame with the game and puts the facecam in
  the top corner. It finds the webcam by its unmoving border (about 1â€“4 s per video)
  and falls back to a plain centre crop when there is none.
- `min_score` 65 instead of 80: launch night is chaotic, so a tighter bar means fewer
  clips.
- No AI key at all still works â€” clips are then picked by loudness, with no titles.

## 3. Live clipping

Creator â†’ Live: give the channel, and PeakCut records into a rolling buffer and clips
while the stream is still running, using loudness, chat activity and the transcript.
Chat spikes are counted in **people**, not messages, so one person spamming emotes
does not fake a reaction.

## 4. A 1080p clip in one click: the GTA 6 preset

The **GTA 6 preset** chip above the box sets hype captions, the gameplay layout, 1080p and the
hook on, which is the short list in `GAMING.md` in one press. The **Techno Gamerz preset** is the
Minecraft/GTA version: gameplay + facecam, hype captions, 1080p, hook on, 20 clips of 15-45 s.
**How many** goes up to 50 clips per video. Then **Make clips**.

Two switches on the clip itself:

- **Generate captions** â€” on/off.
- **Hook text** â€” the ALL-CAPS line that sits across the top of the clip. Off, the clip is clean
  picture with captions only. Both are also in the clip dialog, so an existing clip can be
  re-made without its heading (open the clip â†’ untick â†’ *Save and re-make clip*).

Hindi and Urdu speech is written in Roman letters (Hinglish) in the captions automatically.

## 5. Render core: the graphics card does the encoding

**Options â†’ Render core** lists what this computer can actually do, and Auto is the default:

| Choice | What it means |
|---|---|
| Auto | The best hardware here, CPU when there is none |
| NVIDIA Â· NVENC | A Tesla T4 (Colab) or a GeForce card: 3â€“10x faster than the CPU |
| Intel Â· QuickSync / AMD Â· AMF | The integrated or discrete card on a PC |
| CPU | `libx264`, always works, slowest |

The list is measured, not guessed: PeakCut asks ffmpeg to encode three frames with each encoder.
A card that claims to support one but fails costs one fallback, never a broken clip. **Scan again**
looks for a card added since the server started.

On Colab, `deploy/colab.sh` installs an ffmpeg that has NVENC (Colab's own usually does not) â€” see
`COLAB.md`. A 60-second 1080x1920 clip is roughly 5â€“15 s on the T4 against a minute or more on the
CPU.

## 6. The two AI routes on this PC

Set in the dashboard, **Settings â†’ AI** (what is saved there wins over `.env`, which is
where both routes are written down at `C:\peakcut\.env`):

| Route | What to do |
|---|---|
| Google Gemini | Key from https://aistudio.google.com/apikey â†’ pick **Gemini** â†’ paste â†’ **Find models** â†’ **Save and test** |
| Local | Needs something on this machine speaking the OpenAI chat format: Ollama (`winget install Ollama.Ollama`, `ollama pull llama3.1`) â†’ pick **Ollama**; or LM Studio / llama.cpp / your own proxy â†’ pick **Custom** and give the `/v1` address |

Speech-to-text never uses the AI service: it runs locally on the Parakeet model in
`C:\peakcut\data\models` (~480 MB, already downloaded).

## 7. Where things live, and updating

- Everything PeakCut keeps â€” videos, clips, recordings, the database, the speech
  model â€” is in `C:\peakcut\data`. **Settings â†’ Storage** shows the size, opens the
  folder, and moves it to another drive (E: has more room) at the next start.
- Update: the dashboard shows a notice when a newer version exists. By hand:
  `cd C:\peakcut && git pull && .venv\Scripts\pip install -r requirements.txt`,
  then restart. `.env`, keys and clips are not touched.
- Health check: http://127.0.0.1:8765/healthz, and `/api/status` shows whether ffmpeg
  and the AI are ready.

