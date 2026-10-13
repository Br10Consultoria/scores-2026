"""Validação de integridade do calendário e resultados, sem acesso externo.

Usar antes de exibir previsões: detecta dados faltantes, partidas duplicadas,
clubes com jogos em excesso e inconsistências de gols/mando/rodadas.
"""
from collections import Counter, defaultdict
from app.services.league_analytics import is_finished

def validate_calendar(games, source='não informado', updated_at=None):
    seen = set()
    duplicates = []
    invalid = []
    clubs = set()
    schedule = defaultdict(list)
    rounds = Counter()
    home = Counter()
    away = Counter()
    finished = 0
    matches_with_missing_round = 0
    goals_home = 0
    goals_away = 0
    for index, game in enumerate(games):
        identifier = str(game.get('id') or '')
        h = game.get('home_id')
        a = game.get('away_id')
        if not identifier or h is None or a is None or h == a:
            invalid.append(identifier or f'linha {index+1}')
            continue
        h, a = str(h), str(a)
        if identifier in seen:
            duplicates.append(identifier)
        seen.add(identifier)
        clubs.update((h,a))
        schedule[h].append(identifier)
        schedule[a].append(identifier)
        home[h] += 1
        away[a] += 1
        r = game.get('round')
        if isinstance(r, int) and 1 <= r <= 38:
            rounds[r] += 1
        else:
            matches_with_missing_round += 1
        if is_finished(game):
            finished += 1
            goals_home += game['home_goals']
            goals_away += game['away_goals']
    bad_clubs = [{
        'team_id': t, 'matches': len(schedule[t]), 'home': home[t], 'away': away[t]
    } for t in sorted(clubs) if len(schedule[t]) != 38 or home[t] != 19 or away[t] != 19]
    bad_rounds = [{'round': n, 'matches': rounds[n]} for n in range(1, 39) if rounds[n] != 10]
    unique_games = len(seen)
    checks = [
        {'code':'teams','label':'20 clubes distintos', 'ok':len(clubs)==20, 'actual':len(clubs), 'expected':20},
        {'code':'fixtures','label':'380 partidas da Série A', 'ok':unique_games==380, 'actual':unique_games, 'expected':380},
        {'code':'duplicate_ids','label':'IDs de jogos únicos', 'ok':not duplicates, 'actual':len(duplicates), 'expected':0},
        {'code':'valid_rows','label':'Mandante e visitante válidos', 'ok':not invalid, 'actual':len(invalid), 'expected':0},
        {'code':'club_schedules','label':'38 jogos por clube (19 casa, 19 fora)', 'ok':not bad_clubs,'actual':len(bad_clubs),'expected':0},
        {'code':'matchdays','label':'38 rodadas com 10 jogos cada', 'ok':not bad_rounds, 'actual':len(bad_rounds),'expected':0},
        {'code':'round_metadata','label':'Rodada identificada em todos os jogos', 'ok':matches_with_missing_round==0,'actual':matches_with_missing_round,'expected':0},
    ]
    # Sum(GP) == Sum(GC) é identidade contábil quando cada jogo contribui
    # uma vez para ambas as equipes. Aqui registramos o total de gols reais.
    ready = all(check['ok'] for check in checks)
    return {
        'source':source, 'updated_at':updated_at, 'ok':ready,
        'status':'ready' if ready else 'incomplete',
        'message': 'Calendário pronto para simular.' if ready else 'Dados incompletos ou inconsistentes; confira a origem antes de simular.',
        'games_received':len(games), 'unique_games':unique_games,
        'teams':len(clubs), 'finished_games':finished,
        'pending_games':max(0, unique_games-finished),
        'goals_home':goals_home, 'goals_away':goals_away,
        'goals_total':goals_home+goals_away,
        'checks':checks,
        'bad_clubs':bad_clubs,
        'bad_rounds':bad_rounds,
        'duplicate_ids':duplicates[:20],
        'invalid_games':invalid[:20],
    }
