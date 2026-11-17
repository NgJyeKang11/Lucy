"""Lucy: local helper.

Serves index.html (the hand-tracking page) and exposes a tiny API that sets the
Windows master volume via pycaw. Binds to 127.0.0.1 only.

    GET  /api/volume            -> {"level": 0.0-1.0, "muted": bool}
    POST /api/volume  {"level": 0.42} | {"muted": true}   (+ "osd": true to show
                      the native Windows volume pop-up)
    POST /api/heartbeat {...}   page is alive (sent every 2 s from a Web Worker)
    GET  /api/status            -> last heartbeat + how many seconds ago
    POST /api/quit              -> stop the server

The server exits by itself once the tracking window has been closed
(no heartbeat for HEARTBEAT_TIMEOUT seconds).

Usage:
    pythonw server.py               # normal: no console, opens the app window
    python  server.py               # same, with a console for debugging
    python  server.py --no-browser  # server only
    python  server.py --tab         # open in a normal browser tab instead
    python  server.py --stay        # don't auto-exit when the window closes
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from pycaw.pycaw import AudioUtilities

HOST, PORT = "127.0.0.1", 8765
URL = f"http://{HOST}:{PORT}/"
ROOT = Path(__file__).resolve().parent
HEARTBEAT_TIMEOUT = 20  # seconds without a heartbeat before auto-exit

last_heartbeat = {"at": None, "data": None}

# --- Audio -------------------------------------------------------------------
# The default output device can change (headphones, Bluetooth, HDMI), so the
# endpoint is re-fetched every few seconds instead of once at startup.
# All COM calls happen on the single HTTP-server thread.
_endpoint = {"obj": None, "at": 0.0}


def endpoint():
    if _endpoint["obj"] is None or time.time() - _endpoint["at"] > 3:
        _endpoint.update(obj=AudioUtilities.GetSpeakers().EndpointVolume, at=time.time())
    return _endpoint["obj"]


# --- Native Windows volume pop-up ---------------------------------------------
# Windows only shows its volume overlay for the hardware volume keys, so we tap
# them: one step down + one step up (net change zero), then set the exact level.
# The order is chosen so the 0% / 100% limits can't swallow a step.
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
KEYEVENTF_KEYUP = 0x2
OSD_INTERVAL = 0.4  # seconds; don't spam keys while a gesture is in progress
_last_osd = 0.0


def tap_key(vk):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _wait_for_change(ep, old, timeout=0.2):
    """Volume keys are handled asynchronously; wait until one has taken effect."""
    end = time.time() + timeout
    while time.time() < end:
        v = ep.GetMasterVolumeLevelScalar()
        if abs(v - old) > 0.001:
            return v
        time.sleep(0.005)
    return ep.GetMasterVolumeLevelScalar()


def show_volume_osd(ep):
    """Tap one step away and back, waiting for each step, so the caller can then
    set the exact level without a late key event nudging it afterwards."""
    global _last_osd
    if time.time() - _last_osd < OSD_INTERVAL:
        return
    _last_osd = time.time()
    cur = ep.GetMasterVolumeLevelScalar()
    first, second = (VK_VOLUME_DOWN, VK_VOLUME_UP) if cur >= 0.5 else (VK_VOLUME_UP, VK_VOLUME_DOWN)
    tap_key(first)
    cur = _wait_for_change(ep, cur)
    tap_key(second)
    _wait_for_change(ep, cur)


def set_muted(want, osd):
    ep = endpoint()
    if bool(ep.GetMute()) == want:
        return
    if osd:
        tap_key(VK_VOLUME_MUTE)  # shows the pop-up with the mute icon
        for _ in range(10):      # the key is handled asynchronously
            time.sleep(0.02)
            if bool(ep.GetMute()) == want:
                return
    ep.SetMute(1 if want else 0, None)  # fallback / no pop-up


def current_state():
    ep = endpoint()
    return {"level": round(ep.GetMasterVolumeLevelScalar(), 3), "muted": bool(ep.GetMute())}


# --- HTTP --------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/volume":
            self._send(200, current_state())
        elif self.path == "/api/status":
            at = last_heartbeat["at"]
            self._send(200, {
                "page": last_heartbeat["data"],
                "seconds_since_heartbeat": None if at is None else round(time.time() - at, 1),
                **current_state(),
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            if self.path == "/api/heartbeat":
                last_heartbeat.update(at=time.time(), data=self._json_body())
                return self._send(200, {"ok": True})
            if self.path == "/api/quit":
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if self.path != "/api/volume":
                return self._send(404, {"error": "not found"})
            payload = self._json_body()
            osd = bool(payload.get("osd"))
            if "level" in payload:
                level = min(1.0, max(0.0, float(payload["level"])))
                ep = endpoint()
                # Volume keys would unmute, so never show the pop-up this way while muted.
                if osd and not ep.GetMute():
                    show_volume_osd(ep)
                ep.SetMasterVolumeLevelScalar(level, None)
            if "muted" in payload:
                set_muted(bool(payload["muted"]), osd)
            self._send(200, current_state())
        except (ValueError, TypeError) as exc:
            self._send(400, {"error": str(exc)})

    def log_message(self, *args):  # keep quiet
        pass


# --- Browser window ----------------------------------------------------------
def find_browser():
    pf, pf86, local = (os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"))
    candidates = [
        Path(pf) / "Google/Chrome/Application/chrome.exe",
        Path(pf86) / "Google/Chrome/Application/chrome.exe",
        Path(local) / "Google/Chrome/Application/chrome.exe",
        Path(pf86) / "Microsoft/Edge/Application/msedge.exe",
        Path(pf) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return next((c for c in candidates if c.is_file()), None)


def open_app_window():
    """Open the page as a standalone app window that keeps running in the background.

    It uses its own browser profile so the anti-throttling flags always apply and the
    camera permission is remembered for this app only.
    """
    browser = find_browser()
    if browser is None:
        webbrowser.open(URL)
        return
    profile = Path(os.environ.get("LOCALAPPDATA", ".")) / "GestureVolume" / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([
        str(browser),
        f"--app={URL}",
        f"--user-data-dir={profile}",
        "--window-size=420,720",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
    ])


def message_box(text):
    ctypes.windll.user32.MessageBoxW(None, text, "Lucy", 0x40)  # info icon


def existing_instance_status():
    try:
        with urllib.request.urlopen(URL + "api/status", timeout=2) as r:
            return json.load(r)
    except Exception:
        return None


# --- Main --------------------------------------------------------------------
def watchdog(server):
    """Stop the server once the tracking window has gone away."""
    while True:
        time.sleep(2)
        at = last_heartbeat["at"]
        if at is not None and time.time() - at > HEARTBEAT_TIMEOUT:
            server.shutdown()
            return


def main():
    args = sys.argv[1:]
    try:
        server = HTTPServer((HOST, PORT), Handler)
    except OSError:
        # Port taken: most likely Lucy is already running.
        status = existing_instance_status()
        if status is None:
            message_box(f"Port {PORT} is in use by another program, so Lucy can't start.")
        elif (status.get("seconds_since_heartbeat") or 99) < 5:
            message_box("Lucy is already running.\n\nLook for its window on the taskbar.")
        else:
            open_app_window()  # server alive but its window was closed
        return

    print(f"Lucy running at {URL}  (Ctrl+C to stop)")
    if "--no-browser" in args:
        pass
    elif "--tab" in args:
        webbrowser.open(URL)
    else:
        open_app_window()
    if "--stay" not in args and "--no-browser" not in args:
        threading.Thread(target=watchdog, args=(server,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
