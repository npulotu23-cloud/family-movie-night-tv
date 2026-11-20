#!/usr/bin/env python3
"""Print the movies the family said they finished, answered on the TV ("Did you finish it?").

  python3 -I tv_watched.py kids          # reads tv/watched-kids.json
  DATE_KEY=... python3 -I tv_watched.py date   # reads tv/watched-date.enc, scrambled with the Date Night passphrase

Run from this repo's checkout. Prints one line per answer, "<doc id> <time in ms>", oldest first, and nothing when
there are none (or the file can't be read). The TV writes these files with a GitHub token limited to this repo;
the cloud routines mark each movie watched in the phone app and remember "<id>@<time>" so it is applied only once.
"""
import json
import os
import re
import subprocess
import sys

DEC = ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-md", "sha256", "-pass", "env:DATE_KEY"]


def read(which):
    if which == "kids":
        try:
            with open("tv/watched-kids.json", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    if not os.environ.get("DATE_KEY") or not os.path.exists("tv/watched-date.enc"):
        return {}
    r = subprocess.run(DEC + ["-in", "tv/watched-date.enc"], capture_output=True)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        return {}


def main(which):
    rows = []
    for w in read(which).get("watched", []):
        i, at = str(w.get("id", "")), w.get("at")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,120}", i) and isinstance(at, int) and at > 0:
            rows.append((at, i))
    for at, i in sorted(rows):
        print(i, at)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("kids", "date"):
        sys.exit(__doc__)
    main(sys.argv[1])
