"""Testes determinísticos do parser de competições (sem chamadas externas)."""
import unittest
from unittest.mock import patch
from app.services.api_football_cups import (
    _format_fixture, _is_final_round, summarize_competition, check_season_access,
    SeasonAccessError, ApiFootballClient,
)


def game(round_name='Final', status='FT', winner='home'):
    home, away = {'name':'Palmeiras','winner':winner=='home'}, {'name':'Grêmio','winner':winner=='away'}
    if winner == 'unknown':
        home['winner'] = away['winner'] = None
    return {
        'fixture':{'id':12,'status':{'short':status},'date':'2026-12-06T18:00:00Z'},
        'league':{'round':round_name}, 'teams':{'home':home,'away':away},
        'goals':{'home':2,'away':1},'score':{'penalty':{'home':None,'away':None}},
    }


class CupTests(unittest.TestCase):
    def test_free_plan_denies_season_2026_without_fixtures(self):
        sample = {'response': {'subscription': {'plan': 'Free', 'active': True}}}
        with self.assertRaises(SeasonAccessError):
            check_season_access(sample, 2026)
        self.assertEqual(check_season_access(sample, 2024), 'Free')

    def test_paid_plan_allows_season_preflight(self):
        sample = {'response': {'subscription': {'plan': 'Pro', 'active': True}}}
        self.assertEqual(check_season_access(sample, 2026), 'Pro')

    def test_client_uses_cached_status_endpoint_before_season_queries(self):
        client = object.__new__(ApiFootballClient)
        with patch.object(client, 'get', return_value={'response': {'subscription': {'plan': 'Free'}}}) as get:
            with self.assertRaises(SeasonAccessError):
                client.ensure_season_access(2026)
            get.assert_called_once_with('/status', {}, ttl=900)

    def test_final_is_not_semi_final(self):
        self.assertTrue(_is_final_round('Final'))
        self.assertFalse(_is_final_round('Semi-finals'))
        self.assertFalse(_is_final_round('Quarter-final'))

    def test_final_completed(self):
        data=summarize_competition('copa_brasil',[_format_fixture(game())])
        self.assertEqual(data['status'],'confirmed')
        self.assertEqual(data['champion'],'Palmeiras')
        self.assertEqual(data['runner_up'],'Grêmio')

    def test_semi_final_is_not_champion(self):
        data=summarize_competition('copa_brasil',[_format_fixture(game('Semi-finals'))])
        self.assertIsNone(data['champion'])
        self.assertEqual(data['status'],'in_progress')

    def test_two_finals_are_not_inferred_as_single(self):
        data=summarize_competition('libertadores',[_format_fixture(game()),_format_fixture(game())])
        self.assertIsNone(data['champion'])

    def test_final_future_is_not_confirmed(self):
        data=summarize_competition('libertadores',[_format_fixture(game(status='NS'))])
        self.assertIsNone(data['champion'])


if __name__=='__main__':
    unittest.main()
