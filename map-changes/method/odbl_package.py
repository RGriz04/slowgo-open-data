#!/usr/bin/env python3
"""Build the ODbL public package of SlowGo's OSM-derived changes (E25, BackRoad Apps LLC 2026-10-17). DRAFT: nothing is published.

    PY=../fdot-audit/.venv/bin/python            # needs pyosmium for `diff` and `stamps`
    $PY odbl_package.py diff   --state fl --stock data/florida-260831.osm.pbf --final <fl-B-closed.osm.pbf> --out PKG
    $PY odbl_package.py stamps --state ga --final <georgia-260831 closed.osm.pbf> --out PKG
    python3 odbl_package.py lists    --repo ../.. --out PKG [--live-only]  # overrides, closures, cart lists (stdlib only)
    python3 odbl_package.py relabel  --out PKG --state ny --key slowgo:reviewed --from street-view --to nysdot
    python3 odbl_package.py mark     --out PKG                  # street_view_derived / osm_import=never columns
    python3 odbl_package.py drop-google --out PKG               # the 11 Google-only rows out of a built draft
    python3 odbl_package.py manifest --out PKG                  # MANIFEST.sha256 + sizes
    $PY odbl_package.py apply --stock <stock.osm.pbf> --alterations PKG/data/fl/alterations.csv.gz --out rebuilt.osm.pbf

WHAT THE PACKAGE IS FOR. The routing map is built from OpenStreetMap (ODbL 1.0) with our own changes on top:
DOT speed limits joined to OSM ways, corroborated and held-over-45 speeds, approved speed overrides, path closures,
cart-access overrides, a crossing carve-out. ODbL §4.6 asks whoever publicly uses a Derivative Database to offer
either the whole database or "a file containing all of the alterations made to the Database or the method of making
the alterations ... including any additional Contents". This tool writes the alterations file: for every OSM object
our final extract changed, every tag key with its value before (the dated Geofabrik extract we started from) and
after (what the router was built from). Geometry is checked too and reported (our pipeline never moves a node).

TWO MODES FOR THE ALTERATIONS.
  diff    the honest one: the stock extract and the final extract compared object by object (merge join in file
          order, flat memory on an 8 GB Mac; the pattern of scripts/speed-gap/pbf_diff.py). Complete by construction.
  stamps  only for an input whose stock extract is no longer on disk (Georgia 2026-08-31: Geofabrik keeps no dated
          copy). Every SlowGo stage stamps what it changed (slowgo:path_closed + slowgo:bicycle_orig, ...), so the
          alterations are rebuilt from the stamps. Refuses on a stamp it does not know, so it can't silently miss one.

NEVER FOR OPENSTREETMAP (BackRoad Apps LLC, 2026-10-16). The package is an offer under ODbL 4.6, not an OSM contribution, and
nothing here uploads anything.

NO GOOGLE-ONLY ROW (BackRoad Apps LLC, 2026-10-20: no value whose only source is Google Maps or Street View ever goes in a build or
the open-data repo, no matter who looked). The 11 Florida speed rows on the refusal list (street_view.py,
overrides/street-view-derived.json) leave the map with rebuild 4 (google_out.py strip). ODbL needs EVERY alteration of
the map in public use listed, so the package is built from the map it describes, and write_state REFUSES a listed
way that still carries its review: a package can only be built from a map without them, and so it can only be
published once that map is the live one (the rebuild-4 swap at the 1.5 release). `drop-google` takes them out of a
draft built earlier (the 2026-10-16 draft describes rebuild 3); the street_view_derived/osm_import columns stay in the
format and are blank on every row. New
York's 8,204 HELD->45 RELEASE rows left the list on 2026-10-20 (BackRoad Apps LLC, HUB decision ny-rows-nysdot: plain NYSDOT values):
they get the blank marks of every other DOT row, even from an extract built before the relabel that still carries
slowgo:reviewed=street-view on them, because the frozen list decides whenever street_view.py is beside this file.
`mark` re-applies those two columns to an already-built package without the extracts.

NO SCDOT VALUE (BackRoad Apps LLC 2026-10-21: SCDOT values blocked in every build until a written yes covering open publishing
(ODbL) is on file in legal/scdot/). Publishing this package IS open publishing, so every writer refuses an alteration,
list row or package file that names SCDOT unless quarantine.require_scdot finds the complete permission file: `diff`
and `stamps` (write_state, on the keys our stages changed), `lists` (rows citing SCDOT), `apply` (load_alterations)
and `manifest` (a last scan of everything in the package). The flag-free hard gate, not the quarantine flag.

ONLY "YES" SOURCES (BackRoad Apps LLC 2026-10-21: nothing from Google, SCDOT or any source the register marks "no" or "unclear"
for ODbL republishing). `lists` keeps a row's source line only when every register source it cites is odbl_republish
"yes" / "yes with credit" (our own observations count as yes); a row left with no such line is dropped and reported.
`--live-only` keeps only rows the live map carries (read back from the alterations files) and writes no file that
would be empty. `manifest` refuses a package whose data or lists still name Google or Street View.

WHAT IS NEVER IN THE PACKAGE. No rider data (no trips, no reports, no names; the crossing file's rider-testimony
line is replaced by "first-party field report"), no business data, no keys, no server names or addresses, no local
paths. `lists` copies only whitelisted fields from the override files and scrubs personal names (anyone a rule file names in a who-field) to "BackRoad Apps LLC".
"""
import argparse
import csv
import datetime
import gzip
import hashlib
import json
import os
import re
import struct
import sys
import tempfile

