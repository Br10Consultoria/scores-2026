from __future__ import annotations

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Retorna o horário atual em UTC sem tzinfo para compatibilidade com colunas DateTime existentes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_iso(value: datetime | None) -> str | None:
    """Serializa datetimes persistidos em UTC usando sufixo Z para o frontend converter ao horário local."""
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace('+00:00', 'Z')
