"""Importação paginada de estatísticas individuais do Brasileirão via API-Football.

Preserva os times da football-data.org e mantém a cota do plano gratuito sob
controle. Não inventa stats nem associa atletas a clubes por semelhança vaga.
"""
from datetime import datetime, timezone
import logging
import re
import time
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now_naive
from app.models import Player, PlayerStats, Team, StandingRow, PlayerImportCheckpoint
from app.services.api_football_cups import ApiFootballClient, SeasonAccessError
from app.services.continental_qualification import _short

LOG = logging.getLogger(__name__)
PLAYER_ID_OFFSET = 1000000000
COMP_ID = settings.SOFASCORE_SERIE_A_TOURNAMENT_ID
SEASON_ID = settings.SOFASCORE_SERIE_A_SEASON_ID


def player_pk(remote_id):
    value = int(remote_id)
    if not (0 < value < 1000000000):
        raise ValueError('ID de jogador fora do namespace da API-Football')
    return PLAYER_ID_OFFSET + value


def number(value, *, decimal=False):
    if value is None or value == '':
        return None
    try:
        if isinstance(value, bool):
            return None
        parsed = float(value)
        if parsed != parsed or abs(parsed) == float('inf'):
            return None
        return parsed if decimal else int(parsed)
    except (ValueError, TypeError):
        return None


def _team_key(name):
    name = _short(name)
    aliases = {
        'ec vitoria': 'vitoria', 'vitoria salvador': 'vitoria',
        'sport club corinthians paulista':'corinthians',
        'cr flamengo':'flamengo','cr vasco da gama':'vasco',
        'clube de regatas do flamengo':'flamengo',
        'clube de regatas vasco da gama':'vasco',
        'atletico paranaense':'athletico pr',
        'atletico pr':'athletico pr',
        'athletico paranaense':'athletico pr',
        'atletico mg':'atletico mg',
        'america mg':'america mg',
        'rb bragantino':'bragantino',
        'botafogo rio de janeiro':'botafogo',
        'mirassol futebol clube':'mirassol',
        'gremio porto alegre':'gremio',
        'gremio fbpa':'gremio',
        'internacional porto alegre':'internacional',
        'sport club internacional':'internacional',
        'associacao chapecoense de futebol':'chapecoense',
        'chapecoense sc':'chapecoense',
        'remo belem':'remo',
        'clube do remo':'remo',
        'coritiba foot ball club':'coritiba',
        'coritiba fc':'coritiba',
        'santos fc':'santos',
        'fluminense fc':'fluminense',
        'sao paulo fc':'sao paulo',
        'ec bahia':'bahia',
        'esporte clube bahia':'bahia',
    }
    return aliases.get(name, name)


def team_map(db: Session):
    # Se houver clubes de mais de um provedor, preferir os 20 associados
    # ao cadastro da temporada do Brasileirão.
    standings = db.query(Team).join(StandingRow, StandingRow.team_id == Team.team_id).filter(
        StandingRow.competition_id == COMP_ID,
        StandingRow.season_id == SEASON_ID
    ).all()
    if not standings:
        return {}
    result = {}
    for team in sorted(standings, key=lambda row: row.team_id < 900000000):
        key = _team_key(team.name)
        if key not in result:
            result[key] = team.team_id
    return result


