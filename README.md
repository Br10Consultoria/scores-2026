# Scores 2026

**Scores 2026** é um sistema web profissional para coleta, organização e análise de dados da SofaScore. O projeto inclui autenticação por usuário/senha, autenticação de dois fatores, painel responsivo, relatórios estatísticos, exportação CSV e integração com Telegram. A solução foi preparada para execução em **servidor próprio**, usando Docker Compose, PostgreSQL e Redis, sem dependência de hospedagem Manus.

## Recursos implementados

| Área | Recursos |
| --- | --- |
| Segurança | Login com usuário/senha, hash bcrypt, JWT e autenticação 2FA via TOTP. |
| Dados | Coleta ampliada da SofaScore para Série A e Série B, incluindo competições, standings/tabelas, times, escudos, elencos, jogadores, jogos, resultados e estatísticas disponíveis. |
| Banco | PostgreSQL com modelos para usuários, competições, times, jogadores, estatísticas por competição, standings, partidas, registros brutos SofaScore, execuções de coleta e Telegram. |
| Interface | Frontend React responsivo com abas clicáveis, filtros por competição/time/mês/status, cards, gráficos com legendas, tabela classificatória, jogos, rankings e modais de detalhes de times e jogadores. |
| Relatórios | Dashboard estatístico, rankings de rating/gols/assistências, distribuição por posição, partidas por mês, standings, datas de atualização e exportação CSV autenticada em `/api/v1/reports/players.csv`. |
| Telegram | Bot com comandos administrativos, consulta de indicadores e sincronização protegida por lista de chats permitidos. |
| Deploy | Docker Compose com backend FastAPI, frontend Nginx, PostgreSQL, Redis e perfil opcional para Telegram. |

## Estrutura do projeto

| Caminho | Finalidade |
| --- | --- |
| `backend/` | API FastAPI, modelos SQLAlchemy, autenticação, coleta SofaScore, relatórios e bot Telegram. |
| `frontend/` | Interface React + TypeScript + Vite + TailwindCSS. |
| `docker-compose.yml` | Orquestração local/produção em servidor próprio. |
| `.env.example` | Modelo de configuração de ambiente. |
| `ARCHITECTURE.md` | Decisões técnicas e arquitetura da solução. |
| `DEPLOY.md` | Guia completo de deploy, operação, cron e segurança. |

## Como subir em servidor próprio

Copie o arquivo de ambiente e ajuste senhas, chaves, domínio, Telegram e SofaScore.

```bash
cp .env.example .env
nano .env
```

Suba a aplicação principal.

```bash
docker compose up -d --build
```

Para ativar também o bot Telegram:

```bash
docker compose --profile telegram up -d --build
```

Em produção, acesse a interface em `https://scores.br10consultoria.com.br`. Localmente no servidor, os containers ficam em `http://127.0.0.1:18080` (frontend) e `http://127.0.0.1:18000/docs` (API), para serem publicados pelo proxy reverso HTTPS existente.

## Usuário inicial

O primeiro usuário administrador é criado automaticamente com os dados definidos no `.env`.

| Variável | Exemplo |
| --- | --- |
| `FIRST_SUPERUSER_USERNAME` | `admin` |
| `FIRST_SUPERUSER_EMAIL` | `admin@scores.local` |
| `FIRST_SUPERUSER_PASSWORD` | `Admin@123456` |

Altere esses valores antes do primeiro deploy em produção. Depois do login, configure o 2FA via TOTP em aplicativo autenticador compatível.

## Sincronização SofaScore

A sincronização pode ser acionada no painel, pelo comando `/sync` no Telegram ou pelo endpoint autenticado:

```text
POST /api/v1/sofascore/sync
```

As principais consultas ficam em:

| Endpoint | Finalidade |
| --- | --- |
| `GET /api/v1/sofascore/competitions` | Lista competições coletadas, incluindo Série A e Série B conforme configuração. |
| `GET /api/v1/sofascore/teams` | Lista times coletados, com filtro por competição e busca textual. |
| `GET /api/v1/sofascore/teams/{team_id}` | Retorna detalhe clicável do time, elenco, tabela, jogos recentes e rating médio. |
| `GET /api/v1/sofascore/players` | Lista jogadores com filtros por busca, posição, time, competição, rating mínimo, ordenação e limite. |
| `GET /api/v1/sofascore/players/{player_id}` | Retorna detalhe clicável do jogador, estatísticas e registro bruto quando disponível. |
| `GET /api/v1/sofascore/standings` | Retorna tabela/classificação por competição, com pontos, vitórias, saldo e data de atualização. |
| `GET /api/v1/sofascore/matches` | Retorna jogos/resultados com filtros por competição, time, mês e status. |
| `GET /api/v1/sofascore/compare/players` | Compara jogadores selecionados por métricas de rating, gols, assistências e partidas. |
| `GET /api/v1/reports/dashboard` | Retorna estatísticas consolidadas para o dashboard, incluindo metadados e legendas. |
| `GET /api/v1/reports/players.csv` | Exporta relatório CSV autenticado. |

## Telegram

Configure o bot no `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:token_do_bot
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-1001234567890
```

Em seguida, suba o perfil do Telegram:

```bash
docker compose --profile telegram up -d --build telegram
```

## Deploy e operação

Consulte os arquivos [`DEPLOY.md`](DEPLOY.md) e [`PRODUCTION_DOMAIN.md`](PRODUCTION_DOMAIN.md) para instruções completas de produção, incluindo proxy reverso HTTPS para `scores.br10consultoria.com.br`, cron semanal no servidor próprio, backup do PostgreSQL, portas recomendadas e tratamento de bloqueios da SofaScore.

## Segurança em produção

Use uma `SECRET_KEY` forte, altere a senha inicial, habilite HTTPS via Nginx/Traefik/Caddy, restrinja portas internas, use firewall, limite `TELEGRAM_ALLOWED_CHAT_IDS`, mantenha backups do PostgreSQL e revise periodicamente logs de autenticação e coleta.
