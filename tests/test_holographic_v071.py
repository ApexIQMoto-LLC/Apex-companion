import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from companion.holographic_ui import clamp, waveform_points
from companion.away_mode import AwayMonitor


class FakeClock:
    def __init__(self, seconds):self.seconds=seconds
    def idle_seconds(self):return self.seconds


class AwayModeTests(unittest.TestCase):
    def test_idle_without_camera_detects_away(self):
        state=AwayMonitor(idle_clock=FakeClock(600),idle_minutes=8)
        self.assertTrue(state.status(now=1000))
        self.assertEqual(state.mode,'AWAY / IDLE')

    def test_active_keyboard_blocks_auto_away(self):
        state=AwayMonitor(idle_clock=FakeClock(5),idle_minutes=8)
        self.assertFalse(state.status(now=1000))

    def test_camera_present_blocks_idle_away(self):
        state=AwayMonitor(idle_clock=FakeClock(3600),idle_minutes=8)
        state.presence(True,now=1000)
        self.assertFalse(state.status(now=1001))
        state.presence(False,now=1002)
        self.assertFalse(state.status(now=1080))
        self.assertTrue(state.status(now=1201))

    def test_manual_away_has_precedence(self):
        state=AwayMonitor(idle_clock=FakeClock(0))
        state.manual_away=True
        self.assertTrue(state.status(now=1))
        state.manual_away=False
        self.assertFalse(state.status(now=2))

    def test_unsupported_idle_clock_never_assumes_away(self):
        state=AwayMonitor(idle_clock=FakeClock(None))
        self.assertFalse(state.status(now=1))


class WaveformTests(unittest.TestCase):
    def test_points_finite_and_closed(self):
        p=waveform_points(100,100,80,1.4)
        self.assertEqual(len(p),322)
        self.assertAlmostEqual(p[0],p[-2],places=5)
        self.assertAlmostEqual(p[1],p[-1],places=5)

    def test_clamp_bounds_audio(self):
        self.assertEqual(clamp(-3),0)
        self.assertEqual(clamp(3),1)


class SensorMigrationTests(unittest.TestCase):
    def test_migration_only_changes_sensor_defaults_once(self):
        script=Path(__file__).parents[1]/'tools'/'enable_hologram_defaults.py'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir()
            conf=root/'config.json'
            conf.write_text(json.dumps({'camera_autostart':False,'microphone_autostart':False,
                'monthly_budget_usd':4,'private_preference':'kept','autonomous_small_fixes':False}))
            subprocess.run([sys.executable,str(script),str(root)],check=True,capture_output=True)
            x=json.loads(conf.read_text())
            self.assertTrue(x['camera_autostart'])
            self.assertTrue(x['microphone_autostart'])
            self.assertFalse(x['autonomous_small_fixes'])
            self.assertEqual(x['private_preference'],'kept')
            x['camera_autostart']=False
            conf.write_text(json.dumps(x))
            subprocess.run([sys.executable,str(script),str(root)],check=True,capture_output=True)
            self.assertFalse(json.loads(conf.read_text())['camera_autostart'])


if __name__=='__main__':unittest.main()