def parse_player(raw):
    p = raw.get('player') or {}
    stats_list = raw.get('statistics') or []
    if not p.get('id') or not p.get('name') or not isinstance(stats_list, list):
        return None
    stats = next((s for s in stats_list if str((s.get('league') or {}).get('id')) == str(settings.API_FOOTBALL_SERIE_A_LEAGUE_ID)), None)
    if stats is None:
        return None
    team = stats.get('team') or {}
    games = stats.get('games') or {}
    shots = stats.get('shots') or {}
    goals = stats.get('goals') or {}
    passes = stats.get('passes') or {}
    tackles = stats.get('tackles') or {}
    cards = stats.get('cards') or {}
    penalties = stats.get('penalty') or {}
    stat_values = {
        'rating': number(games.get('rating'), decimal=True),
        'matches': number(games.get('appearences')),
        'starts': number(games.get('lineups')),
        'minutes': number(games.get('minutes')),
        'goals': number(goals.get('total')),
        'assists': number(goals.get('assists')),
        'shots': number(shots.get('total')),
        'shots_on_target': number(shots.get('on')),
        'key_passes': number(passes.get('key')),
        'accurate_passes': number(passes.get('total')),
        'tackles': number(tackles.get('total')),
        'interceptions': number(tackles.get('interceptions')),
        'saves': number(goals.get('saves')),
        'goals_conceded': number(goals.get('conceded')),
        'yellow_cards': number(cards.get('yellow')),
        'red_cards': number(cards.get('red')),
    }
    stat_values['accurate_passes'] = None  # passes.total não implica passes certos
    return {
        'remote_id': p['id'], 'name': p['name'], 'position': games.get('position'),
        'team_name': team.get('name'), 'age': number(p.get('age')),
        'nationality': p.get('nationality'), 'photo': p.get('photo'),
        'height': number(re.search(r'\d+',str(p.get('height') or '')).group()) if re.search(r'\d+', str(p.get('height') or '')) else None,
        'birth': (p.get('birth') or {}).get('date'),
        'jersey': games.get('number'),
        'stats': stat_values, 'profile': p, 'raw_stats': stats, 'penalties': penalties,
    }


def store_player(db: Session, raw: dict, mapping: dict):
    item = parse_player(raw)
    if item is None:
        return 'skipped'
    tid = mapping.get(_team_key(item['team_name']))
    if not tid:
        return 'unmatched'
    identifier = player_pk(item['remote_id'])
    player = db.get(Player, identifier) or Player(player_id=identifier)
    player.team_id = tid
    player.name = item['name']
    player.position = item['position']
    player.age = item['age']
    player.nationality = item['nationality']
    player.height = item['height']
    player.date_of_birth = item['birth']
    player.jersey_number = str(item['jersey']) if item['jersey'] is not None else None
    player.raw_data = {'source':'api-football', 'player': item['profile'], 'photo':item['photo']}
    player.updated_at = utc_now_naive()
    db.add(player)
    db.flush()
    stats = db.query(PlayerStats).filter(
        PlayerStats.player_id == identifier,
        PlayerStats.season_id == SEASON_ID,
        PlayerStats.competition_id == COMP_ID,
    ).first() or PlayerStats(player_id=identifier, season_id=SEASON_ID, competition_id=COMP_ID)
    for field, value in item['stats'].items():
        setattr(stats, field, value)
    stats.raw_data = {'source':'api-football', 'statistics':item['raw_stats']}
    stats.updated_at = utc_now_naive()
    db.add(stats)
    return 'saved'



def import_rankings(db: Session, client, league_id: int, season: int, mapping: dict):
    """Atualiza os líderes oficiais mesmo quando o elenco completo é parcial."""
    imported = 0
    for index, endpoint in enumerate(('/players/topscorers', '/players/topassists')):
        if index:
            time.sleep(7)
        try:
            data = client.get(endpoint, {'league':league_id,'season':season}, ttl=21600)
            rows = data.get('response') or []
            for row in rows:
                if store_player(db, row, mapping) == 'saved':
                    imported += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            LOG.warning('Ranking de atletas indisponível (%s): %s', endpoint, str(exc)[:160])
    return imported


def get_checkpoint(db: Session):
    return db.get(PlayerImportCheckpoint, 1)


