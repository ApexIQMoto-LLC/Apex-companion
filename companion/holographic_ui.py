"""Responsive animated APEX holographic voice core.

Canvas effects are generative vector artwork. No microphone recordings or
camera frames are retained. Speaking animation follows TTS busy state, not
real output-audio sampling. Listening amplitude is derived from local RMS.
"""
from __future__ import annotations

import math
import tkinter as tk

BACKDROP = "#06111F"
EDGE = "#163950"
NEON = "#63F5EA"
AZURE = "#6BC6FF"
PURPLE = "#B88BFF"
MUTED = "#63899E"
PAPER = "#E5FCFF"


def clamp(x, low=0.0, high=1.0):
    return max(low, min(high, float(x)))


def waveform_points(cx, cy, radius, phase, n=160, amp=0.16, order=0):
    """Generate a closed, gently pulsating radial waveform for Tk Canvas."""
    points = []
    for k in range(n + 1):
        a = (k / n) * math.tau
        harmonic = math.sin(11 * a + phase * (1.4 + order * 0.1))
        harmonic += 0.50 * math.sin(21 * a - phase * 0.88)
        harmonic += 0.34 * math.sin(7 * a + phase * 1.9)
        r = radius * (1 + amp * harmonic / 1.84)
        points += [cx + math.cos(a) * r, cy + math.sin(a) * r]
    return points


