"""Integração opcional API-Football (API-Sports), sem expor token ao navegador.

Busca IDs das competições na própria API, usa cache Redis e jamais inventa
vencedores quando as finais ainda não foram concluídas.
"""
from datetime import datetime, timezone
import json
import hashlib
import logging
import re
import unicodedata
from typing import Any
import requests
import redis
from app.core.config import settings

LOG = logging.getLogger(__name__)
API_URL = 'https://v3.football.api-sports.io'
COMPETITIONS = {
    'copa_brasil': {'name': 'Copa do Brasil', 'search': 'Copa do Brasil', 'region': 'Brazil'},
    'libertadores': {'name': 'Copa Libertadores', 'search': 'Libertadores', 'region': 'World'},
    'sulamericana': {'name': 'Copa Sul-Americana', 'search': 'Sudamericana', 'region': 'World'},
}
FINISHED = {'FT', 'AET', 'PEN'}
UNAVAILABLE = {'PST', 'CANC', 'ABD', 'SUSP', 'AWD', 'WO'}


class SeasonAccessError(RuntimeError):
    """O plano não permite consultar a temporada solicitada."""


SEASON_RESTRICTION_MESSAGE = (
    'Seu plano Free da API-Football não permite consultar a temporada 2026. '
    'O provedor informou acesso apenas às temporadas de 2022 a 2024. '
    'É necessário um plano com cobertura de 2026 para coletar esses dados.'
)


def check_season_access(status: dict, year: int) -> str:
    """Verificação prévia com /status. Não usa chave/token em logs."""
    subscription = (status.get('response') or {}).get('subscription') or {}
    plan = str(subscription.get('plan') or 'não identificado')
    if plan.casefold() == 'free' and year == 2026:
        raise SeasonAccessError(SEASON_RESTRICTION_MESSAGE)
    return plan



def _norm(value: str | None) -> str:
    value = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in value if not unicodedata.combining(c)).lower()).strip()


class ApiFootballClient:
    def __init__(self):
        if not settings.API_FOOTBALL_KEY:
            raise RuntimeError('API_FOOTBALL_KEY não configurada')
        self.cache = None
        try:
            self.cache = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
            self.cache.ping()
        except Exception as exc:
            LOG.warning('Cache API-Football desativado: %s', exc)

    def ensure_season_access(self, year: int) -> str:
        # O status é cacheado por 15 minutos; evita consultas proibidas às 3 copas.
        status = self.get('/status', {}, ttl=900)
        return check_season_access(status, year)

    def get(self, endpoint: str, params: dict[str, Any], ttl: int) -> dict:
        # Segrega cache por credencial sem armazenar a chave em texto claro.
        account = hashlib.sha256(settings.API_FOOTBALL_KEY.encode('utf-8')).hexdigest()[:16]
        key = 'api-football:v2:' + account + ':' + endpoint + ':' + json.dumps(params, sort_keys=True)
        if self.cache:
            try:
                cached = self.cache.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass
        response = requests.get(
            API_URL + endpoint,
            params=params,
            headers={'x-apisports-key': settings.API_FOOTBALL_KEY},
            timeout=20,
        )
        if response.status_code in (401, 403):
            raise RuntimeError('API-Football: chave inválida ou temporada fora da cobertura do plano')
        if response.status_code == 429:
            raise RuntimeError('API-Football: limite de requisições esgotado')
        response.raise_for_status()
        body = response.json()
        if body.get('errors'):
            errors = body.get('errors')
            plan_error = str(errors.get('plan') or '') if isinstance(errors, dict) else ''
            if 'do not have access to this season' in plan_error.casefold():
                raise SeasonAccessError(SEASON_RESTRICTION_MESSAGE)
            # Não retornar conteúdo arbitrário do provedor: evita vazamento de tokens nos logs.
            raise RuntimeError('API-Football rejeitou a consulta (verifique o plano e a competição)')
        if self.cache:
            try:
                self.cache.set(key, json.dumps(body), ex=max(ttl, 300))
            except Exception:
                pass
        return body


def _resolve_league(client: ApiFootballClient, key: str, year: int) -> dict | None:
    meta = COMPETITIONS[key]
    body = client.get('/leagues', {'search': meta['search']}, ttl=86400)
    choices = []
    for item in body.get('response') or []:
        league = item.get('league') or {}
        country = item.get('country') or {}
        name = _norm(league.get('name'))
        region = _norm(country.get('name'))
        if league.get('type') != 'Cup' or year not in [
            s.get('year') for s in (item.get('seasons') or []) if s.get('coverage') is not None or s.get('year')
        ]:
            continue
        if key == 'copa_brasil':
            if 'copa do brasil' not in name or region != 'brazil':
                continue
        elif key == 'libertadores':
            if 'libertadores' not in name or any(w in name for w in ('women','femenin','u20','sub 20')):
                continue
        else:
            if not ('sudamericana' in name or 'sul americana' in name or 'sudamericana' in _norm(league.get('name'))) or any(w in name for w in ('women','femenin','u20','sub 20')):
                continue
        score = 2 if name in {'copa do brasil', 'copa libertadores', 'conmebol libertadores', 'copa sudamericana', 'conmebol sudamericana'} else 1
        if region in ('world','south america','brazil'):
            score += 1
        choices.append((score, league))
    if not choices:
        return None
    choices.sort(key=lambda row: (-row[0], int(row[1].get('id') or 0)))
    return choices[0][1]


