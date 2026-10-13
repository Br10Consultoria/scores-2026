"""Fallback de importação da Série A, usado quando a SofaScore falha (403).

IDs da football-data.org vivem em namespace distinto para não colisão com
as IDs SofaScore. Não apaga informações preexistentes.
"""
from datetime import datetime, timezone
from app.core.config import settings
from app.core.datetime_utils import utc_now_naive
from app.models import Competition, Match, StandingRow, Team
from app.services.football_data import get_brazil_serie_a
from app.services.league_analytics import overview

PROVIDER_ID_OFFSET = 900000000


def _numeric_id(value):
    number = int(str(value).split('-')[-1])
    if not 0 < number < 100000000:
        raise ValueError('ID da football-data.org fora do namespace suportado')
    return PROVIDER_ID_OFFSET + number


def import_brasileirao(db, year=2026):
    if not settings.FOOTBALL_DATA_API_KEY:
        raise RuntimeError('Configure FOOTBALL_DATA_API_KEY para habilitar o fallback')
    payload = get_brazil_serie_a(year)
    games = payload['games']
    analyzed = overview(games, source='football-data.org', season=year)
    if len(games) < 200 or len(analyzed['table']) != 20:
        raise RuntimeError('Football-data.org retornou calendário insuficiente para importar a Série A')
    now = utc_now_naive()
    competition = db.get(Competition, settings.SOFASCORE_SERIE_A_TOURNAMENT_ID)
    if not competition:
        competition = Competition(id=settings.SOFASCORE_SERIE_A_TOURNAMENT_ID)
    competition.name = 'Brasileirão Série A'
    competition.slug = 'brasileirao-serie-a'
    competition.country = 'Brazil'
    competition.season_id = settings.SOFASCORE_SERIE_A_SEASON_ID
    competition.season_name = str(year)
    competition.updated_at = now
    db.merge(competition)
    db.flush()
    team_lookup = {}
    for row in analyzed['table']:
        identifier = _numeric_id(row['team_id'])
        team_lookup[str(row['team_id'])] = identifier
        team = db.get(Team, identifier) or Team(team_id=identifier)
        team.name = row['team']
        team.short_name = row['team']
        team.country = 'Brazil'
        team.primary_competition_id = competition.id
        team.raw_data = {'source':'football-data.org','external_id':row['team_id']}
        team.updated_at = now
        db.merge(team)
        standing = (db.query(StandingRow).filter(
            StandingRow.competition_id==competition.id,
            StandingRow.season_id==competition.season_id,
            StandingRow.team_id==identifier).first()
            or StandingRow(competition_id=competition.id, season_id=competition.season_id, team_id=identifier))
        for field, value in {
            'position': row['position'], 'matches':row['played'], 'wins':row['wins'],
            'draws':row['draws'], 'losses':row['losses'],
            'scores_for':row['goals_for'], 'scores_against':row['goals_against'],
            'score_diff':row['goal_difference'], 'points':row['points'],
        }.items():
            setattr(standing,field,value)
        standing.raw_data = {'source':'football-data.org'}
        standing.updated_at = now
        db.add(standing)
    db.flush()

    for game in games:
        match_id = _numeric_id(game['id'])
        match = db.get(Match,match_id) or Match(match_id=match_id)
        match.competition_id = competition.id
        match.season_id = competition.season_id
        match.home_team_id = team_lookup[str(game['home_id'])]
        match.away_team_id = team_lookup[str(game['away_id'])]
        match.round_info = str(game['round']) if game.get('round') else None
        finished = str(game.get('status') or '').upper() == 'FINISHED'
        match.home_score = game.get('home_goals') if finished else None
        match.away_score = game.get('away_goals') if finished else None
        match.status = str(game.get('status') or '')
        date = game.get('date')
        if date:
            date_utc = datetime.fromisoformat(date.replace('Z','+00:00'))
            match.start_timestamp = int(date_utc.timestamp())
            match.start_time = date_utc.astimezone(timezone.utc).replace(tzinfo=None)
        match.raw_data = {'source':'football-data.org','external_id':game['id']}
        match.updated_at = now
        db.merge(match)
    db.commit()
    return {'teams':len(team_lookup),'standings':len(analyzed['table']),'matches':len(games),'source':'football-data.org'}
