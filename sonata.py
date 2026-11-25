import os
import sys

# Ensure no console window issues
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import glob
import time
import json
import atexit
import ctypes
import threading
import subprocess
import numpy as np
import pyaudiowpatch as pyaudio
from PIL import Image, ImageDraw
import pystray

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "enabled": True,
    "mode": "punchy",
    "sensitivity": 1.2,
    "idle_level": 2,
    "hold_time_ms": 75,
    "min_interval_ms": 55,
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass


class VantageBacklight:
    LEVELS = {0: "Off", 1: "Level_1", 2: "Level_2"}

    def __init__(self, min_interval_ms=55, hold_time_ms=75):
        self.min_interval = min_interval_ms / 1000.0
        self.hold_time = hold_time_ms / 1000.0
        self.current_level = 2
        self.last_change = 0.0
        self.last_bright = 0.0
        self.lock = threading.Lock()
        self.ps_proc = None

        self._start_backend()

    def _start_backend(self):
        # Locate Vantage DLLs: bundled first, then dynamic Vantage system addin path
        bundled = os.path.join(APP_DIR, "lenovo_dlls")
        if os.path.exists(os.path.join(bundled, "IdeaNotebookAddin.dll")):
            contract = os.path.join(bundled, "KeyboardContract.dll")
            addin = os.path.join(bundled, "IdeaNotebookAddin.dll")
            newton = os.path.join(bundled, "Newtonsoft.Json.dll")
        else:
            vantage_matches = sorted(glob.glob(r"C:\ProgramData\Lenovo\Vantage\Addins\IdeaNotebookAddin\*"), reverse=True)
            vantage_dir = vantage_matches[0] if vantage_matches else ""
            contract = os.path.join(vantage_dir, "KeyboardContract.dll")
            addin = os.path.join(vantage_dir, "IdeaNotebookAddin.dll")
            newton = os.path.join(vantage_dir, "Newtonsoft.Json.dll")

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE

        self.ps_proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        script = f"""
[System.Reflection.Assembly]::LoadFrom('{contract}') | Out-Null
[System.Reflection.Assembly]::LoadFrom('{newton}') | Out-Null
$asm = [System.Reflection.Assembly]::LoadFrom('{addin}')
$agentType = $asm.GetType('IdeaNotebookAddin.IdeaNotebookAgent')
$agent = $agentType.GetMethod('GetInstance', [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Static).Invoke($null, $null)
$setBacklightMethod = $agentType.GetMethods() | Where-Object {{ $_.Name -eq 'SetBacklight' -and $_.GetParameters().Count -eq 2 }}

function Set-KbdBacklight([string]$level) {{
    try {{
        $status = $agentType.GetMethod('GetBacklightStatus', [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Instance).Invoke($agent, $null)
        $list = $status.GetType().GetProperty('List').GetValue($status)
        $items = $list.GetType().GetProperty('Items').GetValue($list)
        foreach ($item in $items) {{
            $keyVal = $item.GetType().GetProperty('key').GetValue($item)
            if ($keyVal -eq 'KeyboardBacklightStatus') {{
                $item.GetType().GetProperty('value').SetValue($item, $level)
            }}
        }}
        $req = New-Object Lenovo.Modern.Contracts.Keyboard.KeyboardSettingsRequest
        $req.List = $list
        $jsonPayload = [Newtonsoft.Json.JsonConvert]::SerializeObject($req)
        $resp = $setBacklightMethod.Invoke($agent, @($jsonPayload, $null))
        Write-Output "OK:$level"
    }} catch {{
        Write-Output "ERR"
    }}
}}
"""
        self.ps_proc.stdin.write(script + "\n")
        self.ps_proc.stdin.flush()

    def set_level(self, level, force=False):
        level = max(0, min(2, int(level)))
        now = time.monotonic()
        with self.lock:
            if level == self.current_level and not force:
                return
            if not force:
                if self.current_level == 2 and level < 2:
                    if (now - self.last_bright) < self.hold_time:
                        return
                if (now - self.last_change) < self.min_interval:
                    return

            try:
                self.ps_proc.stdin.write(f"Set-KbdBacklight '{self.LEVELS[level]}'\n")
                self.ps_proc.stdin.flush()
                resp = self.ps_proc.stdout.readline().strip()
                if resp.startswith("OK:"):
                    self.current_level = level
                    self.last_change = now
                    if level == 2:
                        self.last_bright = now
            except Exception:
                pass

    def close(self):
        with self.lock:
            if self.ps_proc:
                try:
                    self.ps_proc.stdin.write("exit\n")
                    self.ps_proc.stdin.flush()
                    self.ps_proc.kill()
                except Exception:
                    pass
                self.ps_proc = None


