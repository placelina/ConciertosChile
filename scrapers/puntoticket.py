"""
Scraper de PuntoTicket.com

Extrae eventos desde las páginas públicas de listado:
- https://www.puntoticket.com/nuevos   (eventos recién publicados)
- https://www.puntoticket.com/musica   (categoría música/conciertos)

PuntoTicket no tiene API pública, así que esto parsea el HTML directamente.
Si el sitio cambia su estructura, esta es la parte que probablemente
haya que actualizar.
"""

import re
import hashlib
from datetime import datetime
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.puntoticket.com"
LISTING_PAGES = [
    "/nuevos",
    "/musica",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
}

# Meses en español para parsear fechas tipo "04 de octubre 2026"
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _make_event_id(title: str, url: str) -> str:
    """ID estable para un evento, usado para detectar duplicados/novedades."""
    raw = f"puntoticket:{url or title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _parse_spanish_date(text: str):
    """Convierte '04 de octubre 2026' (o rangos) en un date, si se puede."""
    if not text:
        return None
    match = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(\d{4})", text.strip().lower()
    )
    if not match:
        return None
    day, month_name, year = match.groups()
    month = MESES.get(month_name)
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day)).date().isoformat()
    except ValueError:
        return None


def _fetch_page(path: str) -> str:
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse_listing(html: str) -> List[Dict]:
    """
    Parsea una página de listado de PuntoTicket.

    La estructura exacta de tarjetas de evento puede variar; este parser
    busca patrones genéricos (enlaces a páginas de evento + texto cercano
    con venue/género/fecha) para ser resistente a pequeños cambios de
    maquetación.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen_urls = set()

    # Las tarjetas de evento en PuntoTicket son enlaces <a> que apuntan
    # a una página individual de evento (no a categorías ni a login).
    candidate_links = soup.find_all("a", href=True)

    for link in candidate_links:
        href = link["href"]

        if not href.startswith("/") and BASE_URL not in href:
            continue
        if any(skip in href for skip in [
            "/musica", "/nuevos", "/todos", "/especiales", "/login",
            "/Landing/", "javascript:", "#"
        ]):
            continue

        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
        if full_url in seen_urls:
            continue

        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            # A veces el título real está en un atributo title/aria-label
            title = link.get("title") or link.get("aria-label") or ""
        if not title:
            continue

        # Buscamos texto de contexto (venue, género, fecha) cerca del link,
        # típicamente en el contenedor padre de la tarjeta.
        container = link
        for _ in range(3):
            if container.parent:
                container = container.parent
        context_text = container.get_text(" ", strip=True)

        date_iso = _parse_spanish_date(context_text)

        # Heurística simple para separar venue / género si vienen como
        # "Movistar Arena - Santiago Centro / Conciertos"
        venue = None
        genre = None
        venue_genre_match = re.search(
            r"([A-ZÁÉÍÓÚÑ][^/]+?)\s*/\s*([A-Za-zÁÉÍÓÚñÑ ]+)", context_text
        )
        if venue_genre_match:
            venue = venue_genre_match.group(1).strip()
            genre = venue_genre_match.group(2).strip()

        seen_urls.add(full_url)
        events.append({
            "source": "puntoticket",
            "id": _make_event_id(title, full_url),
            "title": title,
            "url": full_url,
            "venue": venue,
            "genre": genre,
            "event_date": date_iso,
            "raw_context": context_text[:300],
        })

    return events


def fetch_events() -> List[Dict]:
    """Punto de entrada: devuelve la lista combinada de eventos encontrados
    en todas las páginas de listado configuradas."""
    all_events = {}
    for path in LISTING_PAGES:
        try:
            html = _fetch_page(path)
            for ev in _parse_listing(html):
                all_events[ev["id"]] = ev
        except requests.RequestException as exc:
            print(f"[puntoticket] Error obteniendo {path}: {exc}")

    return list(all_events.values())


if __name__ == "__main__":
    import json
    found = fetch_events()
    print(f"Encontrados {len(found)} eventos")
    print(json.dumps(found[:5], indent=2, ensure_ascii=False))
