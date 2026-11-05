import threading
import time
from datetime import datetime


class PresenceCamera:
    """Local-only face presence detector; never identifies or saves a face."""

    def __init__(self, settings, on_greeting, on_status, on_presence=None):
        self.settings = settings
        self.greet = on_greeting
        self.status = on_status
        self.presence_change = on_presence or (lambda present: None)
        self._reported_presence = None
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="PresenceCamera", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _in_quiet_hours(self):
        hour = datetime.now().hour
        start = int(self.settings["quiet_hours_start"])
        end = int(self.settings["quiet_hours_end"])
        if start == end:
            return False
        return (hour >= start or hour < end) if start > end else (start <= hour < end)

    def _run(self):
        cap = None
        try:
            import cv2
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(path)
            if detector.empty():
                raise RuntimeError("Built-in OpenCV face cascade unavailable")
            index = int(self.settings["camera_index"])
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(index)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open camera index {index}")
            self.status("Camera: local face presence ON (no video uploads/storage)")
            confirm = 0
            last_seen = 0.0
            last_greet = -1e12
            absence_sec = int(self.settings["presence_absence_seconds"])
            last_reported = None
            cooldown = int(self.settings["greeting_cooldown_minutes"]) * 60
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    self.stop_event.wait(1.0)
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Downsample for lower CPU usage and discard frame immediately.
                gray = cv2.resize(gray, None, fx=0.5, fy=0.5)
                faces = detector.detectMultiScale(gray, scaleFactor=1.15,
                                                   minNeighbors=5, minSize=(35, 35))
                now = time.monotonic()
                if len(faces):
                    confirm += 1
                    returned = last_seen == 0 or (now - last_seen >= absence_sec)
                    # A transition after a prolonged absence should greet only
                    # after two positive frames, subject to cooldown/quiet hours.
                    if confirm >= 2 and returned and now - last_greet >= cooldown:
                        if not self._in_quiet_hours():
                            self.greet()
                            last_greet = now
                    if confirm >= 2:
                        last_seen = now
                        if last_reported is not True:
                            self.presence_change(True)
                            last_reported = True
                else:
                    confirm = 0
                    if last_reported is True and now-last_seen >= 4:
                        self.presence_change(False)
                        last_reported = False
                self.stop_event.wait(1.4)
        except Exception as ex:
            self.status(f"Camera error: {ex}")
        finally:
            try:
                self.presence_change(False)
            except Exception:
                pass
            if cap is not None:
                cap.release()
            self.status("Camera stopped")