class Visualizer:
    def __init__(self, hardware, config):
        self.hardware = hardware
        self.config = config
        self.running = False
        self.active = config.get("enabled", True)
        self.p = None
        self.stream = None
        self.peak_energy = 0.05
        self.last_sound = 0.0
        self.smoothed_ratio = 0.0

    def start(self):
        self.running = True
        self.p = pyaudio.PyAudio()
        try:
            loopback = self.p.get_default_wasapi_loopback()
        except Exception:
            loopback = None
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice", False):
                    loopback = dev
                    break
        if not loopback:
            return

        self.sr = int(loopback["defaultSampleRate"])
        self.ch = loopback["maxInputChannels"]

        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=self.ch,
            rate=self.sr,
            input=True,
            input_device_index=loopback["index"],
            frames_per_buffer=1024,
            stream_callback=self._callback,
        )
        self.stream.start_stream()

        threading.Thread(target=self._watchdog, daemon=True).start()

    def _callback(self, in_data, frame_count, time_info, status):
        if not in_data or not self.active or not self.running:
            return (None, pyaudio.paContinue)

        audio = np.frombuffer(in_data, dtype=np.float32)
        if self.ch > 1:
            audio = audio.reshape(-1, self.ch).mean(axis=1)

        raw_rms = float(np.sqrt(np.mean(audio ** 2)))
        now = time.monotonic()
        if raw_rms < 0.0003:
            return (None, pyaudio.paContinue)

        self.last_sound = now
        n = len(audio)
        fft_vals = np.abs(np.fft.rfft(audio * np.hanning(n)))
        freqs = np.fft.rfftfreq(n, 1.0 / self.sr)
        bass_mask = (freqs >= 30) & (freqs <= 240)
        bass = float(np.sqrt(np.mean(fft_vals[bass_mask] ** 2))) if np.any(bass_mask) else 0.0

        sens = self.config.get("sensitivity", 1.2)
        score = (bass * 2.5 + raw_rms * 1.0) * sens

        if score > self.peak_energy:
            self.peak_energy = score
        else:
            self.peak_energy = max(self.peak_energy * 0.985, 0.015)

        norm = min(1.0, score / self.peak_energy)
        self.smoothed_ratio = 0.4 * norm + 0.6 * self.smoothed_ratio

        mode = self.config.get("mode", "punchy")
        if mode == "punchy":
            target = 2 if self.smoothed_ratio > 0.58 else (1 if self.smoothed_ratio > 0.15 else 0)
        elif mode == "dynamic":
            target = 2 if self.smoothed_ratio > 0.65 else (1 if self.smoothed_ratio > 0.22 else 0)
        else:
            target = 2 if self.smoothed_ratio > 0.50 else 1

        self.hardware.set_level(target)
        return (None, pyaudio.paContinue)

    def _watchdog(self):
        while self.running:
            time.sleep(0.15)
            if not self.active:
                continue
            if (time.monotonic() - self.last_sound) > 0.4:
                idle = self.config.get("idle_level", 2)
                if self.hardware.current_level != idle:
                    self.hardware.set_level(idle)

    def toggle(self):
        self.active = not self.active
        if not self.active:
            self.hardware.set_level(self.config.get("idle_level", 2), force=True)
        else:
            self.last_sound = time.monotonic()
        return self.active

    def close(self):
        self.running = False
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.p:
                self.p.terminate()
        except Exception:
            pass


