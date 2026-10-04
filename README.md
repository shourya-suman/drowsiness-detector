# Driver Drowsiness & Distraction Alert

A safety camera that watches a driver's face, tracks blink frequency and head
orientation, and sounds an alarm if the eyes stay closed or the head turns
away from the road for more than **2 seconds**.

Two versions are included:

| Version | Works on | Setup |
|---|---|---|
| **Web app** (`index.html`) | **Any device with a browser** — phone, tablet, laptop | Open the GitHub Pages link, allow camera. Zero install. |
| **Python app** (`drowsiness_detector.py`) | Laptops / desktops with a webcam, runs fully offline | `pip install -r requirements.txt`, then `python drowsiness_detector.py` |

Both use the same detection logic: Eye Aspect Ratio (EAR) for eye closure and
landmark-geometry head pose (yaw/pitch) for distraction, with automatic
calibration to your seated position.

**Privacy:** the web app processes video entirely in your browser — no video,
images, or data ever leave your device. The Python app likewise runs 100%
locally.

---

## Run the web app (any device)

1. Publish this repo to GitHub Pages (see below), or serve it locally:
   `python -m http.server 8000` and open `http://localhost:8000`.
2. Open the page and press **Start camera**.
3. Look straight ahead for ~3 seconds while it calibrates.
4. The alarm sounds if eyes stay closed or the head turns away > 2 s.

Controls: **R** = recalibrate after changing seating position.

> Camera access requires a secure context, so use GitHub Pages (https) or
> localhost — opening the file directly via `file://` will not grant camera
> permission in most browsers.

### Publish to GitHub Pages

1. Push this repository to GitHub.
2. Repo **Settings → Pages** → Source: **Deploy from a branch** → branch
   `main`, folder `/ (root)` → **Save**.
3. Your app goes live at
   `https://<your-username>.github.io/<repo-name>/` in 1–2 minutes.
4. Open that URL on any phone or laptop, allow camera, and go.

---

## Run the Python app (laptop)

```bash
pip install -r requirements.txt
python drowsiness_detector.py
```

- Look straight at the camera for the first ~45 frames to calibrate.
- **C** = recalibrate · **Q** = quit.
- If the wrong camera opens, change `CAMERA_INDEX` at the top of the script
  (0 = default, 1 = second camera, …).
- Linux note: if the alarm is silent, install SDL audio:
  `sudo apt install libsdl2-mixer-2.0-0`.

### On Windows

1. Install **64-bit Python 3.11 or 3.12** from
   [python.org/downloads/windows](https://www.python.org/downloads/windows/).
   On the very first installer screen tick **"Add python.exe to PATH"**.
2. Open this folder in PowerShell — right-click the folder while holding
   **Shift** → **Open PowerShell window here** — and run:

   ```powershell
   py -m pip install --upgrade pip
   py -m pip install -r requirements.txt
   py drowsiness_detector.py
   ```

   `py` is the Windows Python launcher; if it isn't recognised, use `python`
   in place of `py`.

3. Let Windows give the script your webcam: **Settings → Privacy & security →
   Camera → "Let desktop apps access your camera"** must be **On**.

First run takes a minute or two (MediaPipe and OpenCV are large downloads).
After that: a camera window opens, it says `Calibrating - look straight ahead
(0/45)` — keep still and look at the screen — then `Monitoring`.

#### Windows troubleshooting

| You see | What to do |
|---|---|
| Black window, or a window that takes ages to appear | The script already tries the DirectShow camera backend first on Windows. If it still misbehaves, set `CAMERA_INDEX = 1` at the top of the script. |
| `Could not open camera 0` | Only one app can use the webcam at a time — close Teams, Zoom, Meet or the Camera app, then re-run. Also check the privacy setting in step 3. |
| `py : The term 'py' is not recognized` | Re-run the Python installer and tick **Add python.exe to PATH**, or use `python` instead of `py`. |
| MediaPipe or OpenCV fails to install | You have 32-bit Python, or a version newer than MediaPipe supports. Install **64-bit Python 3.11 or 3.12**. |
| No alarm sound | Windows has no output device selected or the volume is muted — the script prints `Audio alarm unavailable` and keeps watching silently. |
| pip stalls or errors on a work laptop | Try `py -m pip install -r requirements.txt --user`. |

> The browser version still needs an **https** or **localhost** address —
> double-clicking `index.html` (a `file://` path) will not grant camera access
> in Chrome or Edge.

---

## How it works

- **Eye closure** — MediaPipe Face Mesh provides 478 face landmarks; the Eye
  Aspect Ratio (vertical eye opening ÷ horizontal eye width) drops sharply
  when the eyes close. Alarms when below 72% of your calibrated baseline for
  2+ seconds (covers micro-sleep / nodding off).
- **Distraction** — the nose tip's position relative to the face's centre,
  normalised by face size, gives scale-invariant yaw/pitch estimates. Alarms
  when your head pose leaves the calibrated tolerance for 2+ seconds.
- **Calibration** — the first ~3 s (web) / 45 frames (Python) establish your
  open-eye EAR baseline and neutral head pose. Recalibrate with **R** (web)
  or **C** (Python) whenever you change seating position.

### Tuning

All thresholds live at the top of each app (`CLOSED_TIME_LIMIT_S`,
`AWAY_TIME_LIMIT_S`, `CLOSED_RATIO`, `YAW_TOLERANCE`, `PITCH_TOLERANCE`).

⚠️ **Disclaimer:** this is a driver-assistance demo, not a certified safety
system. Never rely on it as your only safeguard against drowsy driving.
