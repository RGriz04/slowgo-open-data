# SlowGo map data changes (OpenStreetMap derivative)

SlowGo plans golf-cart and low-speed-vehicle routes on a routing map built from **OpenStreetMap** data,
© OpenStreetMap contributors, available under the **Open Database License (ODbL) 1.0**
(https://opendatacommons.org/licenses/odbl/1-0/, full text in `../LICENSE`).

We change that data before building our map: we add posted speed limits published by state transportation
departments, close bike and walking paths that aren't tagged for golf carts, and make a small number of hand-checked
corrections. This package contains **all of those changes**, so anyone can rebuild the same map data. Our changes are
made available under the **ODbL 1.0**, the same licence as OpenStreetMap.

Map build: **merged input 5dc02e86… (Florida c23ff167…, Georgia d3cb77d8…, New York 5a4c071e…, Arizona f86be527…)**,
the routing map in use since 2026-10-11 and still live on 2026-10-21 (routing tiles 9391baf8…). This release describes
that map, minus the rows we don't offer (below, "Rows left out").

## What's in it

| Path | What it is |
|---|---|
| `data/<state>/alterations.csv.gz` | **Every change**, one row per changed tag: `osm_type` (n/w/r), `osm_id`, `change`, `key`, `before` (value in the stock OpenStreetMap extract, empty = absent), `after` (value in our map data, empty = removed). |
| `data/<state>/speed.csv.gz` | The speed-limit part of those changes, one row per OSM way: `osm_way_id`, `maxspeed`, `maxspeed_before`, `maxspeed_source`, `slowgo_action`, `class`, `station`, `dot_roadway`, `override_id`, `street_view_derived`, `osm_import`. |
| `data/<state>/summary.json` | The stock and final extracts (file name, size, SHA-256), counts, which keys changed, and what was relabelled or left out (`relabelled`, `google_rows_removed`). |
| `lists/*.json` | The hand-ruled rule files behind some changes, each row with its sources: `fl.speed-overrides.json` (4 Villages speed limits), `fl.golfcart-overrides.json` (1 path kept open), `fl.crossings.json` (1 signalised crossing). Only rows in the live map are listed (`in_live_map`); rules not yet in it are published when they are. |
| `lists/cart-legal-ways.json` | The OSM way ids our app treats as tagged for golf carts (a copy ships inside the app). |
| `method/odbl_package.py` | The script that produced the alteration files and can apply them (`apply`). |
| `../LICENSE`, `NOTICE.md` | The licence and the attribution notice. |
| `MANIFEST.sha256` | SHA-256 of every file. |

States and counts:

| State | Stock extract | Final extract (SHA-256, first 12) | Objects changed | Speed rows | Paths closed | Method |
|---|---|---|---|---|---|---|
| Florida | florida-260831.osm.pbf | fl-B-closed.osm.pbf (c23ff1673767) | 740,613 | 30,869 | 709,717 | diff |
| Georgia | georgia-260831.osm.pbf (Geofabrik 2026-08-31, stock) | georgia-260831.osm.pbf (d3cb77d8b94d) | 200,547 | 0 | 200,533 | stamps |
| New York | new-york-latest.osm.pbf | new-york-enriched-v3.osm.pbf (5a4c071eb14d) | 668,636 | 51,574 | 617,056 | diff |
| Arizona | arizona-261006.osm.pbf | az-B-closed.osm.pbf (f86be5274dd5) | 307,987 | 29,790 | 278,188 | diff |

No node moved and no object was added or deleted in any state (geometry changes: 0).

## How to rebuild our map data

1. Get the stock OpenStreetMap extract named in `data/<state>/summary.json` (Geofabrik's dated extracts:
   `florida-260831`, `arizona-261006`, `georgia-260831`; New York is the Geofabrik extract pulled 2026-08-24). Geofabrik
   doesn't keep old dated files, so the same data can be cut from an OpenStreetMap full-history planet at that date;
   check the SHA-256 in `summary.json`.
2. Apply the changes (Python 3 with `osmium` installed):
   `python3 method/odbl_package.py apply --stock florida-260831.osm.pbf --alterations data/fl/alterations.csv.gz --out florida-slowgo.osm.pbf`
   The script refuses any object whose stock tags aren't what the file expects, so a wrong base extract is caught.
3. The result is tag-for-tag our map input for that state (we merge the four states with `osmium merge` and build
   Valhalla routing tiles from the merge), with two known differences: Florida lacks the 11 rows we don't offer
   ("Rows left out"), and New York's 8,204 `slowgo:reviewed` labels read `nysdot` (the live file says
   `street-view`, a wrong label; the values are identical). So the rebuilt Florida and New York files won't match the
   SHA-256 of our final extracts; Arizona and Georgia should.

