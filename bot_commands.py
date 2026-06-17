"""
Procesa los comandos que los usuarios envían al bot de Telegram.

Comandos soportados:
  /buscar <texto>     -> busca eventos conocidos que coincidan con el texto
  /seguir <id_evento>  -> marca un evento como "me interesa"
  /dejar <id_evento>   -> deja de seguir un evento
  /miseventos          -> lista los eventos que el chat sigue, con sus fechas
  /ayuda                -> muestra los comandos disponibles

Este script se ejecuta una vez por corrida del workflow: lee los mensajes
nuevos recibidos por el bot desde la última vez, los procesa, y guarda
el offset para no reprocesarlos.
"""

import os
import json

import storage
import telegram_client

OFFSET_PATH = os.path.join(os.path.dirname(__file__), "data", "telegram_offset.json")

HELP_TEXT = (
    "<b>Comandos disponibles</b>\n\n"
    "/buscar texto - busca eventos guardados que coincidan con el texto\n"
    "/seguir id - sigue un evento (recibirás recordatorios)\n"
    "/dejar id - deja de seguir un evento\n"
    "/miseventos - lista los eventos que sigues\n"
    "/ayuda - muestra este mensaje"
)


def _load_offset() -> int:
    if os.path.exists(OFFSET_PATH):
        with open(OFFSET_PATH, "r") as f:
            return json.load(f).get("offset", 0)
    return 0


def _save_offset(offset: int) -> None:
    os.makedirs(os.path.dirname(OFFSET_PATH), exist_ok=True)
    with open(OFFSET_PATH, "w") as f:
        json.dump({"offset": offset}, f)


def _format_event(ev: dict) -> str:
    parts = [f"<b>{ev.get('title', 'Sin título')}</b>"]
    if ev.get("venue"):
        parts.append(f"📍 {ev['venue']}")
    if ev.get("event_date"):
        parts.append(f"📅 {ev['event_date']}")
    if ev.get("sales_start"):
        parts.append(f"🎟️ Venta de entradas: {ev['sales_start']}")
    if ev.get("url"):
        parts.append(ev["url"])
    return "\n".join(parts)


def _handle_buscar(chat_id: str, query: str, known_events: dict) -> None:
    if not query:
        telegram_client.send_message(chat_id, "Uso: /buscar nombre del artista o evento")
        return
    query_lower = query.lower()
    matches = [
        ev for ev in known_events.values()
        if query_lower in (ev.get("title") or "").lower()
    ]
    if not matches:
        telegram_client.send_message(chat_id, f"No encontré eventos que coincidan con «{query}».")
        return
    for ev in matches[:5]:
        button = telegram_client.build_follow_button(ev["id"])
        telegram_client.send_message(chat_id, _format_event(ev), reply_markup=button)
    if len(matches) > 5:
        telegram_client.send_message(chat_id, f"...y {len(matches) - 5} resultados más. Afina tu búsqueda.")


def _follow_event(chat_id: str, event_id: str, known_events: dict) -> str:
    """Lógica compartida de 'seguir': usada tanto por el comando de texto
    /seguir como por el botón inline. Devuelve el texto de respuesta."""
    if not event_id or event_id not in known_events:
        return "No reconozco ese evento (puede que ya no esté disponible). Usa /buscar para encontrarlo de nuevo."
    added = storage.add_follow(event_id, chat_id)
    ev = known_events[event_id]
    if added:
        return f"✅ Ahora sigues:\n{_format_event(ev)}"
    return "Ya estabas siguiendo ese evento."


def _handle_seguir(chat_id: str, event_id: str, known_events: dict) -> None:
    telegram_client.send_message(chat_id, _follow_event(chat_id, event_id, known_events))


def _handle_dejar(chat_id: str, event_id: str) -> None:
    removed = storage.remove_follow(event_id, chat_id)
    if removed:
        telegram_client.send_message(chat_id, "Listo, dejaste de seguir ese evento.")
    else:
        telegram_client.send_message(chat_id, "No estabas siguiendo ese evento.")


def _handle_miseventos(chat_id: str, known_events: dict) -> None:
    event_ids = storage.get_follows_for_chat(chat_id)
    if not event_ids:
        telegram_client.send_message(chat_id, "Aún no sigues ningún evento. Usa /buscar para encontrar uno.")
        return
    telegram_client.send_message(chat_id, f"Sigues {len(event_ids)} evento(s):")
    for eid in event_ids:
        ev = known_events.get(eid)
        if ev:
            button = {
                "inline_keyboard": [[
                    {"text": "❌ Dejar de seguir", "callback_data": f"unfollow:{eid}"}
                ]]
            }
            telegram_client.send_message(chat_id, _format_event(ev), reply_markup=button)


def _handle_callback_query(callback_query: dict, known_events: dict) -> None:
    """Maneja el toque de un botón inline (follow:<id> o unfollow:<id>)."""
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")

    if chat_id is None or ":" not in data:
        telegram_client.answer_callback_query(callback_id)
        return

    action, event_id = data.split(":", 1)

    if action == "follow":
        reply_text = _follow_event(chat_id, event_id, known_events)
        telegram_client.answer_callback_query(callback_id, text="Listo")
        telegram_client.send_message(chat_id, reply_text)
    elif action == "unfollow":
        removed = storage.remove_follow(event_id, chat_id)
        telegram_client.answer_callback_query(callback_id, text="Listo")
        telegram_client.send_message(
            chat_id,
            "Dejaste de seguir ese evento." if removed else "No estabas siguiendo ese evento."
        )
    else:
        telegram_client.answer_callback_query(callback_id)


def process_pending_commands() -> None:
    known_events = storage.load_known_events()
    offset = _load_offset()
    updates = telegram_client.get_updates(offset=offset)

    for update in updates:
        offset = update["update_id"] + 1

        if "callback_query" in update:
            _handle_callback_query(update["callback_query"], known_events)
            continue

        message = update.get("message", {})
        text = (message.get("text") or "").strip()
        chat_id = message.get("chat", {}).get("id")
        if not text or chat_id is None:
            continue

        if text.startswith("/buscar"):
            _handle_buscar(chat_id, text[len("/buscar"):].strip(), known_events)
        elif text.startswith("/seguir"):
            _handle_seguir(chat_id, text[len("/seguir"):].strip(), known_events)
        elif text.startswith("/dejar"):
            _handle_dejar(chat_id, text[len("/dejar"):].strip())
        elif text.startswith("/miseventos"):
            _handle_miseventos(chat_id, known_events)
        elif text.startswith("/ayuda") or text.startswith("/start"):
            telegram_client.send_message(chat_id, HELP_TEXT)
        else:
            telegram_client.send_message(chat_id, "No reconozco ese comando. Usa /ayuda para ver las opciones.")

    _save_offset(offset)


if __name__ == "__main__":
    process_pending_commands()
