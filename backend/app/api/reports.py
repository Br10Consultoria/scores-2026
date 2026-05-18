import csv
from io import StringIO
from fastapi import APIRouter, Depends, Response
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.database import get_db
from app.models import Player, PlayerStats, Team
from app.schemas import DashboardStats

router = APIRouter(prefix='/reports', tags=['reports'])


@router.get('/dashboard', response_model=DashboardStats)
def dashboard(_: object = Depends(get_current_user), db: Session = Depends(get_db)):
    teams = db.query(func.count(Team.team_id)).scalar() or 0
    players = db.query(func.count(Player.player_id)).scalar() or 0
    stats_rows = db.query(func.count(PlayerStats.id)).scalar() or 0
    avg_rating = db.query(func.avg(PlayerStats.rating)).scalar()

    top_goals_rows = (
        db.query(Player.name, Team.name.label('team'), PlayerStats.goals)
        .join(PlayerStats, PlayerStats.player_id == Player.player_id)
        .outerjoin(Team, Team.team_id == Player.team_id)
        .filter(PlayerStats.goals.isnot(None))
        .order_by(desc(PlayerStats.goals))
        .limit(10)
        .all()
    )
    top_rating_rows = (
        db.query(Player.name, Team.name.label('team'), PlayerStats.rating)
        .join(PlayerStats, PlayerStats.player_id == Player.player_id)
        .outerjoin(Team, Team.team_id == Player.team_id)
        .filter(PlayerStats.rating.isnot(None))
        .order_by(desc(PlayerStats.rating))
        .limit(10)
        .all()
    )
    positions_rows = db.query(Player.position, func.count(Player.player_id)).group_by(Player.position).all()

    return DashboardStats(
        teams=teams,
        players=players,
        stats_rows=stats_rows,
        avg_rating=round(float(avg_rating), 2) if avg_rating else None,
        top_goals=[{'name': n, 'team': t, 'goals': g or 0} for n, t, g in top_goals_rows],
        top_rating=[{'name': n, 'team': t, 'rating': r or 0} for n, t, r in top_rating_rows],
        positions=[{'position': p or 'Não informado', 'total': c} for p, c in positions_rows],
    )


@router.get('/players.csv')
def export_players_csv(_: object = Depends(get_current_user), db: Session = Depends(get_db)):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['player_id', 'name', 'team', 'position', 'nationality', 'age', 'height', 'rating', 'matches', 'goals', 'assists'])
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
            stats.rating if stats else '',
            stats.matches if stats else '',
            stats.goals if stats else '',
            stats.assists if stats else '',
        ])
    return Response(
        content=buffer.getvalue(),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=players_report.csv'},
    )
