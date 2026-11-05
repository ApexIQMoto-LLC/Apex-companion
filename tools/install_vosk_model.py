"""Explicit, optional installation of the official Vosk English speech model."""
from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
NAME="vosk-model-small-en-us-0.15"
URL=f"https://alphacephei.com/vosk/models/{NAME}.zip"
DEST=BASE/"models"/NAME
MAX_COMPRESSED=100_000_000
MAX_UNCOMPRESSED=650_000_000


def install():
    if (DEST/"am"/"final.mdl").is_file() and (DEST/"conf"/"model.conf").is_file():
        print("Offline voice model already installed:",DEST)
        return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="apex_vosk_") as tmp:
        folder=Path(tmp)
        downloaded=folder/"vosk.zip"
        print("Downloading Apache-2.0 offline Vosk speech model from official source:",URL)
        request=urllib.request.Request(URL,headers={"User-Agent":"ApexIQCompanion/0.10"})
        with urllib.request.urlopen(request,timeout=35) as source,downloaded.open("wb") as output:
            amount=0
            while True:
                block=source.read(1024*1024)
                if not block:break
                amount+=len(block)
                if amount>MAX_COMPRESSED:raise RuntimeError("Downloaded archive larger than expected")
                output.write(block)
        extracted=folder/NAME
        extracted.mkdir()
        with zipfile.ZipFile(downloaded) as archive:
            members=archive.infolist()
            if sum(i.file_size for i in members)>MAX_UNCOMPRESSED:
                raise RuntimeError("Model contents larger than allowed")
            for info in members:
                path=Path(info.filename)
                if not path.parts or path.parts[0]!=NAME or path.is_absolute() or ".." in path.parts:
                    raise RuntimeError("Unexpected path in model archive")
                if (info.external_attr>>16)&0o170000==0o120000:
                    raise RuntimeError("Symlinks are not allowed in model archive")
                rel=Path(*path.parts[1:])
                if not rel.parts:continue
                target=extracted/rel
                if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as src,target.open("wb") as dst:
                    shutil.copyfileobj(src,dst)
        if not (extracted/"am"/"final.mdl").is_file() or not (extracted/"conf"/"model.conf").is_file():
            raise RuntimeError("The archive did not contain a valid Vosk model")
        if DEST.exists():
            raise RuntimeError("An incomplete model directory already exists. Move it aside and retry: "+str(DEST))
        shutil.move(str(extracted),str(DEST))
    print("Installed:",DEST)
    print("Restart APEX or use the VOICE button to start the microphone.")


if __name__=="__main__":
    install()
