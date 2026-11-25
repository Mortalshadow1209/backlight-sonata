# Backlight Sonata 🎵⌨️

A lightweight, real-time keyboard audio visualizer crafted for Lenovo LOQ and IdeaPad laptops featuring single-zone white backlit keyboards (Off / Dim / Bright).

Backlight Sonata captures system audio in real-time via WASAPI loopback and rhythmically pulses the physical keyboard backlights to the music beat without perceptible latency or command-prompt windows.

---

## ✨ Features

- **Direct Hardware Interop**: Communicates directly through Lenovo Vantage energy management services for fast, sub-50ms transitions.
- **Hardware-Safe Regulation**: Enforces hardware cooldown limits and minimum state hold times to protect the keyboard backlight LEDs from rapid wear.
- **Background System Tray**: Runs silently in the Windows system tray with zero terminal popups.
- **Customizable Modes**:
  - `⚡ Punchy Beat`: Reacts sharply to bass hits and dynamic drum drops.
  - `🌊 Dynamic 3-Stage`: Smoothly steps across Off, Dim, and Bright depending on song intensity.
  - `✨ Subtle Glow`: Keeps a gentle ambient presence with accents on crests.
- **Live Sensitivity Adjustment**: Quick on-the-fly sensitivity tuning (+/- 0.2x) from the tray context menu.
- **Customizable Idle State**: Choose whether the backlight rests at Bright, Dim, or Off when music pauses or the app exits.

---

## 💻 Compatibility

- **Hardware**: Lenovo LOQ series (e.g. 15IAX9, 15IRX9) and compatible IdeaPad laptops equipped with single-zone white backlight keyboards.
- **Operating System**: Windows 10 / 11 (64-bit).
- **Audio Output**: Any default output device (Speakers, Headphones) utilizing Windows Audio Session API (WASAPI).

---

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have [Python 3.10+](https://www.python.org/downloads/) installed on Windows.

### 2. Clone Repository
```powershell
git clone https://github.com/Mortalshadow1209/backlight-sonata.git
cd backlight-sonata
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Run Application
You can run it directly:
```powershell
pythonw sonata.py
```
Or create a permanent Desktop shortcut by running:
```powershell
python install_shortcut.py
```

---

## 🎛️ Usage

1. Launch **Backlight Sonata** from your desktop shortcut or via `run.bat`.
2. Look for the circular audio wave icon in your Windows System Tray (near the clock).
3. **Left Click**: Instantly toggle audio sync ON or PAUSED.
4. **Right Click**: Open settings to adjust sensitivity, switch visualizer modes, or select your preferred idle brightness.

---

## 📂 Project Structure

```text
backlight-sonata/
├── lenovo_dlls/          # Helper interop libraries for Lenovo hardware
├── config.json           # User configuration (mode, sensitivity, idle state)
├── install_shortcut.py   # Automatic desktop shortcut creator
├── requirements.txt      # Python dependencies
├── run.bat               # Simple batch launcher
├── sonata.ico            # Minimalist application icon
├── sonata.py             # Main application and visualizer engine
└── README.md             # Project documentation
```
