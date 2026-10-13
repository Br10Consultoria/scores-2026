"""Copas de 2026 e distribuição de vagas da Libertadores/Sul-Americana 2027."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.api.analytics import _dataset
from app.services.api_football_cups import load_cup_statuses
from app.services.league_analytics import overview
from app.services.continental_qualification import allocate_2026

router = APIRouter(prefix='/analytics/continental', tags=['continental'])


def _auto_selection(cups):
    copa = cups.get('copa_brasil') or {}
    lib = cups.get('libertadores') or {}
    sula = cups.get('sulamericana') or {}
    return {
        'copa_winner': copa.get('champion') if copa.get('status') == 'confirmed' else None,
        'copa_runner': copa.get('runner_up') if copa.get('status') == 'confirmed' else None,
        'libertadores_winner': lib.get('champion') if lib.get('status') == 'confirmed' else None,
        'sulamericana_winner': sula.get('champion') if sula.get('status') == 'confirmed' else None,
    }


@router.get('')
def current_continental(
    season: int = Query(2026, ge=2026, le=2026),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data, warning = _dataset(db, season)
    league = overview(data['games'], source=data['source'], updated_at=data['updated_at'])
    cups = load_cup_statuses(season)
    selected = _auto_selection(cups)
    allocation = allocate_2026(league['table'], **selected)
    return {
        'season': season, 'provider_warning': warning,
        'league_source': data['source'], 'league_coverage': league['coverage'],
        'cups': cups, 'auto_selections': selected,
        'allocation': allocation,
        'automatic': all(c.get('status') == 'confirmed' for c in cups.values()) and allocation.get('ready', False),
    }


class ScenarioRequest(BaseModel):
    season: int = Field(2026, ge=2026, le=2026)
    copa_winner: str | None = None
    copa_runner: str | None = None
    libertadores_winner: str | None = None
    sulamericana_winner: str | None = None
    ranking: list[str] | None = None
    use_confirmed_results: bool = True


@router.post('/scenario')
def continental_scenario(
    payload: ScenarioRequest,
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data, warning = _dataset(db, payload.season)
    league = overview(data['games'], source=data['source'], updated_at=data['updated_at'])
    cups = load_cup_statuses(payload.season) if payload.use_confirmed_results else {}
    selected = _auto_selection(cups) if payload.use_confirmed_results else {}
    for field in ('copa_winner', 'copa_runner', 'libertadores_winner', 'sulamericana_winner'):
        supplied = getattr(payload, field)
        if supplied:
            selected[field] = supplied
    try:
        allocation = allocate_2026(league['table'], ranking=payload.ranking, **selected)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        'season': payload.season, 'league_source': data['source'],
        'provider_warning': warning, 'auto_selections': _auto_selection(cups),
        'applied_selections': selected, 'allocation': allocation,
        'source': 'simulacao de usuario' if not payload.use_confirmed_results else 'dados confirmados mais simulacao',
    }
