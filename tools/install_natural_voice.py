"""Owner-initiated local Kokoro model download from official upstream release."""
from pathlib import Path
import hashlib
import os
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'models' / 'kokoro'
BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
FILES = {'kokoro-v1.0.int8.onnx': (95_000_000, 140_000_000),
         'voices-v1.0.bin': (20_000_000, 40_000_000)}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for filename, (lower, upper) in FILES.items():
        target = DEST / filename
        if target.exists() and lower <= target.stat().st_size <= upper:
            print(f'Already installed: {filename}')
            continue
        temp = DEST / (filename + '.partial')
        temp.unlink(missing_ok=True)
        url = BASE + filename
        print(f'Downloading {filename} from official project release...', flush=True)
        hasher = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'APEX-Companion/0.10.4'}), timeout=45) as source, temp.open('wb') as out:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    size += len(block)
                    if size > upper:
                        raise RuntimeError('Download exceeds approved size; refusing to install')
                    hasher.update(block)
                    out.write(block)
                    if size % (8 * 1024 * 1024) < 1024 * 1024:
                        print(f'  {size // (1024*1024)} MB', flush=True)
            if not lower <= size <= upper:
                raise RuntimeError('Downloaded model size is unexpected; refusing to install')
            temp.replace(target)
            print(f'Installed {filename} ({size // 1048576} MB, SHA256 {hasher.hexdigest()})')
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    print('\nVoice models installed. In APEX choose Voice Output Settings > Kokoro natural offline voice.')


if __name__ == '__main__':
    main()