ORDER = {"n": 0, "w": 1, "r": 2}
REC = struct.Struct("<cqQQ")            # type, id, geometry digest, tag digest
OWNER = "BackRoad Apps LLC"   # the publisher; any person's name in text copied into the package becomes this
# People are found by a general rule, never a list of names written here: whoever a rule file records in a who-field
# (verified_by, ruled_by, confirmed_by, by, ...: any key ending in "by") is a person, and that name, and its first
# name, is replaced in any free text we copy (riders: see the testimony rule in scrub).
WHO_KEY = re.compile(r"(^|_)by$")
NAME_LIKE = re.compile(r"^[A-Z][a-z]+(?: [A-Z][A-Za-z'.-]+){0,2}$")
_PEOPLE = None
SPEED_KEY = re.compile(r"^maxspeed($|:)")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def d8(obj):
    return int.from_bytes(hashlib.blake2b(repr(obj).encode(), digest_size=8).digest(), "little")


def people_in(obj, found=None):
    """Names held in who-fields (keys ending in "by") anywhere in a JSON object."""
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and WHO_KEY.search(str(k)) and NAME_LIKE.match(v.strip()):
                found.add(v.strip())
                found.add(v.strip().split()[0])
            else:
                people_in(v, found)
    elif isinstance(obj, list):
        for v in obj:
            people_in(v, found)
    return found


def people(root=None):
    """Every person the rule files beside this script name in a who-field, longest first (cached). A recipient's copy
    of method/ has no rule files and copies no free text, so it finds none and needs none."""
    global _PEOPLE
    if _PEOPLE is not None and root is None:
        return _PEOPLE
    base = root or os.path.dirname(os.path.abspath(__file__))
    found = set()
    for sub in ("overrides", "states"):
        d = os.path.join(base, sub)
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if n.endswith(".json"):
                try:
                    people_in(readj(os.path.join(d, n)), found)
                except (OSError, ValueError):
                    continue
    names = tuple(sorted(found, key=lambda x: (-len(x), x)))
    if root is None:
        _PEOPLE = names
    return names


def scrub(text):
    """Personal names out of any free text we copy (rulings, sources): see people()."""
    if not isinstance(text, str):
        return text
    # A rider's own words can say where they ride from and to: keep only that a field report exists, and its date.
    text = re.sub(r"Rider testimony \([^,)]*,\s*([0-9-]+)\):.*", r"First-party field report (\1): a rider crosses here at grade at this signal.", text)
    text = re.sub(r"Rider testimony \([^)]*\)", "first-party field report", text)
    text = re.sub(r"/Users/[^\s'\"]+", "<local path>", text)
    for n in people():
        text = re.sub(r"\b%s\b" % re.escape(n), OWNER, text)
    return text


def readj(path):
    with open(path) as fh:
        return json.load(fh)


def writej(obj, path, **kw):
    with open(path, "w") as fh:
        json.dump(obj, fh, **kw)


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


# ── alterations: diff mode ──────────────────────────────────────────────────────────────────────────────────────
def _digests():
    """Per-object (geometry, tags) digests. Python's own hash() is used (both passes run in ONE process, so string
    hashing is consistent): ~15x faster than a cryptographic digest, and a collision could only HIDE a change if two
    different tag sets hashed alike in the same slot, which the full tag comparison in pass 3 would then never see.
    Node geometry is stored exactly (the coordinates themselves), not hashed."""
    import osmium
    M = (1 << 64) - 1

    class Dig(osmium.SimpleHandler):
        def __init__(self, sink):
            super().__init__()
            self.sink = sink

        def node(self, n):
            loc = n.location
            g = ((loc.x & 0xFFFFFFFF) << 32) | (loc.y & 0xFFFFFFFF)
            tg = (hash(frozenset((t.k, t.v) for t in n.tags)) & M) if len(n.tags) else 0
            self.sink(b"n", n.id, g, tg, n)

        def way(self, w):
            self.sink(b"w", w.id, hash(tuple(nd.ref for nd in w.nodes)) & M,
                      hash(frozenset((t.k, t.v) for t in w.tags)) & M, w)

        def relation(self, r):
            self.sink(b"r", r.id, hash(tuple((m.type, m.ref, m.role) for m in r.members)) & M,
                      hash(frozenset((t.k, t.v) for t in r.tags)) & M, r)
    return Dig


