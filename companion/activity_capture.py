"""Optional coarse Windows activity sampling: PROCESS NAME ONLY.

Never reads browser history, filenames, window titles, keyboard input,
clipboard, audio, screen content or process memory. Disabled by default via
PersonalIntelStore scope 'computer' permission.
"""
from __future__ import annotations
import os
from pathlib import Path


def foreground_application():
    if os.name!="nt":return None
    try:
        import ctypes
        from ctypes import wintypes
        user32=ctypes.WinDLL("user32",use_last_error=True)
        kernel32=ctypes.WinDLL("kernel32",use_last_error=True)
        user32.GetForegroundWindow.restype=wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype=wintypes.DWORD
        kernel32.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel32.OpenProcess.restype=wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype=wintypes.BOOL
        kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel32.CloseHandle.restype=wintypes.BOOL
        window=user32.GetForegroundWindow()
        if not window:return None
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(window,ctypes.byref(pid))
        handle=kernel32.OpenProcess(0x1000,False,pid.value)
        if not handle:return None
        try:
            buff=ctypes.create_unicode_buffer(4096)
            size=wintypes.DWORD(len(buff))
            if not kernel32.QueryFullProcessImageNameW(handle,0,buff,ctypes.byref(size)):
                return None
            # Return ONLY executable basename, not the user's private file path.
            return Path(buff.value).name[:95]
        finally:kernel32.CloseHandle(handle)
    except Exception:
        return None


class CoarseActivityCapture:
    def __init__(self,store):
        self.store=store
        self.last_app=None
        self.samples=0

    def tick(self,app_name=None):
        if not self.store.permitted("computer","local"):
            self.last_app=None;self.samples=0
            return {"status":"disabled"}
        name=app_name if app_name is not None else foreground_application()
        if not name or any(x in str(name).lower() for x in ("password","credential","vault","bank")):
            return {"status":"unavailable"}
        name=Path(str(name)).name[:95]
        self.samples+=1
        # One event per app switch or every 5 samples, not a high resolution
        # tracking feed or a guarantee of focused work.
        if name!=self.last_app or self.samples%5==0:
            self.store.add_event("foreground_app","Foreground app: "+name,
                                 "Observed application process name only. Not evidence of active work.",
                                 scope="computer",source="companion_activity")
        self.last_app=name
        return {"status":"sampled","app":name}
