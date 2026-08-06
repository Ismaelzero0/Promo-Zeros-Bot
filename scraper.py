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

import groq_helper

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
    ("Whey Protein", "https://www.promobit.com.br/promocoes/whey-protein/s/"),
]

# Cupons são tratados separado (estrutura de página diferente das ofertas)
CUPONS = [
    ("Cupom Mercado Livre", "https://www.promobit.com.br/cupons/loja/mercado-livre/"),
    ("Cupom Amazon", "https://www.promobit.com.br/cupons/loja/amazon/"),
    ("Cupom Shopee", "https://www.promobit.com.br/cupons/loja/shopee/"),
    ("Cupom AliExpress", "https://www.promobit.com.br/cupons/loja/aliexpress/"),
    ("Cupom Netshoes", "https://www.promobit.com.br/cupons/loja/netshoes/"),
    ("Cupom KaBuM!", "https://www.promobit.com.br/cupons/loja/kabum/"),
    ("Cupom Nike", "https://www.promobit.com.br/cupons/loja/nike/"),
    ("Cupom Loja LG", "https://www.promobit.com.br/cupons/loja/loja-lg/"),
]

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# trava de segurança: no máximo X mensagens novas por categoria por execução.
# evita flood se a página mudar de estrutura e "revelar" muitas ofertas de vez.
MAX_NOVAS_POR_CATEGORIA = 8

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


def carregar_vistos(categoria_slug: str) -> tuple[set, bool]:
    """Devolve (ids_vistos, eh_primeira_vez). eh_primeira_vez=True quando
    ainda não existe histórico pra essa categoria — usado pra não postar
    tudo que já tava na página de uma vez só (flood no primeiro run)."""
    arquivo = DATA_DIR / f"{categoria_slug}.json"
    if arquivo.exists():
        try:
            return set(json.loads(arquivo.read_text(encoding="utf-8"))), False
        except Exception:
            return set(), False
    return set(), True


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


CUPOM_HREF_RE = re.compile(r"/cupons?/loja/[\w-]+/?$")


def buscar_cupons(url: str):
    """
    Extrai cupons de uma página de loja do Promobit.
    IMPORTANTE: o código do cupom em si só aparece depois de clicar em
    "Pegar cupom" no site (carregado via JS), então não conseguimos pegar
    o código automaticamente. O que dá pra fazer é avisar que saiu um
    cupom novo, com o desconto e o link direto pra página.
    """
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cupons = []

    # cada cupom fica dentro de um bloco com um <h2>/<h3> de título e
    # um badge de desconto antes dele (ex: "25%", "R$ 60", "Frete grátis")
    for titulo_tag in soup.find_all(["h2", "h3"]):
        texto_titulo = titulo_tag.get_text(strip=True)
        if not texto_titulo or len(texto_titulo) < 8:
            continue

        # ignora títulos que claramente não são de cupom (ex: títulos de seção)
        if texto_titulo.lower().startswith(("perguntas frequentes", "resumo de", "informações sobre",
                                              "opiniões sobre", "melhores cupons", "cupom ")):
            continue

        # tenta achar o desconto (badge) que vem antes do título no HTML
        desconto = None
        anterior = titulo_tag.find_previous(string=re.compile(r"^\s*(\d+%|R\$\s?[\d.,]+|Frete Grátis)\s*$"))
        if anterior:
            desconto = anterior.strip()

        # gera um id estável baseado no texto do título (não muda entre execuções)
        import hashlib
        cupom_id = hashlib.md5(texto_titulo.encode("utf-8")).hexdigest()[:12]

        cupons.append(
            {
                "id": cupom_id,
                "titulo": texto_titulo,
                "desconto": desconto,
                "link": url,
            }
        )

    return cupons


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


def formatar_mensagem(categoria: str, oferta: dict, comentario_ia: str = None) -> str:
    partes = [f"🔥 <b>{oferta['titulo']}</b>"]
    if oferta["preco"]:
        partes.append(f"💰 {oferta['preco']}")
    if comentario_ia:
        partes.append(f"🤖 {comentario_ia}")
    partes.append(f"📂 {categoria}")
    partes.append(oferta["link"])
    return "\n".join(partes)


def formatar_mensagem_cupom(categoria: str, cupom: dict) -> str:
    partes = [f"🎟️ <b>{cupom['titulo']}</b>"]
    if cupom["desconto"]:
        partes.append(f"💸 {cupom['desconto']}")
    partes.append(f"📂 {categoria}")
    partes.append("👉 clique no link e depois em \"Pegar cupom\" pra ver o código")
    partes.append(cupom["link"])
    return "\n".join(partes)


# ----------------------------------------------------------------------
# Execução principal
# ----------------------------------------------------------------------

