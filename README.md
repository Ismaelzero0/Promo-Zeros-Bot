# Promo Zeros Bot

Projeto que eu e uns amigos criamos pra não perder mais nenhuma promoção de hardware. O bot fica de olho em várias categorias do Promobit (placa de vídeo, processador, SSD, etc.) e manda direto no nosso grupo do Telegram assim que sai algo novo.

Roda 100% de graça via GitHub Actions, a cada 5 minutos, sem precisar de servidor.

## Stack

- Python (scraping com `requests` + `BeautifulSoup`)
- Telegram Bot API
- GitHub Actions (cron a cada 5 min)
- Groq (IA opcional pra limpar título, avaliar preço e filtrar spam)

## Setup

1. `git clone` esse repo
2. Cria os secrets no repositório (`Settings → Secrets and variables → Actions`):
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GROQ_API_KEY` (opcional — sem ele o bot funciona igual, só sem IA)
3. Habilita o Actions e pronto, roda sozinho

Pra testar local:

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
export GROQ_API_KEY="..."   # opcional
python scraper.py
```

## Como funciona

`scraper.py` varre cada categoria, extrai as ofertas e compara com o histórico salvo em `data/`. Só o que é novo é postado — e passa antes por uma camada de IA (opcional) que limpa o título, comenta se o preço tá bom com base no histórico, e corta ofertas fracas.

Cupons também são monitorados, mas o código em si só aparece com um clique no site (carregado via JS) — o bot avisa que saiu cupom novo e já manda o link direto.

## Categorias

Edita a lista `CATEGORIAS` ou `CUPONS` no topo do `scraper.py` pra adicionar/remover o que monitora.
