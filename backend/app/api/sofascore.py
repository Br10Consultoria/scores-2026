from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_superuser
from app.database import get_db
from app.models import Competition, Match, Player, PlayerStats, StandingRow, Team
from app.core.datetime_utils import utc_iso
from app.schemas import SyncResponse
from app.services.sofascore import sync_teams_and_players

router = APIRouter(prefix='/sofascore', tags=['sofascore'])


def _dt(value):
    return utc_iso(value)


def _team_dict(team: Team | None):
    if not team:
        return None
    return {
        'team_id': team.team_id,
        'name': team.name,
        'short_name': team.short_name,
        'slug': team.slug,
        'country': team.country,
        'logo_url': team.logo_url,
        'primary_competition_id': team.primary_competition_id,
        'updated_at': _dt(team.updated_at),
    }


def _player_dict(player: Player, team_name: str | None = None, stats: PlayerStats | None = None):
    data = {
        'player_id': player.player_id,
        'name': player.name,
        'slug': player.slug,
        'team_id': player.team_id,
        'team_name': team_name or (player.team.name if player.team else None),
        'position': player.position,
        'jersey_number': player.jersey_number,
        'nationality': player.nationality,
        'height': player.height,
        'age': player.age,
        'date_of_birth': player.date_of_birth,
        'preferred_foot': player.preferred_foot,
        'market_value': player.market_value,
        'updated_at': _dt(player.updated_at),
    }
    if stats:
        data['stats'] = _stats_dict(stats)
    return data


def _team_ids_for_competition(db: Session, competition_id: int | None = None) -> set[int]:
    standing_query = db.query(StandingRow.team_id)
    match_query = db.query(Match.home_team_id, Match.away_team_id)
    if competition_id:
        standing_query = standing_query.filter(StandingRow.competition_id == competition_id)
        match_query = match_query.filter(Match.competition_id == competition_id)

    team_ids = {team_id for (team_id,) in standing_query.distinct().all() if team_id is not None}
    for home_team_id, away_team_id in match_query.all():
        if home_team_id is not None:
            team_ids.add(home_team_id)
        if away_team_id is not None:
            team_ids.add(away_team_id)
    return team_ids


def _stats_dict(stats: PlayerStats | None):
    if not stats:
        return None
    return {
        'rating': stats.rating,
        'matches': stats.matches,
        'starts': stats.starts,
        'minutes': stats.minutes,
        'goals': stats.goals,
        'assists': stats.assists,
        'shots': stats.shots,
        'shots_on_target': stats.shots_on_target,
        'big_chances_created': stats.big_chances_created,
        'key_passes': stats.key_passes,
        'accurate_passes': stats.accurate_passes,
        'tackles': stats.tackles,
        'interceptions': stats.interceptions,
        'clearances': stats.clearances,
        'saves': stats.saves,
        'clean_sheets': stats.clean_sheets,
        'goals_conceded': stats.goals_conceded,
        'yellow_cards': stats.yellow_cards,
        'red_cards': stats.red_cards,
        'updated_at': _dt(stats.updated_at),
    }


def _match_dict(match: Match):
    return {
        'match_id': match.match_id,
        'competition_id': match.competition_id,
        'competition_name': match.competition.name if match.competition else None,
        'season_id': match.season_id,
        'round_info': match.round_info,
        'home_team': _team_dict(match.home_team),
        'away_team': _team_dict(match.away_team),
        'home_score': match.home_score,
        'away_score': match.away_score,
        'status': match.status,
        'start_timestamp': match.start_timestamp,
        'start_time': _dt(match.start_time),
        'venue': match.venue,
        'updated_at': _dt(match.updated_at),
    }


@router.post('/sync', response_model=SyncResponse)
def sync(_: object = Depends(get_superuser), db: Session = Depends(get_db)):
    message = sync_teams_and_players(db)
    return SyncResponse(status='ok', message=message)


@router.get('/competitions')
def list_competitions(_: object = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'country': c.country,
            'season_id': c.season_id,
            'season_name': c.season_name,
            'updated_at': _dt(c.updated_at),
        }
        for c in db.query(Competition).order_by(Competition.name.asc()).all()
    ]


@router.get('/teams')
def list_teams(
    competition_id: int | None = None,
    q: str | None = None,
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Team)
    if competition_id:
        team_ids = list(_team_ids_for_competition(db, competition_id)) or [-1]
        query = query.filter(Team.team_id.in_(team_ids))
    if q:
        query = query.filter(Team.name.ilike(f'%{q}%'))
    teams = query.order_by(Team.name.asc()).all()
    return [_team_dict(team) for team in teams]


