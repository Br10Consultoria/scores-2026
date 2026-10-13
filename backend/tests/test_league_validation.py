"""Testes de integridade sem banco nem APIs externas."""
import unittest
from app.services.league_validation import validate_calendar


def round_robin_games():
    clubs = [str(t) for t in range(1, 21)]
    games = []
    counter = 0
    for rnd in range(1, 20):
        for idx in range(10):
            first, second = clubs[idx], clubs[19-idx]
            # Mantém o mando equilibrado e espelha na segunda volta.
            host, visitor = (first, second) if (rnd + idx) % 2 else (second, first)
            counter += 1
            games.append({'id': f'm-{counter}', 'home_id': host, 'away_id': visitor, 'round': rnd,
                          'status':'FINISHED', 'home_goals':1, 'away_goals':0})
            counter += 1
            games.append({'id': f'm-{counter}', 'home_id': visitor, 'away_id': host, 'round': rnd + 19,
                          'status':'SCHEDULED', 'home_goals':None, 'away_goals':None})
        clubs = [clubs[0]] + [clubs[-1]] + clubs[1:-1]
    return games


class LeagueValidationTests(unittest.TestCase):
    def test_valid_full_schedule(self):
        result = validate_calendar(round_robin_games())
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['finished_games'], 190)
        self.assertEqual(result['pending_games'], 190)
        self.assertEqual(result['goals_total'], 190)
        self.assertEqual(result['bad_clubs'], [])
        self.assertEqual(result['bad_rounds'], [])

    def test_incomplete_schedule(self):
        result = validate_calendar(round_robin_games()[:200])
        self.assertFalse(result['ok'])
        self.assertIn('fixtures', {c['code'] for c in result['checks'] if not c['ok']})

    def test_duplicate_id(self):
        games = round_robin_games()
        games[1]['id'] = games[0]['id']
        result = validate_calendar(games)
        self.assertFalse(result['ok'])
        self.assertEqual(len(result['duplicate_ids']), 1)

    def test_missing_round(self):
        games = round_robin_games()
        games[0]['round'] = None
        result = validate_calendar(games)
        self.assertFalse(result['ok'])
        self.assertGreater(len(result['bad_rounds']), 0)


if __name__ == '__main__':
    unittest.main()
