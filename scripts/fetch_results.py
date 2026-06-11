#!/usr/bin/env python3
"""
Fetches FIFA World Cup 2026 results from API-Football (api-sports.io).
Run manually or via GitHub Actions.
Requires: RAPIDAPI_KEY environment variable (your API-Football key from dashboard.api-football.com).
"""
import os, json, requests
from datetime import datetime, timezone
from pathlib import Path

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
BASE = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": RAPIDAPI_KEY,
}
DATA_DIR = Path(__file__).parent.parent / "data"

# API-Football league ID for FIFA World Cup 2026
WC_LEAGUE_ID = 1  # FIFA World Cup

def load_team_map():
    with open(DATA_DIR / "team_names.json") as f:
        data = json.load(f)
    en_to_es = {v: k for k, v in data["es_to_en"].items()}
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
        "Cape Verde Islands": "Cabo Verde",
        "Saudi Arabia": "Arabia Saudita",
        "South Korea": "Corea del Sur",
        "Korea Republic": "Corea del Sur",
        "Curacao": "Curazao",
        "Curaçao": "Curazao",
        "Bosnia And Herzegovina": "Bosnia y Herzegovina",
        "Bosnia-Herzegovina": "Bosnia y Herzegovina",
        "Bosnia & Herzegovina": "Bosnia y Herzegovina",
        "Uzbekistan": "Uzbekistán",
        "Jordan": "Jordania",
        "Haiti": "Haití",
        "Scotland": "Escocia",
        "Netherlands": "Países Bajos",
        "Belgium": "Bélgica",
        "Egypt": "Egipto",
        "Iran": "Irán",
        "New Zealand": "Nueva Zelanda",
        "Norway": "Noruega",
        "Algeria": "Argelia",
        "Austria": "Austria",
        "Portugal": "Portugal",
        "DR Congo": "RD Congo",
        "England": "Inglaterra",
        "Croatia": "Croacia",
        "Ghana": "Ghana",
        "Panama": "Panamá",
        "Iraq": "Irak",
        "Senegal": "Senegal",
        "France": "Francia",
        "Germany": "Alemania",
        "Ecuador": "Ecuador",
        "Sweden": "Suecia",
        "Tunisia": "Túnez",
        "Japan": "Japón",
        "Qatar": "Catar",
        "Switzerland": "Suiza",
        "Canada": "Canadá",
        "Morocco": "Marruecos",
        "Brazil": "Brasil",
        "Spain": "España",
        "Uruguay": "Uruguay",
        "Argentina": "Argentina",
        "Colombia": "Colombia",
        "Mexico": "México",
        "South Africa": "Sudáfrica",
        "Australia": "Australia",
        "Paraguay": "Paraguay",
    }
    en_to_es.update(aliases)
    return en_to_es

def normalize(name, en_to_es):
    if not name:
        return None
    return en_to_es.get(name, name)

def map_status(api_status):
    # API-Football statuses: NS, TBD, 1H, HT, 2H, ET, BT, P, SUSP, INT, FT, AET, PEN, PST, CANC, ABD, AWD, WO, LIVE
    live = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}
    finished = {"FT", "AET", "PEN"}
    if api_status in finished:
        return "FINISHED"
    if api_status in live:
        return "IN_PLAY"
    if api_status == "HT":
        return "PAUSED"
    return "TIMED"

def map_stage(round_name):
    if not round_name:
        return "group"
    r = round_name.upper()
    if "GROUP" in r:
        return "group"
    if "32" in r or "LAST 32" in r:
        return "Round of 32"
    if "16" in r or "LAST 16" in r:
        return "Round of 16"
    if "QUARTER" in r:
        return "Quarter-final"
    if "SEMI" in r:
        return "Semi-final"
    if "THIRD" in r or "3RD" in r:
        return "Third place"
    if "FINAL" in r:
        return "Final"
    return round_name

def fetch_fixtures():
    url = f"{BASE}/fixtures"
    resp = requests.get(url, headers=HEADERS, params={"league": WC_LEAGUE_ID, "season": 2026}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", [])

def main():
    if not RAPIDAPI_KEY:
        print("ERROR: RAPIDAPI_KEY not set")
        raise SystemExit(1)

    en_to_es = load_team_map()
    print("Fetching WC 2026 fixtures from API-Football...")

    try:
        fixtures = fetch_fixtures()
    except requests.HTTPError as e:
        print(f"API error: {e} — {e.response.text[:200] if e.response else ''}")
        raise SystemExit(1)

    processed = []
    for f in fixtures:
        fixture  = f.get("fixture", {})
        teams    = f.get("teams", {})
        goals    = f.get("goals", {})
        league   = f.get("league", {})

        api_status = fixture.get("status", {}).get("short", "NS")
        status = map_status(api_status)

        home_name = teams.get("home", {}).get("name", "")
        away_name = teams.get("away", {}).get("name", "")
        home_goals = goals.get("home")
        away_goals = goals.get("away")

        home_es = normalize(home_name, en_to_es)
        away_es = normalize(away_name, en_to_es)

        winner = None
        if status == "FINISHED" and home_goals is not None and away_goals is not None:
            if home_goals > away_goals:
                winner = home_es
            elif away_goals > home_goals:
                winner = away_es
            else:
                winner = "draw"

        processed.append({
            "api_id": fixture.get("id"),
            "stage": map_stage(league.get("round", "")),
            "utc_date": fixture.get("date"),
            "status": status,
            "home_team_es": home_es,
            "away_team_es": away_es,
            "home_team_en": home_name,
            "away_team_en": away_name,
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

    live    = sum(1 for m in processed if m["status"] == "IN_PLAY")
    finished = sum(1 for m in processed if m["status"] == "FINISHED")
    print(f"Done. {finished} finished, {live} live, {len(processed)} total. Saved to {out_path}")

if __name__ == "__main__":
    main()
