"""Simple CLI for the public starter."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .monitor import capture
from .server import serve
from .settings import Settings

def main() -> None:
    parser = argparse.ArgumentParser(description="APEX Companion local read-only desktop monitor")
    parser.add_argument("command", nargs="?", choices=("serve", "status"), default="serve")
    parser.add_argument("--config", default="config.local.json")
    args = parser.parse_args()
    settings = Settings.load(Path(args.config))
    if args.command == "status":
        print(json.dumps(capture(settings), indent=2))
    else:
        serve(settings)