def _completed_final(item: dict) -> bool:
    return (item.get('status') in FINISHED
            and bool(item.get('home')) and bool(item.get('away'))
            and bool(item.get('winner')) and item.get('winner') != item.get('loser'))


def _is_final_round(name: str | None) -> bool:
    value = _norm(name)
    # Proíbe "Semi-finals" e "Quarter-finals". A última partida deve estar
    # explicitamente na fase final, não só ser a última cadastrada.
    return value.startswith('final') or value in {'final', 'grand final'}


def _format_fixture(raw: dict) -> dict:
    fix = raw.get('fixture') or {}
    teams = raw.get('teams') or {}
    home, away = teams.get('home') or {}, teams.get('away') or {}
    goals = raw.get('goals') or {}
    sc = raw.get('score') or {}
    penalty = sc.get('penalty') or {}
    winner = None
    loser = None
    if home.get('winner') is True and away.get('winner') is False:
        winner, loser = home.get('name'), away.get('name')
    elif away.get('winner') is True and home.get('winner') is False:
        winner, loser = away.get('name'), home.get('name')
    elif (fix.get('status') or {}).get('short') in FINISHED:
        hg, ag = goals.get('home'), goals.get('away')
        if isinstance(hg, int) and isinstance(ag, int) and hg != ag:
            winner, loser = ((home.get('name'), away.get('name')) if hg > ag else (away.get('name'), home.get('name')))
        elif isinstance(penalty.get('home'), int) and isinstance(penalty.get('away'), int) and penalty['home'] != penalty['away']:
            winner, loser = ((home.get('name'), away.get('name')) if penalty['home'] > penalty['away'] else (away.get('name'), home.get('name')))
    return {
        'id': fix.get('id'), 'date': fix.get('date'), 'round': (raw.get('league') or {}).get('round'),
        'status': (fix.get('status') or {}).get('short'),
        'home': home.get('name'), 'away': away.get('name'),
        'home_goals': goals.get('home'), 'away_goals': goals.get('away'),
        'winner': winner, 'loser': loser,
    }


def summarize_competition(key: str, games: list[dict], source='API-Football') -> dict:
    finals = sorted((g for g in games if _is_final_round(g.get('round'))),
                    key=lambda x: str(x.get('date') or ''))
    # Final da Copa do Brasil de 2026 é jogo único; duas partidas não
    # podem ser interpretadas como um campeão único sem agregado.
    champion = runner_up = None
    if len(finals) == 1 and _completed_final(finals[0]):
        champion, runner_up = finals[0]['winner'], finals[0]['loser']
    result = {
        'key': key, 'name': COMPETITIONS[key]['name'], 'source': source,
        'status': 'confirmed' if champion else 'in_progress' if games else 'no_data',
        'matches': len(games), 'completed_matches': sum(g.get('status') in FINISHED for g in games),
        'champion': champion, 'runner_up': runner_up,
        'finals': finals, 'recent_matches': sorted(games, key=lambda x: str(x.get('date') or ''), reverse=True)[:8],
        'message': ('Campeão confirmado pela final encerrada.'
                    if champion else 'Final ainda não concluída/identificável; não há campeão confirmado.'),
    }
    return result


def load_cup_statuses(year=2026):
    if not settings.API_FOOTBALL_KEY:
        return {
            key: {'key': key, 'name': meta['name'], 'source': 'API-Football',
                  'status': 'not_configured', 'matches': 0, 'completed_matches': 0,
                  'champion': None, 'runner_up': None, 'finals': [], 'recent_matches': [],
                  'message': 'Configure API_FOOTBALL_KEY no .env para sincronizar esta copa.'}
            for key, meta in COMPETITIONS.items()
        }
    client = ApiFootballClient()
    try:
        client.ensure_season_access(year)
    except SeasonAccessError as exc:
        return {
            key: {'key': key, 'name': meta['name'], 'source': 'API-Football',
                  'status': 'season_restricted', 'matches': 0, 'completed_matches': 0,
                  'champion': None, 'runner_up': None, 'finals': [], 'recent_matches': [],
                  'message': str(exc)}
            for key, meta in COMPETITIONS.items()
        }
    result = {}
    for key, meta in COMPETITIONS.items():
        try:
            league = _resolve_league(client, key, year)
            if not league:
                raise RuntimeError('Competição/temporada não localizada na API-Football')
            body = client.get('/fixtures', {'league': league['id'], 'season': year},
                              ttl=max(900, settings.API_FOOTBALL_CACHE_SECONDS))
            items = body.get('response') or []
            paging = body.get('paging') or {}
            if (paging.get('total') or 1) > 1:
                raise RuntimeError('Resposta paginada; faltam partidas. Verifique cobertura da API.')
            games = [_format_fixture(raw) for raw in items]
            summary = summarize_competition(key, games)
            summary['league_id'] = league['id']
            result[key] = summary
        except Exception as exc:
            result[key] = {
                'key': key, 'name': meta['name'], 'source': 'API-Football',
                'status': 'unavailable', 'matches': 0, 'completed_matches': 0,
                'champion': None, 'runner_up': None, 'finals': [], 'recent_matches': [],
                'message': str(exc)[:180],
            }
    return result
