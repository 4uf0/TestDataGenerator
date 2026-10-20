#!/usr/bin/env python3
"""Erzeugt realistische FIT-Aktivitätsdateien zum Testen von Garmin-Downloads.

Beispiele:
    python generate_fit.py
    python generate_fit.py --duration 40 --sport running --hr-min 110 --hr-max 165 --hr-jitter 4
    python generate_fit.py --count 3 --start "2025-01-15T18:30:00"
"""

import argparse
import math
import random
import sys
from datetime import datetime, timedelta, timezone

from fit_tool.fit_file import FitFile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import Event, EventType, FileType, Sport
from fit_tool.utils.conversions import (
    MILLISECONDS_EPOCH_1989_DELTA,
    to_seconds_since_1989_epoch,
)

FIT_EPOCH = datetime(1989, 12, 31, 0, 0, 0, tzinfo=timezone.utc)

SPORT_PRESETS = {
    "running": {
        "sport": Sport.RUNNING,
        "speed_kmh": (9.5, 12.5),
        "cadence": (150, 182),
        "hr": (115, 165),
        "position": (48.531839, 11.527053),  # Landshut
    },
    "cycling": {
        "sport": Sport.CYCLING,
        "speed_kmh": (22.0, 30.0),
        "cadence": (70, 95),
        "hr": (110, 158),
        "position": (48.531839, 11.527053),  # Landshut
    },
    "hiking": {
        "sport": Sport.HIKING,
        "speed_kmh": (3.8, 5.2),
        "cadence": (55, 75),
        "hr": (95, 135),
        "position": (48.531839, 11.527053),  # Landshut
    },
}


