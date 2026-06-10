#!/usr/bin/env python3
"""
Extracts a participant's picks from a filled Porra Mundial 2026 Excel file.
Usage: python extract_picks.py <excel_file> <participant_name>
Output: data/picks/<participant_name_lowercase>.json
"""
import sys, json
from pathlib import Path
import openpyxl
from openpyxl.cell.cell import MergedCell

def get_val(ws, row, col):
    cell = ws.cell(row, col)
    v = None if isinstance(cell, MergedCell) else cell.value
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return v

def extract(excel_path, name):
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb['WORLDCUP ✅']

    groups = {
        'A': range(4,10), 'B': range(12,18), 'C': range(20,26),
        'D': range(28,34), 'E': range(36,42), 'F': range(44,50),
        'G': range(52,58), 'H': range(60,66), 'I': range(68,74),
        'J': range(76,82), 'K': range(84,90), 'L': range(92,98),
    }

    group_matches = []
    for group, rows in groups.items():
        for i, r in enumerate(rows):
            home = get_val(ws, r, 27)
            away = get_val(ws, r, 32)
            hg   = get_val(ws, r, 29)
            ag   = get_val(ws, r, 30)
            group_matches.append({
                "match_id": f"G{group}{i+1}", "stage": "group", "group": group,
                "home_team": home, "away_team": away,
                "predicted_home": hg, "predicted_away": ag, "max_points": 3
            })

    ko_defs = (
        [(101+i, f"R32-{i+1}", "Round of 32", 5) for i in range(16)] +
        [(120+i, f"R16-{i+1}", "Round of 16", 10) for i in range(8)] +
        [(131+i, f"QF-{i+1}", "Quarter-final", 15) for i in range(4)] +
        [(138, "SF-1", "Semi-final", 25), (139, "SF-2", "Semi-final", 25),
         (143, "3rd", "Third place", 15), (147, "Final", "Final", 50)]
    )

    knockout_matches = []
    for row, mid, stage, pts in ko_defs:
        home = get_val(ws, row, 27)
        away = get_val(ws, row, 32)
        hg   = get_val(ws, row, 29)
        ag   = get_val(ws, row, 30)
        # Knockout rounds always produce a winner (penalties if tied after 90').
        # When predicted score is a tie, home team is treated as the picked winner.
        winner = None
        if hg is not None and ag is not None:
            if hg > ag:   winner = home
            elif ag > hg: winner = away
            else:         winner = home  # tied score → home team goes through
        knockout_matches.append({
            "match_id": mid, "stage": stage,
            "home_team": home, "away_team": away,
            "predicted_home": hg, "predicted_away": ag,
            "predicted_winner": winner, "max_points": pts
        })

    picks = {
        "participant": name,
        "group_matches": group_matches,
        "knockout_matches": knockout_matches,
        "champion": get_val(ws, 150, 27),
        "extras": {
            "bota_oro":     get_val(ws, 154, 27),
            "bota_plata":   get_val(ws, 155, 27),
            "bota_bronce":  get_val(ws, 156, 27),
            "balon_oro":    get_val(ws, 158, 27),
            "balon_plata":  get_val(ws, 159, 27),
            "balon_bronce": get_val(ws, 160, 27),
        }
    }

    out_dir = Path(__file__).parent.parent / "data" / "picks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name.lower().replace(' ', '_')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(picks, f, indent=2, ensure_ascii=False, default=str)
    print(f"Saved {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_picks.py <excel_file> <ParticipantName>")
        sys.exit(1)
    extract(sys.argv[1], sys.argv[2])
