# Promo Zeros Bot

Bot que monitora várias categorias do Promobit e posta ofertas novas
automaticamente num grupo do Telegram, rodando de graça via GitHub Actions
(a cada 5 minutos).

## Como configurar

1. Suba esse projeto pro seu repositório GitHub (`git add`, `git commit`, `git push`).

2. No repositório, vá em:
   `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   Crie os secrets:
   - `TELEGRAM_TOKEN` → o token do seu bot (do BotFather)
   - `TELEGRAM_CHAT_ID` → o id do grupo (ex: `-1004472372351`)
   - `GROQ_API_KEY` → (opcional) chave da API do Groq, pra ativar limpeza
     de título, comentário de preço e filtro de ofertas fracas.
     Pega grátis em https://console.groq.com → loga com Google/GitHub →
     menu **API Keys** → **Create API Key**. Se não configurar esse secret,
     o bot funciona normal, só sem a parte de IA.

3. Vá na aba **Actions** do repositório e habilite os workflows, se pedir.

4. Pronto. O workflow `Monitor Promobit` vai rodar automaticamente a cada
   5 minutos. Você também pode rodar manualmente clicando em
   `Actions` → `Monitor Promobit` → `Run workflow`.

## Rodando localmente (opcional, pra testar antes)

```bash
pip install -r requirements.txt

export TELEGRAM_TOKEN="seu_token_aqui"
export TELEGRAM_CHAT_ID="-1004472372351"
export GROQ_API_KEY="sua_chave_aqui"     # opcional

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

Edite a lista `CATEGORIAS` (ofertas) ou `CUPONS` no topo do `scraper.py` —
cada item é uma tupla `(nome amigável, url da categoria)`.

## Sobre a IA (Groq)

Se `GROQ_API_KEY` estiver configurado, cada oferta nova passa pela IA antes
de ser postada, que faz 3 coisas:
1. Limpa o título (sem inventar specs, só reorganiza o que já veio do site)
2. Comenta se o preço parece bom comparado ao histórico da categoria
3. Decide se vale a pena postar (filtra spam/duplicata óbvia)

Isso é **best-effort**: se a API falhar ou não tiver chave configurada, o
bot continua funcionando normalmente, só sem esse toque extra.

## Sobre os cupons

O código do cupom (tipo "MACBOOK15OFF") só aparece no site depois de clicar
em "Pegar cupom", que é carregado via JavaScript — não dá pra pegar isso
automaticamente com scraping simples. O bot avisa que saiu um cupom novo
(com o desconto e descrição), e o link já leva direto pra página — só falta
clicar em "Pegar cupom" lá pra ver o código.
