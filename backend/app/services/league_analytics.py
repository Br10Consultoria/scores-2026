"""Análises determinísticas e simulações: dados reais separados de previsões.

Não se inventam partidas: probabilidades só são exibidas com calendário completo.
"""
from collections import defaultdict
import random

FINISHED = {'FINISHED', 'FINALIZADO', 'AWARDED', 'AFTER_EXTRA_TIME', 'AFTER_PENALTIES', 'FT', 'ENDED', 'COMPLETED', 'FULL TIME', 'AFTER PENALTIES', 'TERMINADO'}
EXPECTED_MATCHES = 380


def is_finished(game):
    return str(game.get('status') or '').strip().upper() in FINISHED and isinstance(game.get('home_goals'), int) and isinstance(game.get('away_goals'), int)


def _blank():
    return {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'points': 0}


def _apply(row, scored, conceded):
    row['played'] += 1
    row['goals_for'] += scored
    row['goals_against'] += conceded
    if scored > conceded:
        row['wins'] += 1
        row['points'] += 3
    elif scored == conceded:
        row['draws'] += 1
        row['points'] += 1
    else:
        row['losses'] += 1


def _sort_key(item):
    row = item[1]
    return (-row['points'], -row['wins'], -(row['goals_for'] - row['goals_against']), -row['goals_for'], item[0])


def _ppg(row):
    return round(row['points'] / row['played'], 2) if row['played'] else 0.0


def _teams(games):
    names = {}
    for game in games:
        if game.get('home_id') is not None and game.get('away_id') is not None:
            names[str(game['home_id'])] = game.get('home_name') or str(game['home_id'])
            names[str(game['away_id'])] = game.get('away_name') or str(game['away_id'])
    return names


def _split(games, names):
    stats = {tid: {'total': _blank(), 'home': _blank(), 'away': _blank(), 'first': _blank(), 'return': _blank(), 'recent': _blank()} for tid in names}
    completed = sorted((g for g in games if is_finished(g)), key=lambda g: (str(g.get('date') or ''), str(g.get('id'))))
    history = defaultdict(list)
    for g in completed:
        h, a = str(g['home_id']), str(g['away_id'])
        hg, ag = g['home_goals'], g['away_goals']
        if h not in stats or a not in stats:
            continue
        _apply(stats[h]['total'], hg, ag)
        _apply(stats[a]['total'], ag, hg)
        _apply(stats[h]['home'], hg, ag)
        _apply(stats[a]['away'], ag, hg)
        period = 'first' if g.get('round') is not None and int(g['round']) <= 19 else 'return'
        _apply(stats[h][period], hg, ag)
        _apply(stats[a][period], ag, hg)
        history[h].append((hg, ag))
        history[a].append((ag, hg))
    for tid in names:
        for scored, conceded in history[tid][-5:]:
            _apply(stats[tid]['recent'], scored, conceded)
    return stats


def _strength(stats, tid, venue):
    s = stats[tid]
    total = _ppg(s['total']) if s['total']['played'] else 1.35
    local = _ppg(s[venue]) if s[venue]['played'] >= 3 else total
    recent = _ppg(s['recent']) if s['recent']['played'] >= 3 else total
    ret = _ppg(s['return']) if s['return']['played'] >= 3 else total
    # Suavização para diminuir oscilações de amostras curtas.
    return 0.38 * total + 0.34 * local + 0.18 * ret + 0.10 * recent


def _probabilities(stats, game):
    h, a = str(game['home_id']), str(game['away_id'])
    delta = max(-2.5, min(2.5, _strength(stats, h, 'home') - _strength(stats, a, 'away')))
    home = 0.445 + 0.135 * delta
    away = 0.275 - 0.120 * delta
    draw = 1 - home - away
    probabilities = [max(0.07, home), max(0.15, draw), max(0.07, away)]
    total = sum(probabilities)
    return [p / total for p in probabilities]


def _outcome(rng, probabilities):
    x = rng.random()
    if x < probabilities[0]:
        return 'H'
    if x < probabilities[0] + probabilities[1]:
        return 'D'
    return 'A'


def _score(rng, outcome):
    if outcome == 'D':
        v = rng.choices([0, 1, 2], weights=[3, 6, 1])[0]
        return v, v
    loser = rng.choices([0, 1, 2], weights=[5, 4, 1])[0]
    lead = rng.choices([1, 2, 3], weights=[7, 2, 1])[0]
    return (loser + lead, loser) if outcome == 'H' else (loser, loser + lead)


def _clean_games(games):
    return [g for g in games if g.get('home_id') is not None and g.get('away_id') is not None and str(g['home_id']) != str(g['away_id'])]


