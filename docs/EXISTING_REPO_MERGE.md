# Existing repository integration

This source package is intended to **replace older APEX Companion application source in the same project repository**, not to replace unrelated projects.

1. Confirm the target repository and its default branch. Take a full backup.
2. Create a `public-companion-v0.11` branch.
3. Copy source files from this archive, preserving any existing repo assets that have been reviewed.
4. Keep `.env`, `config.json`, `data/`, personal notes and models untracked; remove tracked secrets and rotate exposed keys.
5. Run `python -m unittest discover -s tests -v` on Windows; install project requirements first.
6. Review diffs and open a PR; merge after verification.

Never push this archive into an unrelated GitHub repository just because it is writable.
