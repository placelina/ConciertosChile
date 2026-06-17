"""
Script principal. Se ejecuta periódicamente vía GitHub Actions.

Flujo:
1. Procesa comandos pendientes de Telegram (/seguir, /miseventos, etc).
2. Obtiene eventos actuales desde todas las fuentes (PuntoTicket, Ticketmaster).
3. Compara contra los eventos ya conocidos para detectar:
   a) Eventos completamente nuevos -> notifica al canal/chat general.
   b) Cambios relevantes en eventos ya seguidos (ej. fecha de venta de
      entradas que antes no existía y ahora sí) -> notifica solo a quienes
      lo siguen.
4. Guarda el estado actualizado.
"""

import os

import storage
import bot_commands
import telegram_client
from scrapers import puntoticket, ticketmaster

# Chat/canal donde se anuncian los eventos nuevos en general.
# Puede ser tu chat personal o un grupo/canal donde estén tus amigos.
ANNOUNCE_CHAT_ID = os.environ.get("TELEGRAM_ANNOUNCE_CHAT_ID")


def fetch_all_events() -> list:
    events = []
    events.extend(puntoticket.fetch_events())
    events.extend(ticketmaster.fetch_events(country_code="CL"))
    return events


def detect_new_events(current_events: list, known_events: dict) -> list:
    return [ev for ev in current_events if ev["id"] not in known_events]


def detect_sales_date_updates(current_events: list, known_events: dict) -> list:
    """Detecta eventos ya conocidos a los que se les agregó/cambió la
    fecha de venta de entradas (sales_start), relevante sobre todo para
    Ticketmaster."""
    updated = []
    for ev in current_events:
        previous = known_events.get(ev["id"])
        if not previous:
            continue
        old_sales = previous.get("sales_start")
        new_sales = ev.get("sales_start")
        if new_sales and new_sales != old_sales:
            updated.append(ev)
    return updated


def announce_new_events(new_events: list) -> None:
    if not ANNOUNCE_CHAT_ID:
        print("[main] TELEGRAM_ANNOUNCE_CHAT_ID no configurado, no se anuncian eventos nuevos.")
        return
    for ev in new_events:
        text = (
            "🆕 <b>Nuevo evento detectado</b>\n\n"
            f"<b>{ev.get('title', 'Sin título')}</b>\n"
        )
        if ev.get("venue"):
            text += f"📍 {ev['venue']}\n"
        if ev.get("event_date"):
            text += f"📅 {ev['event_date']}\n"
        if ev.get("sales_start"):
            text += f"🎟️ Venta de entradas: {ev['sales_start']}\n"
        if ev.get("url"):
            text += f"{ev['url']}\n"
        text += f"\nPara seguirlo: /seguir {ev['id']}"
        telegram_client.send_message(ANNOUNCE_CHAT_ID, text)


def notify_followers_of_update(updated_events: list) -> None:
    follows = storage.load_follows()
    for ev in updated_events:
        chat_ids = follows.get(ev["id"], [])
        if not chat_ids:
            continue
        text = (
            "🔔 <b>Actualización de un evento que sigues</b>\n\n"
            f"<b>{ev.get('title')}</b>\n"
            f"🎟️ Nueva fecha de venta de entradas: {ev.get('sales_start')}\n"
        )
        if ev.get("url"):
            text += ev["url"]
        for chat_id in chat_ids:
            telegram_client.send_message(chat_id, text)


def main():
    print("[main] Procesando comandos pendientes de Telegram...")
    try:
        bot_commands.process_pending_commands()
    except Exception as exc:
        # No queremos que un fallo en el procesamiento de comandos
        # impida que corra la detección de eventos nuevos.
        print(f"[main] Error procesando comandos: {exc}")

    print("[main] Obteniendo eventos de todas las fuentes...")
    known_events = storage.load_known_events()
    current_events = fetch_all_events()
    print(f"[main] {len(current_events)} eventos obtenidos en total.")

    new_events = detect_new_events(current_events, known_events)
    updated_events = detect_sales_date_updates(current_events, known_events)

    print(f"[main] {len(new_events)} eventos nuevos, {len(updated_events)} con cambio de venta de entradas.")

    if new_events:
        announce_new_events(new_events)
    if updated_events:
        notify_followers_of_update(updated_events)

    # Actualizamos el estado conocido con todo lo visto en esta corrida.
    for ev in current_events:
        known_events[ev["id"]] = ev
    storage.save_known_events(known_events)

    print("[main] Listo.")


if __name__ == "__main__":
    main()
