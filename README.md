# TestDataGenerator

Erzeugt realistische FIT-Aktivitätsdateien (Garmin-kompatibel), z. B. um Software zu testen, die Aktivitäten von Garmin herunterlädt.

## Installation

Einmalig Umgebung einrichten (legt `.venv` an und installiert alles):

```bash
./setup.sh
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
.\setup.ps1
.venv\Scripts\Activate.ps1
```

Alternativ minimal per pip:

```bash
pip install -r requirements.txt
```

## Verwendung

Standard: 40 min Lauf, Start gestern, Ausgabe in `./out`:

```bash
python generate_fit.py
```

Dauer und Sportart anpassen:

```bash
python generate_fit.py --duration 35 --sport cycling
```

Herzfrequenz/Cadence mit min/max und Jitter steuern:

```bash
python generate_fit.py --hr-min 110 --hr-max 165 --hr-jitter 4 \
                       --cad-min 155 --cad-max 180 --cad-jitter 3
```

Mehrere Aktivitäten mit festem Startzeitpunkt und Abstand:

```bash
python generate_fit.py --count 3 --start "2025-06-01T09:15:00" --spacing-min 600
```

Reproduzierbare Dateien (gleicher Seed = gleiche Daten):

```bash
python generate_fit.py --seed 42
```

## Parameter

| Parameter | Default | Beschreibung |
|---|---|---|
| `--duration` | 40 | Dauer in Minuten |
| `--sport` | `running` | `running`, `cycling` oder `hiking` |
| `--start` | gestern | Startzeit `YYYY-MM-DDTHH:MM:SS` |
| `--count` | 1 | Anzahl Aktivitäten |
| `--spacing-min` | 120 | Abstand zwischen Aktivitäten (Minuten) |
| `--hr-min` / `--hr-max` | sportabhängig | Herzfrequenz-Bereich |
| `--hr-jitter` | 3 | HF-Jitter (Gauß, Standardabweichung) |
| `--cad-min` / `--cad-max` | sportabhängig | Cadence-Bereich |
| `--cad-jitter` | 2.5 | Cadence-Jitter (Gauß, Standardabweichung) |
| `--record-interval` | 5 | Sekunden zwischen FIT-Records |
| `--outdir` | `./out` | Ausgabeverzeichnis |
| `--seed` | zufällig | Seed für reproduzierbare Daten |

## Web-UI mit Kalender (empfohlen)

`app.py` startet eine lokale Web-UI mit Monatskalender – Aktivitäten pro Tag eintragen,
FIT-Dateien per Klick erzeugen und hochladen. Alle Einträge liegen in SQLite (`activities.db`):

```bash
python app.py
# dann http://127.0.0.1:5000 im Browser öffnen
```

- **Kalender:** Tag anklicken = Datum im Formular; Eintrag anklicken = löschen
- **Formular:** Datum, Uhrzeit, Sport, Dauer; Puls/Cadence min/max/Jitter (leer = Sport-Default), Seed optional
- **„FIT-Dateien erzeugen“:** erzeugt für alle DB-Einträge ohne Datei die FIT-Datei in `out/`
- **„Zu Garmin hochladen“:** lädt `out/` hoch (nutzt `garmin_tokens.json`, falls vorhanden; hochgeladene Dateien werden gelöscht)

## Bestehende Aktivität klonen (neues Datum)

`clone_fit.py` liest eine FIT-Datei, verschiebt alle Zeitstempel auf ein neues Datum und speichert sie als Klon – z. B. um täglich dieselbe Testaktivität in Garmin Connect zu haben:

```bash
# Einzelner Klon auf ein Zieldatum (Uhrzeit der Vorlage bleibt erhalten):
python clone_fit.py out/mein_lauf.fit --to-date 2025-07-01

# Klone für 7 aufeinanderfolgende Tage:
python clone_fit.py out/mein_lauf.fit --to-date 2025-07-01 --days 7

# Ohne --to-date: ab heute
python clone_fit.py out/mein_lauf.fit --days 7
```

Alle Werte (Track, Herzfrequenz, Distanz, Session-Summen) bleiben identisch, nur die Daten wandern. Danach wie gewohnt hochladen:

```bash
python upload_to_garmin.py --use-tokens garmin_tokens.json out/
```

## Aufbau der Dateien

Jede Datei enthält `file_id`, `event` (start/stop), `record`-Mesapunkte (Position, HF, Cadence, Distanz, Speed) sowie konsistente `lap`- und `session`-Summen. Der HF-Verlauf folgt einer Aufwärm-/Auslauf-Kurve mit Jitter und bleibt garantiert innerhalb min/max.

Erzeugte Dateien können direkt über garminconnect.com ("Activity Import"), Garmin Express oder per Skript hochgeladen werden:

```bash
pip install -r requirements.txt
GARMIN_EMAIL=... GARMIN_PASSWORD=... python upload_to_garmin.py out/
```

Details siehe `upload_to_garmin.py --help` (u. a. Token-basierte Anmeldung für wiederholte Uploads).

Alternativ per Makefile:

```bash
make setup
generate:  # venv muss aktiv sein
make upload  # GARMIN_EMAIL/GARMIN_PASSWORD als env setzen
```
