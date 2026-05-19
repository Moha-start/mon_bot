import asyncio
import sys
import io
from telegram import Bot
from check_synchro import *
import os
from dotenv import load_dotenv
load_dotenv()

# --- TA CONFIGURATION (Celle de ton bot actuel) ---
TOKEN = os.getenv("TOKEN_CALANDER")
CHAT_ID = int(os.getenv("CHAT_ID_CALANDER"))

async def main():
    # 1. On prépare la capture du texte (au lieu d'afficher à l'écran)
    capture_sortie = io.StringIO()
    stdout_original = sys.stdout
    sys.stdout = capture_sortie 

    try:
        # 2. On lance ta synchronisation
        print("⏳ Lancement automatique du script...")
        synchroniser_intelligent()
    except Exception as e:
        print(f"❌ Erreur critique pendant l'exécution : {e}")
    finally:
        # 3. On remet la sortie normale pour ne pas bloquer le script
        sys.stdout = stdout_original

    # 4. On récupère tout ce qui a été "imprimé"
    rapport = capture_sortie.getvalue()

    # 5. Envoi sur Telegram
    # Si le rapport n'est pas vide, on l'envoie
    if rapport.strip():
        try:
            bot = Bot(token=TOKEN)
            
            # Telegram limite les messages à 4096 caractères, on coupe si besoin
            if len(rapport) > 4000:
                rapport = rapport[:4000] + "\n... (coupé car trop long)"
            
            # Envoi avec balise <pre> pour garder l'alignement du texte
            message_final = f"🔄 <b>Rapport Journalier</b>\n<pre>{rapport}</pre>"
            
            await bot.send_message(chat_id=CHAT_ID, text=message_final, parse_mode="HTML")
            print("✅ Rapport envoyé sur Telegram avec succès.")
        except Exception as e:
            print(f"❌ Erreur d'envoi Telegram : {e}")
    else:
        print("⚠️ Le rapport est vide, rien à envoyer.")

if __name__ == "__main__":
    asyncio.run(main())