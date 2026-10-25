#!/usr/bin/env python3
"""Verschiebt eine FIT-Aktivität auf ein neues Datum und speichert sie als Klon.

Nützlich, um z. B. täglich dieselbe Testaktivität in Garmin Connect zu haben.

Beispiele:
    # Einzelner Klon auf ein bestimmtes Datum (Uhrzeit bleibt erhalten):
    python clone_fit.py run.fit --to-date 2025-07-01

    # Klone für 7 aufeinanderfolgende Tage (Start mit --to-date oder heute):
    python clone_fit.py run.fit --to-date 2025-07-01 --days 7
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from fit_tool.fit_file import FitFile

TIMESTAMP_FIELDS = ("timestamp", "time_created", "start_time")


def shift_fit_timestamps(fit: FitFile, delta_ms: int) -> None:
    for record in fit.records:
        if record.header.is_definition:
            continue
        message = record.message
        for field in TIMESTAMP_FIELDS:
            value = getattr(message, field, None)
            if value:
                setattr(message, field, value + delta_ms)
        record.mark_dirty()


def earliest_timestamp(fit: FitFile) -> int:
    values = []
    for record in fit.records:
        if record.header.is_definition:
            continue
        message = record.message
        for field in TIMESTAMP_FIELDS:
            value = getattr(message, field, None)
            if value:
                values.append(value)
    if not values:
        raise SystemExit("Fehler: keine Zeitstempel in der Datei gefunden")
    return min(values)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", help="Vorlage-Datei (.fit)")
    p.add_argument(
        "--to-date",
        type=str,
        default=None,
        help="Zieldatum YYYY-MM-DD (Default: heute; Uhrzeit der Vorlage bleibt erhalten)",
    )
    p.add_argument(
        "--days",
        type=int,
        default=1,
        help="Anzahl Klone für aufeinanderfolgende Tage (Default: 1)",
    )
    p.add_argument("--outdir", type=str, default="out", help="Ausgabeverzeichnis (Default: ./out)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.input)
    if not source.is_file():
        raise SystemExit(f"Fehler: Datei nicht gefunden: {source}")

    import os

    os.makedirs(args.outdir, exist_ok=True)
    stem = source.stem

    for day_offset in range(args.days):
        fit = FitFile.from_file(str(source))
        earliest = earliest_timestamp(fit)
        original_start = datetime.fromtimestamp(earliest / 1000)

        if args.to_date:
            target_date = datetime.strptime(args.to_date, "%Y-%m-%d").date()
        else:
            target_date = datetime.now().date()
        target_date = target_date + timedelta(days=day_offset)

        target_start = datetime.combine(target_date, original_start.time())
        delta_ms = int((target_start - original_start).total_seconds() * 1000)

        shift_fit_timestamps(fit, delta_ms)
        fit.mark_dirty()

        filename = f"{target_start.strftime('%Y-%m-%d_%H-%M-%S')}_clone_{stem}.fit"
        out_path = Path(args.outdir) / filename
        fit.to_file(str(out_path))
        print(f"geschrieben: {out_path} (Start {target_start})")


if __name__ == "__main__":
    main()
