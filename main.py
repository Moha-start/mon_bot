import threading
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from datetime import datetime
import psycopg2

import config
from config import log
import bot_utils
from commands import cerveaux
from instagram_ai import lancer_bot_instagram

async def post_init(application: Application):
    bot_utils.bot_service = application.bot
    log("✅ Bot initialisé et variable connectée !")
    await bot_utils.envoyer_message("🟢 Bot en ligne et prêt à être utilisé !")

async def verification_periodique(context: ContextTypes.DEFAULT_TYPE):
    timestamp_actuel = int(datetime.now().timestamp())
    conn = None
    try:
        conn = psycopg2.connect(**config.DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("SELECT * FROM notification WHERE date_to_send <= %s AND envoye=0", (timestamp_actuel,))
        resultats = curseur.fetchall()
        if resultats:
            for row in resultats:
                notif_id = row[0]
                message_texte = f"{row[3]} expire dans {row[4]}"
                await context.bot.send_message(chat_id=bot_utils.CHAT_ID, text=f"⏳ RAPPEL : {message_texte}")
                curseur.execute("UPDATE notification SET envoye = 1 WHERE id = %s", (notif_id,))
                conn.commit()
    except Exception as e:
        log(f"Erreur SQL : {e}")
    finally:
        if conn: conn.close()

def start():
    log("Démarrage du bot...")
    app = Application.builder().token(config.TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT, cerveaux))

    job_queue = app.job_queue
    job_queue.run_repeating(verification_periodique, interval=60, first=10)

    threading.Thread(target=lancer_bot_instagram, daemon=True).start()

    log("Bot prêt ! Polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    start()