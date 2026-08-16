"""Thu thap chi so tac duong (traffic congestion) tai cac diem ngap cua Da Nang
bang TomTom Traffic Flow Segment Data API (free tier: 2.500 request/ngay).

Vi sao lay mau tai CHINH cac diem ngap: de du lieu giao thong va du lieu ngap
khop nhau ve vi tri -> dung truc tiep cho Routing Engine sau nay (biet doan
duong nao vua hay ngap vua hay tac).

Vi sao TomTom thay vi Google Directions/Distance Matrix:
  - tra thang currentSpeed vs freeFlowSpeed (do truc tiep) thay vi phai suy ra
    do tac tu ti le thoi gian di chuyen
  - 1 request/diem thay vi 1 request/cap diem
  - free tier khong can the tin dung

Cach dung:
    set TOMTOM_API_KEY=<key cua ban>        (Windows CMD)
    $env:TOMTOM_API_KEY="<key>"             (PowerShell)
    export TOMTOM_API_KEY=<key>             (Git Bash)
    python collect_traffic.py

Moi lan chay se APPEND vao traffic_samples.csv kem timestamp -> chay o nhieu
khung gio khac nhau (cao diem sang/chieu, thap diem, cuoi tuan) de co du mau
hieu chinh mo phong giao thong.
"""

import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent

# Uu tien ban copy nam canh script (de chay duoc tren GitHub Actions - may chu
# CI khong co duong dan Windows cuc bo); fallback ve dataset goc tren may ca nhan.
_LOCAL_HOTSPOTS = SCRIPT_DIR / "flood_hotspots.csv"
_DATASET_HOTSPOTS = Path(r"C:\Users\My Computer\Desktop\mua_ngap_dataset\flood_reports\flood_hotspots.csv")
HOTSPOTS_CSV = _LOCAL_HOTSPOTS if _LOCAL_HOTSPOTS.exists() else _DATASET_HOTSPOTS

OUT_CSV = SCRIPT_DIR / "traffic_samples.csv"

API_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
MIN_EVENT_DAYS = 2      # chi lay diem ngap lap lai >=2 dot (32 diem)
REQUEST_DELAY = 0.3     # giay, tranh goi qua nhanh
VN_TZ = timezone(timedelta(hours=7))

CSV_COLUMNS = [
    "sampled_at_vn", "sampled_at_utc", "weekday", "hour_vn",
    "hotspot_label", "ward", "lat", "lng",
    "distinct_event_days", "flood_water_level_avg",
    "current_speed_kmh", "free_flow_speed_kmh", "congestion_ratio",
    "current_travel_time_s", "free_flow_travel_time_s",
    "road_class", "confidence", "road_closure",
]


def get_api_key() -> str:
    """Uu tien bien moi truong; fallback ve file .env canh script (can thiet khi
    chay qua Task Scheduler - no khong thay bien moi truong tam cua terminal)."""
    key = os.environ.get("TOMTOM_API_KEY", "").strip()
    if key:
        return key

    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TOMTOM_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    sys.exit(
        "Chua co API key.\n"
        "  Cach 1: tao file .env canh script voi noi dung TOMTOM_API_KEY=<key>\n"
        "  Cach 2: export TOMTOM_API_KEY=<key> (Git Bash)\n"
        "Lay key tai: https://developer.tomtom.com/user/me/apps"
    )


def load_sampling_points() -> list[dict]:
    with HOTSPOTS_CSV.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    points = [r for r in rows if int(r["distinct_event_days"]) >= MIN_EVENT_DAYS]
    points.sort(key=lambda r: (-int(r["distinct_event_days"]), -int(r["total_reports"])))
    return points


def fetch_flow(lat: float, lng: float, api_key: str, timeout: int = 15) -> dict | None:
    resp = requests.get(
        API_URL,
        params={"key": api_key, "point": f"{lat},{lng}", "unit": "KMPH"},
        timeout=timeout,
    )
    if resp.status_code != 200:
        print(f"      !! HTTP {resp.status_code}: {resp.text[:120]}")
        return None
    return resp.json().get("flowSegmentData")


def main():
    api_key = get_api_key()
    points = load_sampling_points()
    now_vn = datetime.now(VN_TZ)
    now_utc = datetime.now(timezone.utc)

    print(f"Lay mau luc {now_vn:%Y-%m-%d %H:%M} (gio VN) tai {len(points)} diem ngap lap lai\n")

    rows = []
    for i, p in enumerate(points, 1):
        lat, lng = float(p["centroid_lat"]), float(p["centroid_lng"])
        label = (p["street_names"] or p["sample_address"] or "(khong ro)").split("|")[0].strip()[:40]

        flow = fetch_flow(lat, lng, api_key)
        if not flow:
            print(f"  ({i}/{len(points)}) {label[:35]:35} -> khong co du lieu")
            time.sleep(REQUEST_DELAY)
            continue

        current = flow.get("currentSpeed")
        free_flow = flow.get("freeFlowSpeed")
        # congestion_ratio: 1.0 = thong thoang, cang nho cang tac
        ratio = round(current / free_flow, 3) if current and free_flow else None

        rows.append({
            "sampled_at_vn": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
            "sampled_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "weekday": now_vn.strftime("%a"),
            "hour_vn": now_vn.hour,
            "hotspot_label": label,
            "ward": (p["ward_names"] or "").split("|")[0].strip(),
            "lat": lat,
            "lng": lng,
            "distinct_event_days": p["distinct_event_days"],
            "flood_water_level_avg": p["water_level_avg"],
            "current_speed_kmh": current,
            "free_flow_speed_kmh": free_flow,
            "congestion_ratio": ratio,
            "current_travel_time_s": flow.get("currentTravelTime"),
            "free_flow_travel_time_s": flow.get("freeFlowTravelTime"),
            "road_class": flow.get("frc"),
            "confidence": flow.get("confidence"),
            "road_closure": flow.get("roadClosure"),
        })

        status = f"{current}/{free_flow} km/h (ratio {ratio})" if ratio else "?"
        print(f"  ({i}/{len(points)}) {label[:35]:35} -> {status}")
        time.sleep(REQUEST_DELAY)

    if not rows:
        sys.exit("\nKhong thu duoc dong nao. Kiem tra lai API key.")

    is_new = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)

    ratios = [r["congestion_ratio"] for r in rows if r["congestion_ratio"]]
    print(f"\nDa ghi {len(rows)} dong vao {OUT_CSV.name}")
    if ratios:
        print(f"Congestion ratio: TB {sum(ratios)/len(ratios):.2f} | thap nhat {min(ratios):.2f} (tac nhat)")
        worst = min(rows, key=lambda r: r["congestion_ratio"] or 9)
        print(f"Diem tac nhat: {worst['hotspot_label']} ({worst['congestion_ratio']})")


if __name__ == "__main__":
    main()
