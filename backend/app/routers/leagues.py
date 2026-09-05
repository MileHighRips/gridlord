"""League endpoints: CRUD, JSON import with auto-mapping, export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..defaults import DEFAULT_LEAGUE
from ..auth import get_optional_user
from ..mapping import normalize_league
from ..models import AuditLog, League, RosterSlot
from ..schemas.league import (
    LeagueImportRequest,
    LeagueImportResponse,
    LeagueOut,
    LeagueSettingsIn,
)
from ..services import (
    create_league_from_settings,
    league_to_settings,
    persist_scoring_rules,
)
from ..rescore import rescore_projections

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


@router.get("/defaults", response_model=LeagueSettingsIn)
def get_default_settings() -> LeagueSettingsIn:
    """Return the canonical default league ('The League')."""
    return DEFAULT_LEAGUE


@router.get("/mine", response_model=LeagueOut)
def my_league(
    db: Session = Depends(get_db), user=Depends(get_optional_user)
) -> LeagueOut:
    """Return the signed-in user's league, creating one from defaults if needed.

    Guests fall back to the shared default league so the app works without login.
    """
    if user:
        lg = db.query(League).filter(League.owner_user_id == user.id).first()
        if not lg:
            lg = create_league_from_settings(db, DEFAULT_LEAGUE)
            lg.owner_user_id = user.id
            db.commit()
    else:
        lg = db.query(League).first()
        if not lg:
            lg = create_league_from_settings(db, DEFAULT_LEAGUE)
            db.commit()
    return get_league(lg.id, db)


@router.get("", response_model=list[LeagueOut])
def list_leagues(db: Session = Depends(get_db)) -> list[LeagueOut]:
    leagues = db.query(League).all()
    return [
        LeagueOut(
            id=lg.id, name=lg.name, provider=lg.provider, season=lg.season,
            num_teams=lg.num_teams, scoring_type=lg.scoring_type,
            settings=league_to_settings(lg),
        )
        for lg in leagues
    ]


@router.get("/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, db: Session = Depends(get_db)) -> LeagueOut:
    lg = db.get(League, league_id)
    if not lg:
        raise HTTPException(404, "League not found")
    return LeagueOut(
        id=lg.id, name=lg.name, provider=lg.provider, season=lg.season,
        num_teams=lg.num_teams, scoring_type=lg.scoring_type,
        settings=league_to_settings(lg),
    )


@router.post("", response_model=LeagueOut, status_code=201)
def create_league(settings: LeagueSettingsIn, db: Session = Depends(get_db)) -> LeagueOut:
    """Manual-entry create from the canonical settings shape."""
    lg = create_league_from_settings(db, settings)
    return get_league(lg.id, db)


@router.put("/{league_id}", response_model=LeagueOut)
def update_league(
    league_id: int, settings: LeagueSettingsIn, db: Session = Depends(get_db)
) -> LeagueOut:
    """Update a league's settings from the form editor (no JSON required).

    Replaces settings, roster slots, and scoring rules in place.
    """
    lg = db.get(League, league_id)
    if not lg:
        raise HTTPException(404, "League not found")

    # Update scalar fields.
    lg.name = settings.leagueName
    lg.num_teams = settings.teams
    lg.season = settings.season
    lg.scoring_type = settings.scoring.type

    s = lg.settings
    if s:
        s.bench_size = settings.roster.bench
        s.ir_slots = settings.roster.ir_slots
        s.waiver_type = settings.waiver.type
        s.faab_budget = settings.waiver.budget
        s.waiver_reset = settings.waiver.reset
        s.waiver_process_day = settings.waiver.process_day
        s.waiver_clear_days = settings.waiver.clear_days
        s.trade_review = settings.trades.review
        s.trade_veto_votes = settings.trades.veto_votes
        s.trade_reject_days = settings.trades.reject_days
        s.trade_deadline = settings.trades.deadline
        s.allow_draft_pick_trades = settings.trades.allow_draft_pick_trades
        s.keeper_count = settings.keepers.count
        s.keeper_cost_rule = settings.keepers.cost_increase
        s.playoff_teams = settings.playoff_teams
        s.playoff_start_week = settings.playoff_start_week
        s.playoff_end_week = settings.playoff_end_week
        s.fractional_points = settings.fractional_points
        s.negative_points = settings.negative_points

    # Replace roster slots.
    for slot in list(lg.roster_slots):
        db.delete(slot)
    db.flush()
    for pos, count in settings.roster.starters.items():
        db.add(RosterSlot(league_id=lg.id, position=pos, count=count))

    # Replace scoring rules.
    for rule in list(lg.scoring_rules):
        db.delete(rule)
    db.flush()
    persist_scoring_rules(db, lg.id, settings.scoring.rules)

    db.commit()

    # Re-score every projection with the new scoring so rankings/points update now.
    db.refresh(lg)
    rescore_projections(db, lg)
    return get_league(lg.id, db)


@router.post("/import", response_model=LeagueImportResponse)
def import_league(
    req: LeagueImportRequest, db: Session = Depends(get_db)
) -> LeagueImportResponse:
    """Import league JSON from any platform; auto-map fields to the model.

    Example:
        POST /api/leagues/import
        {"provider": "sleeper", "leagueSettingsJson": { ... }}
    """
    settings, accuracy, warnings, unmapped = normalize_league(req.leagueSettingsJson)
    lg = create_league_from_settings(db, settings)
    lg.provider = req.provider
    db.add(
        AuditLog(
            action="league_import", league_id=lg.id, sources=req.provider,
            detail_json=f'{{"accuracy": {accuracy}}}',
        )
    )
    db.commit()

    return LeagueImportResponse(
        league=LeagueOut(
            id=lg.id, name=lg.name, provider=lg.provider, season=lg.season,
            num_teams=lg.num_teams, scoring_type=lg.scoring_type, settings=settings,
        ),
        mapping_accuracy=accuracy,
        warnings=warnings,
        unmapped_fields=unmapped,
    )


@router.get("/{league_id}/export", response_model=LeagueSettingsIn)
def export_league(league_id: int, db: Session = Depends(get_db)) -> LeagueSettingsIn:
    lg = db.get(League, league_id)
    if not lg:
        raise HTTPException(404, "League not found")
    return league_to_settings(lg)
