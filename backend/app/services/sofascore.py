from datetime import datetime
import json
import time
import requests
import redis
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import CollectionRun, Player, Team


class SofaScoreClient:
    def __init__(self):
        self.base_url = settings.SOFASCORE_BASE_URL.rstrip('/')
        self.headers = {
            'User-Agent': settings.SOFASCORE_USER_AGENT,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://www.sofascore.com',
            'Referer': settings.SOFASCORE_REFERER,
        }
        if settings.SOFASCORE_COOKIE:
            self.headers['Cookie'] = settings.SOFASCORE_COOKIE
        try:
            self.cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.cache.ping()
        except Exception:
            self.cache = None

    def _get(self, path: str, ttl: int = 3600) -> dict:
        url = f'{self.base_url}{path}'
        key = f'sofascore:{path}'
        if self.cache:
            cached = self.cache.get(key)
            if cached:
                return json.loads(cached)
        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers=self.headers, timeout=20)
                if response.status_code == 403:
                    raise RuntimeError('SofaScore retornou 403 Forbidden. Em alguns servidores, a API pública pode exigir IP liberado, cookie de sessão ou headers atualizados. Configure SOFASCORE_COOKIE/SOFASCORE_REFERER no .env se necessário.')
                response.raise_for_status()
                data = response.json()
                if self.cache:
                    self.cache.set(key, json.dumps(data), ex=ttl)
                return data
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f'Falha ao consultar SofaScore: {last_error}')

    def get_serie_a_teams(self) -> list[dict]:
        path = f'/unique-tournament/{settings.SOFASCORE_TOURNAMENT_ID}/season/{settings.SOFASCORE_SEASON_ID}/standings/total'
        data = self._get(path, ttl=6 * 3600)
        rows = data.get('standings', [{}])[0].get('rows', [])
        return [row.get('team', {}) for row in rows if row.get('team')]

    def get_team_players(self, team_id: int) -> list[dict]:
        data = self._get(f'/team/{team_id}/players', ttl=24 * 3600)
        return [item.get('player', {}) for item in data.get('players', []) if item.get('player')]


def sync_teams_and_players(db: Session) -> str:
    run = CollectionRun(status='running')
    db.add(run)
    db.commit()
    client = SofaScoreClient()
    teams_count = 0
    players_count = 0
    try:
        for raw_team in client.get_serie_a_teams():
            team_id = raw_team.get('id')
            if not team_id:
                continue
            team = db.get(Team, int(team_id)) or Team(team_id=int(team_id))
            team.name = raw_team.get('name') or raw_team.get('shortName') or f'Time {team_id}'
            team.slug = raw_team.get('slug')
            team.country = (raw_team.get('country') or {}).get('name') if isinstance(raw_team.get('country'), dict) else None
            team.updated_at = datetime.utcnow()
            db.merge(team)
            db.commit()
            teams_count += 1
            for raw_player in client.get_team_players(int(team_id)):
                player_id = raw_player.get('id')
                if not player_id:
                    continue
                player = db.get(Player, int(player_id)) or Player(player_id=int(player_id))
                player.team_id = int(team_id)
                player.name = raw_player.get('name') or raw_player.get('shortName') or f'Jogador {player_id}'
                player.position = raw_player.get('position')
                player.nationality = (raw_player.get('country') or {}).get('name') if isinstance(raw_player.get('country'), dict) else None
                player.height = raw_player.get('height')
                player.age = raw_player.get('age')
                player.updated_at = datetime.utcnow()
                db.merge(player)
                players_count += 1
            db.commit()
        run.status = 'success'
        run.message = f'Coleta concluída: {teams_count} times e {players_count} jogadores atualizados.'
    except Exception as exc:
        db.rollback()
        run.status = 'error'
        run.message = str(exc)
    finally:
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
    return run.message or 'Coleta finalizada.'
