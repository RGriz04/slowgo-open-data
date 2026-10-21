#!/usr/bin/env python3
"""export_places.py on a three-place fixture: the places file, and fixes.json (active + retired fixes with their
provenance; proposed ones left out). Run: python3 -I tools/test_export_places.py. Standard library only."""
import contextlib, gzip, importlib.util, io, json, os, sqlite3, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("export_places", os.path.join(HERE, "export_places.py"))
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

PROV = {"by": "Pat Example", "date": "2026-10-18", "source": "osm", "source_ref": "https://www.openstreetmap.org/way/569669947",
        "licence": "odbl-from-osm"}


def fix(fid, status, **kw):
    f = {"id": fid, "op": "add", "status": status,
         "target": {"pid": "osm:w569669947", "name": "Market Square", "lat": 28.9088, "lng": -81.9745},
         "set": {"name": "Market Square", "cats": ["square"], "lat": 28.9088, "lng": -81.9745}, "why": "test",
         "provenance": PROV, "checked": {"by": "Pat Example", "date": "2026-10-18"} if status != "proposed" else None,
         "note": "internal working note"}
    f.update(kw)
    return f


def make_build(d, sources_of_market_square, fixes=None):
    db = sqlite3.connect(os.path.join(d, "places.sqlite"))
    db.executescript("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);"
                     "CREATE TABLE places (rid INTEGER PRIMARY KEY, pid TEXT NOT NULL UNIQUE, near TEXT, detail TEXT);")
    rows = [("osm:n1", ["osm"]), ("ov:abc", ["overture:meta"])]
    if sources_of_market_square:
        rows.append(("osm:w569669947", sources_of_market_square))
    for i, (pid, src) in enumerate(rows, 1):
        db.execute("INSERT INTO places VALUES (?,?,?,?)", (i, pid, "{}", json.dumps(
            {"pid": pid, "name": pid, "address": {"state": "FL"}, "sources": src})))
    db.execute("INSERT INTO meta VALUES ('release', '2026-10-21.0')")
    db.commit(); db.close()
    if fixes is not None:
        json.dump({"format": "slowgo-place-fixes/1", "fixes": fixes}, open(os.path.join(d, "place-fixes.json"), "w"))
    return os.path.join(d, "places.sqlite")


def run(db, out):
    with contextlib.redirect_stdout(io.StringIO()):
        ex.main(db, out)
    with open(os.path.join(out, "manifest.json")) as f:
        return json.load(f)


class Export(unittest.TestCase):
    def test_fixes_published_with_provenance_proposed_left_out(self):
        with tempfile.TemporaryDirectory() as t:
            db = make_build(t, ["fix:FIX-FL-A"], [fix("FIX-FL-A", "active"), fix("FIX-FL-B", "proposed"),
                                                  fix("FIX-FL-C", "retired")])
            out = os.path.join(t, "places")
            man = run(db, out)
            with open(os.path.join(out, "fixes.json")) as f:
                doc = json.load(f)
            self.assertEqual([f["id"] for f in doc["fixes"]], ["FIX-FL-A", "FIX-FL-C"])
            # who-fields publish the publisher, never a person (BackRoad Apps LLC, 2026-10-21)
            self.assertEqual(doc["fixes"][0]["provenance"], dict(PROV, by="BackRoad Apps LLC"))
            self.assertEqual(doc["fixes"][0]["checked"], {"by": "BackRoad Apps LLC", "date": "2026-10-18"})
            self.assertNotIn("Pat Example", json.dumps(doc))
            self.assertNotIn("note", doc["fixes"][0], "working notes are not published")
            self.assertEqual(doc["build"], "2026-10-21.0")
            self.assertIn("ODbL", doc["about"])
            self.assertEqual((man["fixes"]["active"], man["fixes"]["retired"]), (1, 1))
            self.assertEqual(man["rows_by_source"]["fix:FIX-FL-A"], 1)
            with gzip.open(os.path.join(out, "places.jsonl.gz"), "rt") as g:
                self.assertEqual(len(g.read().splitlines()), 3)

    def test_today_only_a_proposed_fix_publishes_an_empty_list(self):
        with tempfile.TemporaryDirectory() as t:
            db = make_build(t, None, [fix("FIX-FL-VILLAGES-MARKET-SQUARE", "proposed")])
            man = run(db, os.path.join(t, "places"))
            with open(os.path.join(t, "places", "fixes.json")) as f:
                self.assertEqual(json.load(f)["fixes"], [])
            self.assertEqual((man["fixes"]["active"], man["fixes"]["retired"]), (0, 0))

    def test_a_place_naming_a_fix_that_is_not_active_stops_the_export(self):
        with tempfile.TemporaryDirectory() as t:
            db = make_build(t, ["fix:FIX-FL-A"], [fix("FIX-FL-A", "proposed")])
            with self.assertRaises(SystemExit):
                run(db, os.path.join(t, "places"))
        with tempfile.TemporaryDirectory() as t:
            db = make_build(t, ["fix:FIX-FL-A"], None)
            with self.assertRaises(SystemExit):
                run(db, os.path.join(t, "places"))

    def test_build_without_fixes_file_writes_none_and_clears_an_old_one(self):
        with tempfile.TemporaryDirectory() as t:
            db = make_build(t, None, None)
            out = os.path.join(t, "places")
            os.makedirs(out)
            open(os.path.join(out, "fixes.json"), "w").write("{}")
            man = run(db, out)
            self.assertIsNone(man["fixes"])
            self.assertFalse(os.path.exists(os.path.join(out, "fixes.json")))


