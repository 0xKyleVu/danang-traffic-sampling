# Da Nang Traffic Congestion Sampling at Flood-Prone Locations

Automated collection of road-level traffic congestion data at recurring
flood-prone locations in urban Da Nang, Vietnam. Collected as input for a
flood-aware vehicle routing system (predictive engine + routing engine).

**Data source:** [TomTom Traffic Flow Segment Data API](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/traffic-flow/flow-segment-data)
**Collection:** GitHub Actions, every 30 minutes, results committed back to this repo
**Cost:** free (TomTom free tier, 2,500 requests/day; ~1,536 used/day)

---

## Why sample at flood-prone locations

The 32 sampling points are **not arbitrary**. They are the flood locations that
recurred across **two or more independent rainfall events** between 2022 and
2026, derived from 512 cleaned flood reports published by the Da Nang city
flood portal (`muangap.danang.gov.vn`).

Sampling traffic at exactly these coordinates means the traffic data and the
flood data share the same spatial index — so a routing model can reason about
road segments that are *both* flood-prone *and* congested, which is where
proactive rerouting has the most value.

## Method

1. Read the 32 recurring flood locations from `flood_hotspots.csv`
   (filter: `distinct_event_days >= 2`).
2. For each location, query the TomTom Flow Segment endpoint with its
   coordinates. TomTom snaps the coordinate to the nearest road segment and
   returns current vs. free-flow speed.
3. Compute `congestion_ratio = current_speed / free_flow_speed`.
4. Append one row per location per round to `traffic_samples.csv`, tagged with
   the sampling timestamp.

A GitHub Actions workflow (`.github/workflows/collect_traffic.yml`) runs steps
1–4 every 30 minutes at minutes :07 and :37 (offset from the top of the hour,
where GitHub's scheduler is most congested) and commits the updated CSV.

---

## `traffic_samples.csv` — column reference

One row = one location, sampled at one point in time.

### Sampling metadata

| Column | Type | Description |
|---|---|---|
| `sampled_at_vn` | datetime | Sampling time in Vietnam local time (UTC+7), `YYYY-MM-DD HH:MM:SS` |
| `sampled_at_utc` | datetime | Same instant in UTC, ISO 8601 |
| `weekday` | string | `Mon`–`Sun`, derived from Vietnam local time |
| `hour_vn` | int (0–23) | Hour of day in Vietnam local time — the primary grouping key for time-of-day profiles |

### Location identity (joins to the flood dataset)

| Column | Type | Description |
|---|---|---|
| `hotspot_label` | string | Human-readable street/address label for the flood cluster |
| `ward` | string | Administrative ward (`phường`) |
| `lat`, `lng` | float | Cluster centroid coordinates (WGS 84). These are the coordinates sent to the API |
| `distinct_event_days` | int | **Number of separate rainfall events at which this location flooded** (≥2 by construction). Higher = more chronically flood-prone |
| `flood_water_level_avg` | float | Mean reported flood depth at this location across those events, in cm |

### Traffic measurement (from TomTom)

| Column | Type | Description |
|---|---|---|
| `current_speed_kmh` | int | Current average speed on the segment, km/h |
| `free_flow_speed_kmh` | int | Expected speed under uncongested conditions, km/h |
| `congestion_ratio` | float | `current_speed / free_flow_speed`. **1.0 = free-flowing; lower = more congested.** Primary metric |
| `current_travel_time_s` | int | Current travel time across the segment, seconds |
| `free_flow_travel_time_s` | int | Free-flow travel time across the segment, seconds |
| `road_class` | string | TomTom Functional Road Class, `FRC0` (motorway) to `FRC6` (local road). Most points here are `FRC4` (local) and `FRC1` (major arterial) |
| `confidence` | float (0–1) | TomTom's quality estimate for the speed/travel-time values. 1.0 = highest. Observed mean in this dataset: **0.99** |
| `road_closure` | bool | Whether the segment is reported closed |

---

## Repository contents

| Path | Description |
|---|---|
| `collect_traffic.py` | Collection script |
| `traffic_samples.csv` | Accumulated samples (append-only) |
| `flood_hotspots.csv` | The 299 flood clusters; the 32 with `distinct_event_days >= 2` are used as sampling points |
| `.github/workflows/collect_traffic.yml` | Scheduled collection workflow |
| `run_sample.bat`, `run_hidden.vbs` | Optional local Windows Task Scheduler runners (not needed when using GitHub Actions) |

## Running it yourself

```bash
pip install requests
export TOMTOM_API_KEY=<your key>    # or put it in a .env file next to the script
python collect_traffic.py
```

Get a free API key at [developer.tomtom.com](https://developer.tomtom.com/user/me/apps)
(enable the Traffic API product). The script never prints or logs the key; `.env`
is gitignored.
