from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_superuser
from app.database import SessionLocal, get_db
from app.models import CollectionRun, Competition, Match, Player, PlayerStats, StandingRow, Team
from app.core.datetime_utils import utc_iso, utc_now_naive
from app.schemas import SyncResponse
from app.services.sofascore import sync_teams_and_players

router = APIRouter(prefix='/sofascore', tags=['sofascore'])


def _dt(value):
    return utc_iso(value)


_MONTH_NAMES_PT = {
    'janeiro': 1,
    'jan': 1,
    'fevereiro': 2,
    'fev': 2,
    'marco': 3,
    'março': 3,
    'mar': 3,
    'abril': 4,
    'abr': 4,
    'maio': 5,
    'mai': 5,
    'junho': 6,
    'jun': 6,
    'julho': 7,
    'jul': 7,
    'agosto': 8,
    'ago': 8,
    'setembro': 9,
    'set': 9,
    'outubro': 10,
    'out': 10,
    'novembro': 11,
    'nov': 11,
    'dezembro': 12,
    'dez': 12,
}


def _month_range(month: str) -> tuple[datetime, datetime] | None:
    value = (month or '').strip().lower()
    if not value:
        return None
    year = 2026
    parsed_month: int | None = None
    try:
        if len(value) >= 7 and value[4] == '-' and value[:4].isdigit() and value[5:7].isdigit():
            year = int(value[:4])
            parsed_month = int(value[5:7])
        elif value.isdigit():
            parsed_month = int(value)
        else:
            parsed_month = _MONTH_NAMES_PT.get(value)
        if not parsed_month or parsed_month < 1 or parsed_month > 12:
            return None
        start = datetime(year, parsed_month, 1)
        end = datetime(year + 1, 1, 1) if parsed_month == 12 else datetime(year, parsed_month + 1, 1)
        return start, end
    except ValueError:
        return None


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


def _stats_for_player(db: Session, player_id: int, competition_id: int | None = None) -> PlayerStats | None:
    if competition_id:
        stats = (
            db.query(PlayerStats)
            .filter(PlayerStats.player_id == player_id, PlayerStats.competition_id == competition_id)
            .order_by(PlayerStats.updated_at.desc())
            .first()
        )
        if stats:
            return stats
    return (
        db.query(PlayerStats)
        .filter(PlayerStats.player_id == player_id)
        .order_by(PlayerStats.rating.desc().nullslast(), PlayerStats.updated_at.desc())
        .first()
    )


def _stats_sort_value(stats: PlayerStats | None, sort: str):
    if not stats:
        return None
    if sort == 'rating':
        return stats.rating
    if sort == 'goals':
        return stats.goals
    if sort == 'assists':
        return stats.assists
    if sort == 'matches':
        return stats.matches
    if sort == 'shots':
        return stats.shots
    if sort == 'shots_on_target':
        return stats.shots_on_target
    if sort == 'key_passes':
        return stats.key_passes
    if sort == 'big_chances_created':
        return stats.big_chances_created
    if sort in _EXTRA_STAT_FIELDS:
        return _raw_number(stats.raw_data, _EXTRA_STAT_FIELDS[sort])
    return None


_EXTRA_STAT_FIELDS = {
    'penalty_goals': ('penaltyGoals', 'penaltyGoal', 'goalsFromPenalty', 'penaltiesScored'),
    'headed_goals': ('headedGoals', 'headerGoals', 'goalsFromHeader'),
    'free_kick_goals': ('freeKickGoals', 'goalsFromFreeKick'),
    'left_foot_goals': ('leftFootGoals', 'goalsFromLeftFoot'),
    'right_foot_goals': ('rightFootGoals', 'goalsFromRightFoot'),
    'big_chances_missed': ('bigChancesMissed',),
    'successful_dribbles': ('successfulDribbles', 'accurateDribbles'),
    'duels_won': ('duelsWon',),
    'aerial_duels_won': ('aerialDuelsWon',),
    'penalties_won': ('penaltiesWon',),
    'penalties_committed': ('penaltiesCommitted',),
    'errors_leading_to_goal': ('errorsLeadToGoal', 'errorLeadToGoal'),
}


def _raw_number(raw: dict | None, aliases: tuple[str, ...]) -> float | int | None:
    if not isinstance(raw, dict):
        return None
    for key in aliases:
        value = raw.get(key)
        if value is None:
            continue
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except Exception:
            continue
    return None


def _extra_stats(raw: dict | None) -> dict:
    extras = {}
    for name, aliases in _EXTRA_STAT_FIELDS.items():
        value = _raw_number(raw, aliases)
        if value is not None:
            extras[name] = value
    return extras


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
        'extra': _extra_stats(stats.raw_data),
        'competition_id': stats.competition_id,
        'season_id': stats.season_id,
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


def _run_sofascore_sync_background() -> None:
    db = SessionLocal()
    try:
        sync_teams_and_players(db)
    finally:
        db.close()


