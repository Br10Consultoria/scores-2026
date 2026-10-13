"""Testa KPIs com calendário importado e sem jogadores (erro SofaScore 403)."""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Competition, Team, Match
from app.api.reports import dashboard


class DashboardCoverageTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(Competition(id=325, name='Brasileirão Série A', season_id=87678))
        self.db.add(Team(team_id=900000010, name='Time A'))
        self.db.add(Team(team_id=900000011, name='Time B'))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_completed_and_future_games_are_separate(self):
        self.db.add_all([
            Match(match_id=900000101, competition_id=325, season_id=87678,
                  home_team_id=900000010, away_team_id=900000011,
                  status='FINISHED', home_score=2, away_score=1),
            Match(match_id=900000102, competition_id=325, season_id=87678,
                  home_team_id=900000011, away_team_id=900000010,
                  status='TIMED'),
        ])
        self.db.commit()
        result = dashboard(competition_id=325, _=object(), db=self.db)
        self.assertEqual(result['teams'], 2)
        self.assertEqual(result['matches'], 2)
        self.assertEqual(result['finished_matches'], 1)
        self.assertEqual(result['scheduled_matches'], 1)
        self.assertEqual(result['players'], 0)
        self.assertEqual(result['stats_rows'], 0)
        self.assertEqual(result['meta']['sources'], ['football-data.org'])
        self.assertFalse(result['meta']['player_stats_available'])


if __name__ == '__main__':
    unittest.main()