def fit_epoch_seconds(dt: datetime) -> int:
    """Timestamp im Format von fit-tool: Millisekunden seit Unix-Epoche."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return int(dt.timestamp() * 1000)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def generate_track(
    lat0: float, lon0: float, distance_km: float, num_points: int, seed: int
):
    """Erzeugt eine geschlossene, gps-ähnliche Schleife um den Startpunkt."""
    rng = random.Random(seed)
    radius_km = max(0.3, distance_km / (2 * math.pi))
    lat_k = 1.0 / 111.32
    lon_k = 1.0 / (111.32 * math.cos(math.radians(lat0)))
    points = []
    for i in range(num_points):
        frac = i / num_points
        angle = 2 * math.pi * frac
        r_km = radius_km * (1.0 + 0.12 * math.sin(3 * angle + seed))
        lat = lat0 + r_km * lat_k * math.sin(angle) + rng.uniform(-0.00004, 0.00004)
        lon = lon0 + r_km * lon_k * math.cos(angle) + rng.uniform(-0.00004, 0.00004)
        points.append((lat, lon))
    return points


def build_activity(
    duration_min: float,
    sport_name: str,
    hr_range: tuple[int, int],
    hr_jitter: float,
    cad_range: tuple[int, int],
    cad_jitter: float,
    start_dt: datetime,
    record_interval_s: int,
    seed: int,
) -> FitFile:
    preset = SPORT_PRESETS[sport_name]
    sport = preset["sport"]
    speed_min_kmh, speed_max_kmh = preset["speed_kmh"]
    lat0, lon0 = preset["position"]
    rng = random.Random(seed)

    duration_s = int(round(duration_min * 60))
    num_records = duration_s // record_interval_s
    hr_min, hr_max = hr_range
    cad_min, cad_max = cad_range

    start_ts = fit_epoch_seconds(start_dt)
    builder = FitFileBuilder(auto_define=True)
    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = 1  # Garmin
    file_id.product = 3431  # Forerunner 965
    file_id.serial_number = 3479123456 + (seed % 10000)
    file_id.time_created = start_ts
    builder.add(file_id)

    device_info = DeviceInfoMessage()
    device_info.timestamp = start_ts
    device_info.device_type = 4  # running_watch
    device_info.manufacturer = 1  # Garmin
    device_info.product = 3431  # Forerunner 965
    device_info.serial_number = file_id.serial_number
    device_info.software_version = 26.0
    device_info.battery_voltage = 4.1
    builder.add(device_info)

    start_event = EventMessage()
    start_event.event = Event.TIMER
    start_event.event_type = EventType.START
    start_event.timestamp = start_ts
    builder.add(start_event)

    points = generate_track(lat0, lon0, 10.0, num_records, seed)
    total_distance_m = 0.0
    hr_curve = []
    for i in range(num_records):
        frac = (i + 1) / num_records
        warmup = min(1.0, frac / 0.15)
        cooldown = min(1.0, (1.0 - frac) / 0.15)
        ramp = warmup * cooldown
        base_hr = hr_min + (hr_max - hr_min) * ramp * (0.75 + 0.25 * math.sin(frac * 6 * math.pi))
        hr = int(clamp(round(base_hr + rng.gauss(0, hr_jitter)), hr_min, hr_max))
        hr_curve.append(hr)
        speed_kmh = rng.uniform(speed_min_kmh, speed_max_kmh)
        speed_ms = speed_kmh / 3.6
        dist_delta_m = speed_ms * record_interval_s
        total_distance_m += dist_delta_m
        lat, lon = points[i]
        rec = RecordMessage()
        rec.timestamp = start_ts + (i + 1) * record_interval_s * 1000
        rec.position_lat = lat
        rec.position_long = lon
        rec.heart_rate = hr
        rec.distance = total_distance_m
        rec.speed = speed_ms
        rec.cadence = int(
            clamp(round(rng.uniform(*cad_range) + rng.gauss(0, cad_jitter)), cad_min, cad_max)
        )
        builder.add(rec)

    end_ts = start_ts + duration_s * 1000
    stop_event = EventMessage()
    stop_event.event = Event.TIMER
    stop_event.event_type = EventType.STOP
    stop_event.timestamp = end_ts
    builder.add(stop_event)

    avg_hr = sum(hr_curve) / len(hr_curve)
    max_hr = max(hr_curve)
    elapsed_s = num_records * record_interval_s

    lap = LapMessage()
    lap.message_index = 0
    lap.timestamp = end_ts
    lap.start_time = start_ts
    lap.total_elapsed_time = float(elapsed_s)
    lap.total_timer_time = float(elapsed_s)
    lap.total_distance = total_distance_m
    builder.add(lap)

    session = SessionMessage()
    session.message_index = 0
    session.sport = sport
    session.sub_sport = 0  # generic
    session.start_time = start_ts
    session.timestamp = end_ts
    session.total_elapsed_time = float(elapsed_s)
    session.total_timer_time = float(elapsed_s)
    session.total_distance = total_distance_m
    session.avg_heart_rate = int(round(avg_hr))
    session.max_heart_rate = int(max_hr)
    session.total_calories = int(round(duration_min * (6.0 if sport_name == "running" else 8.5)))
    builder.add(session)

    activity = ActivityMessage()
    activity.timestamp = end_ts
    activity.type = FileType.ACTIVITY
    activity.event = Event.TIMER
    activity.event_type = EventType.STOP
    activity.num_sessions = 1
    builder.add(activity)
    return builder.build()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--duration", type=float, default=40.0, help="Dauer in Minuten (Default: 40)")
    p.add_argument(
        "--sport",
        choices=sorted(SPORT_PRESETS),
        default="running",
        help="Aktivitätsart (Default: running)",
    )
    p.add_argument("--start", type=str, default=None, help="Startzeit im Format YYYY-MM-DDTHH:MM:SS (localnahe Zeit)")
    p.add_argument("--count", type=int, default=1, help="Anzahl zu erzeugender Dateien")
    p.add_argument("--spacing-min", type=float, default=120.0, help="Abstand zwischen Aktivitäten in Minuten")
    p.add_argument("--hr-min", type=int, default=None, help="Min. Herzfrequenz (Default: sportabhängig)")
    p.add_argument("--hr-max", type=int, default=None, help="Max. Herzfrequenz (Default: sportabhängig)")
    p.add_argument("--hr-jitter", type=float, default=3.0, help="HF-Jitter (Standardabweichung, Default: 3)")
    p.add_argument("--cad-min", type=int, default=None, help="Min. Cadence (Default: sportabhängig)")
    p.add_argument("--cad-max", type=int, default=None, help="Max. Cadence (Default: sportabhängig)")
    p.add_argument("--cad-jitter", type=float, default=2.5, help="Cadence-Jitter (Standardabweichung, Default: 2.5)")
    p.add_argument("--record-interval", type=int, default=5, help="Sekunden zwischen Records (Default: 5)")
    p.add_argument("--outdir", type=str, default="out", help="Ausgabeverzeichnis (Default: ./out)")
    p.add_argument("--seed", type=int, default=None, help="Zufalls-Seed für reproduzierbare Daten")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    preset = SPORT_PRESETS[args.sport]
    hr_range = (
        args.hr_min if args.hr_min is not None else preset["hr"][0],
        args.hr_max if args.hr_max is not None else preset["hr"][1],
    )
    if hr_range[0] >= hr_range[1]:
        raise SystemExit("Fehler: hr-min muss kleiner als hr-max sein")
    cad_range = (
        args.cad_min if args.cad_min is not None else preset["cadence"][0],
        args.cad_max if args.cad_max is not None else preset["cadence"][1],
    )
    if cad_range[0] >= cad_range[1]:
        raise SystemExit("Fehler: cad-min muss kleiner als cad-max sein")

    if args.start:
        start_dt = datetime.fromisoformat(args.start).replace(tzinfo=None).astimezone()
    else:
        start_dt = datetime.now().replace(microsecond=0) - timedelta(days=1)

    if start_dt.date() > datetime.now().date():
        raise SystemExit(
            f"Fehler: Startdatum {start_dt.date()} liegt in der Zukunft. "
            "Garmin lehnt zukünftige Aktivitäten beim Import oft still ab. "
            "Bitte ein vergangenes Datum setzen oder --start weglassen."
        )
    if start_dt.date() < datetime.now().date() - timedelta(days=365):
        print(
            f"Warnung: Startdatum {start_dt.date()} liegt über einem Jahr zurück; "
            "Garmin zeigt solche Aktivitäten evtl. nicht im Standard-Kalender.",
            file=sys.stderr,
        )

    import os

    os.makedirs(args.outdir, exist_ok=True)
    base_seed = args.seed if args.seed is not None else random.randrange(2**31)

    for i in range(args.count):
        activity_start = start_dt + timedelta(minutes=args.spacing_min * i)
        seed = base_seed + i
        fit = build_activity(
            duration_min=args.duration,
            sport_name=args.sport,
            hr_range=hr_range,
            hr_jitter=args.hr_jitter,
            cad_range=cad_range,
            cad_jitter=args.cad_jitter,
            start_dt=activity_start,
            record_interval_s=args.record_interval,
            seed=seed,
        )
        filename = f"{activity_start.strftime('%Y-%m-%d_%H-%M-%S')}_{args.sport}_{seed}.fit"
        path = os.path.join(args.outdir, filename)
        with open(path, "wb") as fh:
            fh.write(fit.to_bytes())
        print(f"geschrieben: {path} ({args.duration:g} min, {args.sport})")


if __name__ == "__main__":
    main()
