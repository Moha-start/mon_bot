import config
from config import log

# Variables globales pour l'état du bot
bot_service = None
CHAT_ID = config.INITIAL_CHAT_ID

async def envoyer_message(message: str):
    """Envoie un message en utilisant l'instance globale du bot."""
    if bot_service is None:
        log("⚠️ Erreur : Le bot n'est pas encore prêt pour envoyer des messages.")
        return
    try:
        await bot_service.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
        log(f"📤 Message envoyé : {message}")
    except Exception as e:
        log(f"❌ Erreur Telegram lors de l'envoi : {e}")