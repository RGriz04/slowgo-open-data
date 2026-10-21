#!/usr/bin/env python3
"""Export SlowGo's merged places build (OpenStreetMap + Overture) to one gzipped JSON-lines file.

    python3 tools/export_places.py <path/to/places.sqlite> places/

Reads only the `places.detail` column (one JSON object per place, exactly what SlowGo's places server returns for a
place card) and the `meta` table. Writes places/places.jsonl.gz (rows sorted by pid, gzip mtime 0 so the output is
byte-reproducible) and places/manifest.json (counts by state and by source, the build's meta, SHA-256 of each file).

Place fixes: when the build folder has place-fixes.json next to places.sqlite (SlowGo's build keeps the fixes file it
used there), writes places/fixes.json: the ACTIVE and RETIRED fixes with their provenance (who, when, source,
reference, licence) and our check. Proposed fixes (not yet checked, never applied) are not published. Every place
whose `sources` names `fix:<id>` must have that fix active in the file, or the export stops. A build without the
file writes no fixes.json (and removes one left from an earlier export).

No Google links (SlowGo's rule, 2026-10-21: nothing from Google in the open data). A `website`, `menu` or `address`
value that is a Google Maps or Google Search link (maps.app.goo.gl, goo.gl, google.<tld>/maps|search|url,
maps.google.*, g.page, g.co, share.google, local.google, business.google, googlemaps.com, Google's cached copies,
Google's food-ordering and Google+ pages, anything on Google's main site, google.<tld> or www.google.<tld>, and
gmail.com given as a website, which is never the business's own page and can carry a mailbox name) is dropped from the record; the place stays. Such values came to us from
Overture's sources, not from Google, but they point into Google's own place database. A business's own web page
that merely happens to be hosted by Google (sites.google.com, a Google Drive or Docs menu, a Play Store app page, business.site) or a link that only carries a
utm_source=google tracking tag is the
business's own content and stays. A name, website, menu or address value holding an e-mail address is set to null
too (a mailbox can be a person's). manifest.json counts both (`google_links_dropped`, keys "email:<field>").
Standard library only.
"""
import collections
import gzip
import hashlib
import json
import os
import re
import sqlite3
import sys

GOOGLE_LINK = re.compile(r"maps\.app\.goo\.gl|goo\.gl/|google\.[a-z.]+/(maps|search|url)\b|maps\.google\.|"
                         r"(^|[/.\s])g\.page\b|(^|//)g\.co/|share\.google\b|(food|plus|local|business)\.google\.|"
                         r"(^|[/.])(googlemaps|gmail)\.com\b|google\.[a-z.]+/viewer/chooseprovider|webcache\.googleusercontent\.|"
                         r"^\s*(https?://)?(www\.)?google\.(com|co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2})(?=[/?#:]|\s*$)", re.I)
LINK_FIELDS = ("website", "menu")


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
EMAIL_FIELDS = ("name", "website", "menu")


def drop_google_links(j, counter):
    """Set to null the Google Maps / Search link values of a place record (the place stays), and any name, website,
    menu or address value that holds an e-mail address (a mailbox can be a person's; none of these fields is meant
    for one). Counts by field in `counter` ("email:<field>" for the second kind)."""
    for k in LINK_FIELDS:
        if isinstance(j.get(k), str) and GOOGLE_LINK.search(j[k]):
            j[k] = None
            counter[k] += 1
    for k in EMAIL_FIELDS:
        if isinstance(j.get(k), str) and EMAIL.search(j[k]):
            j[k] = None
            counter["email:" + k] += 1
    a = j.get("address")
    if isinstance(a, dict):
        for k in list(a):
            if isinstance(a[k], str) and GOOGLE_LINK.search(a[k]):
                a[k] = None
                counter["address." + k] += 1
            elif isinstance(a[k], str) and EMAIL.search(a[k]):
                a[k] = None
                counter["email:address." + k] += 1
    return j


