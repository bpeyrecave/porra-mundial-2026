#!/usr/bin/env python3
"""
Fetches FIFA World Cup 2026 results from football-data.org API.
Run manually or via GitHub Actions.
Requires: FOOTBALL_DATA_API_KEY environment variable.
"""
import os, json, requests
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}
DATA_DIR = Path(__file__).parent.parent / "data"

def load_team_map():
    with open(DATA_DIR / "team_names.json") as f:
        data = json.load(f)
    # Build reverse map: English → Spanish
    en_to_es = {v: k for k, v in data["es_to_en"].items()}
    # Also add common aliases that APIs may use
    aliases = {
        "Czech Republic": "República Checa",
        "Czechia": "República Checa",
        "USA": "Estados Unidos",
        "United States": "Estados Unidos",
        "Turkey": "Turquía",
        "Türkiye": "Turquía",
        "Ivory Coast": "Costa de Marfil",
        "Côte d'Ivoire": "Costa de Marfil",
        "DR Congo": "RD Congo",
        "Congo DR": "RD Congo",
        "Cape Verde": "Cabo Verde",
        "Saudi Arabia": "Arabia Saudita",
        "South Korea": "Corea del Sur",
        "Korea Republic": "Corea del Sur",
        "Curacao": "Curazao",
        "Curaçao": "Curazao",
    }
    en_to_es.update(aliases)
    return en_to_es

def normalize(name, en_to_es):
    return en_to_es.get(name, name)

def fetch_matches():
    url = f"{BASE}/competitions/WC/matches?season=2026"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code == 404:
        # Try alternative endpoint
        url = f"{BASE}/competitions/FIFA World Cup/matches?season=2026"
        resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("matches", [])

def map_stage(api_stage):
    stage_map = {
        "GROUP_STAGE": "group",
        "ROUND_OF_32": "Round of 32",
        "ROUND_OF_16": "Round of 16",
        "QUARTER_FINALS": "Quarter-final",
        "SEMI_FINALS": "Semi-final",
        "THIRD_PLACE": "Third place",
        "FINAL": "Final",
    }
    return stage_map.get(api_stage, api_stage)

def main():
    if not API_KEY:
        print("ERROR: FOOTBALL_DATA_API_KEY not set")
        raise SystemExit(1)

    en_to_es = load_team_map()
    print("Fetching WC 2026 matches...")

    try:
        matches = fetch_matches()
    except requests.HTTPError as e:
        print(f"API error: {e}")
        raise SystemExit(1)

    processed = []
    for m in matches:
        status = m.get("status")
        home_api = m.get("homeTeam", {}).get("name", "")
        away_api = m.get("awayTeam", {}).get("name", "")
        score = m.get("score", {})
        full = score.get("fullTime", {})
        home_goals = full.get("home")
        away_goals = full.get("away")
        # For live matches the current score may be under different keys
        if home_goals is None and status in ("IN_PLAY", "PAUSED", "HALFTIME"):
            for period in ("regularTime", "halfTime", "currentPeriod"):
                p = score.get(period, {})
                if p.get("home") is not None:
                    home_goals = p.get("home")
                    away_goals = p.get("away")
                    break

        winner = None
        if status == "FINISHED" and home_goals is not None and away_goals is not None:
            if home_goals > away_goals:
                winner = normalize(home_api, en_to_es)
            elif away_goals > home_goals:
                winner = normalize(away_api, en_to_es)
            else:
                winner = "draw"

        processed.append({
            "api_id": m.get("id"),
            "stage": map_stage(m.get("stage", "")),
            "matchday": m.get("matchday"),
            "group": m.get("group"),
            "utc_date": m.get("utcDate"),
            "status": status,
            "home_team_es": normalize(home_api, en_to_es),
            "away_team_es": normalize(away_api, en_to_es),
            "home_team_en": home_api,
            "away_team_en": away_api,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "winner_es": winner,
        })

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "competition": "FIFA World Cup 2026",
        "total_matches": len(processed),
        "matches": processed,
    }

    out_path = DATA_DIR / "results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    finished = sum(1 for m in processed if m["status"] == "FINISHED")
    print(f"Done. {finished}/{len(processed)} matches finished. Saved to {out_path}")

if __name__ == "__main__":
    main()
