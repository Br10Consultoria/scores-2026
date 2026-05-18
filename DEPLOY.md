# Guia de Deploy — Scores 2026

Este documento descreve como publicar o **Scores 2026** em um servidor próprio, sem hospedagem Manus. A stack foi preparada para execução com **Docker Compose**, com backend FastAPI, frontend React/Nginx, PostgreSQL, Redis e um serviço opcional para o bot Telegram.

## 1. Pré-requisitos do servidor

O servidor deve possuir Docker, Docker Compose, Git e acesso de saída à internet para consultar a API pública da SofaScore. Recomenda-se Ubuntu Server 22.04/24.04 LTS, ao menos 2 GB de RAM e firewall liberando somente as portas necessárias.

| Serviço | Porta interna | Porta publicada | Observação |
| --- | ---: | ---: | --- |
| Frontend | 80 | 8080 | Interface web React servida via Nginx. |
| Backend | 8000 | 8000 | API FastAPI. Em produção, coloque atrás de proxy reverso HTTPS. |
| PostgreSQL | 5432 | 5432 | Pode ser removido da publicação externa se usado apenas internamente. |
| Redis | 6379 | 6379 | Pode ser removido da publicação externa se usado apenas internamente. |

> Em produção, a recomendação é expor publicamente apenas o proxy reverso HTTPS, mantendo PostgreSQL e Redis acessíveis somente dentro da rede Docker ou rede privada do servidor.

## 2. Configuração inicial

Clone o repositório no servidor, copie o arquivo de ambiente e edite as senhas e chaves.

```bash
git clone <URL_DO_REPOSITORIO> scores-2026
cd scores-2026
cp .env.example .env
nano .env
```

Defina, no mínimo, `POSTGRES_PASSWORD`, `SECRET_KEY`, `FIRST_SUPERUSER_PASSWORD`, `CORS_ORIGINS` e `VITE_API_URL`. Para produção com domínio próprio, um exemplo típico seria:

```env
CORS_ORIGINS=https://scores.seudominio.com
VITE_API_URL=https://api.scores.seudominio.com/api/v1
SECRET_KEY=gere_uma_chave_longa_aleatoria
FIRST_SUPERUSER_EMAIL=admin@seudominio.com
FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_PASSWORD=troque_antes_do_primeiro_acesso
TZ=America/Bahia
```

## 3. Subida dos serviços

Para subir apenas a aplicação web com banco e cache:

```bash
docker compose up -d --build
```

Para subir também o bot Telegram:

```bash
docker compose --profile telegram up -d --build
```

Após a primeira subida, acesse:

| Recurso | URL local padrão |
| --- | --- |
| Interface web | `http://SEU_SERVIDOR:8080` |
| API | `http://SEU_SERVIDOR:8000` |
| Documentação OpenAPI | `http://SEU_SERVIDOR:8000/docs` |

## 4. Autenticação e 2FA

O sistema cria um superusuário inicial a partir das variáveis `FIRST_SUPERUSER_*`. O login usa usuário/senha e JWT. O segundo fator usa **TOTP**, compatível com Google Authenticator, Microsoft Authenticator, 1Password, Bitwarden e aplicativos similares.

O fluxo esperado é: fazer login com o usuário inicial, acessar a área de segurança, gerar o segredo TOTP, cadastrar no aplicativo autenticador, confirmar o código e passar a informar o código 2FA no login quando solicitado.

## 5. Coleta SofaScore

A coleta utiliza a API pública da SofaScore configurada por estas variáveis:

| Variável | Finalidade |
| --- | --- |
| `SOFASCORE_BASE_URL` | URL base da API pública. |
| `SOFASCORE_TOURNAMENT_ID` | Identificador do torneio. O padrão foi configurado para Brasileirão Série A. |
| `SOFASCORE_SEASON_ID` | Identificador da temporada. |
| `SOFASCORE_USER_AGENT` | Cabeçalho de navegador usado na requisição. |
| `SOFASCORE_REFERER` | Referer usado na requisição. |
| `SOFASCORE_COOKIE` | Cookie opcional se a SofaScore bloquear o IP do servidor com 403. |

Se a SofaScore retornar **403 Forbidden**, configure `SOFASCORE_COOKIE` com um cookie de sessão válido obtido em navegador autorizado e revise o `SOFASCORE_REFERER`. Esse comportamento depende de políticas externas da SofaScore e pode variar por IP, região e data.

A sincronização manual pode ser disparada pela API autenticada em:

```text
POST /api/v1/sofascore/sync
```

## 6. Agendamento em servidor próprio

Como a execução é determinística e deve rodar no servidor do usuário, o agendamento recomendado é via **cron do próprio servidor**, sem qualquer dependência de execução Manus. Um exemplo para sincronizar semanalmente às segundas-feiras, 06:00 no fuso `America/Bahia`, é:

```cron
TZ=America/Bahia
0 6 * * 1 cd /caminho/scores-2026 && docker compose exec -T backend python -c "from app.database import SessionLocal; from app.services.sofascore import sync_teams_and_players; db=SessionLocal(); print(sync_teams_and_players(db)); db.close()" >> /var/log/scores2026-sync.log 2>&1
```

## 7. Telegram

Para ativar o Telegram, crie um bot no BotFather, configure `TELEGRAM_BOT_TOKEN` e, por segurança, restrinja os chats autorizados em `TELEGRAM_ALLOWED_CHAT_IDS`.

```env
TELEGRAM_BOT_TOKEN=123456:token_do_bot
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-1001234567890
```

Suba o perfil do Telegram:

```bash
docker compose --profile telegram up -d --build telegram
```

O bot possui comandos de consulta administrativa, como `/start`, `/resumo` e comandos de status/relatórios implementados no backend.

## 8. Relatórios e estatísticas

A interface web possui dashboard responsivo com totais, rankings e gráficos. A API expõe também relatório CSV autenticado em:

```text
GET /api/v1/reports/players.csv
```

Esse arquivo pode ser baixado pela área administrativa ou consumido por ferramentas externas de BI.

## 9. Proxy reverso e HTTPS

Para produção, utilize Nginx, Traefik ou Caddy na frente dos serviços. Um desenho recomendado é:

| Domínio | Destino interno |
| --- | --- |
| `scores.seudominio.com` | `http://127.0.0.1:8080` |
| `api.scores.seudominio.com` | `http://127.0.0.1:8000` |

Depois de configurar HTTPS, atualize `CORS_ORIGINS` e `VITE_API_URL`, então reconstrua o frontend:

```bash
docker compose up -d --build frontend backend
```

## 10. Manutenção

Use os comandos abaixo para operação diária:

```bash
# Ver logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose --profile telegram logs -f telegram

# Atualizar aplicação
git pull
docker compose up -d --build

# Backup PostgreSQL
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_scores2026.sql
```

Antes de expor em produção, altere todas as senhas padrão, gere uma `SECRET_KEY` forte, limite portas públicas no firewall e use HTTPS obrigatório.
