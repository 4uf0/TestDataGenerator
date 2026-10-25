#!/usr/bin/env python3
"""Web-UI mit Kalender: Aktivitäten pro Tag eintragen und FIT-Dateien erzeugen.

Start:    python app.py   (dann http://127.0.0.1:5000 im Browser)

Daten liegen in SQLite (activities.db) – Einträge und erzeugte Dateien
werden lokal gespeichert, damit der Kalender den Stand anzeigt.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import generate_fit

DB_PATH = Path(__file__).parent / "activities.db"
OUT_DIR = Path(__file__).parent / "out"

app = Flask(__name__)


# ---------------------------------------------------------------- Datenbank

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,          -- YYYY-MM-DD
                time TEXT NOT NULL,          -- HH:MM
                sport TEXT NOT NULL,         -- running/cycling/hiking
                duration_min REAL NOT NULL,
                hr_min INTEGER NOT NULL,
                hr_max INTEGER NOT NULL,
                hr_jitter REAL NOT NULL,
                cad_min INTEGER NOT NULL,
                cad_max INTEGER NOT NULL,
                cad_jitter REAL NOT NULL,
                seed INTEGER,
                filename TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


# ------------------------------------------------------------------ Routing

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/activities")
def list_activities():
    start = request.args.get("start")
    end = request.args.get("end")
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM activities ORDER BY date, time"
        ).fetchall()
    events = []
    for r in rows:
        events.append(
            {
                "id": r["id"],
                "title": f"{r['sport']} {r['duration_min']:g}min",
                "start": f"{r['date']}T{r['time']}:00",
                "extendedProps": dict(r),
            }
        )
    return jsonify(events)


@app.route("/api/activities", methods=["POST"])
def add_activity():
    data = request.get_json(force=True)
    required = ["date", "time", "sport", "duration_min"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Feld '{field}' fehlt"}), 400
    hr_min = int(data.get("hr_min") or generate_fit.SPORT_PRESETS[data["sport"]]["hr"][0])
    hr_max = int(data.get("hr_max") or generate_fit.SPORT_PRESETS[data["sport"]]["hr"][1])
    cad_min = int(data.get("cad_min") or generate_fit.SPORT_PRESETS[data["sport"]]["cadence"][0])
    cad_max = int(data.get("cad_max") or generate_fit.SPORT_PRESETS[data["sport"]]["cadence"][1])
    hr_jitter = float(data.get("hr_jitter") or 3.0)
    cad_jitter = float(data.get("cad_jitter") or 2.5)
    seed = data.get("seed")
    if seed is not None:
        seed = int(seed)
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO activities
                (date, time, sport, duration_min, hr_min, hr_max, hr_jitter,
                 cad_min, cad_max, cad_jitter, seed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["date"],
                data["time"],
                data["sport"],
                float(data["duration_min"]),
                hr_min,
                hr_max,
                hr_jitter,
                cad_min,
                cad_max,
                cad_jitter,
                seed,
            ),
        )
        new_id = cur.lastrowid
    return jsonify({"id": new_id}), 201


@app.route("/api/activities/<int:activity_id>", methods=["DELETE"])
def delete_activity(activity_id):
    with db() as conn:
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    return jsonify({"ok": True})


@app.route("/api/generate", methods=["POST"])
def generate():
    """Erzeugt FIT-Dateien für alle DB-Einträge ohne Datei."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM activities WHERE filename IS NULL ORDER BY date, time"
        ).fetchall()
    generated = []
    errors = []
    for r in rows:
        try:
            start_dt = datetime.fromisoformat(f"{r['date']}T{r['time']}:00")
            seed = r["seed"] if r["seed"] else random.randrange(2**31)
            fit = generate_fit.build_activity(
                duration_min=r["duration_min"],
                sport_name=r["sport"],
                hr_range=(r["hr_min"], r["hr_max"]),
                hr_jitter=r["hr_jitter"],
                cad_range=(r["cad_min"], r["cad_max"]),
                cad_jitter=r["cad_jitter"],
                start_dt=start_dt,
                record_interval_s=5,
                seed=seed,
            )
            OUT_DIR.mkdir(exist_ok=True)
            filename = f"{start_dt.strftime('%Y-%m-%d_%H-%M-%S')}_{r['sport']}_{seed}.fit"
            (OUT_DIR / filename).write_bytes(fit.to_bytes())
            with db() as conn:
                conn.execute(
                    "UPDATE activities SET filename = ? WHERE id = ?",
                    (filename, r["id"]),
                )
            generated.append(filename)
        except Exception as exc:
            errors.append(f"{r['date']} {r['time']}: {exc}")
    return jsonify({"generated": generated, "errors": errors})


@app.route("/api/upload", methods=["POST"])
def upload():
    """Lädt alle erzeugten Dateien aus out/ hoch (nutzt upload_to_garmin-Logik)."""
    import subprocess
    import sys

    files = sorted(OUT_DIR.glob("*.fit"))
    if not files:
        return jsonify({"uploaded": 0, "failed": []})
    script = Path(__file__).parent / "upload_to_garmin.py"
    tokens = Path(__file__).parent / "garmin_tokens.json"
    cmd = [sys.executable, str(script)]
    if tokens.exists():
        cmd += ["--use-tokens", str(tokens)]
    cmd.append(str(OUT_DIR))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    failed = [ln for ln in proc.stderr.splitlines() if ln.startswith("FEHLER")]
    return jsonify({"uploaded": proc.returncode == 0, "failed": failed, "log": proc.stdout + proc.stderr})


@app.route("/api/queue")
def queue():
    """Einträge ohne erzeugte Datei (Upload-Warteschlange)."""
    with db() as conn:
        rows = conn.execute(
            "SELECT id, date, time, sport, duration_min FROM activities WHERE filename IS NULL"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="127.0.0.1", port=5000)
