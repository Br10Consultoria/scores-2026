from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from openai import OpenAI, OpenAIError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Competition, Match, Player, PlayerStats, StandingRow, Team


class AIAnalysisError(RuntimeError):
    """Erro controlado para falhas na camada de análise com IA."""


class AIAnalysisService:
    """Serviço de análise esportiva com OpenAI sobre os dados coletados da SofaScore."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_team(self, team_id: int) -> dict[str, Any]:
        team = self.db.get(Team, team_id)
        if not team:
            raise AIAnalysisError('Time não encontrado')

        standings_rows = (
            self.db.query(StandingRow, Competition.name.label('competition_name'))
            .join(Competition, Competition.id == StandingRow.competition_id)
            .filter(StandingRow.team_id == team_id)
            .order_by(StandingRow.updated_at.desc())
            .all()
        )
        player_rows = (
            self.db.query(Player, PlayerStats)
            .outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id)
            .filter(Player.team_id == team_id)
            .order_by(PlayerStats.rating.desc().nullslast(), PlayerStats.goals.desc().nullslast(), Player.name.asc())
            .limit(35)
            .all()
        )
        matches = (
            self.db.query(Match)
            .filter(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
            .order_by(Match.start_time.desc().nullslast())
            .limit(20)
            .all()
        )
        avg_rating = (
            self.db.query(func.avg(PlayerStats.rating))
            .join(Player, Player.player_id == PlayerStats.player_id)
            .filter(Player.team_id == team_id, PlayerStats.rating.isnot(None))
            .scalar()
        )

        context = {
            'time': self._team_dict(team),
            'rating_medio_elenco': round(float(avg_rating), 2) if avg_rating else None,
            'classificacao': [
                self._standing_dict(row, competition_name)
                for row, competition_name in standings_rows
            ],
            'principais_jogadores': [
                self._player_dict(player, stats)
                for player, stats in player_rows
            ],
            'ultimos_jogos': [self._match_dict(match) for match in matches],
        }
        analysis = self._generate(
            title=f'Análise do time {team.name}',
            context=context,
            task=(
                'Produza uma análise executiva do time, incluindo momento competitivo, pontos fortes, '
                'fragilidades observáveis, destaques individuais, leitura da tabela, últimos resultados e recomendações práticas. '
                'Use apenas os dados fornecidos; quando algum dado estiver ausente, indique a limitação.'
            ),
        )
        return {'scope': 'team', 'entity_id': team_id, 'title': f'Análise de {team.name}', 'analysis': analysis, 'context': context}

    def analyze_player(self, player_id: int) -> dict[str, Any]:
        player = self.db.get(Player, player_id)
        if not player:
            raise AIAnalysisError('Jogador não encontrado')

        stats = (
            self.db.query(PlayerStats)
            .filter(PlayerStats.player_id == player_id)
            .order_by(PlayerStats.updated_at.desc())
            .first()
        )
        team = player.team
        team_standing = None
        if team:
            team_standing = (
                self.db.query(StandingRow, Competition.name.label('competition_name'))
                .join(Competition, Competition.id == StandingRow.competition_id)
                .filter(StandingRow.team_id == team.team_id)
                .order_by(StandingRow.updated_at.desc())
                .first()
            )
        recent_matches = []
        if team:
            recent_matches = (
                self.db.query(Match)
                .filter(or_(Match.home_team_id == team.team_id, Match.away_team_id == team.team_id))
                .order_by(Match.start_time.desc().nullslast())
                .limit(10)
                .all()
            )

        context = {
            'jogador': self._player_dict(player, stats),
            'time': self._team_dict(team),
            'classificacao_time': self._standing_dict(team_standing[0], team_standing[1]) if team_standing else None,
            'ultimos_jogos_do_time': [self._match_dict(match) for match in recent_matches],
        }
        analysis = self._generate(
            title=f'Análise do jogador {player.name}',
            context=context,
            task=(
                'Analise o desempenho individual do jogador, destacando produtividade, regularidade, encaixe tático provável, '
                'riscos, pontos de atenção e comparação qualitativa com o contexto do time. '
                'Não invente estatísticas que não estejam no contexto.'
            ),
        )
        return {'scope': 'player', 'entity_id': player_id, 'title': f'Análise de {player.name}', 'analysis': analysis, 'context': context}

    def analyze_match(self, match_id: int) -> dict[str, Any]:
        match = self.db.get(Match, match_id)
        if not match:
            raise AIAnalysisError('Jogo não encontrado')

        home_top = self._top_players_for_team(match.home_team_id, limit=12) if match.home_team_id else []
        away_top = self._top_players_for_team(match.away_team_id, limit=12) if match.away_team_id else []
        context = {
            'jogo': self._match_dict(match),
            'classificacao_mandante': self._latest_standing(match.home_team_id) if match.home_team_id else None,
            'classificacao_visitante': self._latest_standing(match.away_team_id) if match.away_team_id else None,
            'destaques_mandante': home_top,
            'destaques_visitante': away_top,
        }
        analysis = self._generate(
            title='Análise de partida',
            context=context,
            task=(
                'Produza um insight da partida com leitura de confronto, momento das equipes, jogadores-chave, '
                'fatores que podem explicar o resultado quando já houver placar e pontos de atenção quando a partida ainda não estiver finalizada.'
            ),
        )
        return {'scope': 'match', 'entity_id': match_id, 'title': 'Análise de partida', 'analysis': analysis, 'context': context}

    def compare_players(self, player_ids: list[int]) -> dict[str, Any]:
        if len(player_ids) < 2:
            raise AIAnalysisError('Informe pelo menos dois jogadores para comparação')
        if len(player_ids) > 8:
            raise AIAnalysisError('Compare no máximo oito jogadores por vez')

        rows = (
            self.db.query(Player, Team.name.label('team_name'), PlayerStats)
            .outerjoin(Team, Team.team_id == Player.team_id)
            .outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id)
            .filter(Player.player_id.in_(player_ids))
            .all()
        )
        if len(rows) < 2:
            raise AIAnalysisError('Jogadores insuficientes encontrados para comparação')

        context = {
            'jogadores': [
                self._player_dict(player, stats, team_name=team_name)
                for player, team_name, stats in rows
            ]
        }
        analysis = self._generate(
            title='Comparação de jogadores',
            context=context,
            task=(
                'Compare os jogadores de forma objetiva, apontando quem se destaca em rating, gols, assistências, volume de jogo, '
                'perfil defensivo/ofensivo e possível melhor escolha conforme diferentes critérios. Use uma conclusão clara.'
            ),
        )
        return {'scope': 'player_comparison', 'entity_id': None, 'title': 'Comparação com IA', 'analysis': analysis, 'context': context}

    def dashboard_insight(self, competition_id: int | None = None) -> dict[str, Any]:
        competition = self.db.get(Competition, competition_id) if competition_id else None

        players_query = self.db.query(Player, Team.name.label('team_name'), PlayerStats).outerjoin(Team, Team.team_id == Player.team_id).outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id)
        standings_query = self.db.query(StandingRow, Team, Competition).join(Team, Team.team_id == StandingRow.team_id).join(Competition, Competition.id == StandingRow.competition_id)
        matches_query = self.db.query(Match)
        if competition_id:
            players_query = players_query.filter(or_(PlayerStats.competition_id == competition_id, Team.primary_competition_id == competition_id))
            standings_query = standings_query.filter(StandingRow.competition_id == competition_id)
            matches_query = matches_query.filter(Match.competition_id == competition_id)

        top_rating = players_query.order_by(PlayerStats.rating.desc().nullslast(), Player.name.asc()).limit(12).all()
        top_goals = players_query.order_by(PlayerStats.goals.desc().nullslast(), Player.name.asc()).limit(12).all()
        top_assists = players_query.order_by(PlayerStats.assists.desc().nullslast(), Player.name.asc()).limit(12).all()
        standings = standings_query.order_by(Competition.name.asc(), StandingRow.position.asc().nullslast()).limit(30).all()
        recent_matches = matches_query.order_by(Match.start_time.desc().nullslast()).limit(20).all()

        context = {
            'competicao': self._competition_dict(competition) if competition else 'Todas as competições',
            'totais': {
                'times': self.db.query(Team).count(),
                'jogadores': self.db.query(Player).count(),
                'jogos': matches_query.count(),
                'linhas_estatisticas': self.db.query(PlayerStats).count(),
            },
            'top_rating': [self._player_dict(p, s, team_name=t) for p, t, s in top_rating],
            'top_gols': [self._player_dict(p, s, team_name=t) for p, t, s in top_goals],
            'top_assistencias': [self._player_dict(p, s, team_name=t) for p, t, s in top_assists],
            'classificacao': [self._standing_dict(row, comp.name, team=team) for row, team, comp in standings],
            'jogos_recentes': [self._match_dict(match) for match in recent_matches],
        }
        analysis = self._generate(
            title='Insight geral do dashboard',
            context=context,
            task=(
                'Gere uma leitura gerencial do dashboard, resumindo tendências, times em destaque, jogadores relevantes, '
                'situação da tabela, possíveis alertas e oportunidades de acompanhamento para tomada de decisão.'
            ),
        )
        return {'scope': 'dashboard', 'entity_id': competition_id, 'title': 'Insight geral com IA', 'analysis': analysis, 'context': context}

    def _generate(self, title: str, context: dict[str, Any], task: str) -> str:
        if not settings.OPENAI_API_KEY:
            raise AIAnalysisError('OPENAI_API_KEY não configurada no ambiente do backend')

        client_kwargs: dict[str, Any] = {'api_key': settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs['base_url'] = settings.OPENAI_BASE_URL
        client = OpenAI(**client_kwargs)

        system_prompt = (
            'Você é um analista profissional de futebol brasileiro, especializado em dados da SofaScore. '
            'Responda sempre em português do Brasil, em Markdown, com tom executivo e objetivo. '
            'Use exclusivamente as informações fornecidas no JSON de contexto. Não invente fatos, placares, lesões, odds, escalações ou dados ausentes. '
            'Quando os dados forem insuficientes, diga explicitamente o que falta. '
            'Organize a resposta com seções curtas, destaques acionáveis e uma conclusão prática.'
        )
        user_prompt = (
            f'# {title}\n\n'
            f'## Tarefa\n{task}\n\n'
            '## Contexto estruturado em JSON\n'
            f'{json.dumps(self._json_safe(context), ensure_ascii=False, indent=2)}\n\n'
            '## Formato esperado\n'
            'Forneça: 1) resumo executivo; 2) evidências numéricas; 3) interpretação; 4) alertas/limitações; 5) conclusão prática.'
        )
        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
            )
        except OpenAIError as exc:
            raise AIAnalysisError(f'Falha ao consultar OpenAI: {exc}') from exc
        except Exception as exc:  # pragma: no cover - proteção operacional para produção
            raise AIAnalysisError(f'Falha inesperada na análise com IA: {exc}') from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise AIAnalysisError('A OpenAI retornou uma resposta vazia')
        return content.strip()

    def _top_players_for_team(self, team_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
        if not team_id:
            return []
        rows = (
            self.db.query(Player, PlayerStats)
            .outerjoin(PlayerStats, PlayerStats.player_id == Player.player_id)
            .filter(Player.team_id == team_id)
            .order_by(PlayerStats.rating.desc().nullslast(), PlayerStats.goals.desc().nullslast(), Player.name.asc())
            .limit(limit)
            .all()
        )
        return [self._player_dict(player, stats) for player, stats in rows]

    def _latest_standing(self, team_id: int | None) -> dict[str, Any] | None:
        if not team_id:
            return None
        row = (
            self.db.query(StandingRow, Competition.name.label('competition_name'))
            .join(Competition, Competition.id == StandingRow.competition_id)
            .filter(StandingRow.team_id == team_id)
            .order_by(StandingRow.updated_at.desc())
            .first()
        )
        return self._standing_dict(row[0], row[1]) if row else None

    @staticmethod
    def _dt(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _competition_dict(self, competition: Competition | None) -> dict[str, Any] | None:
        if not competition:
            return None
        return {
            'id': competition.id,
            'nome': competition.name,
            'pais': competition.country,
            'temporada': competition.season_name,
            'season_id': competition.season_id,
        }

    def _team_dict(self, team: Team | None) -> dict[str, Any] | None:
        if not team:
            return None
        return {
            'team_id': team.team_id,
            'nome': team.name,
            'nome_curto': team.short_name,
            'pais': team.country,
            'logo_url': team.logo_url,
            'competition_id': team.primary_competition_id,
            'atualizado_em': self._dt(team.updated_at),
        }

    def _player_dict(self, player: Player, stats: PlayerStats | None = None, team_name: str | None = None) -> dict[str, Any]:
        return {
            'player_id': player.player_id,
            'nome': player.name,
            'time_id': player.team_id,
            'time': team_name or (player.team.name if player.team else None),
            'posicao': player.position,
            'camisa': player.jersey_number,
            'nacionalidade': player.nationality,
            'idade': player.age,
            'altura_cm': player.height,
            'pe_preferido': player.preferred_foot,
            'valor_mercado': player.market_value,
            'estatisticas': self._stats_dict(stats),
            'atualizado_em': self._dt(player.updated_at),
        }

    def _stats_dict(self, stats: PlayerStats | None) -> dict[str, Any] | None:
        if not stats:
            return None
        return {
            'rating': stats.rating,
            'jogos': stats.matches,
            'titularidades': stats.starts,
            'minutos': stats.minutes,
            'gols': stats.goals,
            'assistencias': stats.assists,
            'finalizacoes': stats.shots,
            'finalizacoes_no_alvo': stats.shots_on_target,
            'grandes_chances_criadas': stats.big_chances_created,
            'passes_chave': stats.key_passes,
            'passes_certos': stats.accurate_passes,
            'desarmes': stats.tackles,
            'interceptacoes': stats.interceptions,
            'cortes': stats.clearances,
            'defesas': stats.saves,
            'jogos_sem_sofrer_gol': stats.clean_sheets,
            'gols_sofridos': stats.goals_conceded,
            'cartoes_amarelos': stats.yellow_cards,
            'cartoes_vermelhos': stats.red_cards,
            'competition_id': stats.competition_id,
            'season_id': stats.season_id,
            'atualizado_em': self._dt(stats.updated_at),
        }

    def _standing_dict(self, row: StandingRow, competition_name: str | None = None, team: Team | None = None) -> dict[str, Any]:
        return {
            'competicao': competition_name,
            'time': self._team_dict(team or row.team),
            'posicao': row.position,
            'jogos': row.matches,
            'vitorias': row.wins,
            'empates': row.draws,
            'derrotas': row.losses,
            'gols_pro': row.scores_for,
            'gols_contra': row.scores_against,
            'saldo_gols': row.score_diff,
            'pontos': row.points,
            'forma': row.form,
            'atualizado_em': self._dt(row.updated_at),
        }

    def _match_dict(self, match: Match) -> dict[str, Any]:
        return {
            'match_id': match.match_id,
            'competicao': match.competition.name if match.competition else None,
            'rodada': match.round_info,
            'mandante': self._team_dict(match.home_team),
            'visitante': self._team_dict(match.away_team),
            'placar_mandante': match.home_score,
            'placar_visitante': match.away_score,
            'status': match.status,
            'inicio': self._dt(match.start_time),
            'local': match.venue,
            'atualizado_em': self._dt(match.updated_at),
        }

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._json_safe(val) for key, val in value.items() if val is not None}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        return value
