from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    requires_2fa: bool
    access_token: str | None = None
    temp_token: str | None = None
    token_type: str = 'bearer'


class Verify2FARequest(BaseModel):
    temp_token: str
    code: str = Field(min_length=6, max_length=8)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    is_active: bool
    is_superuser: bool
    totp_enabled: bool

    class Config:
        from_attributes = True


class Enable2FAResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TeamOut(BaseModel):
    team_id: int
    name: str
    slug: str | None = None
    country: str | None = None
    updated_at: datetime

    class Config:
        from_attributes = True


class PlayerOut(BaseModel):
    player_id: int
    team_id: int | None = None
    name: str
    position: str | None = None
    nationality: str | None = None
    height: int | None = None
    age: int | None = None
    team_name: str | None = None


class SyncResponse(BaseModel):
    status: str
    message: str


class DashboardStats(BaseModel):
    teams: int
    players: int
    stats_rows: int
    avg_rating: float | None
    top_goals: list[dict]
    top_rating: list[dict]
    positions: list[dict]
