from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, decode_token, generate_totp_secret, get_totp_uri, verify_password, verify_totp
from app.database import get_db
from app.models import User
from app.schemas import Enable2FAResponse, LoginRequest, LoginResponse, Token, UserOut, Verify2FARequest

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/login', response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(or_(User.email == payload.username, User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Credenciais inválidas')
    if not user.is_active:
        raise HTTPException(status_code=403, detail='Usuário inativo')
    if user.totp_enabled:
        temp = create_access_token(str(user.id), timedelta(minutes=5), {'typ': '2fa_pending'})
        return LoginResponse(requires_2fa=True, temp_token=temp)
    token = create_access_token(str(user.id))
    return LoginResponse(requires_2fa=False, access_token=token)


@router.post('/2fa/verify', response_model=Token)
def verify_2fa(payload: Verify2FARequest, db: Session = Depends(get_db)):
    decoded = decode_token(payload.temp_token)
    if not decoded or decoded.get('typ') != '2fa_pending':
        raise HTTPException(status_code=401, detail='Token temporário inválido')
    user = db.get(User, int(decoded['sub']))
    if not user or not user.totp_secret or not verify_totp(user.totp_secret, payload.code):
        raise HTTPException(status_code=401, detail='Código 2FA inválido')
    return Token(access_token=create_access_token(str(user.id)))


@router.post('/2fa/setup', response_model=Enable2FAResponse)
def setup_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret:
        current_user.totp_secret = generate_totp_secret()
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return Enable2FAResponse(secret=current_user.totp_secret, provisioning_uri=get_totp_uri(current_user.username, current_user.totp_secret))


@router.post('/2fa/enable', response_model=UserOut)
def enable_2fa(code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret or not verify_totp(current_user.totp_secret, code):
        raise HTTPException(status_code=400, detail='Código 2FA inválido')
    current_user.totp_enabled = True
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get('/me', response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
