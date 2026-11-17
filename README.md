# Lucy: Gesture Volume Control for Windows

Lucy is a gesture volume control app: change your Windows volume with hand gestures, using just your laptop webcam.

Pinch or spread your thumb and index finger to set the volume, hold still to lock it, and make a fist to mute. It works system-wide (YouTube, Spotify, games…), keeps running while minimised, and shows the native Windows volume pop-up.

## Gestures

| Gesture | What it does |
| --- | --- |
| Curl your middle, ring and pinky fingers, then pinch or spread thumb and index | Set the volume |
| Hold your fingers still until the ring fills and turns amber | Lock the current value; small movements are then ignored |
| Move fingers clearly further apart or closer while locked | Unlock and adjust again |
| Open hand, or move it out of view | Leave the volume where it is |
| Make a fist and hold for about 1 second | Mute / unmute (volume is frozen while muted) |

## Requirements

- Windows 10 or 11
- Python 3.10+
- Google Chrome or Microsoft Edge
- A webcam (a built-in laptop camera is fine)

## Setup

```powershell
git clone https://github.com/NgJyeKang11/Lucy.git
cd Lucy
powershell -ExecutionPolicy Bypass -File setup.ps1
```

This creates a Python environment in `%USERPROFILE%\.venvs\gesture-volume`, installs the dependencies and adds **Lucy** shortcuts to the Start menu and desktop. On first launch, allow camera access in the Lucy window.

Optional:

```powershell
powershell -ExecutionPolicy Bypass -File install_shortcuts.ps1 -Startup   # start with Windows
powershell -ExecutionPolicy Bypass -File install_shortcuts.ps1 -Remove    # remove shortcuts
```

## Usage

- Launch **Lucy** from the Start menu or desktop. A small window opens with the camera view.
- Minimise it; it keeps working in the background.
- **Gesture control on** pauses or resumes tracking; **Show Windows volume pop-up** toggles the native overlay.
- **Quit** (or closing the window) stops everything.
- The **Calibration** section lets you tune the pinch/spread range, smoothing, volume step, lock timing and more. Settings are remembered.
- `start.bat` runs the same app with a console window, for troubleshooting.

## How it works

- **`index.html`**: hand tracking runs in the browser with [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) (WebAssembly). The thumb–index distance, divided by hand size so it doesn't depend on how far you are from the camera, is mapped to a volume level. Pose debouncing, smoothing, step snapping, a hold-to-lock and a release rollback keep it from jumping around.
- **`server.py`**: a small local server (127.0.0.1 only) that sets the Windows master volume through [pycaw](https://github.com/AndreMiras/pycaw). It opens the page as a Chrome/Edge app window with background throttling disabled, and shuts down when that window closes.
- To show the native volume pop-up, the server taps the volume keys one step down and back up, then sets the exact level.

Why a browser and not OpenCV in Python? On PCs with **Smart App Control** enabled, Windows blocks OpenCV's unsigned native libraries. Running the tracking in the browser avoids that without turning off a security feature.

## Privacy

Camera frames are processed locally in the browser and never leave your computer. The MediaPipe library and model are downloaded from public CDNs (jsDelivr, Google Cloud Storage) when the window loads. The volume server only listens on `127.0.0.1`.

## License

[MIT](LICENSE)
