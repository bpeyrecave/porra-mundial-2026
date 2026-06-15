#!/usr/bin/env python3
"""
Fetches FIFA World Cup 2026 results.

Two sources:
  1. api-sports.io  — primary source for FINISHED match results (requires RAPIDAPI_KEY secret)
  2. ESPN Core API  — free, no key needed, used for live scores during games in progress

Live score flow:
  - Before kickoff      → status stays TIMED
  - During game         → ESPN Core API sets status to IN_PLAY + live score
  - After final whistle → api-sports.io sets status to FINISHED + final score (within 5 min)
"""
import os, json, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
APISPORTS_BASE = "https://v3.football.api-sports.io"
APISPORTS_HEADERS = {"x-apisports-key": RAPIDAPI_KEY}
WC_LEAGUE_ID = 1

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues/fifa.world"

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Status mapping ────────────────────────────────────────────────────────────
def map_apisports_status(s):
    if s in {"FT", "AET", "PEN"}:       return "FINISHED"
    if s == "HT":                        return "PAUSED"
    if s in {"1H", "2H", "ET", "BT", "P", "LIVE", "INT"}: return "IN_PLAY"
    return "TIMED"

def map_espn_status(s):
    if s in {"STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"}:
        return "FINISHED"
    if s == "STATUS_HALFTIME":
        return "PAUSED"
    if s in {"STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_END_PERIOD",
             "STATUS_EXTRA_TIME", "STATUS_PENALTY", "STATUS_IN_PROGRESS"}:
        return "IN_PLAY"
    return "TIMED"

# ── Team name mapping ────────────────────────────────────────────────────────
def load_en_to_es():
    with open(DATA_DIR / "team_names.json") as f:
        data = json.load(f)
    mapping = {v: k for k, v in data["es_to_en"].items()}
    mapping.update({
        "Czechia": "República Checa", "Czech Republic": "República Checa",
        "United States": "Estados Unidos", "USA": "Estados Unidos",
        "Turkey": "Turquía", "Türkiye": "Turquía",
        "Ivory Coast": "Costa de Marfil", "Côte d'Ivoire": "Costa de Marfil",
        "Congo DR": "RD Congo", "DR Congo": "RD Congo",
        "Cape Verde Islands": "Cabo Verde", "Cape Verde": "Cabo Verde",
        "Saudi Arabia": "Arabia Saudita",
        "South Korea": "Corea del Sur", "Korea Republic": "Corea del Sur",
        "Curaçao": "Curazao",
        "Bosnia-Herzegovina": "Bosnia y Herzegovina",
        "Bosnia And Herzegovina": "Bosnia y Herzegovina",
        "Bosnia & Herzegovina": "Bosnia y Herzegovina",
        "Uzbekistan": "Uzbekistán",
        "Jordan": "Jordania", "Haiti": "Haití",
        "Scotland": "Escocia", "Netherlands": "Países Bajos",
        "Belgium": "Bélgica", "Egypt": "Egipto",
        "Iran": "Irán", "New Zealand": "Nueva Zelanda",
        "Norway": "Noruega", "Algeria": "Argelia",
        "Mexico": "México", "South Africa": "Sudáfrica",
        "Australia": "Australia", "Paraguay": "Paraguay",
    })
    return mapping