def player_status(db: Session):
    state = get_checkpoint(db)
    player_count = db.query(func.count(Player.player_id)).filter(
        Player.player_id >= PLAYER_ID_OFFSET, Player.player_id < 1900000000
    ).scalar() or 0
    stat_count = db.query(func.count(PlayerStats.id)).filter(
        PlayerStats.player_id >= PLAYER_ID_OFFSET,
        PlayerStats.competition_id == COMP_ID,
        PlayerStats.season_id == SEASON_ID
    ).scalar() or 0
    return {
        'configured': bool(settings.API_FOOTBALL_KEY),
        'league_id': settings.API_FOOTBALL_SERIE_A_LEAGUE_ID,
        'status': state.status if state else 'idle',
        'message': state.message if state else 'Ainda não foi executada a coleta de jogadores.',
        'next_page': state.next_page if state else 1,
        'total_pages': state.total_pages if state else None,
        'imported_players': state.imported_players if state else 0,
        'skipped_players': state.skipped_players if state else 0,
        'players_in_database': player_count,
        'stats_in_database': stat_count,
        'source': 'API-Football',
        'partial': not state or state.status != 'completed',
    }


def import_players(db: Session, *, pages=None):
    limit = min(15, max(1, int(pages or settings.API_FOOTBALL_PLAYERS_PAGES_PER_SYNC)))
    checkpoint = get_checkpoint(db)
    if checkpoint is None:
        checkpoint = PlayerImportCheckpoint(id=1, source='api-football', next_page=1)
        db.add(checkpoint)
        db.commit()
    try:
        client = ApiFootballClient()
        # Verifica plano antes de qualquer consulta /leagues ou /players.
        # No Free não vale a pena repetir tentativas para temporada 2026.
        client.ensure_season_access(2026)
        mapping = team_map(db)
        if len(mapping) < 20:
            raise RuntimeError('Importe primeiro os 20 clubes da Série A.')
        season = 2026
        league_id = settings.API_FOOTBALL_SERIE_A_LEAGUE_ID
        leagues = client.get('/leagues', {'id':league_id,'season':season}, ttl=86400)
        if not any(int((entry.get('league') or {}).get('id') or 0) == league_id for entry in leagues.get('response') or []):
            raise RuntimeError('Série A 2026 não disponível para sua chave/API-Football.')
        page = max(1, checkpoint.next_page)
        imported = skipped = 0
        completed = False
        for step in range(limit):
            data = client.get('/players', {'league':league_id,'season':season,'page':page}, ttl=21600)
            response = data.get('response') or []
            paging = data.get('paging') or {}
            total = int(paging.get('total') or 0)
            if not response or not total:
                raise RuntimeError(f'API-Football não retornou atletas na página {page}; confira cobertura 2026.')
            imported_page = skipped_page = 0
            for item in response:
                result = store_player(db,item,mapping)
                if result == 'saved':
                    imported += 1
                    imported_page += 1
                else:
                    skipped += 1
                    skipped_page += 1
            checkpoint.next_page = page + 1
            checkpoint.total_pages = total
            checkpoint.imported_players += imported_page
            checkpoint.skipped_players += skipped_page
            db.add(checkpoint)
            db.commit()
            if page >= total:
                completed = True
                break
            page += 1
            # Respeita o limite gratuito de 10 chamadas por minuto.
            if step < limit - 1:
                time.sleep(7)
        time.sleep(7)
        ranking_count = import_rankings(db, client, league_id, season, mapping)
        checkpoint = get_checkpoint(db)
        if completed:
            checkpoint.status = 'completed'
            checkpoint.next_page = 1
            checkpoint.message = f'Catálogo percorrido: {imported} atletas nesta etapa e {ranking_count} registros de rankings de artilheiros/assistências consultados. Cobertura sujeita ao provedor.'
        else:
            checkpoint.status = 'partial'
            checkpoint.message = f'Etapa concluída: {imported} atletas, {skipped} sem equipe/estatísticas. {ranking_count} registros de rankings consultados. Próxima página: {checkpoint.next_page}/{checkpoint.total_pages}.'
        db.commit()
        return player_status(db)
    except Exception as exc:
        db.rollback()
        checkpoint = get_checkpoint(db) or PlayerImportCheckpoint(id=1, source='api-football', next_page=1)
        checkpoint.status = 'season_restricted' if isinstance(exc, SeasonAccessError) else 'error'
        checkpoint.message = str(exc)[:400]
        db.add(checkpoint)
        db.commit()
        LOG.warning('Importação de jogadores interrompida: %s', str(exc)[:180])
        return player_status(db)
