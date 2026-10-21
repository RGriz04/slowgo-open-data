# Notice

This package contains information from **OpenStreetMap** (https://www.openstreetmap.org), which is made available
here under the **Open Database License (ODbL) 1.0** (https://opendatacommons.org/licenses/odbl/1-0/).
© OpenStreetMap contributors. Copyright and licence details: https://www.openstreetmap.org/copyright

The changes BackRoad Apps LLC (SlowGo) made to that data (every file under `data/` and `lists/`) are a derivative database and are
made available under the same **Open Database License 1.0**. A copy of the licence is in `../LICENSE`.

Additional contents and their publishers (named as a courtesy; each provides its data "as is" and none endorses
SlowGo):
- Florida Department of Transportation, Transportation Data & Analytics Office — Maximum Speed Limit layer.
- Arizona Department of Transportation, Multimodal Planning Division Data Analytics — HPMS 2024 speed limits and
  All Roads Network.
- New York State Department of Transportation, Highway Data Services Bureau — Roadway Inventory.
- Sumter County, Florida (public records) — sign inventory and road centrelines (rule rows in
  `lists/fl.speed-overrides.json`; each row names its sources in `register_sources`). Florida county records are
  public records (Florida Constitution art. I §24; chapter 119 Florida Statutes; Microdecisions, Inc. v. Skinner,
  889 So. 2d 871 (Fla. 2d DCA 2004)).

Laws the lists cite (public law; named for reference): Florida Statutes §316.2122 (`lists/fl.crossings.json`).

Observations by BackRoad Apps LLC (SlowGo) (a field report on `lists/fl.crossings.json`, our golf-cart path override)
are released under the ODbL as part of this database.

Every source behind this package may be republished under the ODbL ("yes" or "yes with credit" in our source
register). Nothing here comes from Google, from South Carolina's state transportation department, or from a source whose terms for open
republishing are unclear; rows that rest on such a source are left out (`README.md`, "What's not in it").

`method/odbl_package.py` is a script by BackRoad Apps LLC (SlowGo), included so the alteration files can be checked and applied.