Georgia note: its changes were rebuilt from the stamps our path-closing step leaves on every way it changes
(`slowgo:path_closed`, `slowgo:bicycle_orig`), because we no longer hold the stock 2026-08-31 Georgia extract. The
counts match that step's own log exactly. All other states are a direct object-by-object comparison of the stock and
final extracts.

## What the changes are

- **Speed limits from transportation departments** (`maxspeed`, `maxspeed:source`, `slowgo:maxspeed_action=fill`):
  a published posted limit written onto an OSM road that had none (never above 45 mph by this step).
  Sources: Florida Department of Transportation (Maximum Speed Limit, TDA), Arizona Department of Transportation
  (HPMS 2024, All Roads Network), New York State Department of Transportation (Roadway Inventory). We name them as a
  courtesy; their data is provided "as is" by them, and they don't endorse SlowGo.
- **Corroborated limits** (`slowgo:maxspeed_action=corroborated_fill|corroborated`, `slowgo:maxspeed_station`):
  a published value confirmed by the posted limits on the same road on both sides.
- **Corridor floor** (`slowgo:maxspeed_action=corridor_floor`, `maxspeed=56 mph`, `slowgo:maxspeed_sentinel=yes`):
  not a posted limit. A marker meaning "treat as over 55 mph" on a major road whose neighbours are all posted above
  45; `slowgo:maxspeed_true` holds the neighbours' value.
- **Held over-45 values** (`slowgo:maxspeed_action=held_over45_written`) and **reviewed values**
  (`reviewed_confirm`): a published value above 45 mph written after review.
- **Overrides** (`slowgo:maxspeed_override=<id>`, `slowgo:maxspeed_source`): a posted limit from an official record
  (Sumter County's sign inventory, FDOT); the row and its sources are in `lists/`.
- **Path closures** (`bicycle=no`, `slowgo:path_closed=1`, earlier value in `slowgo:bicycle_orig`): bike and walking
  paths not tagged for golf carts are closed to our cart router. `slowgo:short_link_open=1` marks a short connector
  left open. This changes only our routing; it says nothing about bicycles.
- **Crossing carve-out** (`slowgo:crossing_carveout`, earlier value in `slowgo:bicycle_was`): short approach streets at
  one signalised crossing kept usable.
- **Golf-cart path override** (`slowgo:golf_cart_override`): one untagged path kept open.

None of these are edits to OpenStreetMap itself; they exist only in our copy. We never submit automated changes to
OpenStreetMap.

## Rows left out

**11 Florida speed rows are still in our live map until our next routing-map rebuild (planned with SlowGo 1.5); they
are not offered here because their only source was Google Street View.** We took them out of our next map and out of
this package on 2026-10-20; their way ids are in `data/fl/summary.json` (`google_rows_removed`). For every other
change of those ways (a path closure, say) the row is here.

Also not here, by our rule that everything in this package must come from a source we may republish under the ODbL
("yes" or "yes with credit" in our source register), or from today's live map:
- **No Google content.** No value rests on any Google service. The crossing in `lists/fl.crossings.json`
  (FL-466A-PINELLAS) stands on Florida Statutes §316.2122 and our own field report; an imagery note that had been
  one of its sources is gone. New York's 8,204 rows that the live file labels `slowgo:reviewed=street-view` are
  New York State DOT values (no imagery was used) and carry the label `nysdot` here (`data/ny/summary.json`,
  `relabelled`). The `street_view_derived` and `osm_import` columns of `speed.csv.gz` are kept for format stability
  and are empty on every row.
- **No value from South Carolina's state transportation department**, and no South Carolina rule at all: South Carolina is not in our live map.
- **No row from a source whose open-republishing terms are unclear** (for example private association rules or
  contributor street imagery). None is in the live map.
- **Rules not yet in the live map** (a Brownwood roundabout speed limit, Villages cart-lane rules, Arizona speed
  overrides, South Carolina closures): published with the map that first uses them.

None of the values here should be imported into OpenStreetMap automatically; when editing OpenStreetMap, use the
department's own published data.

## What's not in it

Nothing about any rider, trip or business; no keys, server names or addresses. Free-text sources in `lists/` have
personal names replaced by "BackRoad Apps LLC" and a rider's report reduced to its date.

Published by BackRoad Apps LLC (SlowGo).

## Questions

Write to hello@slowgoapp.com.
