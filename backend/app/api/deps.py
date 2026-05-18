from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.database import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if not payload or payload.get('typ') == '2fa_pending':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido ou pendente de 2FA')
    user_id = payload.get('sub')
    user = db.get(User, int(user_id)) if user_id and str(user_id).isdigit() else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuário inválido')
    return user


def get_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail='Permissão insuficiente')
    return current_user
