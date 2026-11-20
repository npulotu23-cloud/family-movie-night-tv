#!/usr/bin/env python3
"""Write the couple's Date Night list, scrambled, into this repo for the TV.

  DATE_KEY=<passphrase> python3 -I sync_datenight.py <docs dir> <repo dir>

<docs dir>: one JSON file per title doc (ArtifactData list of the Date Night `movies` collection with out_dir).
Writes <repo dir>/date-night.enc and prints "changed" or "nochange"; commit and push only after "changed".

The file is {"updated", "movies": [...]} encrypted with `openssl enc -aes-256-cbc -pbkdf2 -iter 100000 -md sha256`
and the passphrase in DATE_KEY, which only the couple knows (it is set in the cloud environment and on the TV).
Without it the file is unreadable. Only "Our list" goes in: list "watchlist", status "cleared"; watched ones carry "watched": true (the TV's Watched tab).
Titles kept out ("kept") never do. Each title carries its poster as base64 ("poster_b64"): from the doc's
`poster` data URI, else from the previous file, else from JustWatch's poster for that title.
"""
import base64
import datetime
import json
import os
import re
import subprocess
import sys

KEEP = ("title", "year", "rating", "type", "runtime", "seasons", "genres", "line", "about", "glow", "lg", "stream")
ENC = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-md", "sha256", "-pass", "env:DATE_KEY"]


def load_docs(folder):
    docs = {}
    for root, _, files in os.walk(folder):
        for name in files:
            if name.endswith(".json"):
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d.get("data"), dict):
                    d = d["data"]
                docs[name[:-5]] = d
    return docs


def old_bundle(path):
    if not os.path.exists(path):
        return {}
    r = subprocess.run(ENC + ["-d", "-in", path], capture_output=True)
    if r.returncode != 0:
        return {}  # a new passphrase: start over
    try:
        return json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        return {}


def justwatch_poster(slug, kind, title):
    """The s332 poster from the title's JustWatch page, as base64, or ''."""
    tries = [slug, re.sub(r"-\d{4}$", "", slug), re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")]
    for s in dict.fromkeys(tries):
        url = "https://www.justwatch.com/us/%s/%s" % ("tv-show" if kind == "show" else "movie", s)
        page = subprocess.run(["curl", "-sL", "--max-time", "20", "-A", "Mozilla/5.0", url], capture_output=True).stdout
        m = re.search(rb'og:image" content="([^"]+)"', page)
        if not m:
            continue
        img = re.sub(r"/s\d+/", "/s332/", m.group(1).decode())
        data = subprocess.run(["curl", "-sL", "--max-time", "20", "-A", "Mozilla/5.0", img], capture_output=True).stdout
        if data[:2] == b"\xff\xd8":  # a JPEG
            return base64.b64encode(data).decode()
    return ""


def main(folder, repo):
    if not os.environ.get("DATE_KEY"):
        print("skipped: no DATE_KEY")
        return
    docs = load_docs(folder)
    out = os.path.join(repo, "date-night.enc")
    old = old_bundle(out)
    old_posters = {m.get("id"): m.get("poster_b64", "") for m in old.get("movies", [])}

    ours = [(s, d) for s, d in docs.items()
            if d.get("list") == "watchlist" and d.get("status") == "cleared"]
    # Still to watch first (newest added first), then watched ones (most recently watched first): the TV's two tabs.
    ours.sort(key=lambda sd: (1, -(sd[1].get("watchedAt") or 0), sd[0]) if sd[1].get("watched")
              else (0, -(sd[1].get("addedAt") or 0), sd[0]))

    movies = []
    for slug, d in ours:
        m = {k: d[k] for k in KEEP if k in d}
        m["id"] = slug
        if d.get("watched"):
            m["watched"] = True
        m["rows"] = [{"k": r.get("k"), "l": r.get("l"), "w": r.get("w")} for r in d.get("rows", [])]
        m["watch"] = [{"key": w.get("key"), "name": w.get("name"), "how": w.get("how"), "url": w.get("url")}
                      for w in d.get("watch", [])]
        uri = d.get("poster") or ""
        if uri.startswith("data:image") and "," in uri:
            m["poster_b64"] = uri.split(",", 1)[1]
        else:
            m["poster_b64"] = old_posters.get(slug) or justwatch_poster(slug, d.get("type"), d.get("title", ""))
        movies.append(m)

    if old.get("movies") == movies:
        print("nochange", len(movies), "titles")
        return
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    plain = json.dumps({"updated": now, "movies": movies}, ensure_ascii=False).encode("utf-8")
    r = subprocess.run(ENC + ["-salt", "-out", out], input=plain, capture_output=True)
    if r.returncode != 0:
        sys.exit("openssl failed: " + r.stderr.decode(errors="replace")[:200])
    print("changed", len(movies), "titles,", sum(1 for m in movies if m["poster_b64"]), "with posters")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