# ── api-sports.io: fetch all fixtures (FINISHED results) ─────────────────────
def fetch_apisports_finished(en_to_es):
    """Returns dict of (home_es, away_es) → match update for FINISHED games."""
    if not RAPIDAPI_KEY:
        print("  RAPIDAPI_KEY not set — skipping api-sports.io")
        return {}

    try:
        resp = requests.get(
            f"{APISPORTS_BASE}/fixtures",
            headers=APISPORTS_HEADERS,
            params={"league": WC_LEAGUE_ID, "season": 2026},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        fixtures = data.get("response", [])
        print(f"  api-sports.io: HTTP {resp.status_code}, {len(fixtures)} fixtures, errors={data.get('errors')}, results={data.get('results')}")
    except Exception as e:
        print(f"  api-sports.io request failed: {e}")
        return {}

    updates = {}
    for f in fixtures:
        fixture = f.get("fixture", {})
        api_status = fixture.get("status", {}).get("short", "NS")
        status = map_apisports_status(api_status)

        # Only apply api-sports.io data for FINISHED games
        # (live status from this API is unreliable on free tier)
        if status != "FINISHED":
            continue

        teams = f.get("teams", {})
        goals = f.get("goals", {})
        home_en = teams.get("home", {}).get("name", "")
        away_en = teams.get("away", {}).get("name", "")
        home_es = en_to_es.get(home_en, home_en)
        away_es = en_to_es.get(away_en, away_en)
        home_goals = goals.get("home")
        away_goals = goals.get("away")

        winner = None
        if home_goals is not None and away_goals is not None:
            if home_goals > away_goals:   winner = home_es
            elif away_goals > home_goals: winner = away_es
            else:                         winner = "draw"

        updates[(home_es, away_es)] = {
            "status": "FINISHED",
            "home_goals": home_goals,
            "away_goals": away_goals,
            "winner_es": winner,
        }

    finished = len(updates)
    print(f"  api-sports.io: {finished} finished matches found")
    return updates

# ── ESPN Core API: fetch live scores for in-progress games ───────────────────
def fetch_espn_live(now, en_to_es):
    """Returns dict of (home_es, away_es) → match update for IN_PLAY/PAUSED games."""
    updates = {}

    # Get events from yesterday AND today to catch games that were live around midnight
    events = []
    for d in [(now - timedelta(days=1)).strftime("%Y%m%d"), now.strftime("%Y%m%d")]:
        try:
            resp = requests.get(ESPN_SCOREBOARD, params={"dates": d, "limit": 50}, timeout=15)
            resp.raise_for_status()
            events += resp.json().get("events", [])
        except Exception as e:
            print(f"  ESPN scoreboard failed for {d}: {e}")

    for event in events:
        eid = event.get("id")
        if not eid:
            continue

        # Only process games past their kickoff time
        try:
            kickoff = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if now < kickoff:
            continue

        # Get team names and IDs from the scoreboard competitors
        scoreboard_comps = event.get("competitions", [{}])[0].get("competitors", [])
        home_sb = next((c for c in scoreboard_comps if c.get("homeAway") == "home"), {})
        away_sb = next((c for c in scoreboard_comps if c.get("homeAway") == "away"), {})
        home_id = home_sb.get("id")
        away_id = away_sb.get("id")
        home_en = home_sb.get("team", {}).get("displayName", "")
        away_en = away_sb.get("team", {}).get("displayName", "")
        home_es = en_to_es.get(home_en, home_en)
        away_es = en_to_es.get(away_en, away_en)

        if not home_id or not away_id or not home_es or not away_es:
            continue

        # Fetch live status from ESPN Core API
        core_base = f"{ESPN_CORE}/events/{eid}/competitions/{eid}"
        try:
            status_resp = requests.get(f"{core_base}/status", timeout=10)
            status_resp.raise_for_status()
            espn_state = status_resp.json().get("type", {}).get("name", "")
            status = map_espn_status(espn_state)
        except Exception as e:
            print(f"  ESPN Core status failed for event {eid}: {e}")
            continue

        if status == "TIMED":
            continue  # hasn't started yet

        # Fetch scores
        home_goals = away_goals = None
        try:
            hr = requests.get(f"{core_base}/competitors/{home_id}/score", timeout=10)
            if hr.ok:
                home_goals = int(hr.json().get("value", 0))
        except Exception:
            pass
        try:
            ar = requests.get(f"{core_base}/competitors/{away_id}/score", timeout=10)
            if ar.ok:
                away_goals = int(ar.json().get("value", 0))
        except Exception:
            pass

        winner = None
        if status == "FINISHED" and home_goals is not None and away_goals is not None:
            if home_goals > away_goals:   winner = home_es
            elif away_goals > home_goals: winner = away_es
            else:                         winner = "draw"

        updates[(home_es, away_es)] = {
            "status": status,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "winner_es": winner,
        }
        label = "FINISHED" if status == "FINISHED" else "LIVE"
        print(f"  {label}: {home_es} {home_goals} - {away_goals} {away_es} ({espn_state})")

    return updates

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc)
    en_to_es = load_en_to_es()

    # Load existing results.json (preserves all 104 matches + metadata)
    out_path = DATA_DIR / "results.json"
    try:
        with open(out_path) as f:
            content = f.read().strip()
        if not content:
            raise ValueError("results.json is empty")
        existing = json.loads(content)
    except (json.JSONDecodeError, ValueError, FileNotFoundError) as e:
        print(f"WARNING: Could not load results.json ({e}), starting fresh")
        existing = {"competition": "FIFA World Cup 2026", "total_matches": 104, "matches": []}
    matches = existing.get("matches", [])

    # 1. Get FINISHED results from api-sports.io
    finished_updates = fetch_apisports_finished(en_to_es)

    # 2. Get live scores from ESPN Core API
    live_updates = fetch_espn_live(now, en_to_es)

    # 3. Apply updates — finished results take priority over live
    #    (a game already marked FINISHED should not be overwritten by a stale live update)
    all_updates = {**live_updates, **finished_updates}

    applied = 0
    for m in matches:
        key = (m.get("home_team_es"), m.get("away_team_es"))
        if key in all_updates:
            m.update(all_updates[key])
            applied += 1

    existing["last_updated"] = now.isoformat()

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    live    = sum(1 for m in matches if m["status"] == "IN_PLAY")
    paused  = sum(1 for m in matches if m["status"] == "PAUSED")
    finished = sum(1 for m in matches if m["status"] == "FINISHED")
    print(f"Done. {finished} finished, {live} live, {paused} paused, {applied} updated. Saved.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"FATAL ERROR in main(): {e}")
        traceback.print_exc()
        # Still write last_updated so the commit captures the error timestamp
        try:
            out_path = Path(__file__).parent.parent / "data" / "results.json"
            with open(out_path) as f:
                existing = json.load(f)
            existing["last_updated"] = datetime.now(timezone.utc).isoformat()
            existing["last_error"] = str(e)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            print("Wrote last_updated despite fatal error.")
        except Exception as e2:
            print(f"Could not write results.json: {e2}")
