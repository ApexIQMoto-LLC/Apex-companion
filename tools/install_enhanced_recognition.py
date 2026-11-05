"""Explicit owner installation of local English Whisper model; no audio upload."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'models' / 'whisper-small.en'


def main():
    from huggingface_hub import snapshot_download
    DEST.mkdir(parents=True, exist_ok=True)
    print('Downloading authorized MIT-licensed Systran faster-whisper small.en model (~500 MB)...')
    snapshot_download(repo_id='Systran/faster-whisper-small.en',
                      local_dir=str(DEST),
                      allow_patterns=['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt'])
    if not (DEST / 'model.bin').is_file():
        raise RuntimeError('Recognition model installation incomplete')
    config = ROOT / 'config.json'
    existing = json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
    if not isinstance(existing, dict):
        raise ValueError('Invalid config.json; enhanced recognition not enabled')
    existing['speech_enhanced_recognition'] = True
    temp = config.with_name('config.json.tmp')
    temp.write_text(json.dumps(existing, indent=2), encoding='utf-8')
    temp.replace(config)
    print('Enhanced speech recognition enabled. Restart APEX to take effect.')


if __name__ == '__main__':
    main()
