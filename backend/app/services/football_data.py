"""Fonte opcional licenciada para partidas da Série A via football-data.org v4.

O navegador nunca recebe a chave. Redis evita consultas repetidas e respeita cotas.
"""
from datetime import datetime, timezone
import json
import logging
import requests
import redis
from app.core.config import settings

log = logging.getLogger(__name__)
COMPETITION_CODE = 'BSA'


def get_brazil_serie_a(season: int = 2026):
    if not settings.FOOTBALL_DATA_API_KEY:
        raise RuntimeError('FOOTBALL_DATA_API_KEY não configurada')
    if season < 2020 or season > 2035:
        raise ValueError('Temporada fora do intervalo permitido')

    cache = None
    cache_key = f'football-data:bsa:season:{season}:v1'
    try:
        cache = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
        content = cache.get(cache_key)
        if content:
            return json.loads(content)
    except Exception as exc:
        log.warning('Redis indisponível para cache de partidas: %s', exc)
        cache = None

    response = requests.get(
        f'https://api.football-data.org/v4/competitions/{COMPETITION_CODE}/matches',
        headers={'X-Auth-Token': settings.FOOTBALL_DATA_API_KEY},
        params={'season': season},
        timeout=20,
    )
    if response.status_code in (401, 403):
        raise RuntimeError('Chave football-data.org inválida ou competição não incluída no plano')
    if response.status_code == 429:
        raise RuntimeError('Limite de requisições da football-data.org excedido. Tente novamente depois.')
    response.raise_for_status()
    payload = response.json()
    matches = payload.get('matches')
    if not isinstance(matches, list):
        raise RuntimeError('Resposta de partidas inválida na football-data.org')

    games = []
    for match in matches:
        home = match.get('homeTeam') or {}
        away = match.get('awayTeam') or {}
        match_id = match.get('id')
        if not match_id or not home.get('id') or not away.get('id'):
            continue
        full_time = (match.get('score') or {}).get('fullTime') or {}
        status = match.get('status') or ''
        date = match.get('utcDate')
        try:
            round_number = int(match['matchday']) if match.get('matchday') is not None else None
        except (TypeError, ValueError):
            round_number = None
        games.append({
            'id': f'fd-{match_id}',
            'round': round_number,
            'date': date,
            'home_id': f'fd-{home["id"]}',
            'away_id': f'fd-{away["id"]}',
            'home_name': home.get('shortName') or home.get('name'),
            'away_name': away.get('shortName') or away.get('name'),
            'home_goals': full_time.get('home'),
            'away_goals': full_time.get('away'),
            'status': status,
        })
    result = {
        'games': games, 'source': 'football-data.org',
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    if cache:
        try:
            cache.set(cache_key, json.dumps(result), ex=max(300, settings.FOOTBALL_DATA_CACHE_SECONDS))
        except Exception as exc:
            log.warning('Falha ao armazenar cache: %s', exc)
    return result
