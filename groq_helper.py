"""
Integração com a API do Groq (llama, compatível com formato OpenAI).

Usado pra:
  1. Deixar o título da oferta mais limpo/legível
  2. Dizer se o preço parece bom comparado ao histórico
  3. Filtrar ofertas fracas (pra não floodar o grupo)

Importante: a IA NUNCA inventa specs, preço ou informação que não veio
do scraping. Ela só reorganiza/resume o que já foi extraído, e opina
sobre o preço com base no histórico que a gente mesmo guarda.
"""

import os
import json
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ATIVO = bool(GROQ_API_KEY)


def _chamar_groq(prompt: str) -> str | None:
    """Faz a chamada bruta pra API e devolve o texto de resposta (ou None se falhar)."""
    if not ATIVO:
        return None

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,  # baixo = menos "criativo", mais fiel aos dados
                "max_tokens": 300,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [groq] falha ao chamar API: {e}")
        return None


def avaliar_oferta(titulo: str, preco: str | None, categoria: str, historico_precos: list) -> dict:
    """
    Pede pra IA:
      - limpar o título (sem inventar nada)
      - dizer se o preço parece bom vs o histórico
      - decidir se vale a pena postar (filtro)

    Devolve um dict: {"titulo": str, "comentario": str, "postar": bool}
    Se a IA não estiver configurada ou falhar, devolve os dados originais
    sem filtro (postar=True), pra nunca travar o bot por causa da IA.
    """
    padrao = {"titulo": titulo, "comentario": None, "postar": True}

    if not ATIVO:
        return padrao

    contexto_precos = ""
    if historico_precos:
        contexto_precos = (
            f"Preços já vistos antes nesta categoria (mais recentes primeiro): "
            f"{', '.join(historico_precos[:15])}"
        )

    prompt = f"""Você está ajudando a filtrar e formatar ofertas de um bot de promoções de hardware/informática.

REGRAS IMPORTANTES:
- NUNCA invente especificações, preços ou informações que não foram fornecidas.
- Só use os dados abaixo. Se não tiver certeza de algo, não mencione.
- Seja direto e objetivo.

Categoria: {categoria}
Título original (pode vir bagunçado do site): {titulo}
Preço atual: {preco or "não informado"}
{contexto_precos}

Responda APENAS em JSON válido, sem markdown, no formato:
{{
  "titulo_limpo": "título reescrito de forma clara e curta, mantendo o modelo/specs originais, sem inventar nada",
  "comentario_preco": "uma frase curta dizendo se o preço parece bom comparado ao histórico, ou null se não der pra avaliar",
  "vale_a_pena_postar": true ou false (false só se for claramente irrelevante, spam, ou duplicata óbvia)
}}"""

    resposta = _chamar_groq(prompt)
    if not resposta:
        return padrao

    try:
        parsed = json.loads(resposta)
        return {
            "titulo": parsed.get("titulo_limpo") or titulo,
            "comentario": parsed.get("comentario_preco"),
            "postar": parsed.get("vale_a_pena_postar", True),
        }
    except Exception as e:
        print(f"  [groq] resposta inesperada, usando dados originais: {e}")
        return padrao