@router.get('/teams/{team_id}')
def team_detail(team_id: int, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        return {'detail': 'Time não encontrado'}
    standings = (
        db.query(StandingRow, Competition.name.label('competition_name'))
        .join(Competition, Competition.id == StandingRow.competition_id)
        .filter(StandingRow.team_id == team_id)
        .order_by(StandingRow.updated_at.desc())
        .all()
    )
    players = db.query(Player).filter(Player.team_id == team_id).order_by(Player.name.asc()).all()
    matches = (
        db.query(Match)
        .filter(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
        .order_by(Match.start_time.desc().nullslast())
        .limit(30)
        .all()
    )
    avg_rating = (
        db.query(func.avg(PlayerStats.rating))
        .join(Player, Player.player_id == PlayerStats.player_id)
        .filter(Player.team_id == team_id, PlayerStats.rating.isnot(None))
        .scalar()
    )
    return {
        'team': _team_dict(team),
        'avg_rating': round(float(avg_rating), 2) if avg_rating else None,
        'standings': [
            {
                'competition_name': competition_name,
                'position': row.position,
                'matches': row.matches,
                'wins': row.wins,
                'draws': row.draws,
                'losses': row.losses,
                'scores_for': row.scores_for,
                'scores_against': row.scores_against,
                'score_diff': row.score_diff,
                'points': row.points,
                'form': row.form,
                'updated_at': _dt(row.updated_at),
            }
            for row, competition_name in standings
        ],
        'players': [_player_dict(p) for p in players],
        'matches': [_match_dict(m) for m in matches],
    }


@router.get('/players')
def list_players(
    q: str | None = None,
    position: str | None = None,
    team_id: int | None = None,
    competition_id: int | None = None,
    min_rating: float | None = None,
    sort: str = Query('name', pattern='^(name|rating|goals|assists|matches|age)$'),
    limit: int = Query(100, le=1000),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Player, Team.name.label('team_name'), PlayerStats).outerjoin(Team, Team.team_id == Player.team_id).outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id)
    if q:
        query = query.filter(Player.name.ilike(f'%{q}%'))
    if position:
        query = query.filter(Player.position == position)
    if team_id:
        query = query.filter(Player.team_id == team_id)
    if competition_id:
        team_ids = list(_team_ids_for_competition(db, competition_id)) or [-1]
        query = query.filter(or_(PlayerStats.competition_id == competition_id, Team.team_id.in_(team_ids)))
    if min_rating:
        query = query.filter(PlayerStats.rating >= min_rating)
    if sort == 'rating':
        query = query.order_by(PlayerStats.rating.desc().nullslast(), Player.name.asc())
    elif sort == 'goals':
        query = query.order_by(PlayerStats.goals.desc().nullslast(), Player.name.asc())
    elif sort == 'assists':
        query = query.order_by(PlayerStats.assists.desc().nullslast(), Player.name.asc())
    elif sort == 'matches':
        query = query.order_by(PlayerStats.matches.desc().nullslast(), Player.name.asc())
    elif sort == 'age':
        query = query.order_by(Player.age.asc().nullslast(), Player.name.asc())
    else:
        query = query.order_by(Player.name.asc())
    rows = query.limit(limit).all()
    return [_player_dict(player, team_name, stats) for player, team_name, stats in rows]


@router.get('/players/{player_id}')
def player_detail(player_id: int, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if not player:
        return {'detail': 'Jogador não encontrado'}
    stats = db.query(PlayerStats).filter(PlayerStats.player_id == player_id).order_by(PlayerStats.updated_at.desc()).first()
    return {
        'player': _player_dict(player, player.team.name if player.team else None, stats),
        'team': _team_dict(player.team),
        'raw_data': player.raw_data,
        'raw_stats': stats.raw_data if stats else None,
    }


@router.get('/standings')
def standings(competition_id: int | None = None, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(StandingRow, Team, Competition).join(Team, Team.team_id == StandingRow.team_id).join(Competition, Competition.id == StandingRow.competition_id)
    if competition_id:
        query = query.filter(StandingRow.competition_id == competition_id)
    rows = query.order_by(Competition.name.asc(), StandingRow.position.asc().nullslast()).all()
    return [
        {
            'competition_id': comp.id,
            'competition_name': comp.name,
            'season_id': row.season_id,
            'team': _team_dict(team),
            'position': row.position,
            'matches': row.matches,
            'wins': row.wins,
            'draws': row.draws,
            'losses': row.losses,
            'scores_for': row.scores_for,
            'scores_against': row.scores_against,
            'score_diff': row.score_diff,
            'points': row.points,
            'form': row.form,
            'updated_at': _dt(row.updated_at),
        }
        for row, team, comp in rows
    ]


@router.get('/matches')
def matches(
    competition_id: int | None = None,
    team_id: int | None = None,
    month: str | None = Query(None, description='Formato YYYY-MM'),
    status: str | None = None,
    limit: int = Query(100, le=500),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Match)
    if competition_id:
        query = query.filter(Match.competition_id == competition_id)
    if team_id:
        query = query.filter(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
    if status:
        query = query.filter(Match.status.ilike(f'%{status}%'))
    if month:
        start = datetime.strptime(month + '-01', '%Y-%m-%d')
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1)
        else:
            end = datetime(start.year, start.month + 1, 1)
        query = query.filter(and_(Match.start_time >= start, Match.start_time < end))
    return [_match_dict(match) for match in query.order_by(Match.start_time.desc().nullslast()).limit(limit).all()]


@router.get('/compare/players')
def compare_players(ids: str, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    player_ids = [int(x) for x in ids.split(',') if x.strip().isdigit()]
    rows = db.query(Player, Team.name.label('team_name'), PlayerStats).outerjoin(Team, Team.team_id == Player.team_id).outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id).filter(Player.player_id.in_(player_ids)).all()
    return [_player_dict(player, team_name, stats) for player, team_name, stats in rows]
