# Concert Tracker

Monitorea PuntoTicket y Ticketmaster en busca de nuevos conciertos en Chile,
avisa por Telegram cuando aparece un evento nuevo, y permite a cualquier
persona del grupo "seguir" un evento para recibir recordatorios sobre
fechas de venta de entradas y del concierto mismo.

Corre completamente gratis en GitHub Actions: no necesitas un servidor.

## Cómo funciona

Cada 3 horas, GitHub Actions ejecuta `main.py`, que:
1. Revisa si hay mensajes nuevos en el bot de Telegram (comandos como `/seguir`).
2. Busca eventos en PuntoTicket (scraping) y Ticketmaster (API).
3. Compara contra lo que ya conocía y avisa si hay algo nuevo.
4. Guarda el estado actualizado en `data/` (vía commit automático).

## Configuración paso a paso

### 1. Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**.
2. Envíale `/newbot`, ponle un nombre (ej. "Conciertos Chile Tracker").
3. BotFather te dará un **token** (algo como `123456:ABC-DEF...`). Guárdalo.
4. Habla con tu bot (o agrégalo a un grupo con tus amigos) y envíale `/start`
   para que quede "activo" y puedas obtener el chat_id en el siguiente paso.

### 2. Obtener el chat_id donde se anunciarán los eventos nuevos

Después de enviarle un mensaje al bot, visita en el navegador (reemplazando
TU_TOKEN):

```
https://api.telegram.org/botTU_TOKEN/getUpdates
```

Busca el campo `"chat":{"id": ...}`. Ese número es tu `TELEGRAM_ANNOUNCE_CHAT_ID`.
Si es un grupo, el id suele ser negativo (ej. `-1001234567890`) — eso es normal.

### 3. (Opcional) Obtener API key de Ticketmaster

1. Crea una cuenta en https://developer.ticketmaster.com/
2. Crea una "App" para obtener tu Consumer Key (esa es tu API key).
3. Nota: la cobertura oficial de Ticketmaster no menciona explícitamente
   Chile, así que es posible que esta fuente no aporte eventos. El sistema
   funciona igual sin ella, usando solo PuntoTicket.

### 4. Subir este proyecto a GitHub

1. Crea un repositorio nuevo (puede ser privado) en GitHub.
2. Sube estos archivos.

### 5. Configurar los Secrets del repositorio

En el repo: **Settings → Secrets and variables → Actions → New repository secret**.

Agrega:
- `TELEGRAM_BOT_TOKEN` → el token de BotFather
- `TELEGRAM_ANNOUNCE_CHAT_ID` → el chat_id obtenido en el paso 2
- `TICKETMASTER_API_KEY` → (opcional) tu API key de Ticketmaster

### 6. Probarlo manualmente

Ve a la pestaña **Actions** del repo → selecciona el workflow "Monitor de
conciertos" → **Run workflow**. Revisa los logs para confirmar que todo
funciona, y deberías ver mensajes en tu Telegram si hay eventos.

## Comandos del bot (para ti y tus amigos)

- `/buscar <texto>` — busca eventos guardados que coincidan con el texto
  (ej. `/buscar Karol G`). Cada resultado viene con un botón **"✅ Seguir
  este evento"** — solo hay que tocarlo, no es necesario copiar ningún ID.
- `/miseventos` — lista los eventos que sigues, cada uno con un botón
  **"❌ Dejar de seguir"**.
- `/seguir <id>` — alternativa por texto si por algún motivo prefieres
  escribir el ID en vez de tocar el botón.
- `/dejar <id>` — alternativa por texto de "dejar de seguir".
- `/ayuda` — muestra los comandos.

Cuando aparece un anuncio de evento nuevo en el chat/grupo, también trae
directamente el botón "Seguir este evento".

## Recordatorios automáticos

Una vez que sigues un evento, el sistema te avisa automáticamente (sin que
tengas que hacer nada más) en estos momentos:

- **Venta de entradas**: 3 días antes, 1 día antes, y el mismo día.
- **Concierto**: 7 días antes, 1 día antes, y el mismo día.

Cada recordatorio se envía una sola vez (no se repite en cada corrida del
workflow), gracias a un registro en `data/sent_reminders.json`.

## Limitaciones conocidas

- El scraper de PuntoTicket depende de la estructura HTML actual del sitio.
  Si PuntoTicket cambia su diseño, `scrapers/puntoticket.py` puede necesitar
  ajustes.
- El bot no responde en tiempo real: solo procesa mensajes y botones cuando
  corre el workflow (cada 3 horas, o cuando lo corres manualmente desde la
  pestaña Actions). Si quieres respuestas instantáneas, habría que cambiar
  a un modelo de servidor siempre encendido en vez de GitHub Actions.
- Esto usa GitHub Actions cron, que puede tener algunos minutos de retraso
  respecto al horario exacto programado (normal en el tier gratuito).

## Estructura del proyecto

```
concert-tracker/
├── main.py                  # Orquestador principal
├── bot_commands.py          # Procesa comandos y botones de Telegram
├── reminders.py              # Recordatorios programados (venta/concierto)
├── storage.py                # Guardado en JSON (eventos conocidos, seguimientos)
├── telegram_client.py       # Cliente mínimo de Telegram Bot API
├── scrapers/
│   ├── puntoticket.py        # Scraper de PuntoTicket
│   └── ticketmaster.py       # Cliente de la API de Ticketmaster
├── data/                      # Estado persistente (se actualiza vía commit automático)
├── .github/workflows/monitor.yml  # Cron job de GitHub Actions
└── requirements.txt
```
