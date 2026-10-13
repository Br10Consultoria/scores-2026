"""Análises e simulação da Série A baseadas em resultados reais.

Fonte preferencial: football-data.org (com token); fallback: partidas já
persistidas pela coleta SofaScore. Não mistura IDs de fornecedores.
"""
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.config import settings
from app.database import get_db
from app.models import Match
from app.services.football_data import get_brazil_serie_a
from app.services.league_analytics import overview, simulate
from app.services.league_validation import validate_calendar

router = APIRouter(prefix='/analytics', tags=['analytics'])


def _from_database(db: Session, season: int):
    if season != 2026:
        raise RuntimeError('Fallback SofaScore está configurado apenas para 2026')
    matches = db.query(Match).filter(
        Match.competition_id == settings.SOFASCORE_SERIE_A_TOURNAMENT_ID,
        Match.season_id == settings.SOFASCORE_SERIE_A_SEASON_ID,
    ).all()
    games = []
    for match in matches:
        if not match.home_team_id or not match.away_team_id:
            continue
        number = re.search(r'\d+', str(match.round_info or ''))
        round_number = int(number.group(0)) if number else None
        games.append({
            'id': f'sofa-{match.match_id}',
            'round': round_number,
            'date': match.start_time.isoformat() + 'Z' if match.start_time else None,
            'home_id': f'sofa-{match.home_team_id}',
            'away_id': f'sofa-{match.away_team_id}',
            'home_name': match.home_team.name if match.home_team else str(match.home_team_id),
            'away_name': match.away_team.name if match.away_team else str(match.away_team_id),
            'home_goals': match.home_score,
            'away_goals': match.away_score,
            'status': match.status,
        })
    return {'games': games, 'source': 'SofaScore (banco local)', 'updated_at': None}


def _dataset(db: Session, season: int):
    warning = None
    if settings.FOOTBALL_DATA_API_KEY:
        try:
            data = get_brazil_serie_a(season)
            if data['games']:
                return data, warning
            warning = 'football-data.org retornou lista vazia; usando banco local.'
        except Exception as exc:
            warning = f'Fonte football-data.org indisponível: {exc}. Usando dados locais.'
    else:
        warning = 'Configure FOOTBALL_DATA_API_KEY para importar automaticamente o calendário completo.'
    return _from_database(db, season), warning


@router.get('/brasileirao')
def brasileirao(
    season: int = Query(2026, ge=2020, le=2035),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data, warning = _dataset(db, season)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = overview(data['games'], source=data['source'], updated_at=data['updated_at'], season=season)
    response['provider_warning'] = warning
    response['validation'] = validate_calendar(data['games'], data['source'], data['updated_at'])
    response['simulation_available'] = response['simulation_available'] and response['validation']['ok']
    if not response['validation']['ok']:
        response['notice'] = response['validation']['message']
    return response


@router.get('/brasileirao/validation')
def validate_brasileirao(
    season: int = Query(2026, ge=2020, le=2035),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data, warning = _dataset(db, season)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result = validate_calendar(data['games'], data['source'], data['updated_at'])
    result['provider_warning'] = warning
    return result


class SimulationRequest(BaseModel):
    season: int = Field(2026, ge=2020, le=2035)
    runs: int = Field(2000, ge=100, le=10000)
    seed: int = 2026
    libertadores_places: int = Field(6, ge=4, le=12)
    sula_places: int = Field(6, ge=0, le=10)
    overrides: dict[str, str] = Field(default_factory=dict)


@router.post('/brasileirao/simulate')
def simulate_brasileirao(
    payload: SimulationRequest,
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data, warning = _dataset(db, payload.season)
        validation = validate_calendar(data['games'], data['source'], data['updated_at'])
        if not validation['ok']:
            raise ValueError('Calendário inválido ou incompleto. Consulte /api/v1/analytics/brasileirao/validation para detalhes.')
        result = simulate(
            data['games'], overrides=payload.overrides,
            libertadores_places=payload.libertadores_places,
            sula_places=payload.sula_places,
            runs=payload.runs, seed=payload.seed,
        )
        result['source'] = data['source']
        result['updated_at'] = data['updated_at']
        result['provider_warning'] = warning
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