def alterations_by_diff(stock, final, tmpdir):
    """Yield (type, id, before_tags|None, after_tags|None, geometry_changed) for every object that differs."""
    import osmium
    Dig = _digests()
    dig = os.path.join(tmpdir, "stock.dig")
    counts = {"stock": {"n": 0, "w": 0, "r": 0}, "final": {"n": 0, "w": 0, "r": 0}}
    with open(dig, "wb", buffering=1 << 22) as f:
        cs = counts["stock"]

        def put(t, i, g, tg, _o, pack=REC.pack, write=f.write):
            write(pack(t, i, g, tg)); cs[t.decode()] += 1
        Dig(put).apply_file(stock)

    changed = os.path.join(tmpdir, "changed.jsonl")
    state = {"buf": None}
    want = {"n": set(), "w": set(), "r": set()}
    deleted = []
    fin = open(dig, "rb", buffering=1 << 22)
    out = open(changed, "w")

    def nxt():
        raw = fin.read(REC.size)
        return REC.unpack(raw) if raw else None

    state["buf"] = nxt()

    def key(t, i):
        return (ORDER[t.decode() if isinstance(t, bytes) else t], i)

    def take(t, i, g, tg, o):
        counts["final"][t.decode()] += 1
        while state["buf"] is not None and key(state["buf"][0], state["buf"][1]) < key(t, i):
            bt, bi = state["buf"][0].decode(), state["buf"][1]
            deleted.append((bt, bi)); want[bt].add(bi)
            state["buf"] = nxt()
        b = state["buf"]
        if b is not None and (b[0], b[1]) == (t, i):
            state["buf"] = nxt()
            if (b[2], b[3]) == (g, tg):
                return
            tags = {x.k: x.v for x in o.tags}
            out.write(json.dumps([t.decode(), i, tags, b[2] != g, False]) + "\n")
            want[t.decode()].add(i)
        else:                                   # only in final: an added object
            out.write(json.dumps([t.decode(), i, {x.k: x.v for x in o.tags}, True, True]) + "\n")

    Dig(take).apply_file(final)
    while state["buf"] is not None:
        bt, bi = state["buf"][0].decode(), state["buf"][1]
        deleted.append((bt, bi)); want[bt].add(bi)
        state["buf"] = nxt()
    out.close(); fin.close(); os.unlink(dig)

    before = {}

    def _grab(kind):
        def cb(self, o):
            if o.id in want[kind]:
                before[(kind, o.id)] = {x.k: x.v for x in o.tags}
        return cb
    Before = type("Before", (osmium.SimpleHandler,),
                  {name: _grab(kind) for kind, name in (("n", "node"), ("w", "way"), ("r", "relation")) if want[kind]})

    if any(want.values()):
        Before().apply_file(stock)
    with open(changed) as f:
        for line in f:
            t, i, after, geom, added = json.loads(line)
            yield t, i, (None if added else before.get((t, i), {})), after, geom
    for t, i in deleted:
        yield t, i, before.get((t, i), {}), None, True
    os.unlink(changed)
    alterations_by_diff.counts = counts


# ── alterations: stamps mode ────────────────────────────────────────────────────────────────────────────────────
KNOWN_STAMPS = {"slowgo:path_closed", "slowgo:bicycle_orig", "slowgo:short_link_open"}


def alterations_by_stamps(final):
    import osmium
    rows, unknown = [], set()

    class S(osmium.SimpleHandler):
        def way(self, w):
            tags = {x.k: x.v for x in w.tags}
            stamps = {k for k in tags if k.startswith("slowgo:")}
            if not stamps:
                return
            unknown.update(stamps - KNOWN_STAMPS)
            before = {k: v for k, v in tags.items() if k not in stamps}
            if "slowgo:path_closed" in tags:
                if "slowgo:bicycle_orig" in tags:
                    before["bicycle"] = tags["slowgo:bicycle_orig"]
                else:
                    before.pop("bicycle", None)
            rows.append(("w", w.id, before, tags, False))

    S().apply_file(final)
    if unknown:
        raise SystemExit(f"stamps mode refuses: unknown stamps {sorted(unknown)} — use diff mode with the stock extract")
    return rows


# ── Street View-derived rows: listed (ODbL 4.6) but never for OSM ───────────────────────────────────────────────
SV_COLUMNS = ("street_view_derived", "osm_import")