def get_icon(active):
    # Minimalist, solid high-contrast icon for tray
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (0, 220, 255, 255) if active else (130, 130, 130, 255)
    # Modern circular badge with white soundwave
    d.ellipse([2, 2, 30, 30], fill=(20, 25, 35, 255), outline=color, width=2)
    d.rectangle([9, 13, 11, 19], fill=color)
    d.rectangle([13, 8, 15, 24], fill=(255, 255, 255, 255))
    d.rectangle([17, 10, 19, 22], fill=color)
    d.rectangle([21, 14, 23, 18], fill=color)
    return img


def main():
    config = load_config()
    hw = VantageBacklight(
        min_interval_ms=config.get("min_interval_ms", 55),
        hold_time_ms=config.get("hold_time_ms", 75)
    )
    vis = Visualizer(hw, config)

    def cleanup():
        try:
            exit_level = config.get("idle_level", 2)
            hw.set_level(exit_level, force=True)
            vis.close()
            hw.close()
        except Exception:
            pass

    atexit.register(cleanup)
    vis.start()

    def on_toggle(icon, item):
        is_on = vis.toggle()
        config["enabled"] = is_on
        save_config(config)
        icon.icon = get_icon(is_on)
        icon.title = f"Backlight Sonata — {'ON' if is_on else 'PAUSED'}"

    def set_mode(m):
        def _fn(icon, item):
            config["mode"] = m
            save_config(config)
        return _fn

    def set_idle(l):
        def _fn(icon, item):
            config["idle_level"] = l
            save_config(config)
            if not vis.active:
                hw.set_level(l, force=True)
        return _fn

    def adjust_sens(delta):
        def _fn(icon, item):
            new_s = round(max(0.5, min(2.5, config.get("sensitivity", 1.2) + delta)), 1)
            config["sensitivity"] = new_s
            save_config(config)
        return _fn

    def on_quit(icon, item):
        cleanup()
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem(lambda _: f"{'🟢 Music Sync: ON' if vis.active else '⚫ Music Sync: PAUSED'}", on_toggle, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sensitivity", pystray.Menu(
            pystray.MenuItem(lambda _: f"Current: {config.get('sensitivity', 1.2):.1f}x", None, enabled=False),
            pystray.MenuItem("🔺 Increase (+0.2x)", adjust_sens(0.2)),
            pystray.MenuItem("🔻 Decrease (-0.2x)", adjust_sens(-0.2)),
        )),
        pystray.MenuItem("Mode", pystray.Menu(
            pystray.MenuItem("⚡ Punchy Beat", set_mode("punchy"), checked=lambda _: config.get("mode") == "punchy"),
            pystray.MenuItem("🌊 Dynamic 3-Stage", set_mode("dynamic"), checked=lambda _: config.get("mode") == "dynamic"),
            pystray.MenuItem("✨ Subtle Glow", set_mode("subtle"), checked=lambda _: config.get("mode") == "subtle"),
        )),
        pystray.MenuItem("When Paused", pystray.Menu(
            pystray.MenuItem("Bright", set_idle(2), checked=lambda _: config.get("idle_level") == 2),
            pystray.MenuItem("Dim", set_idle(1), checked=lambda _: config.get("idle_level") == 1),
            pystray.MenuItem("Off", set_idle(0), checked=lambda _: config.get("idle_level") == 0),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Exit", on_quit),
    )

    icon = pystray.Icon(
        name="BacklightSonata",
        icon=get_icon(vis.active),
        title=f"Backlight Sonata — {'ON' if vis.active else 'PAUSED'}",
        menu=menu,
    )

    icon.run()

if __name__ == "__main__":
    main()
