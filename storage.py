"""
Almacenamiento simple basado en archivos JSON.

No usamos una base de datos real porque el volumen de datos es pequeño
(cientos de eventos, un puñado de usuarios) y así no hace falta
infraestructura adicional: los archivos viven dentro del propio repo
de GitHub y se actualizan vía commit automático en cada corrida del
workflow.

Archivos:
- data/known_events.json   -> todos los eventos vistos hasta ahora
- data/follows.json        -> qué chat_id de Telegram sigue qué evento
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
KNOWN_EVENTS_PATH = os.path.join(DATA_DIR, "known_events.json")
FOLLOWS_PATH = os.path.join(DATA_DIR, "follows.json")


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def _save_json(path: str, data) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def load_known_events() -> dict:
    """dict: event_id -> evento (último dato visto de ese evento)."""
    return _load_json(KNOWN_EVENTS_PATH, {})


def save_known_events(events: dict) -> None:
    _save_json(KNOWN_EVENTS_PATH, events)


def load_follows() -> dict:
    """dict: event_id -> lista de chat_ids de Telegram que lo siguen."""
    return _load_json(FOLLOWS_PATH, {})


def save_follows(follows: dict) -> None:
    _save_json(FOLLOWS_PATH, follows)


def add_follow(event_id: str, chat_id: str) -> bool:
    """Agrega un seguimiento. Devuelve False si ya existía."""
    follows = load_follows()
    chat_ids = follows.setdefault(event_id, [])
    chat_id = str(chat_id)
    if chat_id in chat_ids:
        return False
    chat_ids.append(chat_id)
    save_follows(follows)
    return True


def remove_follow(event_id: str, chat_id: str) -> bool:
    follows = load_follows()
    chat_id = str(chat_id)
    if event_id in follows and chat_id in follows[event_id]:
        follows[event_id].remove(chat_id)
        if not follows[event_id]:
            del follows[event_id]
        save_follows(follows)
        return True
    return False


def get_follows_for_chat(chat_id: str) -> list:
    follows = load_follows()
    chat_id = str(chat_id)
    return [eid for eid, chats in follows.items() if chat_id in chats]
