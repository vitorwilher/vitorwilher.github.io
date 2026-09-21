#!/usr/bin/env python3
"""Regenera newsletter/boletins.json com as edicoes mais recentes do Boletim AM.

Duas fontes, porque nenhuma sozinha tem todos os campos que o index.qmd consome:

1. API v3 do ConvertKit/Kit (autenticada) — fonte autoritativa da LISTA. Devolve
   todas as edicoes com `description` no formato "[BOLETIM AM][ALL] #208", que e
   o filtro confiavel para separar o boletim dos demais disparos. De aqui vem
   id, titulo, published_at, thumbnail e o corpo (para o excerpt).
2. Pagina publica /profile/posts — de aqui vem `slug`, `url` e `readingTime`,
   que a v3 nao expoe. Casada com a API pelo campo `campaignId`.

Quando a pagina publica nao cobre uma edicao (ela so lista ~10), a URL e montada
a partir do slug derivado do titulo e o tempo de leitura e estimado do texto.

A chave vive no .env do ROI_Diagnostico (CONVERTKIT_API_SECRET) — pasta fora do
versionamento. Nada de credencial entra neste arquivo.

Uso:
    python3 newsletter/atualiza_boletins.py [--limite 12] [--paginas 4]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.convertkit.com/v3"
FEED = "https://analisemacro.kit.com/profile/posts"
BASE_POSTS = "https://analisemacro.kit.com/posts"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

AQUI = Path(__file__).parent
DESTINO = AQUI / "boletins.json"
ENV_ROI = AQUI.parent / "projetos" / "ROI_Diagnostico" / ".env"

# "[BOLETIM AM][ALL] #208" -> 208
MARCADOR = re.compile(r"boletim\s*am", re.I)
NUM_EDICAO = re.compile(r"#\s*(\d+)")
PALAVRAS_POR_MINUTO = 265


def carrega_segredo() -> str:
    """Le CONVERTKIT_API_SECRET do ambiente ou do .env do ROI_Diagnostico."""
    if s := os.environ.get("CONVERTKIT_API_SECRET"):
        return s
    if not ENV_ROI.exists():
        raise SystemExit(f"CONVERTKIT_API_SECRET nao definido e {ENV_ROI} nao existe")
    for linha in ENV_ROI.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha.startswith("CONVERTKIT_API_SECRET=") and not linha.startswith("#"):
            return linha.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"CONVERTKIT_API_SECRET nao encontrado em {ENV_ROI}")


_trava = threading.Lock()
_proxima_chamada = 0.0
INTERVALO = 0.35  # s entre requisicoes; a v3 corta agressivamente acima disso


def busca_json(url: str, tentativas: int = 8) -> dict:
    """GET serializado com backoff.

    A v3 devolve 429 com facilidade: 700+ chamadas de detalhe estouram o limite
    mesmo com poucas threads. Um portao global espaca as requisicoes, e o
    backoff cobre o que ainda escapar. Sem isso o script perde edicoes em
    silencio e grava um JSON com buracos.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(tentativas):
        global _proxima_chamada
        with _trava:
            espera = _proxima_chamada - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            _proxima_chamada = time.monotonic() + INTERVALO
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tentativas - 1:
                raise
            time.sleep(min(2 ** i, 30))
    raise SystemExit("inalcancavel")


def busca_texto(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


# --------------------------------------------------------------------------- #
# Fonte 1 — API v3 (lista autoritativa)
# --------------------------------------------------------------------------- #

def ultima_pagina(segredo: str) -> int:
    """Descobre a ultima pagina de broadcasts dobrando o passo e refinando."""
    pg = 1
    while busca_json(f"{API}/broadcasts?api_secret={segredo}&per_page=50&page={pg * 2}").get("broadcasts"):
        pg *= 2
        if pg > 512:
            break
    while busca_json(f"{API}/broadcasts?api_secret={segredo}&per_page=50&page={pg + 1}").get("broadcasts"):
        pg += 1
    return pg


def broadcasts_recentes(segredo: str, paginas: int) -> list[dict]:
    fim = ultima_pagina(segredo)
    inicio = max(1, fim - paginas + 1)
    resumos: list[dict] = []
    for pg in range(inicio, fim + 1):
        resumos += busca_json(
            f"{API}/broadcasts?api_secret={segredo}&per_page=50&page={pg}"
        ).get("broadcasts", [])

    falhas: list[tuple[int, str]] = []

    def detalhe(b: dict) -> dict | None:
        try:
            return busca_json(f"{API}/broadcasts/{b['id']}?api_secret={segredo}").get("broadcast")
        except Exception as e:  # noqa: BLE001 — registrado e reportado abaixo
            falhas.append((b["id"], f"{type(e).__name__}: {e}"))
            return None

    # Sequencial: o portao de taxa em busca_json serializa as chamadas de
    # qualquer forma, entao threads so adicionariam contencao.
    detalhes = [d for d in map(detalhe, resumos) if d]

    if falhas:
        print(f"  AVISO: {len(falhas)} disparos sem detalhe (podem faltar edicoes):")
        for bid, erro in falhas[:5]:
            print(f"    {bid}: {erro}")

    # So edicoes do boletim, publicas e ja publicadas. Reenvios a segmentos
    # entram como public=False e sao descartados.
    return [
        d for d in detalhes
        if MARCADOR.search(d.get("description") or "")
        and d.get("public")
        and d.get("published_at")
    ]


# --------------------------------------------------------------------------- #
# Fonte 2 — feed publico (slug, url, reading time)
# --------------------------------------------------------------------------- #

def posts_do_feed() -> dict[int, dict]:
    """Mapa campaignId -> post do feed publico. Falha silenciosa e tolerada."""
    try:
        html = busca_texto(FEED)
        marcador = html.find('"recentPosts":')
        if marcador == -1:
            return {}
        inicio = html.index("[", marcador)
        profundidade = 0
        dentro_de_string = escapado = False
        fim = None
        for i in range(inicio, len(html)):
            c = html[i]
            if escapado:
                escapado = False
                continue
            if c == "\\":
                escapado = True
                continue
            if c == '"':
                dentro_de_string = not dentro_de_string
                continue
            if dentro_de_string:
                continue
            if c == "[":
                profundidade += 1
            elif c == "]":
                profundidade -= 1
                if profundidade == 0:
                    fim = i + 1
                    break
        if fim is None:
            return {}
        bruto = html[inicio:fim].replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
        # O feed serializa campaignId/readingTime como string; a API usa int.
        # Sem normalizar, o casamento entre as fontes falha silenciosamente e a
        # edicao aparece duplicada (uma vez por fonte).
        return {int(p["campaignId"]): p for p in json.loads(bruto) if p.get("campaignId")}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# Transformacao
# --------------------------------------------------------------------------- #

def slug_do_titulo(titulo: str) -> str:
    s = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", s).strip().lower()
    return re.sub(r"[\s-]+", "-", s)


def texto_limpo(html: str) -> str:
    txt = re.sub(r"(?is)<(style|script).*?</\1>", " ", html)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
              .replace("&quot;", '"'))
    return re.sub(r"\s+", " ", txt).strip()


