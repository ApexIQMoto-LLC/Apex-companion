"""One-time migration of sensor autostart after explicit owner request.

Does not inspect or print secrets, session data, or memory. Previous settings
remain intact except the two requested sensor-autostart flags. Users can
subsequently disable them in APEX and that opt-out persists across updates.
"""
import json
from pathlib import Path
import os
import sys

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent.parent
config=root/'config.json'
marker=root/'data'/'apex_hologram_sensor_migration_v07.flag'
if marker.exists():
    print('Sensor auto-start already migrated; retaining user preferences')
    raise SystemExit(0)
config.parent.mkdir(parents=True,exist_ok=True)
marker.parent.mkdir(parents=True,exist_ok=True)
if config.exists():
    value=json.loads(config.read_text(encoding='utf-8'))
    if not isinstance(value,dict):
        raise ValueError('config.json must be an object; no modifications made')
else:
    value={}
value['camera_autostart']=True
value['microphone_autostart']=True
value['autonomous_small_fixes']=bool(value.get('autonomous_small_fixes',True))
target=config.with_name(config.name+'.apex_new')
with target.open('w',encoding='utf-8') as f:
    json.dump(value,f,indent=2)
    f.write('\n')
os.replace(target,config)
marker.write_text('Holographic voice and camera auto-start enabled on initial upgrade. Toggle either off in APEX to opt out.\n',encoding='utf-8')
print('Enabled camera/microphone autostart for holographic APEX; all other config retained')