def overview(games, source='sem dados', updated_at=None, season=2026):
    games = _clean_games(games)
    names = _teams(games)
    stats = _split(games, names)
    current = sorted(((tid, stats[tid]['total']) for tid in names), key=_sort_key)
    pending = [g for g in games if not is_finished(g)]
    rows = []
    for position, (tid, row) in enumerate(current, 1):
        entry = {'position': position, 'team_id': tid, 'team': names[tid], **row, 'goal_difference': row['goals_for'] - row['goals_against']}
        for category in ('first', 'return', 'home', 'away', 'recent'):
            entry[category] = {**stats[tid][category], 'ppg': _ppg(stats[tid][category])}
        entry['ppg'] = _ppg(row)
        rows.append(entry)
    total = len(games)
    participation = defaultdict(int)
    for g in games:
        participation[str(g['home_id'])] += 1
        participation[str(g['away_id'])] += 1
    complete = (len(names) == 20 and total == EXPECTED_MATCHES
                and len({str(g['id']) for g in games}) == total
                and all(participation[team] == 38 for team in names))
    return {
        'season': season, 'source': source, 'updated_at': updated_at,
        'coverage': {'fixtures': total, 'expected': EXPECTED_MATCHES, 'finished': total - len(pending), 'pending': len(pending), 'teams': len(names), 'complete': complete},
        'simulation_available': complete,
        'notice': ('Calendário completo: projeções probabilísticas estimadas, não chances oficiais.'
                   if complete else 'Calendário incompleto. Probabilidades desativadas até importar os 380 jogos da temporada; estatísticas apenas das partidas disponíveis.'),
        'table': rows,
        'fixtures': [{
            'id': str(g['id']), 'round': g.get('round'), 'date': g.get('date'),
            'home_id': str(g['home_id']), 'away_id': str(g['away_id']),
            'home': names[str(g['home_id'])], 'away': names[str(g['away_id'])],
            'status': g.get('status'), 'home_goals': g.get('home_goals') if is_finished(g) else None,
            'away_goals': g.get('away_goals') if is_finished(g) else None,
            'played': is_finished(g)
        } for g in sorted(games, key=lambda g: (int(g.get('round') or 0), str(g.get('date') or '')))]
    }


def simulate(games, overrides=None, libertadores_places=6, sula_places=6, runs=2000, seed=2026):
    games = _clean_games(games)
    current = overview(games)
    if not current['simulation_available']:
        raise ValueError(current['notice'])
    if not 4 <= libertadores_places <= 12 or not 0 <= sula_places <= 10:
        raise ValueError('Quantidade de vagas fora do intervalo permitido.')
    if not 100 <= runs <= 10000:
        raise ValueError('Número de simulações deve ficar entre 100 e 10.000.')
    names = _teams(games)
    stats = _split(games, names)
    scheduled = [g for g in games if not is_finished(g)]
    overrides = overrides or {}
    fixture_ids = {str(g['id']) for g in scheduled}
    if any(str(key) not in fixture_ids or outcome not in {'H', 'D', 'A'} for key, outcome in overrides.items()):
        raise ValueError('Palpite inválido: escolha H, D ou A apenas para partidas não realizadas.')
    probabilities = {str(g['id']): _probabilities(stats, g) for g in scheduled}
    rng = random.Random(seed)
    tally = {tid: {'title': 0, 'libertadores': 0, 'sulamericana': 0, 'relegation': 0, 'positions': [], 'points': []} for tid in names}
    for _ in range(runs):
        table = {tid: dict(stats[tid]['total']) for tid in names}
        for game in scheduled:
            outcome = overrides.get(str(game['id'])) or _outcome(rng, probabilities[str(game['id'])])
            hg, ag = _score(rng, outcome)
            _apply(table[str(game['home_id'])], hg, ag)
            _apply(table[str(game['away_id'])], ag, hg)
        ranked = sorted(table.items(), key=_sort_key)
        for index, (tid, values) in enumerate(ranked):
            place = index + 1
            result = tally[tid]
            result['positions'].append(place)
            result['points'].append(values['points'])
            result['title'] += place == 1
            result['libertadores'] += place <= libertadores_places
            result['sulamericana'] += libertadores_places < place <= libertadores_places + sula_places
            result['relegation'] += place > len(names) - 4

    def pct(n):
        return round(n * 100 / runs, 1)

    def percentile(values, factor):
        values = sorted(values)
        return values[round((len(values) - 1) * factor)]

    forecast = []
    for tid, outcome in tally.items():
        pts = outcome['points']
        positions = outcome['positions']
        forecast.append({
            'team_id': tid, 'team': names[tid],
            'current_points': stats[tid]['total']['points'],
            'expected_points': round(sum(pts) / runs, 1),
            'points_p10': percentile(pts, 0.10),
            'points_p90': percentile(pts, 0.90),
            'expected_position': round(sum(positions) / runs, 1),
            'title_pct': pct(outcome['title']),
            'libertadores_pct': pct(outcome['libertadores']),
            'sulamericana_pct': pct(outcome['sulamericana']),
            'relegation_pct': pct(outcome['relegation'])
        })
    forecast.sort(key=lambda item: (item['expected_position'], -item['expected_points']))
    return {
        'method': 'Monte Carlo com mando, pontos por jogo geral, returno e últimos 5; modelo heurístico não calibrado. Critérios simplificados de desempate. Vagas continentais hipotéticas, sem ajuste automático de campeões de copas.',
        'runs': runs, 'seed': seed, 'libertadores_places': libertadores_places, 'sula_places': sula_places,
        'overrides': overrides, 'forecast': forecast,
        'fixture_probabilities': [{
            'id': str(g['id']), 'home_pct': round(100 * probabilities[str(g['id'])][0], 1),
            'draw_pct': round(100 * probabilities[str(g['id'])][1], 1),
            'away_pct': round(100 * probabilities[str(g['id'])][2], 1)
        } for g in scheduled]
    }
