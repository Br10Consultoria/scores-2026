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
- `GET /api/v1/analytics/brasileirao/validation?season=2026`: checklist automático de 20 clubes, 380 partidas, 38 rodadas, 10 partidas por rodada, 38 jogos por clube (19 mandante e 19 visitante), IDs duplicados e partidas inválidas. Também está integrado à aba no navegador.
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

Depois de login, acesse **Projeções Brasileirão** e confira o quadro **Validação automática dos dados**, a fonte e a cobertura do calendário. A simulação só é liberada quando todos os testes de integridade são aprovados.

**Verificar pelo console sem exibir sua chave:**

```bash
docker compose exec -T backend python - <<'PY'
from app.services.football_data import get_brazil_serie_a
from app.services.league_validation import validate_calendar
from app.core.config import settings
print('Chave configurada:', bool(settings.FOOTBALL_DATA_API_KEY))
result = get_brazil_serie_a(2026)
checks = validate_calendar(result['games'], result['source'], result['updated_at'])
print('Fonte:', checks['source'], '| jogos:', checks['unique_games'], '| disputados:', checks['finished_games'])
for check in checks['checks']:
    print('OK' if check['ok'] else 'PENDENTE', '-', check['label'], check['actual'], '/', check['expected'])
PY
```

Esse comando faz consulta real à API e requer `FOOTBALL_DATA_API_KEY`. Caso a chave não esteja configurada, o painel pode usar os dados SofaScore locais, mas o comando acima retornará erro de chave ausente.

## Testes

```bash
cd backend
python -m unittest discover -s tests -v
```

Os testes usam somente a biblioteca padrão e não consultam APIs externas.

## Copa do Brasil, Libertadores, Sul-Americana e repasse de vagas 2027

A aba **Projeções Brasileirão** exibe três cards de competições, resultado de finais quando confirmado e simulador de distribuição das vagas por classificação brasileira.

### Fonte das três copas

