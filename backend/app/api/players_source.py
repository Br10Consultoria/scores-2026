"""Rotas autenticadas para verificar e sincronizar jogadores da Série A."""
from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_superuser
from app.core.config import settings
from app.core.datetime_utils import utc_now_naive
from app.database import get_db, SessionLocal
from app.models import PlayerImportCheckpoint
from app.services.api_football_players import import_players, player_status
from app.services.api_football_cups import ApiFootballClient, SeasonAccessError

router = APIRouter(prefix='/players-source', tags=['players-source'])


@router.get('/status')
def status(_: object = Depends(get_current_user), db: Session = Depends(get_db)):
    result = player_status(db)
    if settings.API_FOOTBALL_KEY:
        try:
            result['subscription_plan'] = ApiFootballClient().ensure_season_access(2026)
            result['season_access'] = True
        except SeasonAccessError as exc:
            result['subscription_plan'] = 'Free'
            result['season_access'] = False
            result['status'] = 'season_restricted'
            result['message'] = str(exc)
        except Exception:
            # Status de assinatura indisponível não implica falta de acesso.
            result['season_access'] = None
    return result


def _worker(pages: int):
    db = SessionLocal()
    try:
        import_players(db, pages=pages)
    finally:
        db.close()


@router.post('/sync')
def sync_players(
    background_tasks: BackgroundTasks,
    pages: int = Query(8, ge=1, le=15),
    _: object = Depends(get_superuser),
    db: Session = Depends(get_db),
):
    if not settings.API_FOOTBALL_KEY:
        raise HTTPException(status_code=503, detail='Configure API_FOOTBALL_KEY no .env para obter estatísticas de jogadores.')
    try:
        ApiFootballClient().ensure_season_access(2026)
    except SeasonAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    state = db.get(PlayerImportCheckpoint, 1)
    if state and state.status == 'running' and state.updated_at and state.updated_at > utc_now_naive() - timedelta(minutes=30):
        raise HTTPException(status_code=409, detail='Já existe importação de jogadores em andamento.')
    if not state:
        state = PlayerImportCheckpoint(id=1, source='api-football', next_page=1)
    state.status = 'running'
    state.updated_at = utc_now_naive()
    state.message = 'Importação em execução. Aguarde e acompanhe o progresso na aba Jogadores.'
    db.add(state)
    db.commit()
    background_tasks.add_task(_worker, pages)
    return player_status(db)
