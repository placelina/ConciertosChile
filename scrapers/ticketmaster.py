"""
Cliente de la Ticketmaster Discovery API, filtrado por Chile.

Requiere una API key gratuita: https://developer.ticketmaster.com/
La cobertura oficial documentada no menciona explícitamente a Chile,
así que este cliente está pensado para "intentarlo": si no devuelve
eventos, simplemente no aporta nada y el resto del sistema sigue
funcionando con las otras fuentes.
"""

import hashlib
import os
from typing import List, Dict

import requests

DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"


def _make_event_id(tm_id: str) -> str:
    raw = f"ticketmaster:{tm_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _normalize_event(raw: Dict) -> Dict:
    venue = None
    try:
        venue = raw["_embedded"]["venues"][0]["name"]
    except (KeyError, IndexError):
        pass

    event_date = None
    try:
        event_date = raw["dates"]["start"]["localDate"]
    except KeyError:
        pass

    sales_start = None
    try:
        sales_start = raw["sales"]["public"]["startDateTime"]
    except KeyError:
        pass

    genre = None
    try:
        genre = raw["classifications"][0]["genre"]["name"]
    except (KeyError, IndexError):
        pass

    return {
        "source": "ticketmaster",
        "id": _make_event_id(raw.get("id", raw.get("name", ""))),
        "title": raw.get("name"),
        "url": raw.get("url"),
        "venue": venue,
        "genre": genre,
        "event_date": event_date,
        "sales_start": sales_start,
    }


def fetch_events(country_code: str = "CL") -> List[Dict]:
    """Devuelve eventos de Ticketmaster para el país indicado.

    Si no hay API key configurada (variable de entorno TICKETMASTER_API_KEY)
    o la API no devuelve datos para el país, devuelve lista vacía sin
    lanzar error, para no romper el resto del pipeline.
    """
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        print("[ticketmaster] No hay TICKETMASTER_API_KEY configurada, se omite esta fuente.")
        return []

    events = []
    page = 0
    max_pages = 5  # tope de seguridad, ~100 eventos por página

    while page < max_pages:
        params = {
            "apikey": api_key,
            "countryCode": country_code,
            "classificationName": "music",
            "size": 100,
            "page": page,
        }
        try:
            resp = requests.get(DISCOVERY_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            print(f"[ticketmaster] Error de red: {exc}")
            break

        if resp.status_code == 401:
            print("[ticketmaster] API key inválida (401).")
            break
        if resp.status_code != 200:
            print(f"[ticketmaster] Respuesta inesperada: {resp.status_code}")
            break

        data = resp.json()
        raw_events = data.get("_embedded", {}).get("events", [])
        if not raw_events:
            break

        events.extend(_normalize_event(e) for e in raw_events)

        total_pages = data.get("page", {}).get("totalPages", 1)
        page += 1
        if page >= total_pages:
            break

    if not events:
        print(
            f"[ticketmaster] No se encontraron eventos para countryCode={country_code}. "
            "Es posible que Ticketmaster no tenga cobertura en este país."
        )

    return events


if __name__ == "__main__":
    import json
    found = fetch_events()
    print(f"Encontrados {len(found)} eventos")
    print(json.dumps(found[:5], indent=2, ensure_ascii=False))
