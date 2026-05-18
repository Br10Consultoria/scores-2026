from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_superuser
from app.database import get_db
from app.models import Player, Team
from app.schemas import PlayerOut, SyncResponse, TeamOut
from app.services.sofascore import sync_teams_and_players

router = APIRouter(prefix='/sofascore', tags=['sofascore'])


@router.post('/sync', response_model=SyncResponse)
def sync(_: object = Depends(get_superuser), db: Session = Depends(get_db)):
    message = sync_teams_and_players(db)
    return SyncResponse(status='ok', message=message)


@router.get('/teams', response_model=list[TeamOut])
def list_teams(_: object = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Team).order_by(Team.name.asc()).all()


@router.get('/players', response_model=list[PlayerOut])
def list_players(q: str | None = None, position: str | None = None, limit: int = Query(100, le=500), _: object = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Player, Team.name.label('team_name')).outerjoin(Team, Team.team_id == Player.team_id)
    if q:
        query = query.filter(Player.name.ilike(f'%{q}%'))
    if position:
        query = query.filter(Player.position == position)
    rows = query.order_by(Player.name.asc()).limit(limit).all()
    return [PlayerOut(**{**p.__dict__, 'team_name': team_name}) for p, team_name in rows]
