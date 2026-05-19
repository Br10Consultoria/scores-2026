from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, or_, text
from app.api.router import api_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import User


def _column_type_for_dialect(column_type: str) -> str:
    if engine.dialect.name == 'postgresql' and column_type == 'JSON':
        return 'JSONB'
    if engine.dialect.name == 'postgresql' and column_type == 'DATETIME':
        return 'TIMESTAMP'
    return column_type


def _ensure_column(table: str, column: str, column_type: str) -> None:
    inspector = inspect(engine)
    existing = {col['name'] for col in inspector.get_columns(table)} if inspector.has_table(table) else set()
    if column in existing:
        return
    ddl_type = _column_type_for_dialect(column_type)
    with engine.begin() as connection:
        connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))


def _ensure_player_stats_unique_constraint() -> None:
    """Atualiza a unicidade de estatísticas para permitir dados separados por competição.

    Versões antigas tinham uma chave única apenas em `(player_id, season_id)`, o que fazia
    Série A, Série B, Copa do Brasil e Copa do Mundo disputarem o mesmo registro do atleta.
    """
    if engine.dialect.name != 'postgresql':
        return
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE player_stats DROP CONSTRAINT IF EXISTS uq_player_season'))
        exists = connection.execute(
            text("""
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_player_season_competition'
                  AND conrelid = 'player_stats'::regclass
            """)
        ).first()
        if not exists:
            connection.execute(
                text('ALTER TABLE player_stats ADD CONSTRAINT uq_player_season_competition UNIQUE (player_id, season_id, competition_id)')
            )


def run_light_migrations() -> None:
    """Aplica migrações simples para instalações que já possuem banco criado.

    O projeto ainda não usa Alembic para facilitar operação em servidor próprio. Esta rotina
    adiciona colunas novas de forma idempotente e deixa `create_all` criar as tabelas novas.
    """
    Base.metadata.create_all(bind=engine)
    additions = {
        'teams': [
            ('slug', 'VARCHAR(255)'),
            ('short_name', 'VARCHAR(120)'),
            ('country', 'VARCHAR(120)'),
            ('logo_url', 'VARCHAR(500)'),
            ('primary_competition_id', 'INTEGER'),
            ('raw_data', 'JSON'),
            ('updated_at', 'DATETIME'),
        ],
        'players': [
            ('slug', 'VARCHAR(255)'),
            ('jersey_number', 'VARCHAR(20)'),
            ('date_of_birth', 'VARCHAR(30)'),
            ('preferred_foot', 'VARCHAR(40)'),
            ('market_value', 'INTEGER'),
            ('raw_data', 'JSON'),
            ('updated_at', 'DATETIME'),
        ],
        'player_stats': [
            ('competition_id', 'INTEGER'),
            ('starts', 'INTEGER'),
            ('minutes', 'INTEGER'),
            ('shots', 'INTEGER'),
            ('shots_on_target', 'INTEGER'),
            ('big_chances_created', 'INTEGER'),
            ('key_passes', 'INTEGER'),
            ('accurate_passes', 'INTEGER'),
            ('tackles', 'INTEGER'),
            ('interceptions', 'INTEGER'),
            ('clearances', 'INTEGER'),
            ('saves', 'INTEGER'),
            ('clean_sheets', 'INTEGER'),
            ('goals_conceded', 'INTEGER'),
            ('yellow_cards', 'INTEGER'),
            ('red_cards', 'INTEGER'),
            ('raw_data', 'JSON'),
            ('updated_at', 'DATETIME'),
        ],
    }
    for table, columns in additions.items():
        for column, column_type in columns:
            _ensure_column(table, column, column_type)
    _ensure_player_stats_unique_constraint()
    Base.metadata.create_all(bind=engine)


def create_initial_data() -> None:
    run_light_migrations()
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


app = FastAPI(title=settings.PROJECT_NAME, version='1.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex_value,
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
