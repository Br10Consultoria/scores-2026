"""Testes sem dependências externas para as regras de classificação e simulação."""
import unittest
from app.services.league_analytics import overview, simulate


def fixture(identifier, h, a, rnd, status='SCHEDULED', hg=None, ag=None):
    return {
        'id': str(identifier), 'home_id': str(h), 'away_id': str(a),
        'home_name': f'Clube {h:02}', 'away_name': f'Clube {a:02}',
        'home_goals': hg, 'away_goals': ag, 'status': status, 'round': rnd,
        'date': f'2026-{1+(rnd//4):02}-02T12:00:00Z' if rnd <= 40 else '',
    }


def complete_calendar():
    games = []
    num = 1
    for i in range(1, 21):
        for j in range(i + 1, 21):
            games.append(fixture(num, i, j, 1))
            num += 1
            games.append(fixture(num, j, i, 20))
            num += 1
    return games


class LeagueAnalyticsTests(unittest.TestCase):
    def test_returno_casa_fora(self):
        games = [
            fixture(1, 1, 2, 1, 'FINISHED', 1, 0),
            fixture(2, 2, 1, 20, 'FINISHED', 1, 1),
        ]
        data = overview(games)
        a = next(r for r in data['table'] if r['team_id'] == '1')
        self.assertEqual(a['points'], 4)
        self.assertEqual(a['first']['points'], 3)
        self.assertEqual(a['return']['points'], 1)
        self.assertEqual(a['home']['points'], 3)
        self.assertEqual(a['away']['points'], 1)
        self.assertFalse(data['simulation_available'])

    def test_calendar_and_uniform_draws(self):
        games = complete_calendar()
        self.assertEqual(len(games), 380)
        self.assertTrue(overview(games)['simulation_available'])
        overrides = {g['id']: 'D' for g in games}
        result = simulate(games, overrides=overrides, runs=100)
        self.assertEqual(len(result['forecast']), 20)
        for team in result['forecast']:
            self.assertEqual(team['expected_points'], 38)
            self.assertEqual(team['points_p10'], 38)
            self.assertEqual(team['points_p90'], 38)
        self.assertAlmostEqual(sum(t['title_pct'] for t in result['forecast']), 100.0)

    def test_monte_carlo_with_cbf_cup_winners(self):
        result = simulate(complete_calendar(), runs=100, continental_selections={
            'copa_winner': '1', 'copa_runner': '2',
            'libertadores_winner': '1', 'sulamericana_winner': '7',
        })
        self.assertEqual(result['qualification_mode'], 'cbf_2026')
        # Em cada simulação 9 clubes distintos ganham Libertadores e 6
        # ganham Sul-Americana. Soma das porcentagens equivale às vagas.
        self.assertAlmostEqual(sum(r['libertadores_pct'] for r in result['forecast']), 900.0, delta=0.1)
        self.assertAlmostEqual(sum(r['sulamericana_pct'] for r in result['forecast']), 600.0, delta=0.1)

    def test_bad_override(self):
        with self.assertRaises(ValueError):
            simulate(complete_calendar(), overrides={'unknown': 'H'}, runs=100)

    def test_incomplete_calendar_disables_simulation(self):
        with self.assertRaises(ValueError):
            simulate([fixture(1, 1, 2, 1)], runs=100)


if __name__ == '__main__':
    unittest.main()
