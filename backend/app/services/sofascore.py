from datetime import datetime, timezone
import json
import time
from typing import Any
import requests
import redis
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import CollectionRun, Competition, Match, Player, PlayerStats, StandingRow, Team
from app.core.datetime_utils import utc_now_naive


COMPETITIONS = [
    {
        'id': settings.SOFASCORE_SERIE_A_TOURNAMENT_ID,
        'season_id': settings.SOFASCORE_SERIE_A_SEASON_ID,
        'name': 'Brasileirão Série A',
        'slug': 'brasileirao-serie-a',
        'country': 'Brazil',
    },
    {
        'id': settings.SOFASCORE_SERIE_B_TOURNAMENT_ID,
        'season_id': settings.SOFASCORE_SERIE_B_SEASON_ID,
        'name': 'Brasileirão Série B',
        'slug': 'brasileirao-serie-b',
        'country': 'Brazil',
    },
]


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
                response = requests.get(url, headers=self.headers, timeout=25)
                if response.status_code == 403:
                    raise RuntimeError('SofaScore retornou 403 Forbidden. Configure SOFASCORE_COOKIE/SOFASCORE_REFERER/SOFASCORE_USER_AGENT no .env do servidor se necessário.')
                response.raise_for_status()
                data = response.json()
                if self.cache:
                    self.cache.set(key, json.dumps(data), ex=ttl)
                return data
            except Exception as exc:
                last_error = exc
                time.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f'Falha ao consultar SofaScore em {path}: {last_error}')

    def _get_optional(self, path: str, ttl: int = 3600) -> dict:
        try:
            return self._get(path, ttl=ttl)
        except Exception:
            return {}

    def get_standings(self, tournament_id: int, season_id: int) -> list[dict]:
        path = f'/unique-tournament/{tournament_id}/season/{season_id}/standings/total'
        data = self._get(path, ttl=3 * 3600)
        return data.get('standings', [{}])[0].get('rows', [])

    def get_team_players(self, team_id: int) -> list[dict]:
        data = self._get(f'/team/{team_id}/players', ttl=24 * 3600)
        return data.get('players', [])

    def get_player_statistics(self, player_id: int, tournament_id: int, season_id: int) -> dict:
        paths = [
            f'/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall',
            f'/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics',
        ]
        for path in paths:
            data = self._get_optional(path, ttl=24 * 3600)
            if data:
                return data.get('statistics') or data
        return {}

    def get_events(self, tournament_id: int, season_id: int) -> list[dict]:
        events: list[dict] = []
        seen: set[int] = set()
        paths = [
            f'/unique-tournament/{tournament_id}/season/{season_id}/events/last/0',
            f'/unique-tournament/{tournament_id}/season/{season_id}/events/last/1',
            f'/unique-tournament/{tournament_id}/season/{season_id}/events/next/0',
            f'/unique-tournament/{tournament_id}/season/{season_id}/events/next/1',
        ]
        for path in paths:
            data = self._get_optional(path, ttl=30 * 60)
            for event in data.get('events', []):
                event_id = event.get('id')
                if event_id and event_id not in seen:
                    seen.add(int(event_id))
                    events.append(event)
        return events


def _team_logo_url(team_id: int) -> str:
    return f'https://api.sofascore.app/api/v1/team/{team_id}/image'


def _int(value: Any) -> int | None:
    try:
        if value is None or value == '':
            return None
        return int(value)
    except Exception:
        return None


