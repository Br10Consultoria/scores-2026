"""Valida integração e mapeamento de estatísticas de atletas sem usar a API externa."""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Competition, Team, StandingRow, Player, PlayerStats
from app.services.api_football_players import (
    player_pk, parse_player, store_player, team_map, number, player_status,
)


def sample(position='Attacker', club='Atlético Mineiro', **overrides):
    stats = {
        'league': {'id':71,'season':2026},
        'team': {'id': 222,'name':club},
        'games': {'appearences':12,'lineups':10,'minutes':950,'position':position,'rating':'7.22','number':9},
        'shots': {'total':34,'on':19},'goals':{'total':8,'assists':3,'saves':None,'conceded':None},
        'passes': {'key':13,'total':140,'accuracy':77},
        'tackles': {'total':5,'interceptions':2},
        'cards':{'yellow':2,'red':0},'penalty':{'saved':0},
    }
    if position == 'Goalkeeper':
        stats['goals']={'total':0,'assists':0,'saves':42,'conceded':11}
    stats.update(overrides)
    return {'player':{'id':123,'name':'Jogador Teste','age':29,
            'nationality':'Brazil','height':'182 cm',
            'birth':{'date':'1997-01-01'},'photo':'https://example.com/photo.png'},
            'statistics':[stats]}


class PlayerImportTests(unittest.TestCase):
    def setUp(self):
        engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        self.engine=engine
        self.db=sessionmaker(bind=engine)()
        self.db.add(Competition(id=325,name='Série A',season_id=87678))
        self.db.add(Team(team_id=900002001,name='Atlético-MG'))
        self.db.add(StandingRow(competition_id=325,season_id=87678,team_id=900002001,position=1,points=20))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_team_alias_and_stats(self):
        mapping=team_map(self.db)
        self.assertEqual(mapping['atletico mg'],900002001)
        self.assertEqual(store_player(self.db,sample(),mapping),'saved')
        self.db.commit()
        p=self.db.get(Player,player_pk(123))
        self.assertEqual(p.team_id,900002001)
        self.assertEqual(p.height,182)
        s=self.db.query(PlayerStats).filter(PlayerStats.player_id==p.player_id).one()
        self.assertEqual(s.goals,8)
        self.assertEqual(s.assists,3)
        self.assertEqual(s.shots_on_target,19)
        self.assertEqual(s.rating,7.22)
        self.assertIsNone(s.accurate_passes)
        self.assertEqual(player_status(self.db)['stats_in_database'],1)

    def test_goalkeeper_saves(self):
        mapping=team_map(self.db)
        self.assertEqual(store_player(self.db,sample(position='Goalkeeper'),mapping),'saved')
        self.db.commit()
        s=self.db.query(PlayerStats).one()
        self.assertEqual(s.saves,42)
        self.assertEqual(s.goals_conceded,11)

    def test_unknown_team_is_not_assigned(self):
        self.assertEqual(store_player(self.db,sample(club='Time desconhecido'),team_map(self.db)),'unmatched')
        self.assertEqual(self.db.query(Player).count(),0)

    def test_absent_values_are_not_zero(self):
        item=sample()
        item['statistics'][0]['goals']={'total':None,'assists':None}
        self.assertIsNone(parse_player(item)['stats']['goals'])
        self.assertIsNone(number(None))

    def test_namespaced_id(self):
        self.assertEqual(player_pk(123),1000000123)
        with self.assertRaises(ValueError):
            player_pk(0)


if __name__=='__main__':
    unittest.main()
