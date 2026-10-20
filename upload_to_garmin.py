#!/usr/bin/env python3
"""Lädt FIT-Aktivitätsdateien zu Garmin Connect hoch (Batch oder Einzeldatei).

Anmeldung per E-Mail/Passwort (Umgebungsvariablen empfohlen) oder optional
gespeicherten OAuth-Tokens (--save-tokens / --use-tokens), um wiederholte
Logins zu vermeiden.

Beispiele:
    GARMIN_EMAIL=... GARMIN_PASSWORD=... python upload_to_garmin.py out/
    python upload_to_garmin.py --save-tokens garmin_tokens.json out/       # 1. Login
    python upload_to_garmin.py --use-tokens garmin_tokens.json out/       # Folgelogins
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from garminconnect import Garmin


def load_client(args: argparse.Namespace) -> Garmin:
    if args.use_tokens:
        token_path = Path(args.use_tokens)
        if not token_path.exists():
            raise SystemExit(f"Token-Datei nicht gefunden: {token_path}")
        tokens = json.loads(token_path.read_text())
        client = Garmin()
        client.login(tokens["oauth1"], tokens["oauth2"])
        print("angemeldet (Tokens)")
        return client

    email = args.email or os.environ.get("GARMIN_EMAIL")
    password = args.password or os.environ.get("GARMIN_PASSWORD")
    if not email:
        email = input("Garmin E-Mail: ")
    if not password:
        password = getpass.getpass("Garmin Passwort: ")

    def prompt_mfa() -> str:
        return input("MFA-Code (aus Authenticator-App/E-Mail): ")

    client = Garmin(email, password, prompt_mfa=prompt_mfa)
    client.login()
    if args.save_tokens:
        oauth1 = client.oauth1
        oauth2 = client.oauth2
        Path(args.save_tokens).write_text(
            json.dumps({"oauth1": oauth1, "oauth2": oauth2})
        )
        print(f"Tokens gespeichert: {args.save_tokens}")
    print("angemeldet")
    return client


def collect_fit_files(path: str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    files = sorted(p.glob("*.fit"))
    if not files:
        raise SystemExit(f"Keine .fit-Dateien in {p} gefunden")
    return files


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("path", help=".fit-Datei oder Verzeichnis mit .fit-Dateien")
    p.add_argument("--email", help="Garmin E-Mail (alternativ GARMIN_EMAIL)")
    p.add_argument("--password", help="Garmin Passwort (alternativ GARMIN_PASSWORD)")
    p.add_argument("--save-tokens", metavar="FILE", help="OAuth-Tokens nach Login in Datei speichern")
    p.add_argument("--use-tokens", metavar="FILE", help="Anmeldung mit gespeicherten OAuth-Tokens")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    files = collect_fit_files(args.path)
    client = load_client(args)
    ok = 0
    failed = []
    for f in files:
        try:
            response = client.upload_activity(str(f))
            status = response.get("upload", {}).get("status", {}).get("status", "OK") if isinstance(response, dict) else "OK"
            print(f"hochgeladen: {f.name} ({status})")
            f.unlink()
            print(f"  gelöscht: {f.name}")
            ok += 1
        except Exception as exc:
            print(f"FEHLER bei {f.name}: {exc}", file=sys.stderr)
            failed.append(f.name)
    print(f"\nfertig: {ok} erfolgreich, {len(failed)} fehlgeschlagen")
    if ok:
        print(f"{ok} hochgeladene Datei(en) lokal gelöscht; nur fehlgeschlagene bleiben übrig")
    if failed:
        print("fehlgeschlagen:", ", ".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
