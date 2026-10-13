"""Regressões da distribuição das vagas CBF 2026 (não envolve API externa)."""
import unittest

from app.services.continental_qualification import allocate_2026, resolve_club


NAMES = [
    'Palmeiras','Flamengo','Athletico-PR','Fluminense','Bahia',
    'Cruzeiro','Atlético-MG','Santos','Bragantino','São Paulo',
    'Coritiba','Vitória','Botafogo','Vasco','Mirassol',
    'Corinthians','Internacional','Grêmio','Remo','Chapecoense'
]


def table():
    return [{
        'team_id':f's-{i+1}', 'team':name, 'points':80-i*3,
        'wins':25-i if i<20 else 0, 'goal_difference':30-i,
        'goals_for':65-i, 'position':i+1
    } for i,name in enumerate(NAMES)]


class ContinentalTests(unittest.TestCase):
    def test_resolution_aliases(self):
        self.assertEqual(resolve_club('Atlético Mineiro',table()),'s-7')
        self.assertEqual(resolve_club('Red Bull Bragantino',table()),'s-9')
        self.assertEqual(resolve_club('Athletico Paranaense',table()),'s-3')

    def test_base_without_cup_results_is_provisional(self):
        result=allocate_2026(table())
        self.assertFalse(result['ready'])
        self.assertEqual(result['counts']['libertadores'],5)
        self.assertEqual(result['counts']['sulamericana'],6)

    def test_cup_champion_first_and_runner_fourteenth(self):
        result=allocate_2026(table(),copa_winner='Palmeiras',copa_runner='Vasco',
                            libertadores_winner='Boca Juniors',sulamericana_winner='Independiente')
        self.assertEqual(result['counts']['libertadores'],7)
        self.assertEqual(result['counts']['sulamericana'],6)
        self.assertEqual(result['slots'][0]['phase'],'groups')
        self.assertEqual(result['slots'][13]['phase'],'groups')
        self.assertEqual(result['slots'][6]['competition'],'sulamericana')

    def test_cup_champion_and_runner_both_top_two(self):
        result=allocate_2026(table(),copa_winner='Palmeiras',copa_runner='Flamengo')
        self.assertEqual(result['counts']['libertadores'],7)
        self.assertEqual(result['counts']['groups'],5)
        self.assertEqual(result['counts']['pre'],2)
        self.assertEqual(result['slots'][1]['phase'],'groups')

    def test_triple_palmeiras_sulamericana_atletico(self):
        result=allocate_2026(table(),copa_winner='Palmeiras',copa_runner='Atlético-MG',
                            libertadores_winner='Palmeiras',sulamericana_winner='Atlético-MG')
        self.assertTrue(result['ready'])
        self.assertEqual(result['counts']['libertadores'],9)
        self.assertEqual(result['counts']['sulamericana'],6)
        self.assertEqual(result['slots'][8]['competition'],'libertadores')
        self.assertEqual(result['slots'][9]['competition'],'sulamericana')

    def test_triple_palmeiras_gremio_runner_atletico_continental(self):
        result=allocate_2026(table(),copa_winner='Palmeiras',copa_runner='Grêmio',
                            libertadores_winner='Palmeiras',sulamericana_winner='Atlético-MG')
        self.assertEqual(result['counts']['libertadores'],9)
        self.assertEqual(result['slots'][17]['competition'],'libertadores')
        self.assertEqual(result['slots'][17]['phase'],'groups')

    def test_invalid_ranking_and_same_finalist(self):
        with self.assertRaises(ValueError):
            allocate_2026(table(),ranking=['s-1'])
        with self.assertRaises(ValueError):
            allocate_2026(table(),copa_winner='Palmeiras',copa_runner='Palmeiras')


if __name__=='__main__':
    unittest.main()
