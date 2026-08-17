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

## Why TomTom Flow Segment instead of Google Directions / Distance Matrix

| Criterion | Google Directions + Distance Matrix | TomTom Flow Segment |
|---|---|---|
| **Measurement** | Travel time between point pairs; congestion must be *inferred* from `duration_in_traffic / duration` | Returns `currentSpeed` and `freeFlowSpeed` for the road segment directly — a **direct measurement**, not an inference |
| **Request complexity** | 1 request per origin–destination pair → O(n²) to cover a network | 1 request per point → O(n). 32 points = 32 requests |
| **Cost** | Distance Matrix billed per element; expensive for continuous sampling | Free tier, 2,500 requests/day, no credit card required |
| **Reproducibility** | Manual | Every sampling round is a timestamped git commit; the full collection history is auditable and the pipeline can be re-run by anyone |

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

## Notes and limitations

1. **This measures speed, not vehicle volume.** `congestion_ratio` is a speed-
   based congestion index, not a vehicle count or density. Under traffic flow
   theory (`flow = density × speed`) volume cannot be derived from speed alone.
   For routing purposes speed is arguably the more directly useful quantity —
   it *is* the traversal cost of an edge — but any claim about vehicle counts
   would require a different source (TomTom Traffic Stats / Historical Traffic
   Volumes, or vehicle counting from public traffic cameras).

2. **No open government traffic data was available.** The Da Nang Open Data
   Portal (`congdulieu.vn`) was checked and contains no traffic volume
   datasets; most of its published data ends around 2023. This is why a
   commercial API was used.

3. **Some locations are slow even at night.** A handful of segments show
   `congestion_ratio < 0.8` at 2–4 AM. This most likely reflects a persistent
   property of the segment (narrow road, works, low speed limit) rather than
   demand-driven congestion, and should be treated as a baseline offset rather
   than as congestion.

4. **Coordinates are cluster centroids, not exact road geometry.** Flood
   reports within 120 m were merged into clusters upstream; the centroid is
   sent to the API, and TomTom snaps it to the nearest segment. For short
   `kiệt`/alley entries the snapped segment may be the adjoining main road.

5. **Sampling depends on GitHub's scheduler.** Scheduled workflows can be
   delayed by several minutes under load, so intervals are not exactly 30
   minutes. Every row records its own actual sampling timestamp, so analyses
   should group by `hour_vn` rather than assume a fixed cadence.

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
