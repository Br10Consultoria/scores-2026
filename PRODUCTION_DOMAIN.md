# Produção com domínio `scores.br10consultoria.com.br`

Este guia mostra como publicar o **Scores 2026** em `https://scores.br10consultoria.com.br` quando o servidor já possui outra aplicação usando a porta 80. A implementação foi preparada para que os containers do Scores 2026 escutem apenas em `127.0.0.1`, evitando conflito direto com portas públicas e mantendo PostgreSQL/Redis sem exposição externa.

## Modelo adotado

| Camada | Endereço no servidor | Exposição pública |
| --- | --- | --- |
| Frontend Scores 2026 | `127.0.0.1:18080` | Não expõe diretamente. O acesso vem pelo proxy HTTPS. |
| Backend Scores 2026 | `127.0.0.1:18000` | Não expõe diretamente. O acesso vem por `/api/`. |
| PostgreSQL | Rede Docker interna | Não expõe porta pública. |
| Redis | Rede Docker interna | Não expõe porta pública. |
| Proxy reverso existente | Portas públicas `80/443` | Publica `scores.br10consultoria.com.br`. |

> Se a aplicação que já usa a porta 80 roda em Nginx, Caddy, Traefik ou Apache, basta adicionar um novo virtual host para `scores.br10consultoria.com.br`. Se ela ocupa a porta 80 diretamente, será necessário colocar um proxy reverso na frente das duas aplicações ou mover a aplicação antiga para uma porta interna.

## 1. Atualizar o servidor

```bash
cd /opt/scores-2026
git pull origin main
cp .env.example .env   # use somente se ainda não existir .env
nano .env
```

No `.env`, deixe estas variáveis assim:

```env
CORS_ORIGINS=https://scores.br10consultoria.com.br
VITE_API_URL=https://scores.br10consultoria.com.br/api/v1
FRONTEND_BIND_ADDRESS=127.0.0.1
FRONTEND_PORT=18080
BACKEND_BIND_ADDRESS=127.0.0.1
BACKEND_PORT=18000
```

Depois suba os containers:

```bash
docker compose up -d --build
```

Confirme que o backend e frontend respondem localmente:

```bash
curl -I http://127.0.0.1:18080
curl -I http://127.0.0.1:18000/docs
```

## 2. Configuração com Nginx existente

Se o servidor já usa Nginx para a aplicação que ocupa a porta 80, **não instale outro proxy nas portas públicas**. Basta adicionar um novo virtual host para o domínio do Scores.

Copie o modelo HTTP inicial versionado. Ele não referencia certificado ainda inexistente, portanto permite validar o Nginx antes do Certbot:

```bash
sudo cp /opt/scores-2026/infra/nginx/scores.br10consultoria.com.br.conf /etc/nginx/sites-available/scores.br10consultoria.com.br
sudo ln -sfn /etc/nginx/sites-available/scores.br10consultoria.com.br /etc/nginx/sites-enabled/scores.br10consultoria.com.br
sudo nginx -t
sudo systemctl reload nginx
```

Gere e aplique o HTTPS com Certbot:

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d scores.br10consultoria.com.br
```

Depois valide novamente:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Acesse:

```text
https://scores.br10consultoria.com.br
```

O arquivo `infra/nginx/scores.br10consultoria.com.br.ssl.conf` também foi incluído como referência de configuração HTTPS final, caso você prefira editar manualmente em vez de deixar o Certbot ajustar o arquivo.

## 3. Configuração alternativa com Caddy

Se o Caddy for o proxy principal do servidor, incorpore o conteúdo de `infra/caddy/Caddyfile` ao Caddyfile principal do servidor e recarregue:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 4. Quando a porta 80 já está ocupada por outra aplicação

Existem dois cenários possíveis.

| Cenário | O que fazer |
| --- | --- |
| A porta 80 já é ocupada por Nginx/Caddy/Traefik/Apache | Adicione apenas o novo virtual host para `scores.br10consultoria.com.br`; não suba outro proxy nas portas 80/443. |
| A porta 80 é ocupada diretamente por um container/aplicação antiga | Mova a aplicação antiga para uma porta interna, por exemplo `127.0.0.1:18081`, e coloque Nginx/Caddy/Traefik na frente para rotear cada domínio. |

## 5. Atualização futura

```bash
cd /opt/scores-2026
git pull origin main
docker compose up -d --build
sudo nginx -t && sudo systemctl reload nginx
```

Se o Telegram estiver ativo:

```bash
docker compose --profile telegram up -d --build
```
