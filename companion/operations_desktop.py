"""Explicit, permission-gated Windows desktop inspection.

No background screenshots, image uploads, simulated keyboard entry, or
unattended clicking. This module offers on-demand UIA inspection and optional
local screenshot capture of the currently focused application.
"""
from __future__ import annotations

import ctypes
import sys
from datetime import datetime,timezone
from pathlib import Path

from .project_index import redact


class DesktopInspector:
    def __init__(self, captures_dir):
        self.folder=Path(captures_dir)

    def list_windows(self,*,permitted=False):
        if not permitted:raise PermissionError("Grant computer/LOCAL permission first")
        if sys.platform!="win32":return []
        user=ctypes.windll.user32
        results=[]
        CALLBACK=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
        @CALLBACK
        def visitor(hwnd,arg):
            try:
                if not user.IsWindowVisible(hwnd):return True
                length=int(user.GetWindowTextLengthW(hwnd))
                if length<3 or length>300:return True
                buff=ctypes.create_unicode_buffer(length+1)
                user.GetWindowTextW(hwnd,buff,length+1)
                name=redact(buff.value).strip()
                if name:
                    results.append({"handle":int(hwnd),"title":name[:180]})
            except (ValueError,AttributeError,OSError):pass
            return len(results)<60
        user.EnumWindows(visitor,0)
        return results

    def inspect_window(self,hwnd,*,permitted=False,read_controls=False):
        if not permitted:raise PermissionError("Grant computer/LOCAL permission first")
        if sys.platform!="win32":return {"state":"unsupported","reason":"Windows only"}
        if not isinstance(hwnd,int) or hwnd<=0 or not ctypes.windll.user32.IsWindow(hwnd):
            return {"state":"window_closed"}
        user=ctypes.windll.user32
        buf=ctypes.create_unicode_buffer(350)
        user.GetWindowTextW(hwnd,buf,350)
        result={"state":"ok","window_title":redact(buf.value or "[untitled]")[:180],"controls":[],
                "note":"Owner-selected Windows UIA inspection; no clicks, typing, screenshots or uploads."}
        if read_controls:
            try:
                from pywinauto import Desktop
                win=Desktop(backend="uia").window(handle=hwnd)
                controls=[]
                for obj in win.descendants()[:100]:
                    try:
                        typ=str(obj.element_info.control_type or "")[:40]
                        ctl=redact(str(obj.window_text() or ""))[:80]
                        if typ in {"Button","TabItem","MenuItem","Text","Edit","ListItem"}:
                            controls.append({"type":typ,"text":ctl})
                    except (AttributeError,OSError,RuntimeError):continue
                    if len(controls)>=30:break
                result["controls"]=controls
            except (ImportError,OSError,RuntimeError,AttributeError):
                result["reason"]="Optional pywinauto UI Automation dependency unavailable"
        return result

    def active_window(self,*,permitted=False,read_controls=False):
        if not permitted:raise PermissionError("Grant computer/LOCAL permission first")
        if sys.platform!="win32":return {"state":"unsupported","reason":"Windows only"}
        hwnd=int(ctypes.windll.user32.GetForegroundWindow())
        return self.inspect_window(hwnd,permitted=permitted,read_controls=read_controls)

    def capture_window(self,hwnd,*,permitted=False,consented=False):
        if not permitted or not consented:raise PermissionError("Explicit per-capture consent and computer/LOCAL permission required")
        if sys.platform!="win32":raise RuntimeError("Screenshots require Windows")
        if not isinstance(hwnd,int) or hwnd<=0 or not ctypes.windll.user32.IsWindow(hwnd):
            raise ValueError("Window no longer exists")
        from PIL import ImageGrab
        user=ctypes.windll.user32
        class RECT(ctypes.Structure):
            _fields_=[("left",ctypes.c_long),("top",ctypes.c_long),("right",ctypes.c_long),("bottom",ctypes.c_long)]
        rect=RECT()
        if not user.GetWindowRect(hwnd,ctypes.byref(rect)):
            raise OSError("Cannot read selected window bounds")
        bounds=(rect.left,rect.top,rect.right,rect.bottom)
        if bounds[2]-bounds[0]<50 or bounds[3]-bounds[1]<50:
            raise ValueError("Selected window too small")
        if (bounds[2]-bounds[0])*(bounds[3]-bounds[1])>25_000_000:
            raise ValueError("Window capture too large")
        self.folder.mkdir(parents=True,exist_ok=True)
        dest=self.folder/(datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")+str(hwnd)+".png")
        ImageGrab.grab(bbox=bounds).save(dest,"PNG")
        return {"state":"saved_locally","image":str(dest),"uploaded":False,
                "warning":"May contain personal data. Review/delete manually. Never sent to OpenAI or Telegram."}

    def capture_active_window(self,*,permitted=False,consented=False):
        if sys.platform!="win32":raise RuntimeError("Screenshots require Windows")
        hwnd=int(ctypes.windll.user32.GetForegroundWindow())
        return self.capture_window(hwnd,permitted=permitted,consented=consented)
