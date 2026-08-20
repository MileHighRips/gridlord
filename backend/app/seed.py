"""Seed the database with the default league and a sample player universe.

Run:  python -m app.seed
"""
from __future__ import annotations

import random

from .database import SessionLocal, init_db
from .defaults import DEFAULT_LEAGUE
from .models import ADPEntry, League, Player, Projection, ProjectionSource, Team
from .services import create_league_from_settings

# A compact but realistic 2026 player pool for demo/dev. Extend via provider sync.
SAMPLE_PLAYERS = [
    ("Ja'Marr Chase", "WR", "CIN", 1.2), ("Bijan Robinson", "RB", "ATL", 2.1),
    ("CeeDee Lamb", "WR", "DAL", 3.4), ("Justin Jefferson", "WR", "MIN", 3.8),
    ("Saquon Barkley", "RB", "PHI", 4.5), ("Jahmyr Gibbs", "RB", "DET", 5.2),
    ("Amon-Ra St. Brown", "WR", "DET", 6.1), ("Puka Nacua", "WR", "LAR", 7.0),
    ("Malik Nabers", "WR", "NYG", 8.3), ("De'Von Achane", "RB", "MIA", 9.1),
    ("Christian McCaffrey", "RB", "SF", 10.2), ("Nico Collins", "WR", "HOU", 11.4),
    ("Ashton Jeanty", "RB", "LV", 12.0), ("Brian Thomas Jr.", "WR", "JAX", 12.9),
    ("A.J. Brown", "WR", "PHI", 14.1), ("Jonathan Taylor", "RB", "IND", 15.3),
    ("Derrick Henry", "RB", "BAL", 16.0), ("Drake London", "WR", "ATL", 17.2),
    ("Ladd McConkey", "WR", "LAC", 18.4), ("Josh Jacobs", "RB", "GB", 19.1),
    ("Brock Bowers", "TE", "LV", 20.0), ("Kyren Williams", "RB", "LAR", 21.5),
    ("Garrett Wilson", "WR", "NYJ", 22.3), ("Chase Brown", "RB", "CIN", 23.6),
    ("Trey McBride", "TE", "ARI", 24.1), ("Josh Allen", "QB", "BUF", 25.0),
    ("Lamar Jackson", "QB", "BAL", 27.2), ("Jalen Hurts", "QB", "PHI", 33.0),
    ("Jayden Daniels", "QB", "WAS", 30.5), ("George Kittle", "TE", "SF", 34.2),
    ("Davante Adams", "WR", "LAR", 28.9), ("DK Metcalf", "WR", "PIT", 35.7),
    ("James Cook", "RB", "BUF", 29.4), ("Breece Hall", "RB", "NYJ", 26.8),
    ("Sam LaPorta", "TE", "DET", 38.1), ("Tee Higgins", "WR", "CIN", 31.0),
    ("Mike Evans", "WR", "TB", 32.5), ("DJ Moore", "WR", "CHI", 40.2),
    ("Patrick Mahomes", "QB", "KC", 42.0), ("Kenneth Walker III", "RB", "SEA", 36.9),
    ("Alvin Kamara", "RB", "NO", 39.5), ("Terry McLaurin", "WR", "WAS", 37.3),
    ("Jaylen Waddle", "WR", "MIA", 44.1), ("Rome Odunze", "WR", "CHI", 48.0),
    ("Chuba Hubbard", "RB", "CAR", 45.3), ("David Njoku", "TE", "CLE", 52.1),
    ("Justin Tucker", "K", "BAL", 130.0), ("Harrison Butker", "K", "KC", 135.0),
    ("Brandon Aubrey", "K", "DAL", 128.0),
    ("Eagles DST", "DEF", "PHI", 120.0), ("Ravens DST", "DEF", "BAL", 122.0),
    ("Broncos DST", "DEF", "DEN", 125.0),
    # A few deliberate "hidden gem" candidates (low ADP, high projection).
    ("Jordan Addison", "WR", "MIN", 70.0), ("Tank Bigsby", "RB", "JAX", 95.0),
    ("Jauan Jennings", "WR", "SF", 110.0), ("Cade Otton", "TE", "TB", 140.0),
]

# Baseline season points by position (rough PPR w/ bonus scale) for projections.
POS_BASE = {"QB": 320, "RB": 250, "WR": 240, "TE": 170, "K": 140, "DEF": 130}


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        # Idempotent: only seed the player universe once, independent of whether
        # a league already exists (e.g. created via an import in the same DB).
        if db.query(Player).count() > 0:
            print("Players already seeded. Skipping.")
            return

        existing = (
            db.query(League).filter(League.name == DEFAULT_LEAGUE.leagueName).first()
        )
        league = existing or create_league_from_settings(db, DEFAULT_LEAGUE)
        print(f"Using league '{league.name}' (id={league.id}, {league.num_teams} teams)")

        # Seed 14 teams; mark "Conner" as me at draft slot 7.
        team_names = [f"Team {i}" for i in range(1, 15)]
        team_names[6] = "Conner"
        for i, name in enumerate(team_names, start=1):
            db.add(Team(league_id=league.id, name=name, owner=name,
                        draft_slot=i, is_me=(name == "Conner")))

        source = ProjectionSource(name="GridironIQ Consensus", accuracy_weight=1.0)
        db.add(source)
        db.flush()

        rng = random.Random(7)
        for name, pos, team, adp in SAMPLE_PLAYERS:
            p = Player(name=name, position=pos, team=team, active=True,
                       bye_week=rng.choice([5, 6, 7, 9, 10, 11, 12, 14]))
            db.add(p)
            db.flush()

            base = POS_BASE.get(pos, 150)
            adp_factor = max(0.4, 1.25 - adp / 120.0)
            mean = round(base * adp_factor + rng.uniform(-12, 12), 1)
            std = round(mean * (0.28 if pos in ("RB", "WR") else 0.22), 1)
            db.add(Projection(player_id=p.id, source_id=source.id, season=2026,
                              week=0, mean_points=mean, std_points=std,
                              floor_points=round(mean - 1.04 * std, 1),
                              ceiling_points=round(mean + 1.04 * std, 1),
                              is_ensemble=True))
            rostered = max(0.02, min(0.99, 1.1 - adp / 100.0))
            db.add(ADPEntry(player_id=p.id, source="consensus", format="PPR",
                            adp=adp, rostered_pct=round(rostered, 2)))

        db.commit()
        print(f"Seeded {len(SAMPLE_PLAYERS)} players with projections + ADP.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
