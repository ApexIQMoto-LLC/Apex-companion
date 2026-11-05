"""Windows notification-area icon. Callbacks only dispatch events to the Tk thread."""
from __future__ import annotations

import os
import threading


def draw_apex_icon(size=64):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (size, size), (7, 20, 31, 255))
    d = ImageDraw.Draw(image)
    margin = max(3, size // 9)
    d.ellipse((margin, margin, size-margin, size-margin), outline=(77, 228, 216, 255), width=max(2, size//17))
    d.arc((margin+5, margin+5, size-margin-5, size-margin-5), 40, 290, fill=(93, 164, 245, 255), width=max(2, size//20))
    d.text((size//2, size//2), "A", anchor="mm", fill=(231, 252, 250, 255), stroke_width=0)
    return image


class TrayController:
    """A real tray icon on Windows; never hides the UI if creation fails."""
    def __init__(self, emit):
        self.emit = emit
        self.icon = None
        self.thread = None
        self.available = False

    def start(self):
        if os.name != "nt":
            return False
        try:
            import pystray
            # Import before hiding the Tk window; missing dependency is recoverable.
            menu = pystray.Menu(
                pystray.MenuItem("Open APEX hologram", lambda icon, item: self.emit("mini"), default=True),
                pystray.MenuItem("Open full dashboard", lambda icon, item: self.emit("dashboard")),
                pystray.MenuItem("Start business conversation", lambda icon, item: self.emit("business")),
                pystray.MenuItem("Toggle microphone", lambda icon, item: self.emit("microphone")),
                pystray.MenuItem("Microphone setup...", lambda icon, item: self.emit("microphone_setup")),
                pystray.MenuItem("Test spoken voice", lambda icon, item: self.emit("test_voice")),
                pystray.MenuItem("Voice output settings...", lambda icon, item: self.emit("voice_output_setup")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit APEX", lambda icon, item: self.emit("quit")),
            )
            self.icon = pystray.Icon("ApexIQCompanion", draw_apex_icon(), "APEX - Business + Personal", menu)
            self.thread = threading.Thread(target=self._run, name="ApexTray", daemon=True)
            self.thread.start()
            return True
        except Exception:
            self.icon = None
            return False

    def _run(self):
        try:
            def ready(icon):
                icon.visible = True
                self.available = True
                self.emit("tray_ready")
            self.icon.run(setup=ready)
        except Exception:
            self.available = False
            self.emit("tray_failed")

    def stop(self):
        icon = self.icon
        self.available = False
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
