from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Competition(Base):
    __tablename__ = 'competitions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    season_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    season_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    standings: Mapped[list['StandingRow']] = relationship(back_populates='competition', cascade='all, delete-orphan')
    matches: Mapped[list['Match']] = relationship(back_populates='competition')


class Team(Base):
    __tablename__ = 'teams'

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_competition_id: Mapped[int | None] = mapped_column(ForeignKey('competitions.id'), nullable=True, index=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    players: Mapped[list['Player']] = relationship(back_populates='team')


class Player(Base):
    __tablename__ = 'players'

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.team_id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    jersey_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(30), nullable=True)
    preferred_foot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    market_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    team: Mapped[Team | None] = relationship(back_populates='players')
    stats: Mapped[list['PlayerStats']] = relationship(back_populates='player')


class PlayerStats(Base):
    __tablename__ = 'player_stats'
    __table_args__ = (UniqueConstraint('player_id', 'season_id', 'competition_id', name='uq_player_season_competition'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.player_id'), index=True)
    season_id: Mapped[int] = mapped_column(Integer, index=True)
    competition_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    matches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    big_chances_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_passes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accurate_passes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tackles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interceptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clearances: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clean_sheets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_conceded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    player: Mapped[Player] = relationship(back_populates='stats')


class StandingRow(Base):
    __tablename__ = 'standing_rows'
    __table_args__ = (UniqueConstraint('competition_id', 'season_id', 'team_id', name='uq_standing_comp_season_team'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey('competitions.id'), index=True)
    season_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.team_id'), index=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draws: Mapped[int | None] = mapped_column(Integer, nullable=True)
    losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scores_for: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scores_against: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_diff: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    form: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    competition: Mapped[Competition] = relationship(back_populates='standings')
    team: Mapped[Team] = relationship()


class Match(Base):
    __tablename__ = 'matches'

    match_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    competition_id: Mapped[int | None] = mapped_column(ForeignKey('competitions.id'), nullable=True, index=True)
    season_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    round_info: Mapped[str | None] = mapped_column(String(120), nullable=True)
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.team_id'), nullable=True, index=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.team_id'), nullable=True, index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_timestamp: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    competition: Mapped[Competition | None] = relationship(back_populates='matches')
    home_team: Mapped[Team | None] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team | None] = relationship(foreign_keys=[away_team_id])


class CollectionRun(Base):
    __tablename__ = 'collection_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default='running')
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class TelegramChat(Base):
    __tablename__ = 'telegram_chats'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
