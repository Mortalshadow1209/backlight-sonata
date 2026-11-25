"""
Backlight Sonata - Shortcut Installer
Creates a convenient desktop shortcut pointing to pythonw (windowless execution).
"""

import os
import sys
import win32com.client


def create_desktop_shortcut():
    # Detect Desktop directory (supporting both local and OneDrive Desktop)
    user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    desktop_candidates = [
        os.path.join(user_profile, "OneDrive", "Desktop"),
        os.path.join(user_profile, "Desktop")
    ]
    desktop = next((d for d in desktop_candidates if os.path.exists(d)), desktop_candidates[-1])

    app_dir = os.path.dirname(os.path.abspath(__file__))
    target_py = os.path.join(app_dir, "sonata.py")
    icon_path = os.path.join(app_dir, "sonata.ico")

    # Locate pythonw.exe in the current Python environment
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    lnk_path = os.path.join(desktop, "Backlight Sonata.lnk")

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_path)
    shortcut.TargetPath = pythonw
    shortcut.Arguments = f'"{target_py}"'
    shortcut.WorkingDirectory = app_dir
    if os.path.exists(icon_path):
        shortcut.IconLocation = f"{icon_path},0"
    shortcut.Description = "Backlight Sonata — Keyboard Audio Visualizer for Lenovo LOQ"
    shortcut.Save()
    print(f"Desktop shortcut created: {lnk_path}")

    # Clean legacy shortcuts if present
    for old_name in ["LOQ Pulse.lnk", "BeatSync.lnk"]:
        for d in desktop_candidates:
            old_file = os.path.join(d, old_name)
            if os.path.exists(old_file):
                try:
                    os.remove(old_file)
                    print(f"Removed legacy shortcut: {old_name}")
                except Exception:
                    pass


if __name__ == "__main__":
    create_desktop_shortcut()
