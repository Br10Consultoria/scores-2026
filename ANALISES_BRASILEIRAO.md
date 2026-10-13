# Módulo de análises do Brasileirão 2026

A aba **Projeções Brasileirão** foi integrada ao frontend do Scores 2026.

## Fontes e atualização automática

1. **football-data.org** é a fonte preferencial da Série A. A competição `BSA` está na cobertura gratuita (confira o plano e os termos antes de redistribuir dados). Os jogos são consultados via `GET /v4/competitions/BSA/matches?season=2026`. A resposta é armazenada por 30 minutos no Redis. Uma nova consulta ao painel atualiza automaticamente o cache quando expirado.
2. **SofaScore (banco local)** é fallback quando a chave não está definida ou a fonte anterior não responde. A coleta existente não é modificada. O SofaScore pode ter apenas parte do calendário, caso em que o painel informa cobertura incompleta e **não produz probabilidades**.

No `.env`, configure:

```env
FOOTBALL_DATA_API_KEY=seu_token_da_football_data_org
FOOTBALL_DATA_CACHE_SECONDS=1800
```

Obtenha o token em https://www.football-data.org/client/register . A chave fica exclusivamente no backend.

### Endpoints (JWT necessário)

- `GET /api/v1/analytics/brasileirao?season=2026`: tabela, turno, returno, casa, fora, últimos cinco, partidas restantes, cobertura e origem dos dados.
- `POST /api/v1/analytics/brasileirao/simulate`: simulação Monte Carlo (entre 100 e 10 mil execuções). Exemplo:

```json
{
  "season": 2026,
  "runs": 2000,
  "seed": 2026,
  "libertadores_places": 9,
  "sula_places": 6,
  "overrides": {
    "fd-123456": "H",
    "fd-123457": "D"
  }
}
```

Em `overrides`, `H` é vitória do mandante, `D` empate e `A` vitória do visitante. Os IDs devem ser retirados de `fixtures[].id`. O frontend apresenta escolhas 1 / X / 2 para cada partida.

## Interpretação

- Os cálculos de **pontos**, partidas, aproveitamento, placares, turnos, mando e returno são feitos a partir de jogos finalizados.
- O simulador utiliza pesos para pontos por jogo gerais (38%), mando (34%), returno (18%) e últimos cinco jogos (10%). Estes pesos são **heurísticos**, não calibrados cientificamente.
- O modelo simplifica os critérios de desempate e não considera lesões, cartões, escalações, mercado ou força estimada por xG.
- O campo **G4–G12** é apenas um cenário hipotético de distribuição de vagas pela tabela. A combinação efetiva de campeões da Copa do Brasil, da Libertadores e da Sul-Americana deve ser ajustada manualmente segundo regras e elegibilidade aplicáveis. O sistema não alega interpretar automaticamente o regulamento.
- Não projetar rebaixamento com segurança quando a base não contiver **380 partidas, 20 clubes e 38 jogos por equipe**. Nessa situação, a API retorna erro para a simulação, e a UI continua exibindo os dados parciais.

## Deploy

Sem mudanças destrutivas no banco:

```bash
cd /opt/scores-2026
git pull origin main
nano .env        # ajuste FOOTBALL_DATA_API_KEY, se desejar
docker compose up -d --build backend frontend
docker compose logs --tail=50 backend frontend
```

Depois de login, acesse **Projeções Brasileirão** e confirme a fonte e a cobertura de dados na parte superior.

## Testes

```bash
cd backend
python -m unittest discover -s tests -v
```

Os testes usam somente a biblioteca padrão e não consultam APIs externas.
