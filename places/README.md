# Places (OpenStreetMap + Overture Maps)

`places.jsonl.gz`: 402,701 places, one JSON object per line, sorted by `pid`. Built 2026-10-15 from OpenStreetMap
(Geofabrik extracts for Florida, Georgia, New York and Arizona) and Overture Maps places release 2026-09-23.1
(places with Overture confidence 0.6 or higher, clipped to those states). Where an OpenStreetMap place and an
Overture place are the same place, they were merged into one record.

Fields: `pid` (our id: `osm:<n|w|r><id>` or `ov:<Overture id>`), `name`, `cat` / `cats` (our categories), `class`,
`subclass`, `lat`, `lng`, `address` (`street`, `city`, `state`, `postcode`), `phone`, `website`, `menu`, `hours`,
`cuisine`, `wheelchair`, `outdoor_seating`, `brand`, `chain`, `sources`, `updated`.

`sources` says where a record came from: `osm`, and `overture:<source>` for each Overture source (meta, microsoft,
foursquare, brightquery, alltheplaces, dac, renderseo, pinmeto). Counts by source and the file's SHA-256 are in
`manifest.json`. The `address.state` is the place's own address, so a handful of records name a neighbouring state.

Fixes: SlowGo keeps a small file of hand corrections to the places (a place both sources miss, a wrong field, a
closed shop both still list), checked by us before they apply. When a release includes any, `fixes.json` sits
beside `places.jsonl.gz`: every active and retired fix with what it changes, why, and where it came from (who, when,
the source, a reference and its licence), and a place a fix changed lists `fix:<id>` in its `sources`. Fixes taken
from OpenStreetMap stay share-alike under the ODbL; our own observations are licensed under the ODbL as part of
this database. Fixes waiting for our check are not applied and not published. None are submitted to
OpenStreetMap. This release (2026-09-23.1, build of 2026-10-15) has no fixes and no `fixes.json`.

Google links: a `website`, `menu` or `address` value that was a Google Maps or Google Search link (maps.app.goo.gl,
goo.gl, g.page, g.co, share.google, google.<tld>/maps|search|url, maps.google, local.google, business.google,
googlemaps.com, Google's cached copies, Google's food-ordering and Google+ pages, or anything else on google.<tld> or
www.google.<tld>, and gmail.com given as a website, which can carry a mailbox name) is set to null; the place
itself stays. In this release that is 315 websites and 6 street addresses (counted in
`manifest.json`, `google_links_dropped`). They came to us from Overture's sources, not from Google. A business's own
page hosted by Google (sites.google.com, a Google Drive or Docs menu, a Play Store page, business.site) is kept.
E-mail addresses: a name, website, menu or address value that held an e-mail address (8 in this release) is set to
null, because a mailbox can be a person's; the place stays.

Licence: Open Database License 1.0 (`../LICENSE`), © OpenStreetMap contributors and Overture Maps Foundation; the
Overture source licences and Foursquare's NOTICE are in `../licences/`. Made with `../tools/export_places.py`.
Published by BackRoad Apps LLC (SlowGo); a fix's `by` fields name BackRoad Apps LLC, never a person.
