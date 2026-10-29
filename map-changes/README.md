# SlowGo map data changes (OpenStreetMap derivative)

SlowGo plans golf-cart and low-speed-vehicle routes on a routing map built from **OpenStreetMap** data,
© OpenStreetMap contributors, available under the **Open Database License (ODbL) 1.0**
(https://opendatacommons.org/licenses/odbl/1-0/, full text in `../LICENSE`).

We change that data before building our map: we add posted speed limits published by state transportation
departments, close bike and walking paths that aren't tagged for golf carts, and make a small number of hand-checked
corrections. This package contains **all of those changes**, so anyone can rebuild the same map data. Our changes are
made available under the **ODbL 1.0**, the same licence as OpenStreetMap.

Map build: **rebuild 4 (Florida 20ce4bc8…, Georgia 793c4eff…, New York a5177375…, Arizona aa9aed14…)**,
the routing map in use since 2026-10-29 (routing tiles 73e87631…), the map SlowGo 1.5 uses. This release describes
that map, minus the rows we don't offer (below, "Rows left out"). The release of 2026-10-21 described the map before it.

## What's in it

| Path | What it is |
|---|---|
| `data/<state>/alterations.csv.gz` | **Every change**, one row per changed tag: `osm_type` (n/w/r), `osm_id`, `change`, `key`, `before` (value in the stock OpenStreetMap extract, empty = absent), `after` (value in our map data, empty = removed). |
| `data/<state>/speed.csv.gz` | The speed-limit part of those changes, one row per OSM way: `osm_way_id`, `maxspeed`, `maxspeed_before`, `maxspeed_source`, `slowgo_action`, `class`, `station`, `dot_roadway`, `override_id`, `street_view_derived`, `osm_import`. |
| `data/<state>/summary.json` | The stock and final extracts (file name, size, SHA-256), counts, which keys changed, and what was relabelled or left out (`relabelled`, `google_rows_removed`). |
| `lists/*.json` | The hand-ruled rule files behind some changes, each row with its sources: `fl.speed-overrides.json` (5 speed limits: 4 in The Villages and the Brownwood roundabout), `fl.golfcart-overrides.json` (1 path kept open), `fl.crossings.json` (1 signalised crossing). Only rows in the live map are listed (`in_live_map`); rules not yet in it are published when they are. |
| `lists/cart-legal-ways.json` | The OSM way ids our app treats as tagged for golf carts (a copy ships inside the app). |
| `method/odbl_package.py` | The script that produced the alteration files and can apply them (`apply`). |
| `../LICENSE`, `NOTICE.md` | The licence and the attribution notice. |
| `MANIFEST.sha256` | SHA-256 of every file. |

States and counts:

| State | Stock extract | Final extract (SHA-256, first 12) | Objects changed | Speed rows | Paths closed | Faster roads closed | Method |
|---|---|---|---|---|---|---|---|
| Florida | florida-260831.osm.pbf | fl-S-nofast.osm.pbf (20ce4bc8cc1f) | 924,793 | 30,878 | 709,717 | 165,400 | diff |
| Georgia | georgia-260831.osm.pbf (Geofabrik 2026-08-31, stock) | ga-S-nofast.osm.pbf (793c4effce3c) | 332,653 | 0 | 200,533 | 106,316 | stamps |
| New York | new-york-latest.osm.pbf | ny-S-nofast.osm.pbf (a5177375c405) | 748,866 | 51,574 | 617,056 | 80,396 | diff |
| Arizona | arizona-261006.osm.pbf | az-S-nofast.osm.pbf (aa9aed14cda1) | 375,335 | 29,798 | 278,188 | 70,777 | diff |

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
   Valhalla routing tiles from the merge). The rebuilt files should match the SHA-256 of our final extracts.

Georgia note: its changes were rebuilt from the stamps our path-closing and faster-road steps leave on every way they
change (`slowgo:path_closed`, `slowgo:bicycle_orig`, `slowgo:nofast`, `slowgo:nofast_bicycle_orig`), because we no
longer hold the stock 2026-08-31 Georgia extract. All other states are a direct object-by-object comparison of the stock and
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
- **Faster roads closed** (`bicycle=no`, `slowgo:nofast=<reason>`, earlier value in `slowgo:nofast_bicycle_orig`):
  new in this map. Roads posted over 35 mph, and roads with no posted limit that our rules estimate are over 35
  (`slowgo:speed_estimate`, `_confidence`, `_basis`, `_verdict`; an estimate, never a posted limit), are closed to
  our cart router. A crossing of such a road stays possible. This changes only our routing.

None of these are edits to OpenStreetMap itself; they exist only in our copy. We never submit automated changes to
OpenStreetMap.

## Rows left out

**The 11 Florida speed values whose only source was Google Street View are gone from this map.** On 8 of those roads
the map now carries the Florida Department of Transportation's own value (55 mph); they are listed here as FDOT rows
(`maxspeed_source` FDOT, credited to FDOT), recorded 2026-10-29 (`data/fl/summary.json`, `fdot_replaced_rows`). The
other 3 roads carry no value from Street View and have no speed row here.

Also not here, by our rule that everything in this package must come from a source we may republish under the ODbL
("yes" or "yes with credit" in our source register), or from today's live map:
- **No Google content.** No value rests on any Google service. The crossing in `lists/fl.crossings.json`
  (FL-466A-PINELLAS) stands on Florida Statutes §316.2122 and our own field report; an imagery note that had been
  one of its sources is gone. New York's 8,204 reviewed rows are New York State DOT values (no imagery was used)
  and carry the label `nysdot`. The `street_view_derived` and `osm_import` columns of `speed.csv.gz` are kept for format stability
  and are empty on every row.
- **No value from South Carolina's state transportation department**, and no South Carolina rule at all: South Carolina is not in our live map.
- **No rule row from a source whose open-republishing terms are unclear** (for example private association rules or
  contributor street imagery). The two Arizona rule rows for North 91st Avenue in Sun City (posted 40) name such a
  source beside the Arizona DOT, so their rule rows are not in `lists/`; the values themselves, from the Arizona
  DOT's records, are in `data/az/speed.csv.gz` (override ids `AZ-SUNCITY-N91ST-*`).
- **Rules not yet in the live map** (South Carolina closures, the Villages golf-cart rule): published with the map
  that first uses them.

None of the values here should be imported into OpenStreetMap automatically; when editing OpenStreetMap, use the
department's own published data.

## What's not in it

Nothing about any rider, trip or business; no keys, server names or addresses. Free-text sources in `lists/` have
personal names replaced by "BackRoad Apps LLC" and a rider's report reduced to its date.

Published by BackRoad Apps LLC (SlowGo).

## Questions

Write to hello@slowgoapp.com.
