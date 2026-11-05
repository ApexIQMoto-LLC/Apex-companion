"""Local away-state detection; not a determination of physical location.

Uses only elapsed Windows keyboard/mouse inactivity and local camera presence
transitions. It does not record keystrokes, window titles, screen content,
location, work attendance or face imagery.
"""
from __future__ import annotations

import ctypes
import sys
import time


class WindowsIdleClock:
    def __init__(self):
        self.supported = sys.platform == 'win32'

    def idle_seconds(self):
        if not self.supported:
            return None
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        try:
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            elapsed = (int(ctypes.windll.kernel32.GetTickCount64()) - int(info.dwTime)) & 0xFFFFFFFF
            return max(0.0, elapsed/1000.0)
        except (AttributeError, OSError):
            return None


class AwayMonitor:
    def __init__(self, *, idle_clock=None, idle_minutes=8, camera_grace_seconds=150):
        self.idle_clock = idle_clock if idle_clock is not None else WindowsIdleClock()
        self.idle_minutes = max(2.0, min(60., float(idle_minutes)))
        self.camera_grace_seconds = max(60, min(1200, int(camera_grace_seconds)))
        self.camera_works = False
        self.face_present = False
        self.last_face_seen = None
        self.manual_away = False
        self.mode = 'PRESENT'

    def presence(self, visible, *, now=None):
        now = time.monotonic() if now is None else float(now)
        self.camera_works = True
        self.face_present = bool(visible)
        if visible:
            self.last_face_seen = now

    def camera_unavailable(self):
        self.camera_works = False
        self.face_present = False

    def status(self, *, now=None):
        now = time.monotonic() if now is None else float(now)
        if self.manual_away:
            self.mode = 'AWAY / MANUAL'
            return True
        idle = self.idle_clock.idle_seconds()
        if idle is None or idle < self.idle_minutes*60:
            self.mode = 'PRESENT / ACTIVE' if idle is not None else 'AWAY SENSING UNAVAILABLE'
            return False
        if self.camera_works:
            if self.face_present:
                self.mode = 'PRESENT / CAMERA'
                return False
            if self.last_face_seen is not None and (now-self.last_face_seen)<self.camera_grace_seconds:
                self.mode = 'PRESENT / CAMERA GRACE'
                return False
        self.mode = 'AWAY / IDLE'
        return True
