# Promo Zeros Bot

Bot que monitora várias categorias do Promobit e posta ofertas novas
automaticamente num grupo do Telegram, rodando de graça via GitHub Actions
(a cada 5 minutos).

## Como configurar

1. Suba esse projeto pro seu repositório GitHub (`git add`, `git commit`, `git push`).

2. No repositório, vá em:
   `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   Crie dois secrets:
   - `TELEGRAM_TOKEN` → o token do seu bot (do BotFather)
   - `TELEGRAM_CHAT_ID` → o id do grupo (ex: `-1004472372351`)

3. Vá na aba **Actions** do repositório e habilite os workflows, se pedir.

4. Pronto. O workflow `Monitor Promobit` vai rodar automaticamente a cada
   5 minutos. Você também pode rodar manualmente clicando em
   `Actions` → `Monitor Promobit` → `Run workflow`.

## Rodando localmente (opcional, pra testar antes)

```bash
pip install -r requirements.txt

export TELEGRAM_TOKEN="seu_token_aqui"
export TELEGRAM_CHAT_ID="-1004472372351"

python scraper.py
```

## Como funciona

- `scraper.py` acessa cada URL de categoria listada no início do arquivo,
  extrai as ofertas (id, título, preço, link) e compara com o que já foi
  visto antes (guardado em `data/<categoria>.json`).
- Ofertas novas são enviadas pro grupo do Telegram.
- O próprio workflow do GitHub Actions faz commit do histórico atualizado
  a cada execução, então não precisa de banco de dados externo.

## Adicionando/removendo categorias

Edite a lista `CATEGORIAS` no topo do `scraper.py` — cada item é uma tupla
`(nome amigável, url da categoria)`.
