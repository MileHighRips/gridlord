"""Draft endpoints: live recommendations + mock draft simulation."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.draft_engine import DraftContext, draft_intel, recommend, simulate_mock_draft
from ..schemas.draft import (
    DraftRecommendation,
    DraftRecommendResponse,
    DraftStateIn,
)
from ._common import load_ranked_players

router = APIRouter(prefix="/api/draft", tags=["draft"])


@router.post("/recommend", response_model=DraftRecommendResponse)
def recommend_pick(
    state: DraftStateIn, db: Session = Depends(get_db)
) -> DraftRecommendResponse:
    """Live draft assistant.

    Send the current draft state (your slot + every pick made so far). Returns
    the best available for your league scoring, weighted by roster need and
    survival probability to your next pick, with explainability drivers.
    """
    ranked = load_ranked_players(db)
    ranked_by_id = {r.player_id: r for r in ranked}

    drafted_ids = {pk.player_id for pk in state.picks_made}
    available = [r for r in ranked if r.player_id not in drafted_ids]

    my_positions = [
        ranked_by_id[pk.player_id].position
        for pk in state.picks_made
        if pk.slot == state.my_slot and pk.player_id in ranked_by_id
    ]

    ctx = DraftContext(
        num_teams=state.num_teams, rounds=state.rounds,
        my_slot=state.my_slot, draft_type=state.draft_type,
    )

    recs, meta = recommend(
        available=available, ctx=ctx, picks_made=len(state.picks_made),
        my_positions=my_positions, position_filter=state.position_filter,
    )

    # Opponent modeling + positional scarcity forecast.
    picks_with_pos = [
        {"overall": pk.overall_pick, "slot": pk.slot,
         "position": ranked_by_id[pk.player_id].position}
        for pk in state.picks_made
        if pk.player_id in ranked_by_id
    ]
    intel = draft_intel(
        picks_with_pos=picks_with_pos,
        available=available,
        num_teams=state.num_teams,
        rounds=state.rounds,
        my_slot=state.my_slot,
        current_overall=len(state.picks_made) + 1,
        my_next_overall=meta["your_next_overall_pick"] or None,
    )

    def to_schema(rec) -> DraftRecommendation:
        p = rec.player
        return DraftRecommendation(
            player_id=p.player_id, name=p.name, position=p.position, team=p.team,
            proj_points=p.proj_points, vorp=p.vorp,
            need_weighted_value=rec.need_weighted_value, adp=p.adp,
            reach_risk=rec.reach_risk, survival_probability=rec.survival_probability,
            drivers=rec.drivers,
        )

    best_by_pos: dict[str, DraftRecommendation | None] = {}
    for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
        pos_recs = [r for r in recs if r.player.position == pos]
        if pos_recs:
            best_by_pos[pos] = to_schema(pos_recs[0])
        else:
            pos_avail = [a for a in available if a.position == pos]
            if pos_avail:
                top = pos_avail[0]
                best_by_pos[pos] = DraftRecommendation(
                    player_id=top.player_id, name=top.name, position=top.position,
                    team=top.team, proj_points=top.proj_points, vorp=top.vorp,
                    need_weighted_value=top.vorp, adp=top.adp, reach_risk="unknown",
                    survival_probability=0.5, drivers=top.drivers,
                )
            else:
                best_by_pos[pos] = None

    return DraftRecommendResponse(
        on_the_clock=meta["on_the_clock"],
        your_next_overall_pick=meta["your_next_overall_pick"],
        picks_until_next=meta["picks_until_next"],
        current_round=meta["current_round"],
        roster_needs=meta["roster_needs"],
        scarcity_alerts=meta["scarcity_alerts"],
        recommendations=[to_schema(r) for r in recs],
        best_available_by_position=best_by_pos,
        opponent_styles=intel["opponent_styles"],
        predicted_picks=intel["predicted_picks"],
        positional_forecast=intel["positional_forecast"],
    )


@router.post("/mock")
def mock_draft(
    n_sims: int = 1,
    my_slot: int = 7,
    num_teams: int = 14,
    rounds: int = 16,
    db: Session = Depends(get_db),
) -> dict:
    """Run N mock drafts and return your resulting roster + timing.

    Performance target: 1,000 sims < 60s locally.
    """
    board = load_ranked_players(db)
    ctx = DraftContext(num_teams=num_teams, rounds=rounds, my_slot=my_slot)

    start = time.perf_counter()
    last_roster: list[dict] = []
    position_counts: dict[str, int] = {}
    for s in range(n_sims):
        result = simulate_mock_draft(board, ctx, seed=s)
        my_picks = [p for overall, p in result if _slot_of(overall, num_teams) == my_slot]
        if s == n_sims - 1:
            last_roster = [
                {
                    "round": (o - 1) // num_teams + 1, "name": p.name,
                    "position": p.position, "team": p.team,
                }
                for o, p in result if _slot_of(o, num_teams) == my_slot
            ]
        for p in my_picks:
            position_counts[p.position] = position_counts.get(p.position, 0) + 1
    elapsed = round(time.perf_counter() - start, 3)

    return {
        "n_sims": n_sims,
        "elapsed_seconds": elapsed,
        "sample_roster": last_roster,
        "avg_position_distribution": {
            k: round(v / n_sims, 2) for k, v in position_counts.items()
        },
    }


def _slot_of(overall: int, num_teams: int) -> int:
    rnd = (overall - 1) // num_teams + 1
    pos_in_round = (overall - 1) % num_teams + 1
    return pos_in_round if rnd % 2 == 1 else num_teams - pos_in_round + 1