FIX_FIELDS = ("id", "op", "status", "target", "set", "why", "provenance", "checked")
OWNER = "BackRoad Apps LLC"   # who publishes this database: a fix's who-fields are published as this, never a person
PUBLISHED_STATUSES = ("active", "retired")


def public_fixes(doc):
    """SlowGo's place-fixes.json -> the rows we publish: active and retired fixes, designed fields only, by id."""
    if doc.get("format") != "slowgo-place-fixes/1":
        raise SystemExit("place-fixes.json: unknown format %r" % doc.get("format"))
    rows = [{k: f[k] for k in FIX_FIELDS if k in f} for f in doc["fixes"] if f.get("status") in PUBLISHED_STATUSES]
    for f in rows:                      # "by" (who found it, who checked it) names the publisher, not a person
        for k in ("provenance", "checked"):
            if isinstance(f.get(k), dict) and f[k].get("by"):
                f[k] = dict(f[k], by=OWNER)
    return sorted(rows, key=lambda f: f["id"])


def write_fixes(db, out, fix_tags, meta):
    src = os.path.join(os.path.dirname(os.path.abspath(db)), "place-fixes.json")
    dest = os.path.join(out, "fixes.json")
    if not os.path.exists(src):
        if fix_tags:
            raise SystemExit("places name fixes %s but the build has no place-fixes.json" % sorted(fix_tags))
        if os.path.exists(dest):
            os.remove(dest)
        return None
    raw = open(src, "rb").read()
    rows = public_fixes(json.loads(raw))
    active = {f["id"] for f in rows if f["status"] == "active"}
    missing = sorted(fix_tags - active)
    if missing:
        raise SystemExit("places name fixes that aren't active in place-fixes.json: %s" % missing)
    doc = {
        "about": "SlowGo's hand corrections to the places database (additions, corrections, removals), active and "
                 "retired, with where each came from. A place changed by a fix lists fix:<id> in its sources. "
                 "Licence: ODbL 1.0 as part of this database; fixes with licence odbl-from-osm derive from "
                 "OpenStreetMap (share-alike); 'own' fixes are SlowGo's own observations; 'open-other' fixes keep "
                 "their source's notice in ../licences/.",
        "build": meta.get("release"),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "fixes": rows,
    }
    with open(dest, "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return {"active": len(active), "retired": len(rows) - len(active), "bytes": os.path.getsize(dest),
            "sha256": hashlib.sha256(open(dest, "rb").read()).hexdigest()}


def main(db, out):
    os.makedirs(out, exist_ok=True)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    meta = dict(con.execute("select k, v from meta"))
    rows = {"places": []}
    by_src, by_state = collections.Counter(), collections.Counter()
    fix_tags = set()
    dropped = collections.Counter()
    for (d,) in con.execute("select detail from places order by pid"):
        j = drop_google_links(json.loads(d), dropped)
        by_state[(j.get("address") or {}).get("state") or "(none)"] += 1
        rows["places"].append(json.dumps(j, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        for s in j.get("sources") or []:
            by_src[s] += 1
            if s.startswith("fix:"):
                fix_tags.add(s[4:])
    files = {}
    for st, lines in sorted(rows.items()):
        p = os.path.join(out, f"{st}.jsonl.gz")
        with open(p, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as g:
            g.write(("\n".join(lines) + "\n").encode())
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        files[os.path.basename(p)] = {"places": len(lines), "bytes": os.path.getsize(p), "sha256": h}
    man = {"build": meta, "total_places": sum(f["places"] for f in files.values()), "files": files,
           "rows_by_source": dict(by_src.most_common()),
           "rows_by_address_state": dict(by_state.most_common()),
           "google_links_dropped": dict(sorted(dropped.items())),
           "fixes": write_fixes(db, out, fix_tags, meta)}
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    print(json.dumps({"total": man["total_places"], "files": {k: (v["places"], v["bytes"]) for k, v in files.items()}}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