def carregar_precos(categoria_slug: str) -> list:
    """Histórico simples de preços vistos na categoria (só os textos, mais recentes primeiro)."""
    arquivo = DATA_DIR / f"{categoria_slug}_precos.json"
    if arquivo.exists():
        try:
            return json.loads(arquivo.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def salvar_precos(categoria_slug: str, precos: list):
    arquivo = DATA_DIR / f"{categoria_slug}_precos.json"
    arquivo.write_text(json.dumps(precos[:50], ensure_ascii=False), encoding="utf-8")


def main():
    total_novas = 0

    if groq_helper.ATIVO:
        print("IA (Groq) ativada — vai limpar título, comentar preço e filtrar ofertas fracas.\n")
    else:
        print("IA (Groq) desativada (sem GROQ_API_KEY) — postando sem filtro/comentário.\n")

    # ---------------- Ofertas normais ----------------
    for nome_categoria, url in CATEGORIAS:
        slug = slugify(nome_categoria)
        print(f"Checando: {nome_categoria} ({url})")

        try:
            ofertas = buscar_ofertas(url)
        except Exception as e:
            print(f"  falha ao acessar {url}: {e}")
            continue

        vistos, primeira_vez = carregar_vistos(slug)
        precos_historico = carregar_precos(slug)
        novas = [o for o in ofertas if o["id"] not in vistos]

        if primeira_vez:
            # primeira vez que essa categoria é checada: não posta o que já
            # tava na página, só marca tudo como visto e passa a monitorar
            # daqui pra frente.
            print(f"  primeira checagem desta categoria — salvando {len(ofertas)} oferta(s) sem postar")
            for o in ofertas:
                vistos.add(o["id"])
            salvar_vistos(slug, vistos)
            continue

        if not novas:
            print(f"  nenhuma oferta nova ({len(ofertas)} encontradas no total)")
            continue

        if len(novas) > MAX_NOVAS_POR_CATEGORIA:
            print(f"  {len(novas)} novas de uma vez (> limite de {MAX_NOVAS_POR_CATEGORIA}) — "
                  f"postando só as {MAX_NOVAS_POR_CATEGORIA} mais recentes pra não floodar")
            # marca as excedentes como vistas sem postar (evita reavaliar toda hora)
            for o in novas[MAX_NOVAS_POR_CATEGORIA:]:
                vistos.add(o["id"])
            novas = novas[:MAX_NOVAS_POR_CATEGORIA]
        else:
            print(f"  {len(novas)} oferta(s) nova(s) encontrada(s)")

        for oferta in reversed(novas):
            avaliacao = groq_helper.avaliar_oferta(
                titulo=oferta["titulo"],
                preco=oferta["preco"],
                categoria=nome_categoria,
                historico_precos=precos_historico,
            )

            vistos.add(oferta["id"])  # marca como visto mesmo se não postar (evita reavaliar toda hora)

            if not avaliacao["postar"]:
                print(f"  [ignorada pela IA] {oferta['titulo']}")
                continue

            oferta["titulo"] = avaliacao["titulo"]
            msg = formatar_mensagem(nome_categoria, oferta, comentario_ia=avaliacao["comentario"])
            ok = enviar_telegram(msg)
            if ok:
                total_novas += 1
            if oferta["preco"]:
                precos_historico.insert(0, oferta["preco"])
            time.sleep(1.5)  # evita rate limit do Telegram

        salvar_vistos(slug, vistos)
        salvar_precos(slug, precos_historico)

    # ---------------- Cupons ----------------
    for nome_categoria, url in CUPONS:
        slug = slugify(nome_categoria)
        print(f"Checando: {nome_categoria} ({url})")

        try:
            cupons = buscar_cupons(url)
        except Exception as e:
            print(f"  falha ao acessar {url}: {e}")
            continue

        vistos, primeira_vez = carregar_vistos(slug)
        novos = [c for c in cupons if c["id"] not in vistos]

        if primeira_vez:
            print(f"  primeira checagem desta loja — salvando {len(cupons)} cupom(ns) sem postar")
            for c in cupons:
                vistos.add(c["id"])
            salvar_vistos(slug, vistos)
            continue

        if not novos:
            print(f"  nenhum cupom novo ({len(cupons)} encontrados no total)")
            continue

        if len(novos) > MAX_NOVAS_POR_CATEGORIA:
            print(f"  {len(novos)} novos de uma vez (> limite de {MAX_NOVAS_POR_CATEGORIA}) — "
                  f"postando só os {MAX_NOVAS_POR_CATEGORIA} mais recentes pra não floodar")
            for c in novos[MAX_NOVAS_POR_CATEGORIA:]:
                vistos.add(c["id"])
            novos = novos[:MAX_NOVAS_POR_CATEGORIA]
        else:
            print(f"  {len(novos)} cupom(ns) novo(s) encontrado(s)")

        for cupom in reversed(novos):
            msg = formatar_mensagem_cupom(nome_categoria, cupom)
            ok = enviar_telegram(msg)
            if ok:
                total_novas += 1
            vistos.add(cupom["id"])
            time.sleep(1.5)

        salvar_vistos(slug, vistos)

    print(f"\nFinalizado. {total_novas} oferta(s)/cupom(ns) enviada(s) no total.")


if __name__ == "__main__":
    main()