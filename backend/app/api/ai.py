from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.services.ai_analysis import AIAnalysisError, AIAnalysisService


router = APIRouter(prefix='/ai', tags=['ai'])


class ComparePlayersRequest(BaseModel):
    player_ids: list[int] = Field(..., min_length=2, max_length=8, description='IDs dos jogadores a comparar')


class AIAnalysisResponse(BaseModel):
    scope: str
    entity_id: int | None = None
    title: str
    analysis: str
    context: dict


def _service(db: Session) -> AIAnalysisService:
    return AIAnalysisService(db)


def _handle_error(exc: AIAnalysisError) -> HTTPException:
    message = str(exc)
    if 'não configurada' in message:
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)
    if 'não encontrado' in message or 'insuficientes' in message:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    if 'Informe' in message or 'máximo' in message or 'Compare' in message:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message)


@router.post('/team/{team_id}', response_model=AIAnalysisResponse)
def analyze_team(
    team_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).analyze_team(team_id)
    except AIAnalysisError as exc:
        raise _handle_error(exc) from exc


@router.post('/player/{player_id}', response_model=AIAnalysisResponse)
def analyze_player(
    player_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).analyze_player(player_id)
    except AIAnalysisError as exc:
        raise _handle_error(exc) from exc


@router.post('/match/{match_id}', response_model=AIAnalysisResponse)
def analyze_match(
    match_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).analyze_match(match_id)
    except AIAnalysisError as exc:
        raise _handle_error(exc) from exc


@router.post('/compare', response_model=AIAnalysisResponse)
def compare_players(
    payload: ComparePlayersRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).compare_players(payload.player_ids)
    except AIAnalysisError as exc:
        raise _handle_error(exc) from exc


@router.post('/dashboard-insight', response_model=AIAnalysisResponse)
def dashboard_insight(
    competition_id: Annotated[int | None, Query(description='ID da competição para filtrar o insight')] = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return _service(db).dashboard_insight(competition_id=competition_id)
    except AIAnalysisError as exc:
        raise _handle_error(exc) from exc
