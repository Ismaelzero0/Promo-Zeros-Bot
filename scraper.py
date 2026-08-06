"""
Promo Zeros Bot
----------------
Faz scraping de várias categorias do Promobit e posta ofertas novas
(que ainda não foram enviadas antes) num grupo do Telegram.

Variáveis de ambiente necessárias:
  TELEGRAM_TOKEN  -> token do bot (BotFather)
  TELEGRAM_CHAT_ID -> id do grupo/canal (ex: -1001234567890)
"""

import os
import re
import json
import time
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("ERRO: defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID como variáveis de ambiente.")
    sys.exit(1)

# Lista de categorias monitoradas: (nome_amigavel, url)
CATEGORIAS = [
    ("Informática", "https://www.promobit.com.br/promocoes/informatica/"),
    ("Últimas Ofertas", "https://www.promobit.com.br/promocoes/ultimas-ofertas/"),
    ("Hardware e Periféricos", "https://www.promobit.com.br/promocoes/hardware-perifericos/s/"),
    ("Gabinete", "https://www.promobit.com.br/promocoes/gabinete/s/"),
    ("HD e SSD", "https://www.promobit.com.br/promocoes/hd-ssd/s/"),
    ("Headset", "https://www.promobit.com.br/promocoes/headset/s/"),
    ("Impressoras e Multifuncionais", "https://www.promobit.com.br/promocoes/impressoras-multifuncionais/s/"),
    ("Memória RAM", "https://www.promobit.com.br/promocoes/memoria-ram/s/"),
    ("Monitor", "https://www.promobit.com.br/promocoes/monitor/s/"),
    ("PC Gamer", "https://www.promobit.com.br/promocoes/pc-gamer/s/"),
    ("Placa de Vídeo", "https://www.promobit.com.br/promocoes/placa-video/s/"),
    ("Placa Mãe", "https://www.promobit.com.br/promocoes/placa-mae/s/"),
    ("Processador", "https://www.promobit.com.br/promocoes/processador/s/"),
    ("Roteador e Repetidor", "https://www.promobit.com.br/promocoes/roteador-e-repetidor/s/"),
    ("Teclado e Mouse", "https://www.promobit.com.br/promocoes/teclado-mouse/s/"),
    ("Webcam", "https://www.promobit.com.br/promocoes/webcam/s/"),
    ("Projetores", "https://www.promobit.com.br/promocoes/projetores/s/"),
    ("Fone de Ouvido", "https://www.promobit.com.br/promocoes/fone-de-ouvido/s/"),
    ("TV", "https://www.promobit.com.br/promocoes/tv/s/"),
    ("Cupom Mercado Livre", "https://www.promobit.com.br/cupons/loja/mercado-livre/"),
    ("Cupom Amazon", "https://www.promobit.com.br/cupons/loja/amazon/"),
    ("Cupom Shopee", "https://www.promobit.com.br/cupons/loja/shopee/"),
    ("Cupom AliExpress", "https://www.promobit.com.br/cupons/loja/aliexpress/"),
    ("Cupom Netshoes", "https://www.promobit.com.br/cupons/loja/netshoes/"),
    ("Cupom KaBuM!", "https://www.promobit.com.br/cupons/loja/kabum/"),
    ("Cupom Nike", "https://www.promobit.com.br/cupons/loja/nike/"),
    ("Cupom Loja LG", "https://www.promobit.com.br/cupons/loja/loja-lg/"),
    ("Whey Protein", "https://www.promobit.com.br/promocoes/whey-protein/s/"),
]

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

OFERTA_HREF_RE = re.compile(r"/oferta/[\w-]+-(\d+)/?$")
PRICE_RE = re.compile(r"R\$\s?[\d\.]+,\d{2}")


# ----------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------

def slugify(nome: str) -> str:
    """Transforma o nome da categoria num nome de arquivo seguro."""
    s = nome.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def carregar_vistos(categoria_slug: str) -> set:
    arquivo = DATA_DIR / f"{categoria_slug}.json"
    if arquivo.exists():
        try:
            return set(json.loads(arquivo.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def salvar_vistos(categoria_slug: str, vistos: set):
    arquivo = DATA_DIR / f"{categoria_slug}.json"
    # guarda só os últimos 500 ids pra não crescer pra sempre
    lista = list(vistos)[-500:]
    arquivo.write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")


def buscar_ofertas(url: str):
    """Baixa a página e devolve uma lista de ofertas encontradas."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ofertas = []
    vistos_local = set()

    for a in soup.find_all("a", href=True):
        m = OFERTA_HREF_RE.search(a["href"])
        if not m:
            continue

        oferta_id = m.group(1)
        if oferta_id in vistos_local:
            continue
        vistos_local.add(oferta_id)

        link = a["href"]
        if link.startswith("/"):
            link = "https://www.promobit.com.br" + link

        # título: tenta pegar do alt da imagem (mais limpo)
        titulo = None
        img = a.find("img")
        if img and img.get("alt"):
            titulo = img["alt"].replace("Imagem da oferta", "").strip()

        texto_completo = a.get_text(" ", strip=True)

        if not titulo:
            # fallback: pega o texto até o primeiro "R$"
            corte = texto_completo.split("R$")[0].strip()
            titulo = corte[:150] if corte else "Oferta Promobit"

        precos = PRICE_RE.findall(texto_completo)
        preco_atual = precos[-1] if precos else None

        ofertas.append(
            {
                "id": oferta_id,
                "titulo": titulo,
                "link": link,
                "preco": preco_atual,
            }
        )

    return ofertas


def enviar_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, data=payload, timeout=20)
    if not resp.ok:
        print(f"Erro ao enviar mensagem: {resp.status_code} - {resp.text}")
    return resp.ok


def formatar_mensagem(categoria: str, oferta: dict) -> str:
    partes = [f"🔥 <b>{oferta['titulo']}</b>"]
    if oferta["preco"]:
        partes.append(f"💰 {oferta['preco']}")
    partes.append(f"📂 {categoria}")
    partes.append(oferta["link"])
    return "\n".join(partes)


# ----------------------------------------------------------------------
# Execução principal
# ----------------------------------------------------------------------

def main():
    total_novas = 0

    for nome_categoria, url in CATEGORIAS:
        slug = slugify(nome_categoria)
        print(f"Checando: {nome_categoria} ({url})")

        try:
            ofertas = buscar_ofertas(url)
        except Exception as e:
            print(f"  falha ao acessar {url}: {e}")
            continue

        vistos = carregar_vistos(slug)
        novas = [o for o in ofertas if o["id"] not in vistos]

        if not novas:
            print(f"  nenhuma oferta nova ({len(ofertas)} encontradas no total)")
            continue

        print(f"  {len(novas)} oferta(s) nova(s) encontrada(s)")

        # posta as novas (mais antiga primeiro, pra manter ordem cronológica)
        for oferta in reversed(novas):
            msg = formatar_mensagem(nome_categoria, oferta)
            ok = enviar_telegram(msg)
            if ok:
                total_novas += 1
            vistos.add(oferta["id"])
            time.sleep(1.5)  # evita rate limit do Telegram

        salvar_vistos(slug, vistos)

    print(f"\nFinalizado. {total_novas} oferta(s) enviada(s) no total.")


if __name__ == "__main__":
    main()