class GoogleLinks(unittest.TestCase):
    def test_maps_and_search_links_go_business_pages_stay(self):
        c = __import__("collections").Counter()
        j = ex.drop_google_links({"pid": "ov:1", "website": "https://maps.app.goo.gl/AbC?g_st=ic",
                                  "menu": "https://drive.google.com/file/d/x/view",
                                  "address": {"street": "Moon House https://goo.gl/maps/xyz", "city": "Ocala"}}, c)
        self.assertIsNone(j["website"])
        self.assertEqual(j["menu"], "https://drive.google.com/file/d/x/view")
        self.assertEqual(j["address"], {"street": None, "city": "Ocala"})
        self.assertEqual(dict(c), {"website": 1, "address.street": 1})
        for url in ("https://www.google.com/maps/place/x", "https://g.page/r/abc", "https://g.co/kgs/abc",
                    "https://share.google/abc", "http://maps.google.com/?cid=1", "https://goo.gl/abc",
                    "https://food.google.com/chooseprovider?q=x", "https://plus.google.com/u/0/123",
                    "https://local.google.com/place?id=1&use=srp", "https://business.google.com/dashboard/l/1",
                    "http://googlemaps.com", "https://www.google.com/viewer/chooseprovider", "http://Google.com/",
                    "http://www.google.gr/", "http://webcache.googleusercontent.com/",
                    "http://google.com/+TonysPizza", "https://www.google.com/gasearch?q=x", "http://Google.com/Purvis",
                    "https://www.google.com/local/place/fid/0x1:0x2/photosphere", "http://www.google.co.uk/#q=x", "http://gmail.com/", "http://joe.smith.gmail.com/"):
            self.assertIsNone(ex.drop_google_links({"website": url}, c)["website"], url)
        for url in ("https://sites.google.com/view/pharmacy", "https://joes.business.site/", "https://gpage.com",
                    "https://www.googleplex-cafe.com/", "https://news.google.com/newspapers?nid=1",
                    "https://notgooglemaps.com/", "https://www.google.com.example.org/menu",
                    "https://www.dominos.com/en/?utm_source=google&utm_medium=loc"):
            self.assertEqual(ex.drop_google_links({"website": url}, c)["website"], url)

    def test_email_values_go(self):
        c = __import__("collections").Counter()
        j = ex.drop_google_links({"name": "joe@example.com", "website": "http://shop@example.org",
                                  "address": {"street": "1 Main St. Contact x.y@example.net", "city": "Ocala"}}, c)
        self.assertEqual((j["name"], j["website"], j["address"]["street"], j["address"]["city"]),
                         (None, None, None, "Ocala"))
        self.assertEqual(dict(c), {"email:name": 1, "email:website": 1, "email:address.street": 1})
        self.assertEqual(ex.drop_google_links({"website": "https://example.com/@user"}, c)["website"],
                         "https://example.com/@user")


if __name__ == "__main__":
    unittest.main(verbosity=1)
