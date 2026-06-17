"""
Cliente mínimo de Telegram Bot API (solo lo necesario: enviar mensajes
y leer actualizaciones para procesar comandos).
"""

import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Falta la variable de entorno TELEGRAM_BOT_TOKEN")
    return token


def send_message(chat_id: str, text: str, reply_markup: dict = None) -> dict:
    url = TELEGRAM_API.format(token=_token(), method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_updates(offset: int = None) -> list:
    """Trae mensajes nuevos enviados al bot desde la última vez (long-poll
    corto, pensado para correr una vez por ejecución del workflow)."""
    url = TELEGRAM_API.format(token=_token(), method="getUpdates")
    params = {"timeout": 5}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", [])


def build_follow_button(event_id: str) -> dict:
    """Construye el teclado inline con un botón 'Seguir este evento'.

    El callback_data debe ser corto (Telegram limita a 64 bytes), así que
    usamos un prefijo + el id del evento (los ids ya son hashes cortos de
    16 caracteres, entran sin problema).
    """
    return {
        "inline_keyboard": [[
            {"text": "✅ Seguir este evento", "callback_data": f"follow:{event_id}"}
        ]]
    }


def answer_callback_query(callback_query_id: str, text: str = None) -> None:
    """Responde a un toque de botón inline. Esto hace que Telegram quite
    el 'reloj de carga' del botón en el teléfono del usuario."""
    url = TELEGRAM_API.format(token=_token(), method="answerCallbackQuery")
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
