from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from app.api.router import api_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import User


def create_initial_data() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(or_(User.email == settings.FIRST_SUPERUSER_EMAIL, User.username == settings.FIRST_SUPERUSER_USERNAME)).first()
        if not existing:
            user = User(
                email=settings.FIRST_SUPERUSER_EMAIL,
                username=settings.FIRST_SUPERUSER_USERNAME,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


app = FastAPI(title=settings.PROJECT_NAME, version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def on_startup():
    create_initial_data()


@app.get('/health')
def health():
    return {'status': 'ok', 'project': settings.PROJECT_NAME}


app.include_router(api_router)
