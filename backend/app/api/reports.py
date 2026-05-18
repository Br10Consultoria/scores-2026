import csv
from io import StringIO
from fastapi import APIRouter, Depends, Response
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.database import get_db
from app.models import CollectionRun, Competition, Match, Player, PlayerStats, StandingRow, Team

router = APIRouter(prefix='/reports', tags=['reports'])


def _dt(value):
    return value.isoformat() if value else None


@router.get('/dashboard')
def dashboard(competition_id: int | None = None, _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    team_query = db.query(Team)
    player_query = db.query(Player)
    stats_query = db.query(PlayerStats)
    match_query = db.query(Match)
    standing_query = db.query(StandingRow)
    if competition_id:
        team_query = team_query.filter(Team.primary_competition_id == competition_id)
        player_query = player_query.join(Team, Team.team_id == Player.team_id).filter(Team.primary_competition_id == competition_id)
        stats_query = stats_query.filter(PlayerStats.competition_id == competition_id)
        match_query = match_query.filter(Match.competition_id == competition_id)
        standing_query = standing_query.filter(StandingRow.competition_id == competition_id)

    teams = team_query.count()
    players = player_query.count()
    stats_rows = stats_query.count()
    matches = match_query.count()
    avg_rating = stats_query.with_entities(func.avg(PlayerStats.rating)).scalar()
    latest_run = db.query(CollectionRun).order_by(CollectionRun.started_at.desc()).first()
    latest_update = db.query(func.max(Player.updated_at)).scalar()

    top_goals_rows = (
        db.query(Player.player_id, Player.name, Team.name.label('team'), PlayerStats.goals)
        .join(PlayerStats, PlayerStats.player_id == Player.player_id)
        .outerjoin(Team, Team.team_id == Player.team_id)
        .filter(PlayerStats.goals.isnot(None))
    )
    top_rating_rows = (
        db.query(Player.player_id, Player.name, Team.name.label('team'), PlayerStats.rating)
        .join(PlayerStats, PlayerStats.player_id == Player.player_id)
        .outerjoin(Team, Team.team_id == Player.team_id)
        .filter(PlayerStats.rating.isnot(None))
    )
    top_assists_rows = (
        db.query(Player.player_id, Player.name, Team.name.label('team'), PlayerStats.assists)
        .join(PlayerStats, PlayerStats.player_id == Player.player_id)
        .outerjoin(Team, Team.team_id == Player.team_id)
        .filter(PlayerStats.assists.isnot(None))
    )
    if competition_id:
        top_goals_rows = top_goals_rows.filter(PlayerStats.competition_id == competition_id)
        top_rating_rows = top_rating_rows.filter(PlayerStats.competition_id == competition_id)
        top_assists_rows = top_assists_rows.filter(PlayerStats.competition_id == competition_id)

    positions_rows = player_query.with_entities(Player.position, func.count(Player.player_id)).group_by(Player.position).all()
    standings_rows = (
        standing_query.join(Team, Team.team_id == StandingRow.team_id)
        .with_entities(StandingRow, Team)
        .order_by(StandingRow.competition_id.asc(), StandingRow.position.asc().nullslast())
        .limit(60)
        .all()
    )
    monthly_rows = (
        match_query.with_entities(func.to_char(Match.start_time, 'YYYY-MM').label('month'), func.count(Match.match_id))
        .filter(Match.start_time.isnot(None))
        .group_by('month')
        .order_by('month')
        .all()
    ) if db.bind.dialect.name != 'sqlite' else []
    competitions = db.query(Competition).order_by(Competition.name.asc()).all()

    return {
        'meta': {
            'last_collection_status': latest_run.status if latest_run else None,
            'last_collection_message': latest_run.message if latest_run else None,
            'last_collection_started_at': _dt(latest_run.started_at) if latest_run else None,
            'last_collection_finished_at': _dt(latest_run.finished_at) if latest_run else None,
            'latest_data_update': _dt(latest_update),
            'legend': 'Dados coletados da SofaScore e armazenados localmente. Ratings e estatísticas dependem da disponibilidade pública por jogador/competição.',
        },
        'competitions': [{'id': c.id, 'name': c.name, 'season_id': c.season_id, 'updated_at': _dt(c.updated_at)} for c in competitions],
        'teams': teams,
        'players': players,
        'stats_rows': stats_rows,
        'matches': matches,
        'avg_rating': round(float(avg_rating), 2) if avg_rating else None,
        'top_goals': [{'player_id': pid, 'name': n, 'team': t, 'goals': g or 0} for pid, n, t, g in top_goals_rows.order_by(desc(PlayerStats.goals)).limit(10).all()],
        'top_assists': [{'player_id': pid, 'name': n, 'team': t, 'assists': a or 0} for pid, n, t, a in top_assists_rows.order_by(desc(PlayerStats.assists)).limit(10).all()],
        'top_rating': [{'player_id': pid, 'name': n, 'team': t, 'rating': r or 0} for pid, n, t, r in top_rating_rows.order_by(desc(PlayerStats.rating)).limit(10).all()],
        'positions': [{'position': p or 'Não informado', 'total': c} for p, c in positions_rows],
        'standings_preview': [
            {
                'team_id': team.team_id,
                'team': team.name,
                'logo_url': team.logo_url,
                'competition_id': row.competition_id,
                'position': row.position,
                'matches': row.matches,
                'wins': row.wins,
                'draws': row.draws,
                'losses': row.losses,
                'points': row.points,
                'score_diff': row.score_diff,
                'updated_at': _dt(row.updated_at),
            }
            for row, team in standings_rows
        ],
        'monthly_matches': [{'month': m, 'total': total} for m, total in monthly_rows],
    }


@router.get('/players.csv')
def export_players_csv(_: object = Depends(get_current_user), db: Session = Depends(get_db)):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['player_id', 'name', 'team', 'position', 'nationality', 'age', 'height', 'preferred_foot', 'rating', 'matches', 'goals', 'assists', 'minutes', 'yellow_cards', 'red_cards', 'updated_at'])
    rows = (
        db.query(Player, Team.name.label('team'), PlayerStats)
        .outerjoin(Team, Team.team_id == Player.team_id)
        .outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id)
        .order_by(Player.name.asc())
        .all()
    )
    for player, team, stats in rows:
        writer.writerow([
            player.player_id,
            player.name,
            team or '',
            player.position or '',
            player.nationality or '',
            player.age or '',
            player.height or '',
            player.preferred_foot or '',
            stats.rating if stats else '',
            stats.matches if stats else '',
            stats.goals if stats else '',
            stats.assists if stats else '',
            stats.minutes if stats else '',
            stats.yellow_cards if stats else '',
            stats.red_cards if stats else '',
            _dt(player.updated_at),
        ])
    return Response(
        content=buffer.getvalue(),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=players_report.csv'},
    )
