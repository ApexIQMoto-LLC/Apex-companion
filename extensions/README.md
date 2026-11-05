# Optional desktop monitoring prototype

`desktop_monitor` is a separate proof-of-concept read-only localhost HTTP status dashboard. It is **not wired into** the main Windows Companion UI and is included as an example to integrate later.

Start separately with `python -m extensions.desktop_monitor` (from repository root). Never expose its HTTP listener to the public internet; keep it bound to loopback.