def street_view_ids():
    """The frozen street-view-derived way ids, or None where street_view.py isn't beside this file (a recipient's
    copy of method/): then the way's own tags decide (sv_flag)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import street_view
        street_view.check_frozen()
        return street_view.way_ids()
    except ImportError:
        return None


class GoogleRefused(SystemExit):
    pass


REVIEW_KEYS = ("maxspeed", "maxspeed:source", "slowgo:maxspeed_action", "slowgo:fdot_roadway", "slowgo:reviewed",
               "slowgo:street_view_derived", "slowgo:maxspeed_osm_orig")


def refuse_google(way_id, after, ids):
    """A refusal-list way that still carries its Street View review may not be in the package (BackRoad Apps LLC 2026-10-20)."""
    if ids is None or int(way_id) not in ids:
        return
    a = after or {}
    if a.get("slowgo:reviewed") == "street-view" or a.get("slowgo:street_view_derived") \
            or a.get("slowgo:maxspeed_action") == "reviewed_confirm":
        raise GoogleRefused(f"way {way_id}: a Google-only speed row (refusal list, BackRoad Apps LLC 2026-10-20) is in this extract. "
                            f"Build the package from a map without them (google_out.py strip), never list them.")


def sv_flag(way_id, after, ids):
    # The frozen list decides when we have it (an extract built before 2026-10-20 still tags New York's 8,204
    # NYSDOT rows slowgo:reviewed=street-view; they are off the list). The tags decide only in a recipient's copy.
    # Since 2026-10-20 a listed way that still carries its review never gets here (refuse_google stops the build),
    # and a listed way without it (OSM's own value back, or FDOT's own held value) is an ordinary row: no mark.
    if ids is not None:
        return False
    a = after or {}
    return a.get("slowgo:reviewed") == "street-view" or a.get("slowgo:street_view_derived") == "yes"


def sv_cells(flag):
    return ["yes", "never"] if flag else ["", ""]


# ── SCDOT hard gate (BackRoad Apps LLC 2026-10-21) ────────────────────────────────────────────────────────────────────────────
def _quarantine():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import quarantine
    return quarantine


def refuse_scdot_alteration(t, i, key, after_value):
    """An alteration we made whose key or new value names SCDOT may not be in the package without the permission."""
    q = _quarantine()
    if q.mentions_scdot(key) or q.mentions_scdot(after_value):
        q.require_scdot(f"ODbL package alteration {t}{i} {key}={str(after_value)[:60]}")


def refuse_scdot_package(out):
    """Scan a built package (data/*/*.csv.gz, lists/*.json, summaries) for SCDOT before it is sealed."""
    q = _quarantine()
    for root, _, files in os.walk(out):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            if fn == "MANIFEST.sha256":
                continue
            if fn.endswith(".gz"):
                with gzip.open(p, "rt", newline="", errors="replace") as f:
                    for n, line in enumerate(f):
                        if q.mentions_scdot(line):
                            q.require_scdot(f"ODbL package file {os.path.relpath(p, out)} line {n + 1}")
            elif fn.endswith((".json", ".csv", ".md", ".txt")):
                with open(p, errors="replace") as f:
                    if q.mentions_scdot(f.read()):
                        q.require_scdot(f"ODbL package file {os.path.relpath(p, out)}")


# ── writers ─────────────────────────────────────────────────────────────────────────────────────────────────────
def speed_class(after):
    act = after.get("slowgo:maxspeed_action", "")
    if after.get("slowgo:maxspeed_override"):
        return "override_" + after.get("slowgo:maxspeed_source", "unknown")
    if act == "corridor_floor":
        return "corridor_evidence_floor"
    if act in ("corroborated_fill", "corroborated"):
        return "dot_corroborated"
    if act == "held_over45_written":
        return "dot_held_over45_written"
    if act == "reviewed_confirm":
        return "dot_reviewed_confirm"
    if act:
        return "dot_" + act
    return "other"


def write_state(state, rows, out, inputs, mode, counts=None):
    d = ensure(os.path.join(out, "data", state))
    keys, kinds, speed_n, geom, n_obj = {}, {"modified": 0, "added": 0, "deleted": 0}, 0, 0, 0
    reviewed = {}
    sv_ids, sv_n = street_view_ids(), 0
    with gzip.open(os.path.join(d, "alterations.csv.gz"), "wt", newline="") as fa, \
            gzip.open(os.path.join(d, "speed.csv.gz"), "wt", newline="") as fs:
        wa, ws = csv.writer(fa), csv.writer(fs)
        wa.writerow(["osm_type", "osm_id", "change", "key", "before", "after"])
        ws.writerow(["osm_way_id", "maxspeed", "maxspeed_before", "maxspeed_source", "slowgo_action", "class",
                     "station", "dot_roadway", "override_id", *SV_COLUMNS])
        for t, i, before, after, geom_changed in rows:
            n_obj += 1
            change = "added" if before is None else "deleted" if after is None else "modified"
            kinds[change] += 1
            geom += bool(geom_changed and change == "modified")
            b, a = before or {}, after or {}
            for k in sorted(set(b) | set(a)):
                if b.get(k) != a.get(k):
                    refuse_scdot_alteration(t, i, k, a.get(k, ""))
                    wa.writerow([t, i, change, k, b.get(k, ""), a.get(k, "")])
                    keys[k] = keys.get(k, 0) + 1
            if geom_changed and change == "modified":
                wa.writerow([t, i, "geometry", "", "", "node list/location changed"])
            if t == "w" and after is not None and any(SPEED_KEY.match(k) and b.get(k) != a.get(k) for k in set(a) | set(b)):
                refuse_google(i, a, sv_ids)
                speed_n += 1
                if a.get("slowgo:reviewed"):
                    reviewed[a["slowgo:reviewed"]] = reviewed.get(a["slowgo:reviewed"], 0) + 1
                ws.writerow([i, a.get("maxspeed", ""), b.get("maxspeed", ""),
                             a.get("maxspeed:source") or a.get("slowgo:maxspeed_source", ""),
                             a.get("slowgo:maxspeed_action", ""), speed_class(a), a.get("slowgo:maxspeed_station", ""),
                             a.get("slowgo:fdot_roadway", ""), a.get("slowgo:maxspeed_override", ""),
                             *sv_cells(sv_flag(i, a, sv_ids))])
                sv_n += sv_flag(i, a, sv_ids)
    summary = {
        "state": state, "mode": mode, "inputs": inputs,
        "objects_changed": n_obj, "by_change": kinds, "geometry_changes": geom,
        "speed_rows": speed_n, "changed_keys": dict(sorted(keys.items(), key=lambda kv: -kv[1])),
        "speed_rows_reviewed_with": reviewed,
        "street_view_derived_rows": sv_n, "osm_import_never_rows": sv_n,
        "element_counts": counts,
        "built_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    writej(summary, os.path.join(d, "summary.json"), indent=1)
    print(json.dumps({k: summary[k] for k in ("state", "mode", "objects_changed", "by_change", "geometry_changes", "speed_rows")}))
    return summary


def cmd_diff(a):
    inputs = {"stock": {"file": os.path.basename(a.stock), "bytes": os.path.getsize(a.stock), "sha256": sha256(a.stock)},
              "final": {"file": os.path.basename(a.final), "bytes": os.path.getsize(a.final), "sha256": sha256(a.final)}}
    with tempfile.TemporaryDirectory(dir=a.tmp) as td:
        rows = alterations_by_diff(a.stock, a.final, td)
        write_state(a.state, rows, a.out, inputs, "diff")
    s = readj(os.path.join(a.out, "data", a.state, "summary.json"))
    s["element_counts"] = getattr(alterations_by_diff, "counts", None)
    writej(s, os.path.join(a.out, "data", a.state, "summary.json"), indent=1)


def cmd_stamps(a):
    inputs = {"stock": {"file": a.stock_name or "(not on disk)", "sha256": a.stock_sha or ""},
              "final": {"file": os.path.basename(a.final), "bytes": os.path.getsize(a.final), "sha256": sha256(a.final)}}
    write_state(a.state, alterations_by_stamps(a.final), a.out, inputs, "stamps")


# ── lists: overrides, closures, cart lists (whitelisted fields only) ────────────────────────────────────────────
ROW_FIELDS = ("id", "active", "action", "way_id", "way_ids", "maxspeed_mph", "golf_cart", "expected_name",
              "expected_highway", "expected_length_m", "where", "source", "source_type", "source_date", "fetched_on",
              "evidence_objectids", "confidence", "ruled_on", "confirmed", "confirmed_on", "reason", "why")


def _ids_ok(ids, register):
    q = _quarantine()
    return all(i == q.FIRST_PARTY or q.odbl_republish_ok(i, register) for i in ids)


def republishable(r, register):
    """(row, dropped source lines) with only the source lines whose every register source may be republished under
    the ODbL (BackRoad Apps LLC 2026-10-21); row None when nothing permitted is left. Our own observations count as yes; a line
    that matches no register source (unregistered) does not."""
    q = _quarantine()
    if r.get("sources"):
        keep = [t for t in r["sources"] if _ids_ok(q.row_source_ids({"sources": [t]}, register), register)]
        dropped = [t for t in r["sources"] if t not in keep]
        if not keep:
            return None, dropped
        return (dict(r, sources=keep) if dropped else r), dropped
    if r.get("source"):
        ids = q.row_source_ids({"source": r["source"]}, register)
        return (r, []) if _ids_ok(ids, register) else (None, [r["source"]])
    return r, []


def clean_row(r, register=None):
    o = {k: scrub(r[k]) for k in ROW_FIELDS if k in r}
    if "sources" in r:
        o["sources"] = [scrub(s) for s in r["sources"]]
    if register is not None:
        try:
            import quarantine
            ids = quarantine.row_source_ids(r, register)
            o["register_sources"] = ids
            o["quarantined_sources"] = [i for i in ids if quarantine.is_quarantined(i, register)]
        except Exception as e:                               # never block the package on the register
            o["register_sources"] = f"(register unavailable: {e})"
    return o


LIVE_STAMPS = ("slowgo:maxspeed_override", "slowgo:crossing_carveout", "slowgo:golf_cart_override",
               "slowgo:access_closed")


def live_row_ids(out):
    """Rule-row ids the live map actually carries, read back from the alterations files (None if none built yet)."""
    ids, seen = set(), False
    for st in sorted(os.listdir(os.path.join(out, "data"))) if os.path.isdir(os.path.join(out, "data")) else []:
        p = os.path.join(out, "data", st, "alterations.csv.gz")
        if not os.path.exists(p):
            continue
        seen = True
        with gzip.open(p, "rt", newline="") as f:
            for r in csv.DictReader(f):
                if r["key"] in LIVE_STAMPS and r["after"]:
                    ids.add(r["after"])
    return ids if seen else None


def decode_varints(b64):
    import base64
    raw, out, cur, shift, last = base64.b64decode(b64), [], 0, 0, 0
    for byte in raw:
        cur |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            continue
        last += cur
        out.append(last)
        cur, shift = 0, 0
    return out


def read_generated_js(path):
    with open(path) as fh:
        txt = fh.read()
    body = txt[txt.index("export default") + len("export default"):].strip().rstrip(";")
    return json.loads(body)


def cmd_lists(a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import quarantine
        register = quarantine.load_register()
    except Exception:
        register = None
    de = os.path.join(a.repo, "scripts", "dot-enrich")
    d = ensure(os.path.join(a.out, "lists"))
    made = []
    live = live_row_ids(a.out)
    if getattr(a, "live_only", False) and live is None:
        raise SystemExit("lists --live-only needs the alterations files (data/<state>/alterations.csv.gz) first")
    if register is None:
        raise SystemExit("lists needs the source register (source-register.json) to keep out no/unclear sources")
    report = {"withheld": {}, "source_lines_dropped": {}, "not_live": {}, "files_not_written": []}
    for name, key in (("fl.speed-overrides.json", "overrides"), ("az.speed-overrides.json", "overrides"),
                      ("fl.golfcart-overrides.json", "overrides"), ("fl.cart-lanes.json", "rows"),
                      ("sc.access-closure-rules.json", "rules")):
        p = os.path.join(de, "overrides", name)
        if not os.path.exists(p):
            continue
        src = readj(p)
        _quarantine().guard_scdot_rows([r for r in src.get(key, []) if r.get("active")], f"ODbL package list {name}")
        raw = [r for r in src.get(key, []) if r.get("active")]
        inactive = len(src.get(key, [])) - len(raw)
        rows, not_live = _filter_rows(raw, name, register, live, a, report)
        act = [clean_row(r, register) for r in rows]
        for r in act:
            r["in_live_map"] = r["id"] in live if live is not None else None
        if not act and getattr(a, "live_only", False):
            _drop_list(d, name, report)
            continue
        doc = {"file": name, "what": scrub(src.get("_what_this_is", "")), "active_rows": len(act),
               "inactive_rows_omitted": inactive, "rows": act}
        if not_live:
            doc["not_in_live_map_omitted"] = not_live
        if report["withheld"].get(name):
            doc["withheld_not_republishable"] = len(report["withheld"][name])
        if name.startswith("sc."):
            doc["note"] = "South Carolina is not in the live map; listed so the package is complete when it is."
        writej(doc, os.path.join(d, name), indent=1)
        made.append(name)
    cp = os.path.join(de, "states", "fl.crossings.json")
    if os.path.exists(cp):
        src = readj(cp)
        _quarantine().guard_scdot_rows([r for r in src.get("crossings", []) if r.get("status") == "verified"],
                                       "ODbL package list fl.crossings.json")
        kept, _ = _filter_rows([r for r in src.get("crossings", []) if r.get("status") == "verified"],
                               "fl.crossings.json", register, live, a, report)
        rows = [clean_row(r, register) | {k: r[k] for k in ("signal_nodes", "crossed_ways", "approach_ways",
                                                             "crossed_max_mph", "status") if k in r}
                for r in kept]
        for r in rows:
            r["in_live_map"] = r["id"] in live if live is not None else None
        if rows or not getattr(a, "live_only", False):
            writej({"file": "fl.crossings.json", "what": "Allowlisted signalised crossings whose short approach "
                    "streets keep bicycle access in our extract (crossing carve-out).", "rows": rows},
                   os.path.join(d, "fl.crossings.json"), indent=1)
            made.append("fl.crossings.json")
        else:
            _drop_list(d, "fl.crossings.json", report)
    for js, out_name in ((a.cart_legal, "cart-legal-ways.json"), (a.cart_lanes, "villages-cart-lanes.json")):
        if js and os.path.exists(js):
            g = read_generated_js(js)
            if isinstance(g.get("states"), dict):            # cartLegalWays: {state: base64 varints}
                states = {k: decode_varints(v) for k, v in g["states"].items()}
            else:                                              # villagesCartLanes: one list in "ways"
                states = {"fl_villages": decode_varints(g["ways"])}
            prov = json.loads(scrub(json.dumps(g.get("provenance", {}))))
            _quarantine().guard_scdot_text([json.dumps(prov)], f"ODbL package list {out_name} provenance")
            writej({"source": os.path.basename(js), "generatedAt": g.get("generatedAt"), "provenance": prov,
                    "way_ids": states}, os.path.join(d, out_name))
            made.append(out_name)
    for js, out_name in ((a.cart_legal, "cart-legal-ways.json"), (a.cart_lanes, "villages-cart-lanes.json")):
        if not js and getattr(a, "live_only", False):
            _drop_list(d, out_name, report)
    print("lists:", ", ".join(made))
    print(json.dumps(report))
    return report


def _filter_rows(rows, name, register, live, a, report):
    """Republish filter (always) then the live-map filter (--live-only). Returns (rows kept, not-live count)."""
    out, not_live = [], 0
    for r in rows:
        kept, dropped = republishable(r, register)
        if dropped:
            report["source_lines_dropped"].setdefault(name, {})[r.get("id")] = [
                ", ".join(_quarantine().row_source_ids({"sources": [t]}, register)) for t in dropped]
        if kept is None:
            report["withheld"].setdefault(name, []).append(r.get("id"))
            continue
        if getattr(a, "live_only", False) and r.get("id") not in live:
            not_live += 1
            report["not_live"].setdefault(name, []).append(r.get("id"))
            continue
        out.append(kept)
    return out, not_live


def _drop_list(d, name, report):
    p = os.path.join(d, name)
    if os.path.exists(p):
        os.remove(p)
    report["files_not_written"].append(name)


def load_alterations(path):
    """{(type, id): [(key, before, after), ...]} from an alterations.csv.gz; refuses geometry/added/deleted rows,
    which this package never contains (our stages change tags only)."""
    alt = {}
    # The SCDOT gate needs SlowGo's register (quarantine.py beside this file). A recipient's copy of method/ has no
    # register and publishes nothing of ours, so `apply` runs there without it; in SlowGo's repo the gate always runs.
    gate = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine.py"))
    with gzip.open(path, "rt", newline="") as f:
        for r in csv.DictReader(f):
            if r["change"] != "modified":
                raise SystemExit(f"apply: {r['change']} row for {r['osm_type']}{r['osm_id']} — not a tag change")
            if gate:
                refuse_scdot_alteration(r["osm_type"], r["osm_id"], r["key"], r["after"])
            alt.setdefault((r["osm_type"], int(r["osm_id"])), []).append((r["key"], r["before"], r["after"]))
    return alt


def apply_tags(tags, changes):
    """New tag dict, or raise ValueError when the stock value isn't what the alterations file expects."""
    out = dict(tags)
    for k, before, after in changes:
        if out.get(k, "") != before:
            raise ValueError(f"{k}: stock has {out.get(k, '')!r}, alterations expect {before!r}")
        if after == "":
            out.pop(k, None)
        else:
            out[k] = after
    return out


def cmd_apply(a):
    """Rebuild our extract: the stock extract + the alterations file (what a recipient of the package does)."""
    import osmium
    alt = load_alterations(a.alterations)
    writer = osmium.SimpleWriter(a.out)
    stats = {"applied": 0, "mismatch": 0}

    def fix(kind, o, add):
        ch = alt.pop((kind, o.id), None)
        if ch is None:
            add(o)
            return
        try:
            add(o.replace(tags=apply_tags({t.k: t.v for t in o.tags}, ch)))
            stats["applied"] += 1
        except ValueError as e:
            stats["mismatch"] += 1
            if stats["mismatch"] <= 10:
                print(f"  MISMATCH {kind}{o.id}: {e}")
            add(o)

    class H(osmium.SimpleHandler):
        def node(self, n):
            fix("n", n, writer.add_node)

        def way(self, w):
            fix("w", w, writer.add_way)

        def relation(self, r):
            fix("r", r, writer.add_relation)

    H().apply_file(a.stock)
    writer.close()
    stats["not_found"] = len(alt)
    print(json.dumps(stats))
    return 1 if stats["mismatch"] or alt else 0


def cmd_mark(a):
    """Re-apply street_view_derived / osm_import to every data/<state>/speed.csv.gz of a built package (no extracts
    needed): the marks change when the frozen list does, the alterations don't."""
    ids = street_view_ids()
    if ids is None:
        raise SystemExit("mark needs street_view.py and overrides/street-view-derived.json beside this script")
    present = google_rows_in(a.out, ids)
    if present:
        raise GoogleRefused(f"{sum(present.values())} Google-only row(s) in this package ({present}): run drop-google first "
                            f"(BackRoad Apps LLC 2026-10-20)")
    total = {}
    for st in sorted(os.listdir(os.path.join(a.out, "data"))):
        p = os.path.join(a.out, "data", st, "speed.csv.gz")
        if not os.path.exists(p):
            continue
        with gzip.open(p, "rt", newline="") as f:
            r = csv.reader(f)
            head = next(r)
            body = list(r)
        base = [c for c in head if c not in SV_COLUMNS]
        keep = [head.index(c) for c in base]
        wi = head.index("osm_way_id")
        n = 0
        tmp = p + ".tmp"
        with gzip.open(tmp, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(base + list(SV_COLUMNS))
            for row in body:
                flag = int(row[wi]) in ids
                n += flag
                w.writerow([row[k] for k in keep] + sv_cells(flag))
        os.replace(tmp, p)
        sp = os.path.join(a.out, "data", st, "summary.json")
        if os.path.exists(sp):
            s = readj(sp)
            s["street_view_derived_rows"] = n
            s["osm_import_never_rows"] = n
            writej(s, sp, indent=1)
        total[st] = n
    print(json.dumps({"street_view_derived_rows": total, "sum": sum(total.values())}))
    if sum(total.values()) != len(ids):
        print(f"  NOTE: {len(ids) - sum(total.values())} listed way(s) not in any speed file of this package")


def google_rows_in(out, ids):
    """state -> count of refusal-list ways in data/<state>/speed.csv.gz."""
    got = {}
    for st in sorted(os.listdir(os.path.join(out, "data"))):
        p = os.path.join(out, "data", st, "speed.csv.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt", newline="") as f:
                n = sum(int(r["osm_way_id"]) in ids for r in csv.DictReader(f))
            if n:
                got[st] = n
    return got


def cmd_drop_google(a):
    """Take the refusal-list ways' speed rows out of an already-built package (BackRoad Apps LLC 2026-10-20), without the extracts:
    their speed.csv.gz row goes, and in alterations.csv.gz every row of that way whose key the review wrote
    (REVIEW_KEYS) goes; any other alteration of the same way (a path closure, say) stays. summary.json is recounted.
    Idempotent. Returns what it removed."""
    ids = street_view_ids()
    if ids is None:
        raise SystemExit("drop-google needs street_view.py and overrides/street-view-derived.json beside this script")
    removed = {}
    for st in sorted(os.listdir(os.path.join(a.out, "data"))):
        d = os.path.join(a.out, "data", st)
        sp, ap_ = os.path.join(d, "speed.csv.gz"), os.path.join(d, "alterations.csv.gz")
        if not os.path.exists(sp):
            continue
        with gzip.open(sp, "rt", newline="") as f:
            r = csv.reader(f); head = next(r); body = list(r)
        wi = head.index("osm_way_id")
        keep = [row for row in body if int(row[wi]) not in ids]
        gone_speed = sorted(int(row[wi]) for row in body if int(row[wi]) in ids)
        gone_alt, keys_gone, still = 0, {}, set()
        if gone_speed:
            tmp = sp + ".tmp"
            with gzip.open(tmp, "wt", newline="") as f:
                w = csv.writer(f); w.writerow(head); w.writerows(keep)
            os.replace(tmp, sp)
        if gone_speed and os.path.exists(ap_):
            tmp = ap_ + ".tmp"
            with gzip.open(ap_, "rt", newline="") as fi, gzip.open(tmp, "wt", newline="") as fo:
                r = csv.reader(fi); w = csv.writer(fo); h = next(r); w.writerow(h)
                ti, ii, ki = h.index("osm_type"), h.index("osm_id"), h.index("key")
                for row in r:
                    if row[ti] == "w" and int(row[ii]) in ids:
                        if row[ki] in REVIEW_KEYS:
                            gone_alt += 1; keys_gone[row[ki]] = keys_gone.get(row[ki], 0) + 1
                            continue
                        still.add(int(row[ii]))
                    w.writerow(row)
            os.replace(tmp, ap_)
        sj = os.path.join(d, "summary.json")
        if gone_speed and os.path.exists(sj):
            s = readj(sj)
            s["speed_rows"] = s.get("speed_rows", 0) - len(gone_speed)
            ck = s.get("changed_keys", {})
            for k, n in keys_gone.items():
                ck[k] = ck.get(k, 0) - n
                if ck[k] <= 0:
                    ck.pop(k)
            s["changed_keys"] = dict(sorted(ck.items(), key=lambda kv: -kv[1]))
            n_obj_gone = len(set(gone_speed) - still)
            s["objects_changed"] = s.get("objects_changed", 0) - n_obj_gone
            if "by_change" in s:
                s["by_change"]["modified"] = s["by_change"].get("modified", 0) - n_obj_gone
            rw = s.get("speed_rows_reviewed_with", {})
            rw.pop("street-view", None)
            s["speed_rows_reviewed_with"] = rw
            s["street_view_derived_rows"] = 0
            s["osm_import_never_rows"] = 0
            s["google_rows_removed"] = {"ways": gone_speed, "rule": "SlowGo rule 2026-10-20: no value whose only source is Google "
                                        "Maps or Street View in a build or the open-data repo",
                                        "removed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            writej(s, sj, indent=1)
        if gone_speed:
            removed[st] = {"speed_rows": len(gone_speed), "alteration_rows": gone_alt}
    left = google_rows_in(a.out, ids)
    print(json.dumps({"removed": removed, "google_rows_left": left}))
    if left:
        raise GoogleRefused(f"Google-only rows still in the package: {left}")
    return removed


def cmd_relabel(a):
    """Change one tag VALUE label in data/<state>/alterations.csv.gz (the after column of rows with that key), and
    record it in summary.json. For a label that was wrong in the extract the package describes (New York's 8,204
    slowgo:reviewed=street-view ways are NYSDOT values; BackRoad Apps LLC 2026-10-20, HUB ny-rows-nysdot): values are untouched.
    Idempotent."""
    d = os.path.join(a.out, "data", a.state)
    ap_, sj = os.path.join(d, "alterations.csv.gz"), os.path.join(d, "summary.json")
    n, tmp = 0, ap_ + ".tmp"
    with gzip.open(ap_, "rt", newline="") as fi, gzip.open(tmp, "wt", newline="") as fo:
        r = csv.reader(fi); w = csv.writer(fo); h = next(r); w.writerow(h)
        ki, ai = h.index("key"), h.index("after")
        for row in r:
            if row[ki] == a.key and row[ai] == a.frm:
                row[ai] = a.to; n += 1
            w.writerow(row)
    os.replace(tmp, ap_)
    s = readj(sj)
    rw = s.get("speed_rows_reviewed_with", {})
    if a.key == "slowgo:reviewed" and a.frm in rw:
        rw[a.to] = rw.get(a.to, 0) + rw.pop(a.frm)
    rel = s.setdefault("relabelled", [])
    prev = next((x for x in rel if (x["key"], x["from"], x["to"]) == (a.key, a.frm, a.to)), None)
    if prev is None:
        rel.append({"key": a.key, "from": a.frm, "to": a.to, "rows": n, "why": a.why,
                    "relabelled_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    elif n:
        prev["rows"] += n
    writej(s, sj, indent=1)
    print(json.dumps({"state": a.state, "key": a.key, "from": a.frm, "to": a.to, "rows": n}))


GOOGLE_TEXT = re.compile(r"google|street[ _-]?view", re.I)


def refuse_google_package(out):
    """No value or list line in the package may name Google or Street View (BackRoad Apps LLC 2026-10-21). Scans the data rows
    (not the CSV headers, whose empty street_view_derived column is kept for format stability) and every list."""
    hits = []
    for st in sorted(os.listdir(os.path.join(out, "data"))) if os.path.isdir(os.path.join(out, "data")) else []:
        for fn in ("alterations.csv.gz", "speed.csv.gz"):
            p = os.path.join(out, "data", st, fn)
            if os.path.exists(p):
                with gzip.open(p, "rt", newline="", errors="replace") as f:
                    next(f, None)
                    hits += [f"data/{st}/{fn} line {n + 2}" for n, line in enumerate(f) if GOOGLE_TEXT.search(line)]
    ld = os.path.join(out, "lists")
    for fn in sorted(os.listdir(ld)) if os.path.isdir(ld) else []:
        with open(os.path.join(ld, fn), errors="replace") as f:
            if GOOGLE_TEXT.search(f.read()):
                hits.append(f"lists/{fn}")
    if hits:
        raise GoogleRefused(f"Google / Street View named in the package ({len(hits)}): {hits[:5]}")


def cmd_manifest(a):
    refuse_scdot_package(a.out)                 # SCDOT hard gate: the last look before the package is sealed
    refuse_google_package(a.out)
    rows = []
    for root, _, files in os.walk(a.out):
        for fn in sorted(files):
            if fn == "MANIFEST.sha256":
                continue
            p = os.path.join(root, fn)
            rows.append((os.path.relpath(p, a.out), os.path.getsize(p), sha256(p)))
    rows.sort()
    with open(os.path.join(a.out, "MANIFEST.sha256"), "w") as f:
        for rel, size, h in rows:
            f.write(f"{h}  {rel}\n")
    total = sum(r[1] for r in rows)
    print(f"{len(rows)} files, {total / 1e6:.1f} MB")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("diff"); p.add_argument("--state", required=True); p.add_argument("--stock", required=True)
    p.add_argument("--final", required=True); p.add_argument("--out", required=True); p.add_argument("--tmp")
    p = sub.add_parser("stamps"); p.add_argument("--state", required=True); p.add_argument("--final", required=True)
    p.add_argument("--out", required=True); p.add_argument("--stock-name"); p.add_argument("--stock-sha")
    p = sub.add_parser("lists"); p.add_argument("--repo", required=True); p.add_argument("--out", required=True)
    p.add_argument("--cart-legal"); p.add_argument("--cart-lanes"); p.add_argument("--live-only", action="store_true")
    p = sub.add_parser("relabel"); p.add_argument("--out", required=True); p.add_argument("--state", required=True)
    p.add_argument("--key", required=True); p.add_argument("--from", dest="frm", required=True)
    p.add_argument("--to", required=True); p.add_argument("--why", default="")
    p = sub.add_parser("manifest"); p.add_argument("--out", required=True)
    p = sub.add_parser("mark"); p.add_argument("--out", required=True)
    p = sub.add_parser("drop-google"); p.add_argument("--out", required=True)
    p = sub.add_parser("apply"); p.add_argument("--stock", required=True); p.add_argument("--alterations", required=True)
    p.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rc = {"diff": cmd_diff, "stamps": cmd_stamps, "manifest": cmd_manifest, "mark": cmd_mark,
          "apply": cmd_apply, "relabel": cmd_relabel, "drop-google": lambda x: (cmd_drop_google(x), 0)[1],
          "lists": lambda x: (cmd_lists(x), 0)[1]}[a.cmd](a)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