class HolographicCore(tk.Canvas):
    """Draws a glowing circular waveform avatar with microphone/TTS state."""
    def __init__(self, master, **kw):
        kw.setdefault('bg', BACKDROP)
        kw.setdefault('highlightthickness', 0)
        kw.setdefault('borderwidth', 0)
        kw.setdefault('height', 340)
        super().__init__(master, **kw)
        self.phase = 0.0
        self.mode = 'IDLE'
        self.level = 0.0
        self.voice_ready = False
        self.camera_ready = False
        self.presence = False
        self.away = False

    def update_state(self, *, mode: str, microphone_level=0, voice_ready=False,
                     camera_ready=False, presence=False, away=False):
        self.mode = str(mode).upper()
        self.level = clamp(microphone_level)
        self.voice_ready = bool(voice_ready)
        self.camera_ready = bool(camera_ready)
        self.presence = bool(presence)
        self.away = bool(away)

    def render(self):
        """Call from Tk's UI thread at a controlled animation cadence."""
        w = max(self.winfo_width(), 340)
        h = max(self.winfo_height(), 220)
        self.delete('holo')
        self.phase += 0.095
        cx, cy = w * 0.50, h * 0.47
        r = min(h * 0.265, w * 0.145)
        speaking = self.mode == 'SPEAKING'
        listening = self.mode == 'LISTENING'
        thinking = self.mode == 'THINKING'
        envelope = 0.07
        if speaking:
            envelope = 0.58 + 0.25 * math.sin(self.phase * 4.7) ** 2
        elif listening:
            envelope = 0.10 + self.level * 0.95
        elif thinking:
            envelope = 0.24 + 0.16 * math.sin(self.phase * 2.0) ** 2
        if self.away:
            envelope *= 0.50
        # Subtle HUD reticle background.
        for grid_x in range(0, w + 1, 50):
            color = '#0C2638' if grid_x % 100 == 0 else '#081B2D'
            self.create_line(grid_x, 0, grid_x, h, fill=color, tags='holo')
        for grid_y in range(0, h + 1, 50):
            self.create_line(0, grid_y, w, grid_y, fill='#0A2133', tags='holo')
        self.create_line(w*.03, 18, w*.25, 18, fill=EDGE, width=2, tags='holo')
        self.create_line(w*.75, 18, w*.97, 18, fill=EDGE, width=2, tags='holo')
        self.create_text(w*.04, 36, text='APEX  /  ACTIVE' if w < 600 else 'APEX  /  ACTIVE INTELLIGENCE', anchor='w',
                         font=('Consolas', 10, 'bold'), fill=NEON, tags='holo')
        self.create_text(w*.96, 36, text='LOCAL AUDIO' if w < 600 else 'NEURAL AUDIO / 07', anchor='e',
                         font=('Consolas', 9), fill=MUTED, tags='holo')
        # Radial halo.
        for j in range(7, 0, -1):
            rr = r * (1.2 + j * 0.10)
            self.create_oval(cx-rr, cy-rr, cx+rr, cy+rr, outline='#0D293D' if j > 3 else '#173F53',
                             width=1, tags='holo')
        for j, (color, base, strength) in enumerate(((EDGE, 1.25, .30), ('#1D5169', 1.10, .46),
                                                    (AZURE, .96, .52), (NEON, .82, .68))):
            points = waveform_points(cx, cy, r*base, self.phase + j*2.1,
                                     amp=envelope * strength, order=j)
            self.create_line(*points, fill=color, width=2 if j < 2 else 3,
                             smooth=True, splinesteps=10, tags='holo')
        # Split rotating arcs and fine tick marks.
        for i in range(3):
            rr = r * (1.30 + i*.10)
            deg = (self.phase * 24 * ((-1)**i) + i*110) % 360
            color = NEON if i == 0 else AZURE if i == 1 else PURPLE
            self.create_arc(cx-rr, cy-rr, cx+rr, cy+rr,
                            start=deg, extent=46+i*13, style='arc', outline=color, width=2,
                            tags='holo')
            self.create_arc(cx-rr, cy-rr, cx+rr, cy+rr,
                            start=(deg+180)%360, extent=18, style='arc', outline=color, width=2,
                            tags='holo')
        for i in range(72):
            a = i * math.tau / 72 + self.phase*.03
            inner = r * 1.40
            outer = inner + (9 if i%6==0 else 3)
            col = '#3A8395' if i%6==0 else '#1B455A'
            self.create_line(cx+math.cos(a)*inner, cy+math.sin(a)*inner,
                             cx+math.cos(a)*outer, cy+math.sin(a)*outer,
                             fill=col, width=1, tags='holo')
        # Inner core lens.
        self.create_oval(cx-r*.67, cy-r*.67, cx+r*.67, cy+r*.67,
                         fill='#0B2A3C', outline='#1D7992', width=2, tags='holo')
        self.create_oval(cx-r*.52, cy-r*.52, cx+r*.52, cy+r*.52,
                         fill='#0B3547', outline='#2E9FAD', width=1, tags='holo')
        self.create_text(cx, cy-r*.10, text='A P E X', font=('Segoe UI', max(19,int(r*.21)), 'bold'),
                         fill=PAPER, tags='holo')
        self.create_text(cx, cy+r*.15, text=self.mode + '  /  CORE ONLINE',
                         font=('Consolas', 9, 'bold'), fill=NEON, tags='holo')
        self.create_text(cx, h-22, text='SOUND-FORM INTERFACE    •    AUDIO LOCAL TO THIS PC',
                         font=('Consolas', 9), fill=MUTED, tags='holo')
        # Side spectrum meters, animation reflects TTS state or local microphone RMS.
        count = max(6, min(15, int(w / 85)))
        for side in (-1, 1):
            anchor = cx + side*(r*1.9)
            for j in range(count):
                a = math.sin(self.phase*2.2 + j*1.03 + side)
                power = (0.15 + envelope * (0.55+0.45*abs(a)))
                bh = 10+power*56
                xx = anchor+side*j*7.2
                self.create_line(xx, cy-bh/2, xx, cy+bh/2,
                                 fill=NEON if j % 3 else AZURE, width=3, tags='holo')
        # Diagnostics rails at edges.
        left = f'MIC    {"ARMED" if self.voice_ready else "OFFLINE"}'
        right = f'CAM    {"PRESENT" if self.presence else "WATCHING" if self.camera_ready else "OFFLINE"}'
        if w >= 600:
            self.create_text(25, h*.55, text=left, anchor='w', font=('Consolas',9,'bold'), fill=MUTED, tags='holo')
            self.create_text(w-25, h*.55, text=right, anchor='e', font=('Consolas',9,'bold'), fill=MUTED, tags='holo')
            self.create_line(24, h*.60, max(45,cx-r*1.7), h*.60, fill=EDGE, tags='holo')
            self.create_line(min(w-45,cx+r*1.7), h*.60, w-24, h*.60, fill=EDGE, tags='holo')
