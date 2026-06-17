"""
Recordatorios programados para eventos seguidos.

Cada vez que corre el workflow (cada 3 horas), este módulo revisa todos
los eventos que alguien sigue y, si la fecha de venta de entradas o la
fecha del concierto está a X días de distancia, envía un recordatorio.

Para no enviar el mismo recordatorio muchas veces (el workflow corre
cada 3 horas, así que sin control se mandarían duplicados todo el día),
se guarda en data/sent_reminders.json un registro de qué recordatorio
ya se envió a quién.

Hitos de recordatorio (días de anticipación):
- Venta de entradas: 3 días antes, 1 día antes, el mismo día.
- Concierto: 7 días antes, 1 día antes, el mismo día.
"""

import json
import os
from datetime import date, datetime

import storage
import telegram_client

SENT_REMINDERS_PATH = os.path.join(os.path.dirname(__file__), "data", "sent_reminders.json")

SALES_MILESTONES_DAYS = [3, 1, 0]
CONCERT_MILESTONES_DAYS = [7, 1, 0]


def _load_sent() -> dict:
    if not os.path.exists(SENT_REMINDERS_PATH):
        return {}
    with open(SENT_REMINDERS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_sent(sent: dict) -> None:
    os.makedirs(os.path.dirname(SENT_REMINDERS_PATH), exist_ok=True)
    with open(SENT_REMINDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(sent, f, indent=2, ensure_ascii=False, sort_keys=True)


def _parse_date(value: str):
    """Acepta tanto 'YYYY-MM-DD' como timestamps ISO completos
    ('YYYY-MM-DDTHH:MM:SSZ') y devuelve solo la parte de fecha."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _days_until(target: date) -> int:
    return (target - date.today()).days


def _milestone_key(event_id: str, kind: str, days: int) -> str:
    """Clave única para marcar 'ya se envió este recordatorio específico'."""
    return f"{event_id}:{kind}:{days}"


def _build_reminder_text(ev: dict, kind: str, days: int) -> str:
    title = ev.get("title", "Evento")
    if kind == "sales":
        if days == 0:
            headline = "🎟️ ¡Hoy comienza la venta de entradas!"
        else:
            headline = f"🎟️ Faltan {days} día(s) para la venta de entradas"
    else:  # concert
        if days == 0:
            headline = "🎵 ¡Hoy es el concierto!"
        else:
            headline = f"🎵 Faltan {days} día(s) para el concierto"

    text = f"{headline}\n\n<b>{title}</b>\n"
    if ev.get("venue"):
        text += f"📍 {ev['venue']}\n"
    if ev.get("event_date"):
        text += f"📅 {ev['event_date']}\n"
    if ev.get("sales_start"):
        text += f"🎟️ Venta: {ev['sales_start']}\n"
    if ev.get("url"):
        text += ev["url"]
    return text


def check_and_send_reminders() -> None:
    follows = storage.load_follows()
    if not follows:
        return

    known_events = storage.load_known_events()
    sent = _load_sent()

    for event_id, chat_ids in follows.items():
        ev = known_events.get(event_id)
        if not ev or not chat_ids:
            continue

        milestones = [
            ("sales", ev.get("sales_start"), SALES_MILESTONES_DAYS),
            ("concert", ev.get("event_date"), CONCERT_MILESTONES_DAYS),
        ]

        for kind, raw_date, milestone_days in milestones:
            target_date = _parse_date(raw_date)
            if not target_date:
                continue

            days_left = _days_until(target_date)
            if days_left < 0:
                continue  # la fecha ya pasó, no recordamos algo vencido

            # ¿Coincide con alguno de los hitos configurados?
            if days_left not in milestone_days:
                continue

            key = _milestone_key(event_id, kind, days_left)
            if key in sent:
                continue  # ya se mandó este recordatorio específico antes

            text = _build_reminder_text(ev, kind, days_left)
            for chat_id in chat_ids:
                try:
                    telegram_client.send_message(chat_id, text)
                except Exception as exc:
                    print(f"[reminders] Error enviando a {chat_id}: {exc}")

            sent[key] = datetime.utcnow().isoformat()

    _save_sent(sent)


if __name__ == "__main__":
    check_and_send_reminders()