Para Copa do Brasil, Libertadores e Sul-Americana, o sistema usa [API-Football (API-Sports)](https://www.api-football.com/). A chave não é a mesma da football-data.org.

```env
API_FOOTBALL_KEY=chave_gerada_no_painel_api_football
API_FOOTBALL_CACHE_SECONDS=3600
```

- Busca o ID da competição automaticamente em `GET /leagues?search=...`, verificando a temporada 2026.
- Busca calendário e resultados em `GET /fixtures?league={id}&season=2026`.
- Usa Redis (TTL mínimo de 15 minutos para resultados; por padrão, 60 minutos), prevenindo chamadas excessivas.
- Só reconhece campeão e vice ao identificar **uma final única concluída com vencedor inequívoco**. Se não houver final ou se o provedor não tiver cobertura, informa *em andamento / dados indisponíveis* e não fabrica campeão.
- No plano gratuito API-Football disponibiliza até 100 consultas/dia. A cobertura de 2026 deve ser confirmada na resposta da própria API.

Sem `API_FOOTBALL_KEY`, **as copas não podem ser atualizadas automaticamente**. Entretanto, o usuário pode simular os campeões manualmente, selecionando clubes da Série A.

### Regra de vagas (REC Série A 2026, artigos 6 e 7)

- Quatro vagas brasileiras para a **fase de grupos** da Libertadores via Série A e **uma à fase preliminar**.
- **Campeão da Copa do Brasil**: fase de grupos; **vice**: fase preliminar.
- Campeões brasileiros da **Libertadores 2026** e da **Sul-Americana 2026** têm acesso continental independente.
- Quando uma vaga se sobrepõe, é repassada na ordem do Brasileirão, aplicando a preferência por fase de grupos e a regra de redirecionamento da vaga direta da Copa ao vice quando aplicável.
- **Seis vagas à Sul-Americana** para os melhores clubes restantes do Brasileirão que não estejam classificados à Libertadores.
- A aplicação é **condicional** enquanto as competições não estiverem finalizadas, e não substitui decisões de elegibilidade/disciplinas da CBF/Conmebol.

Regulamento oficial: https://stcbfsiteprdimgbrs.blob.core.windows.net/img-site/cdn/REC_Brasileiro_SA_rie_A_2026_v15_12_2025_final_02692c1077.pdf

Rotas autenticadas:

- `GET /api/v1/analytics/continental?season=2026` — fonte, cobertura, copas e projeção atual.
- `POST /api/v1/analytics/continental/scenario` — recalcula com possíveis vencedores/vice da Copa do Brasil e vencedores das duas competições continentais. `ranking` recebe uma permutação dos 20 IDs para simular outra classificação final.

Exemplo sem divulgar chaves:

```json
{
  "season": 2026,
  "copa_winner": "Palmeiras",
  "copa_runner": "Grêmio",
  "libertadores_winner": "Palmeiras",
  "sulamericana_winner": "Atlético-MG",
  "use_confirmed_results": false
}
```

### Como interpretar "automático"

Os resultados das copas podem ser coletados automaticamente **após configurar a chave API-Football**; o cálculo dos repasses de vagas acontece automaticamente a partir dos resultados confirmados. Caso as finais estejam pendentes, o módulo apresenta uma previsão condicional e permite palpites, identificados claramente como simulação. O cenário inicial considera a classificação **atual**, e o botão opcional permite empregar a classificação final projetada pelo Monte Carlo.

### Fallback para erro 403 da SofaScore

A sincronização existente continua tentando a SofaScore. Quando a coleta estrutural da Série A falha, e `FOOTBALL_DATA_API_KEY` está configurada, o backend tenta gravar **times, classificação e calendário do Brasileirão** da football-data.org no PostgreSQL. Os IDs dos dois provedores ficam separados para evitar colisões. Isso **não substitui estatísticas avançadas de jogadores e goleiros**.

Após atualizar:

```bash
cd /opt/scores-2026
git pull origin main
nano .env
docker compose up -d --build backend frontend
docker compose logs --tail=100 backend
```

Depois da atualização, acione **Sincronizar** no painel e aguarde a mensagem de conclusão. O sistema recarrega os dados sob comando do usuário; a sincronização da SofaScore é em segundo plano.

#### Checagem segura das copas dentro do container

```bash
docker compose exec -T backend python - <<'PY'
from app.services.api_football_cups import load_cup_statuses
for key, result in load_cup_statuses().items():
    print(key, result['status'], 'jogos:', result['matches'], 'campeão:', result['champion'])
PY
```

Nenhum token aparece nessa saída. O HTTP 403 da SofaScore pode continuar até o fornecedor autorizar o acesso; não tente contornar bloqueios por scraping agressivo.

#### Segurança do .env

O token usado na Copa é **API_FOOTBALL_KEY**, diferente de **FOOTBALL_DATA_API_KEY**. Nunca compartilhe os valores em chat ou commits. Após exposição, revogue e gere novas credenciais. Prefira `CORS_ORIGIN_REGEX=` vazio em produção e `CORS_ORIGINS` com a URL HTTPS exata. Atualizar `FIRST_SUPERUSER_PASSWORD` no arquivo depois que o usuário já foi criado **não redefine a senha armazenada no banco**.

## Jogadores, artilharia e estatísticas individuais (API-Football)

A SofaScore continua opcional: em caso de `HTTP 403`, a coleta de jogadores pode ocorrer por `API_FOOTBALL_KEY`, a **mesma chave utilizada para as três copas**, e não pela `FOOTBALL_DATA_API_KEY`.

Aba **Jogadores → Coleta de jogadores · API-Football → Sincronizar jogadores**.

No `.env`:

```env
API_FOOTBALL_KEY=seu_token_privado
API_FOOTBALL_SERIE_A_LEAGUE_ID=71
API_FOOTBALL_PLAYERS_PAGES_PER_SYNC=8
```

A função é **manual e paginada**: cada execução solicita até oito páginas da temporada 2026, grava as informações no PostgreSQL e guarda a próxima página, permitindo continuar a coleta sem recomeçar do zero. A requisição é assíncrona no backend. A atualização usa cache Redis de 6 horas e intervalo entre chamadas, respeitando o limite de 10 por minuto. A coleta também tenta buscar os 20 primeiros artilheiros e os 20 primeiros assistentes por endpoints dedicados, mesmo enquanto o elenco completo estiver parcialmente coletado.

Rotas:

- `GET /api/v1/players-source/status`: disponibilidade da chave, atletas e estatísticas no banco, progresso e última mensagem.
- `POST /api/v1/players-source/sync?pages=8`: restrita a administradores; executa coleta em segundo plano (limite de 15 páginas por execução).
- `GET /api/v1/sofascore/players` e `GET /api/v1/sofascore/players/{id}`: continuam sendo os mesmos endpoints do frontend, agora com registros originados da API-Football.

Estatísticas importadas conforme disponibilização: foto do atleta, time, idade, posição, nacionalidade, jogos, titularidades, minutos, gols, assistências, rating, finalizações, chutes no alvo, passes-chave, desarmes, interceptações, cartões, defesas e gols sofridos pelo goleiro. Dados ausentes permanecem nulos; **não devem ser confundidos com zero**. A API gratuita pode não fornecer a temporada atual ou os atributos detalhados de cada competição. O painel informa a indisponibilidade quando a API não fornece resultados. IDs de jogadores e clubes são segregados por fornecedor para evitar colisão.

**Atenção:** se a primeira importação estiver incompleta, os rankings e análises podem usar apenas uma amostra de atletas; a UI identifica o progresso. Para cobranças de alto volume, acompanhe os headers e o consumo da conta API-Football, pois o plano gratuito limita a 100 requisições/dia.

Após `git pull` e recriação do backend, a nova tabela de progresso `player_import_checkpoints` é criada automaticamente pelo `Base.metadata.create_all` na inicialização, sem excluir dados existentes. Caso já tenha executado a coleta anterior, basta atualizar o servidor, abrir Jogadores e iniciar a importação.