def monta_excerpt(edicao: str | None, titulo: str, corpo: str, limite: int = 280) -> str:
    """Reproduz o formato do feed: 'EDICAO #N | NEWSLETTER ... <titulo> <texto>'.

    O index.qmd remove esse prefixo para exibir e usa o numero no card, entao o
    formato precisa casar com a regex de la (que exige o '#').
    """
    cabecalho = f"EDIÇÃO #{edicao} | NEWSLETTER SEMANAL DA ANÁLISE MACRO " if edicao else ""
    corpo = corpo[: limite * 3]
    texto = f"{cabecalho}{titulo} {corpo}".strip()
    return texto[:limite].rstrip() + "..." if len(texto) > limite else texto


def para_formato_do_site(b: dict, feed: dict[int, dict]) -> dict:
    m = NUM_EDICAO.search(b.get("description") or "")
    edicao = m.group(1) if m else None

    post = feed.get(b["id"], {})
    corpo = texto_limpo(b.get("content") or "")

    slug = post.get("slug") or slug_do_titulo(b["subject"])
    leitura = post.get("readingTime") or max(1, round(len(corpo.split()) / PALAVRAS_POR_MINUTO))

    return {
        "id": int(b["id"]),
        "title": b["subject"],
        "slug": slug,
        "url": post.get("url") or f"{BASE_POSTS}/{slug}",
        "published_at": b["published_at"],
        "reading_time": int(leitura),
        "thumbnail_url": post.get("thumbnailUrl") or b.get("thumbnail_url"),
        "excerpt": post.get("introContent") or monta_excerpt(edicao, b["subject"], corpo),
        "_edicao": int(edicao) if edicao else None,
        "_do_feed": bool(post),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=12, help="edicoes a manter (padrao: 12)")
    ap.add_argument("--paginas", type=int, default=4,
                    help="paginas finais da API a varrer (50 disparos cada; padrao: 4)")
    args = ap.parse_args()

    segredo = carrega_segredo()
    print("buscando edicoes na API do Kit...")
    brutos = broadcasts_recentes(segredo, args.paginas)
    feed = posts_do_feed()
    print(f"  {len(brutos)} edicoes do boletim na API; {len(feed)} posts no feed publico")

    novos = [para_formato_do_site(b, feed) for b in brutos]

    antigos = json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else []

    def chave(p: dict):
        """id normalizado; cai na url quando o id e nulo (havia entradas assim)."""
        try:
            return int(p["id"])
        except (KeyError, TypeError, ValueError):
            return p.get("url") or p.get("slug")

    por_id = {chave(p): p for p in antigos}
    for p in novos:
        por_id[chave(p)] = p

    # Ordena por data (desc) e, dentro da mesma edicao, poe primeiro quem tem
    # URL confirmada pelo feed — assim a dedup abaixo descarta a versao com URL
    # apenas derivada do titulo.
    todos = sorted(
        por_id.values(),
        key=lambda p: (p["published_at"], p.get("_do_feed", False)),
        reverse=True,
    )

    # Uma edicao por numero: a mesma edicao aparece com id diferente na API e no
    # feed, e reenvios a segmentos repetem o numero. Entradas vindas do arquivo
    # antigo nao tem `_edicao`, entao o numero e lido do excerpt como fallback.
    def numero(p: dict) -> int | None:
        if p.get("_edicao") is not None:
            return p["_edicao"]
        m = re.search(r"(?i)edi[cç][aã]o\s*#?\s*(\d+)", p.get("excerpt", ""))
        return int(m.group(1)) if m else None

    vistos: set[int] = set()
    unicos = []
    for p in todos:
        n = numero(p)
        if n is not None:
            if n in vistos:
                continue
            vistos.add(n)
        unicos.append(p)

    mantidos = unicos[: args.limite]
    for p in mantidos:
        p.pop("_edicao", None)
        p.pop("_do_feed", None)

    DESTINO.write_text(json.dumps(mantidos, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"{len(mantidos)} edicoes gravadas em {DESTINO.name}")


if __name__ == "__main__":
    main()