def _float(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except Exception:
        return None


def _field(raw: dict, *names: str):
    for name in names:
        if name in raw and raw.get(name) is not None:
            return raw.get(name)
    return None


def _upsert_competition(db: Session, meta: dict) -> Competition:
    comp = db.get(Competition, int(meta['id'])) or Competition(id=int(meta['id']))
    comp.name = meta['name']
    comp.slug = meta.get('slug')
    comp.country = meta.get('country')
    comp.season_id = int(meta['season_id'])
    comp.season_name = str(meta['season_id'])
    comp.updated_at = utc_now_naive()
    db.merge(comp)
    db.commit()
    return comp


def _upsert_team(db: Session, raw_team: dict, competition_id: int | None = None) -> Team | None:
    team_id = raw_team.get('id')
    if not team_id:
        return None
    team = db.get(Team, int(team_id)) or Team(team_id=int(team_id))
    team.name = raw_team.get('name') or raw_team.get('shortName') or f'Time {team_id}'
    team.short_name = raw_team.get('shortName') or team.name
    team.slug = raw_team.get('slug')
    team.country = (raw_team.get('country') or {}).get('name') if isinstance(raw_team.get('country'), dict) else None
    team.logo_url = _team_logo_url(int(team_id))
    team.primary_competition_id = competition_id or team.primary_competition_id
    team.raw_data = raw_team
    team.updated_at = utc_now_naive()
    return db.merge(team)


def _standing_value(row: dict, *names: str) -> int | None:
    for name in names:
        value = row.get(name)
        if value is not None:
            return _int(value)
    return None


def _sync_standings(db: Session, client: SofaScoreClient, comp: Competition, meta: dict) -> tuple[int, list[Team]]:
    rows = client.get_standings(int(meta['id']), int(meta['season_id']))
    teams: list[Team] = []
    for row in rows:
        raw_team = row.get('team') or {}
        team = _upsert_team(db, raw_team, comp.id)
        if not team:
            continue
        teams.append(team)
        standing = (
            db.query(StandingRow)
            .filter(StandingRow.competition_id == comp.id, StandingRow.season_id == int(meta['season_id']), StandingRow.team_id == team.team_id)
            .first()
            or StandingRow(competition_id=comp.id, season_id=int(meta['season_id']), team_id=team.team_id)
        )
        standing.position = _standing_value(row, 'position', 'rank')
        standing.matches = _standing_value(row, 'matches', 'played')
        standing.wins = _standing_value(row, 'wins')
        standing.draws = _standing_value(row, 'draws')
        standing.losses = _standing_value(row, 'losses')
        standing.scores_for = _standing_value(row, 'scoresFor', 'goalsFor')
        standing.scores_against = _standing_value(row, 'scoresAgainst', 'goalsAgainst')
        standing.score_diff = _standing_value(row, 'scoreDiff', 'goalDifference')
        standing.points = _standing_value(row, 'points')
        standing.form = ''.join(row.get('form', []) if isinstance(row.get('form'), list) else []) or row.get('form')
        standing.raw_data = row
        standing.updated_at = utc_now_naive()
        db.merge(standing)
    db.commit()
    return len(rows), teams


def _sync_players(db: Session, client: SofaScoreClient, team: Team, comp: Competition) -> int:
    count = 0
    for item in client.get_team_players(team.team_id):
        raw_player = item.get('player') or item
        player_id = raw_player.get('id')
        if not player_id:
            continue
        player = db.get(Player, int(player_id)) or Player(player_id=int(player_id))
        player.team_id = team.team_id
        player.name = raw_player.get('name') or raw_player.get('shortName') or f'Jogador {player_id}'
        player.slug = raw_player.get('slug')
        player.position = raw_player.get('position')
        player.jersey_number = str(raw_player.get('jerseyNumber')) if raw_player.get('jerseyNumber') is not None else None
        player.nationality = (raw_player.get('country') or {}).get('name') if isinstance(raw_player.get('country'), dict) else None
        player.height = _int(raw_player.get('height'))
        player.age = _int(raw_player.get('age'))
        player.date_of_birth = raw_player.get('dateOfBirth') or raw_player.get('dateOfBirthTimestamp')
        player.preferred_foot = raw_player.get('preferredFoot')
        player.market_value = _int(raw_player.get('proposedMarketValue') or raw_player.get('marketValue'))
        player.raw_data = raw_player
        player.updated_at = utc_now_naive()
        db.merge(player)
        db.commit()

        stats_raw = client.get_player_statistics(int(player_id), comp.id, int(comp.season_id or 0))
        if stats_raw:
            stats = db.query(PlayerStats).filter(PlayerStats.player_id == int(player_id), PlayerStats.season_id == int(comp.season_id or 0)).first() or PlayerStats(player_id=int(player_id), season_id=int(comp.season_id or 0))
            stats.competition_id = comp.id
            stats.rating = _float(_field(stats_raw, 'rating', 'averageRating'))
            stats.matches = _int(_field(stats_raw, 'appearances', 'matches', 'totalMatches'))
            stats.starts = _int(_field(stats_raw, 'starts'))
            stats.minutes = _int(_field(stats_raw, 'minutesPlayed', 'minutes'))
            stats.goals = _int(_field(stats_raw, 'goals', 'goalsScored'))
            stats.assists = _int(_field(stats_raw, 'assists'))
            stats.shots = _int(_field(stats_raw, 'totalShots', 'shots'))
            stats.shots_on_target = _int(_field(stats_raw, 'shotsOnTarget'))
            stats.big_chances_created = _int(_field(stats_raw, 'bigChancesCreated'))
            stats.key_passes = _int(_field(stats_raw, 'keyPasses'))
            stats.accurate_passes = _int(_field(stats_raw, 'accuratePasses'))
            stats.tackles = _int(_field(stats_raw, 'tackles'))
            stats.interceptions = _int(_field(stats_raw, 'interceptions'))
            stats.clearances = _int(_field(stats_raw, 'clearances'))
            stats.saves = _int(_field(stats_raw, 'saves'))
            stats.clean_sheets = _int(_field(stats_raw, 'cleanSheets'))
            stats.goals_conceded = _int(_field(stats_raw, 'goalsConceded'))
            stats.yellow_cards = _int(_field(stats_raw, 'yellowCards'))
            stats.red_cards = _int(_field(stats_raw, 'redCards'))
            stats.raw_data = stats_raw
            stats.updated_at = utc_now_naive()
            db.merge(stats)
            db.commit()
        count += 1
    return count


def _sync_matches(db: Session, client: SofaScoreClient, comp: Competition, meta: dict) -> int:
    count = 0
    for raw in client.get_events(int(meta['id']), int(meta['season_id'])):
        match_id = raw.get('id')
        if not match_id:
            continue
        home = _upsert_team(db, raw.get('homeTeam') or {}, comp.id) if raw.get('homeTeam') else None
        away = _upsert_team(db, raw.get('awayTeam') or {}, comp.id) if raw.get('awayTeam') else None
        match = db.get(Match, int(match_id)) or Match(match_id=int(match_id))
        match.competition_id = comp.id
        match.season_id = int(meta['season_id'])
        match.round_info = str((raw.get('roundInfo') or {}).get('round') or (raw.get('roundInfo') or {}).get('name') or '') or None
        match.home_team_id = home.team_id if home else None
        match.away_team_id = away.team_id if away else None
        home_score = raw.get('homeScore') or {}
        away_score = raw.get('awayScore') or {}
        match.home_score = _int(home_score.get('current') if isinstance(home_score, dict) else None)
        match.away_score = _int(away_score.get('current') if isinstance(away_score, dict) else None)
        match.status = (raw.get('status') or {}).get('description') if isinstance(raw.get('status'), dict) else None
        match.start_timestamp = _int(raw.get('startTimestamp'))
        match.start_time = datetime.fromtimestamp(int(raw['startTimestamp']), tz=timezone.utc).replace(tzinfo=None) if raw.get('startTimestamp') else None
        match.venue = (raw.get('venue') or {}).get('name') if isinstance(raw.get('venue'), dict) else None
        match.raw_data = raw
        match.updated_at = utc_now_naive()
        db.merge(match)
        count += 1
    db.commit()
    return count


def sync_teams_and_players(db: Session) -> str:
    run = CollectionRun(status='running')
    db.add(run)
    db.commit()
    client = SofaScoreClient()
    competitions_count = standings_count = teams_count = players_count = matches_count = 0
    try:
        for meta in COMPETITIONS:
            comp = _upsert_competition(db, meta)
            competitions_count += 1
            standing_rows, teams = _sync_standings(db, client, comp, meta)
            standings_count += standing_rows
            teams_count += len(teams)
            matches_count += _sync_matches(db, client, comp, meta)
            for team in teams:
                players_count += _sync_players(db, client, team, comp)
        run.status = 'success'
        run.message = f'Coleta concluída: {competitions_count} competições, {teams_count} times, {standings_count} linhas de tabela, {matches_count} jogos e {players_count} jogadores atualizados.'
    except Exception as exc:
        db.rollback()
        run.status = 'error'
        run.message = str(exc)
    finally:
        run.finished_at = utc_now_naive()
        db.add(run)
        db.commit()
    return run.message or 'Coleta finalizada.'
