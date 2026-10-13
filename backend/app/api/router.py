from fastapi import APIRouter
from app.api import ai, analytics, auth, continental, reports, sofascore

api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(sofascore.router)
api_router.include_router(reports.router)
api_router.include_router(ai.router)
api_router.include_router(analytics.router)
api_router.include_router(continental.router)
