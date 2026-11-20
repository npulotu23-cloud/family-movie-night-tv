#!/usr/bin/env python3
"""Write the Family Movie Night watchlist into a checkout of the public family-movie-night-tv repo.

  python3 -I sync_watchlist.py <docs dir> <repo dir>

<docs dir>: one JSON file per movie doc (ArtifactData list of collection `movies` with out_dir; a file may hold
the doc itself or {"data": doc}). Writes <repo dir>/watchlist.json and <repo dir>/posters/<slug>.jpg, and prints
"changed" or "nochange". Commit and push only after "changed": then the TV sees a new version.

watchlist.json is {"updated": ISO time, "movies": [...]}: still to watch (newest added first), then watched ones
("watched": true, most recently watched first); "updated" moves only when the
movies change. A poster comes from the doc's `poster` data URI and is written once. Movies that only have a
`posterId` (an artifact asset the cloud routine cannot read) keep the poster seeded from the Mac; posters of
movies that left the watchlist are deleted, except those seeded ones.
"""
import base64
import datetime
import json
import os
import sys

KEEP = ("title", "year", "rating", "age", "runtime", "line", "glow", "lg", "stream", "above")


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


def main(folder, repo):
    docs = load_docs(folder)
    pdir = os.path.join(repo, "posters")
    os.makedirs(pdir, exist_ok=True)
    changed = False

    watch = [(slug, d) for slug, d in docs.items()
             if d.get("list") == "watchlist" and d.get("status") == "cleared"]
    # Still to watch first (newest added first), then watched ones (most recently watched first): the TV shows them in two tabs.
    watch.sort(key=lambda sd: (1, -(sd[1].get("watchedAt") or 0), sd[0]) if sd[1].get("watched")
               else (0, -(sd[1].get("addedAt") or 0), sd[0]))

    movies = []
    for slug, d in watch:
        m = {k: d[k] for k in KEEP if k in d}
        m["id"] = slug
        if d.get("watched"):
            m["watched"] = True
        m["rows"] = [{"k": r.get("k"), "l": r.get("l"), "w": r.get("w")} for r in d.get("rows", [])]
        m["watch"] = [{"key": w.get("key"), "name": w.get("name"), "how": w.get("how"), "url": w.get("url")}
                      for w in d.get("watch", [])]
        path = os.path.join(pdir, slug + ".jpg")
        uri = d.get("poster") or ""
        if not os.path.exists(path) and uri.startswith("data:image") and "," in uri:
            with open(path, "wb") as f:
                f.write(base64.b64decode(uri.split(",", 1)[1]))
            changed = True
        if os.path.exists(path):
            m["poster"] = "posters/%s.jpg" % slug
        movies.append(m)

    on_list = {slug for slug, _ in watch}
    for name in os.listdir(pdir):
        slug = name[:-4] if name.endswith(".jpg") else None
        if slug is None or slug in on_list:
            continue
        d = docs.get(slug)
        if d is not None and d.get("posterId") and not d.get("poster"):
            continue  # seeded from the Mac; the routine could not make it again
        os.remove(os.path.join(pdir, name))
        changed = True

    out = os.path.join(repo, "watchlist.json")
    old = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
    if old.get("movies") != movies or changed:
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"updated": now, "movies": movies}, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        changed = True
    print(("changed" if changed else "nochange"), len(movies), "movies")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