@router.post('/sync', response_model=SyncResponse)
def sync(background_tasks: BackgroundTasks, _: object = Depends(get_superuser), db: Session = Depends(get_db)):
    stale_limit = utc_now_naive() - timedelta(minutes=45)
    stale_runs = db.query(CollectionRun).filter(CollectionRun.status == 'running', CollectionRun.started_at < stale_limit).all()
    for stale in stale_runs:
        stale.status = 'error'
        stale.finished_at = utc_now_naive()
        stale.message = (stale.message or 'Sincronização sem conclusão registrada.') + ' Marcada como órfã automaticamente após 45 minutos sem finalizar.'
        db.add(stale)
    if stale_runs:
        db.commit()

    running = db.query(CollectionRun).filter(CollectionRun.status == 'running').first()
    if running:
        return SyncResponse(status='running', message='Já existe uma sincronização em andamento. Acompanhe a conclusão pelos logs ou pelo status no dashboard.')
    background_tasks.add_task(_run_sofascore_sync_background)
    return SyncResponse(status='accepted', message='Sincronização iniciada em segundo plano. Primeiro serão gravadas competições, tabelas e jogos; depois serão coletados elencos e estatísticas.')


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
    sort: str = Query('name', pattern='^(name|rating|goals|assists|matches|age|shots|shots_on_target|key_passes|big_chances_created|penalty_goals|headed_goals|free_kick_goals|left_foot_goals|right_foot_goals)$'),
    limit: int = Query(100, le=1000),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Player, Team.name.label('team_name')).outerjoin(Team, Team.team_id == Player.team_id)
    if q:
        query = query.filter(Player.name.ilike(f'%{q}%'))
    if position:
        query = query.filter(Player.position == position)
    if team_id:
        query = query.filter(Player.team_id == team_id)
    if competition_id:
        team_ids = list(_team_ids_for_competition(db, competition_id)) or [-1]
        query = query.filter(Team.team_id.in_(team_ids))

    rows = query.all()
    enriched = []
    for player, team_name in rows:
        stats = _stats_for_player(db, player.player_id, competition_id)
        if min_rating and (not stats or stats.rating is None or stats.rating < min_rating):
            continue
        enriched.append((player, team_name, stats))

    if sort in {'rating', 'goals', 'assists', 'matches', 'shots', 'shots_on_target', 'key_passes', 'big_chances_created', 'penalty_goals', 'headed_goals', 'free_kick_goals', 'left_foot_goals', 'right_foot_goals'}:
        enriched.sort(key=lambda row: (_stats_sort_value(row[2], sort) is None, -float(_stats_sort_value(row[2], sort) or 0), row[0].name.lower()))
    elif sort == 'age':
        enriched.sort(key=lambda row: (row[0].age is None, row[0].age or 999, row[0].name.lower()))
    else:
        enriched.sort(key=lambda row: row[0].name.lower())

    return [_player_dict(player, team_name, stats) for player, team_name, stats in enriched[:limit]]


@router.get('/players/{player_id}')
def player_detail(player_id: int, competition_id: int | None = None, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if not player:
        return {'detail': 'Jogador não encontrado'}
    stats = _stats_for_player(db, player_id, competition_id)
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
        month_range = _month_range(month)
        if month_range:
            start, end = month_range
            query = query.filter(and_(Match.start_time >= start, Match.start_time < end))
    return [_match_dict(match) for match in query.order_by(Match.start_time.desc().nullslast()).limit(limit).all()]


@router.get('/compare/players')
def compare_players(ids: str, competition_id: int | None = None, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    player_ids = [int(x) for x in ids.split(',') if x.strip().isdigit()]
    rows = db.query(Player, Team.name.label('team_name')).outerjoin(Team, Team.team_id == Player.team_id).filter(Player.player_id.in_(player_ids)).all()
    return [_player_dict(player, team_name, _stats_for_player(db, player.player_id, competition_id)) for player, team_name in rows]


def _team_comparison_stats(db: Session, team: Team, competition_id: int | None = None) -> dict:
    rows = (
        db.query(Player, PlayerStats)
        .join(PlayerStats, PlayerStats.player_id == Player.player_id)
        .filter(Player.team_id == team.team_id)
    )
    if competition_id:
        rows = rows.filter(PlayerStats.competition_id == competition_id)
    player_stats = rows.all()

    def total(attr: str) -> int:
        return int(sum((getattr(stats, attr) or 0) for _, stats in player_stats))

    ratings = [float(stats.rating) for _, stats in player_stats if stats.rating is not None]
    extras: dict[str, float | int] = {}
    for _, stats in player_stats:
        for name, aliases in _EXTRA_STAT_FIELDS.items():
            value = _raw_number(stats.raw_data, aliases)
            if value is not None:
                extras[name] = extras.get(name, 0) + value
    extras = {key: int(value) if float(value).is_integer() else value for key, value in extras.items()}

    top_players = sorted(
        [
            _player_dict(player, team.name, stats)
            for player, stats in player_stats
        ],
        key=lambda p: (p.get('stats') or {}).get('rating') or 0,
        reverse=True,
    )[:8]

    return {
        'team': _team_dict(team),
        'players_with_stats': len(player_stats),
        'avg_rating': round(sum(ratings) / len(ratings), 2) if ratings else None,
        'matches_sum': total('matches'),
        'goals': total('goals'),
        'assists': total('assists'),
        'shots': total('shots'),
        'shots_on_target': total('shots_on_target'),
        'big_chances_created': total('big_chances_created'),
        'key_passes': total('key_passes'),
        'accurate_passes': total('accurate_passes'),
        'tackles': total('tackles'),
        'interceptions': total('interceptions'),
        'clearances': total('clearances'),
        'saves': total('saves'),
        'clean_sheets': total('clean_sheets'),
        'goals_conceded': total('goals_conceded'),
        'yellow_cards': total('yellow_cards'),
        'red_cards': total('red_cards'),
        'extra': extras,
        'top_players': top_players,
    }


@router.get('/compare/teams')
def compare_teams(ids: str, competition_id: int | None = None, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    team_ids = [int(x) for x in ids.split(',') if x.strip().isdigit()]
    if not team_ids:
        return []
    teams = db.query(Team).filter(Team.team_id.in_(team_ids[:8])).order_by(Team.name.asc()).all()
    return [_team_comparison_stats(db, team, competition_id) for team in teams]
