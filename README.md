# SlowGo open data

SlowGo is an app that plans golf-cart and low-speed-vehicle routes. It is built on **OpenStreetMap** data, and our
places search also uses **Overture Maps** places. This repository publishes, free of charge, the databases we derived
from OpenStreetMap, as the **Open Database License (ODbL) 1.0** asks of anyone who uses a derivative database
publicly.

Published by BackRoad Apps LLC (SlowGo).

Planned home: https://github.com/RGriz04/slowgo-open-data

## What's here

| Folder | What it is | Size |
|---|---|---|
| `map-changes/` | Every change we made to OpenStreetMap data before building the routing map that is live today (Florida, Georgia, New York, Arizona; in use since 2026-10-11): speed limits from state transportation departments, path closures for our cart router, a few hand-checked corrections. One row per changed tag, with the value before and after, plus the rule files behind them and the script that applies them to a stock OpenStreetMap extract. Start with `map-changes/README.md`. | about 13 MB |
| `places/` | The places database behind SlowGo's place search and place cards: OpenStreetMap places merged with Overture Maps places (402,701 places in Florida, Georgia, New York and Arizona, Overture release 2026-09-23.1, our build of 2026-10-15, the one our places server uses). One JSON object per line. See `places/README.md`. | about 34 MB |
| `tools/` | `export_places.py`, the script that wrote `places/` from our places build. | small |
| `licences/` | The licences of the Overture sources merged into `places/` (CDLA Permissive 2.0, Apache 2.0 and Foursquare's NOTICE, CC0 1.0) and Overture's attribution page for this release. | small |
| `LICENSE` | The Open Database License 1.0. | |

## Licence

Both databases are made available under the **Open Database License 1.0** (`LICENSE`).

- **OpenStreetMap:** © OpenStreetMap contributors, https://www.openstreetmap.org/copyright.
- **Overture Maps Foundation** places (`places/`), release 2026-09-23.1. Each place lists its sources in `sources`
  (`osm`, `overture:meta`, `overture:microsoft`, `overture:foursquare`, …). Overture publishes those sources under
  CDLA Permissive 2.0 (Meta, Microsoft, BrightQuery, DAC, PinMeTo, RenderSEO, Krick), Apache 2.0 (Foursquare;
  its NOTICE is in `licences/foursquare-NOTICE.txt`) and CC0 1.0 (AllThePlaces). Because our places database merges
  them with OpenStreetMap places, we treat the whole of it as a derivative of OpenStreetMap and publish it under the
  ODbL, keeping the source licences and notices with it (Overture's own guidance for joining its places with
  OpenStreetMap: `licences/overture-attribution-2026-09-23.1.txt` and its places guide).
- **State transportation departments** (Florida, Arizona, New York) publish the speed limits in `map-changes/`.
  We name them as a courtesy; they provide their data "as is" and don't endorse SlowGo. **Sumter County, Florida**
  public records are the source of a few Villages speed limits. Details in `map-changes/NOTICE.md`.

If you use this data, credit "© OpenStreetMap contributors" and "Overture Maps Foundation", keep Foursquare's
NOTICE (`licences/foursquare-NOTICE.txt`) with any Foursquare places, and keep the notices above. Our own changes and
observations are credited to BackRoad Apps LLC (SlowGo).

## What's not here, and why

- **Nothing about riders or businesses we work with:** no trips, reports, accounts, names, keys or server details.
- **Source layers themselves.** Some speed rules in `map-changes/lists/` come from Sumter County,
  Florida records (each row names its sources). Florida county records are public records (Florida Constitution
  art. I §24, chapter 119 Florida Statutes), so we use them with credit; the county layers themselves are not here,
  only the rule (the way and the value) that our map uses.
- **Nothing from Google, from South Carolina's state transportation department, or from a source we can't clearly republish.** Every source
  here is one whose terms let us republish it under the ODbL. Eleven Florida speed rows that rested only on Google
  Street View are still in our live map until our next map rebuild (planned with SlowGo 1.5) and are not offered
  here (`map-changes/README.md`, "Rows left out"). In `places/`, website and address values that were Google Maps or
  Google Search links are removed (the places stay; `places/README.md`).
- **No edits to OpenStreetMap itself.** Everything here lives only in our copy. We don't submit automated changes to
  OpenStreetMap.
- **Map tiles and the routing graph** are built from these databases and aren't included; they can be rebuilt from
  them with standard tools.

## Updates

We add a dated release here whenever we rebuild the routing map or the places database. Each `summary.json` and
`places/manifest.json` names the exact build and its SHA-256 hashes.

## Contact

hello@slowgoapp.com
