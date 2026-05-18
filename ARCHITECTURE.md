# Arquitetura do Sistema Scores 2026

**Autor:** Manus AI  
**Projeto:** Scores 2026  
**Objetivo:** disponibilizar um sistema web responsivo e profissional para coleta, armazenamento, análise e consulta de dados de futebol a partir da SofaScore, com autenticação forte, relatórios estatísticos, integração com Telegram e análise com IA via OpenAI, preparado para execução em servidor próprio.

## Visão geral

O sistema será implementado como uma aplicação full-stack autocontida no repositório `scores-2026`, sem dependência de hospedagem Manus. A solução usará **Docker Compose** para orquestrar backend, frontend, PostgreSQL e Redis, facilitando instalação em VPS, servidor dedicado ou ambiente on-premises. O backend exporá uma API REST protegida por autenticação JWT e 2FA via TOTP, enquanto o frontend fornecerá um painel responsivo para administração, dashboards e relatórios.

> Conforme o guia fornecido pelo usuário, o fluxo de dados recomendado é: **SofaScore → Collector Python → PostgreSQL → Redis → API → dashboards/IA/RAG**.

## Stack técnica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Backend | FastAPI + SQLAlchemy | API Python moderna, adequada para serviços REST, jobs de coleta e integração com PostgreSQL. |
| Autenticação | JWT + senha com hash bcrypt + TOTP | Permite login com usuário/senha e segundo fator por aplicativo autenticador. |
| Banco de dados | PostgreSQL | Persistência relacional dos dados de times, jogadores, partidas, estatísticas e usuários. |
| Cache e filas leves | Redis | Cache de respostas da SofaScore, controle de taxa e armazenamento temporário. |
| Frontend | React + TypeScript + Vite + TailwindCSS | Interface responsiva, rápida e profissional, com boa organização de componentes. |
| Gráficos | Recharts | Visualização de estatísticas, rankings, distribuição por posição e comparações. |
| Telegram | python-telegram-bot | Bot para consultas, status de coleta e envio de alertas. |
| IA | OpenAI API | Geração de análises textuais em português a partir dos dados persistidos no PostgreSQL. |
| Deploy | Docker Compose + Nginx opcional | Execução em servidor próprio sem plataforma gerenciada externa. |

## Módulos principais

| Módulo | Responsabilidade |
|---|---|
| `backend/app/api` | Rotas REST para autenticação, usuários, times, jogadores, estatísticas, relatórios, Telegram e endpoints de IA. |
| `backend/app/core` | Configurações, segurança, JWT, TOTP, variáveis de ambiente, OpenAI e dependências globais. |
| `backend/app/models` | Modelos SQLAlchemy para usuários, times, jogadores, estatísticas, logs de coleta e configurações. |
| `backend/app/services` | Regras de negócio, coleta SofaScore, relatórios, métricas, integração Telegram e preparação de contexto para OpenAI. |
| `backend/app/tasks` | Jobs periódicos ou comandos manuais de sincronização. |
| `frontend/src` | Aplicação React com telas de login, 2FA, dashboard, relatórios, jogadores, times e configurações. |
| `docker` | Arquivos auxiliares de inicialização, banco e proxy. |

## Modelo de dados inicial

| Tabela | Campos centrais | Finalidade |
|---|---|---|
| `users` | `id`, `email`, `username`, `hashed_password`, `is_active`, `is_superuser`, `totp_secret`, `totp_enabled` | Gerenciar usuários do sistema e 2FA. |
| `teams` | `team_id`, `name`, `slug`, `country`, `updated_at` | Armazenar times coletados da SofaScore. |
| `players` | `player_id`, `team_id`, `name`, `position`, `nationality`, `height`, `age`, `updated_at` | Armazenar jogadores vinculados aos times. |
| `player_stats` | `id`, `player_id`, `rating`, `matches`, `goals`, `assists`, `saves`, `clean_sheets`, `goals_conceded`, `season_id`, `updated_at` | Guardar estatísticas agregadas por temporada. |
| `collection_runs` | `id`, `status`, `started_at`, `finished_at`, `message` | Auditar execuções da coleta. |
| `telegram_chats` | `id`, `chat_id`, `username`, `is_allowed`, `created_at` | Controlar usuários autorizados no bot Telegram. |

## Fluxo de autenticação

O login será dividido em duas etapas. Primeiro, o usuário informa e-mail ou nome de usuário e senha. Se as credenciais forem válidas e o 2FA estiver habilitado, a API retornará um token temporário exigindo o código TOTP. Em seguida, o usuário informa o código de seis dígitos gerado no aplicativo autenticador. Após validação, a API emite o token JWT definitivo para acesso ao painel.

## Integração com SofaScore

A coleta seguirá os endpoints descritos no guia anexado, começando por `unique-tournament/325/season/58766/standings/total` para times da Série A e avançando para `/api/v1/team/{id}/players` para elenco. As requisições usarão `User-Agent`, cache Redis, retry e persistência dos IDs no PostgreSQL para evitar consultas repetitivas.

## Relatórios, estatísticas e IA

O painel terá indicadores de visão geral, rankings, comparações entre jogadores e tabelas filtráveis. A API fornecerá endpoints agregados para total de times, jogadores, média de rating, artilheiros, assistências, goleiros e distribuição por posição. O frontend exibirá os dados por cards, gráficos responsivos e tabelas.

A camada de IA foi isolada no backend em `backend/app/services/ai_analysis.py` e exposta por `backend/app/api/ai.py`. Essa decisão evita expor a chave `OPENAI_API_KEY` no navegador, permite reaproveitar a autenticação JWT existente e mantém o prompt restrito aos dados que já foram coletados e gravados no banco. O serviço monta contextos compactos para dashboard, time, jogador, partida e comparação de jogadores, e instrui o modelo a indicar limitações quando os dados públicos da SofaScore forem incompletos.

## Telegram

O bot Telegram permitirá consultas como `/status`, `/top_gols`, `/top_rating`, `/player nome`, `/sync` e `/help`. O comando de sincronização será restrito a chats autorizados. O token do bot será configurado por variável de ambiente, sem ser versionado no repositório.

## Deploy em servidor próprio

O deploy será feito com `docker compose up -d --build`. O repositório incluirá `.env.example`, `docker-compose.yml`, Dockerfiles para backend e frontend e instruções para configurar domínio, HTTPS via proxy reverso externo e rotina de atualização semanal.
